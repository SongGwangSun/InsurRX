"""
사용자 업로드 보험증권/약관 → OCR → 청킹 → 임베딩 → Pinecone 업서트 파이프라인
"""
import asyncio
import logging
import re
import uuid
from pathlib import Path
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user_policy import UserPolicy, PolicyStatus

logger = logging.getLogger(__name__)

CHUNK_CHARS   = 1500
CHUNK_OVERLAP = 150
EMBED_BATCH   = 100


# 보험증권에 포함된 개인정보는 임베딩 전에 가린다
_RRN_PATTERN   = re.compile(r'(\d{6})\s*-\s*[1-4]\d{6}')            # 주민등록번호
_PHONE_PATTERN = re.compile(r'(01[016789])[-\s]?\d{3,4}[-\s]?(\d{4})')  # 휴대전화


def mask_personal_info(text: str) -> str:
    text = _RRN_PATTERN.sub(r'\1-*******', text)
    return _PHONE_PATTERN.sub(r'\1-****-\2', text)


def is_user_namespace(namespace: str | None) -> bool:
    """개인 문서 네임스페이스인지 — 빈 값(공개 약관 기본 네임스페이스)을 걸러낸다."""
    return bool(namespace) and namespace.startswith("user-")


def new_user_namespace(user_id: int) -> str:
    return f"user-{user_id}-{uuid.uuid4().hex[:8]}"


def _chunk_text(text: str, namespace: str) -> list[dict]:
    chunks = []
    step = CHUNK_CHARS - CHUNK_OVERLAP
    for i in range(0, len(text), step):
        chunk = text[i:i + CHUNK_CHARS].strip()
        if not chunk:
            continue
        chunks.append({
            "id": f"{namespace}-{i}",
            "text": chunk,
            "metadata": {
                "namespace": namespace,
                "chunk_index": i,
                "content": chunk,
            },
        })
    return chunks


async def _embed_chunks(chunks: list[dict]) -> list[dict]:
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    result = []
    for b_start in range(0, len(chunks), EMBED_BATCH):
        batch = chunks[b_start:b_start + EMBED_BATCH]
        texts = [c["text"][:8000] for c in batch]
        try:
            resp = await client.embeddings.create(model="text-embedding-3-small", input=texts)
            for chunk, emb in zip(batch, resp.data):
                chunk["embedding"] = emb.embedding
            result.extend(batch)
        except Exception as e:
            logger.warning("임베딩 배치 오류 (건너뜀): %s", e)
        if b_start + EMBED_BATCH < len(chunks):
            await asyncio.sleep(0.3)
    return result


async def _upsert_to_pinecone(chunks: list[dict], namespace: str):
    from pinecone import Pinecone
    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    index = pc.Index(settings.PINECONE_INDEX)
    batch_size = 100
    vectors = [(c["id"], c["embedding"], c["metadata"]) for c in chunks]
    for i in range(0, len(vectors), batch_size):
        index.upsert(vectors=vectors[i:i + batch_size], namespace=namespace)


async def _extract_text_from_file(file_bytes: bytes, content_type: str, filename: str) -> str:
    """이미지 → Vision OCR, PDF → pdfplumber 텍스트 추출"""
    if content_type == "application/pdf" or filename.lower().endswith(".pdf"):
        import io
        import pdfplumber
        text_parts = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n\n".join(text_parts)
    else:
        from app.services.ocr.clova_ocr import run_ocr
        return await run_ocr(file_bytes, content_type)


async def _load_policy(db: AsyncSession, policy_id: int) -> UserPolicy | None:
    result = await db.execute(select(UserPolicy).where(UserPolicy.id == policy_id))
    return result.scalar_one_or_none()


async def _embed_policy(db: AsyncSession, policy: UserPolicy, text: str):
    """추출 텍스트 → 개인정보 마스킹 → 청킹 → 임베딩 → 벡터DB 업서트 후 상태 업데이트"""
    if not text.strip():
        raise ValueError("문서에서 텍스트를 추출할 수 없습니다.")

    namespace = policy.vector_namespace
    chunks = _chunk_text(mask_personal_info(text), namespace)
    chunks = await _embed_chunks(chunks)

    if not chunks:
        raise ValueError("임베딩 생성에 실패했습니다.")

    await _upsert_to_pinecone(chunks, namespace)

    policy.chunk_count = len(chunks)
    policy.status = PolicyStatus.ready
    await db.commit()
    logger.info("UserPolicy %d 업서트 완료: %d 청크", policy.id, len(chunks))


async def _mark_failed(db: AsyncSession, policy: UserPolicy, e: Exception):
    logger.error("UserPolicy %d 처리 실패: %s", policy.id, e)
    policy.status = PolicyStatus.failed
    policy.error_message = str(e)[:500]
    await db.commit()


async def process_user_policy(
    db: AsyncSession,
    policy_id: int,
    file_bytes: bytes,
    content_type: str,
    filename: str,
):
    """백그라운드에서 실행: OCR → 임베딩 → 벡터DB 업서트 후 상태 업데이트"""
    policy = await _load_policy(db, policy_id)
    if not policy:
        return

    try:
        policy.status = PolicyStatus.processing
        await db.commit()

        text = await _extract_text_from_file(file_bytes, content_type, filename)
        await _embed_policy(db, policy, text)

    except Exception as e:
        await _mark_failed(db, policy, e)


async def process_user_policy_images(
    db: AsyncSession,
    policy_id: int,
    images: list[tuple[bytes, str]],
):
    """여러 장의 증권 사진(카카오톡 등) → 장별 OCR → 하나의 문서로 합쳐 임베딩"""
    policy = await _load_policy(db, policy_id)
    if not policy:
        return

    try:
        policy.status = PolicyStatus.processing
        await db.commit()

        from app.services.ocr.clova_ocr import run_ocr
        pages = [await run_ocr(data, ctype, doc_kind="policy") for data, ctype in images]
        await _embed_policy(db, policy, "\n\n".join(pages))

    except Exception as e:
        await _mark_failed(db, policy, e)


async def collect_policy_sources(db: AsyncSession, user_id: int) -> tuple[list[str], list[str]]:
    """회원의 RAG 검색 대상 수집 → (공개 약관 policy_ids, 개인 문서 네임스페이스).

    - 마이데이터 연결 보험 / 상품을 지정한 보험증권 → 해당 상품의 공개 약관
    - 임베딩 완료된 업로드 보험증권 → 개인 네임스페이스
    """
    from app.models.insurer import InsuranceProduct
    from app.models.mydata_policy import UserMydataPolicy

    policy_ids: list[str] = []
    namespaces: list[str] = []

    mydata_rows = await db.execute(
        select(UserMydataPolicy.vector_policy_id).where(
            UserMydataPolicy.user_id == user_id,
            UserMydataPolicy.is_active == True,  # noqa: E712
            UserMydataPolicy.status == "정상",
            UserMydataPolicy.vector_policy_id.isnot(None),
        )
    )
    product_rows = await db.execute(
        select(InsuranceProduct.vector_policy_id)
        .join(UserPolicy, UserPolicy.product_id == InsuranceProduct.id)
        .where(
            UserPolicy.user_id == user_id,
            UserPolicy.status == PolicyStatus.ready,
            InsuranceProduct.vector_policy_id.isnot(None),
        )
    )
    for pid in [*mydata_rows.scalars().all(), *product_rows.scalars().all()]:
        if pid and pid not in policy_ids:
            policy_ids.append(pid)

    upload_rows = await db.execute(
        select(UserPolicy.vector_namespace).where(
            UserPolicy.user_id == user_id,
            UserPolicy.status == PolicyStatus.ready,
            UserPolicy.chunk_count > 0,
        )
    )
    namespaces = [ns for ns in upload_rows.scalars().all() if is_user_namespace(ns)]
    return policy_ids, namespaces
