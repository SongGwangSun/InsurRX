"""
사용자 업로드 보험증권/약관 → OCR → 청킹 → 임베딩 → Pinecone 업서트 파이프라인
"""
import asyncio
import logging
import uuid
from pathlib import Path
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user_policy import UserPolicy, PolicyStatus

logger = logging.getLogger(__name__)

CHUNK_CHARS   = 1500
CHUNK_OVERLAP = 150
EMBED_BATCH   = 100


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


async def process_user_policy(
    db: AsyncSession,
    policy_id: int,
    file_bytes: bytes,
    content_type: str,
    filename: str,
):
    """백그라운드에서 실행: OCR → 임베딩 → 벡터DB 업서트 후 상태 업데이트"""
    result = await db.execute(
        __import__("sqlalchemy", fromlist=["select"]).select(UserPolicy).where(UserPolicy.id == policy_id)
    )
    policy = result.scalar_one_or_none()
    if not policy:
        return

    try:
        policy.status = PolicyStatus.processing
        await db.commit()

        text = await _extract_text_from_file(file_bytes, content_type, filename)
        if not text.strip():
            raise ValueError("문서에서 텍스트를 추출할 수 없습니다.")

        namespace = policy.vector_namespace
        chunks = _chunk_text(text, namespace)
        chunks = await _embed_chunks(chunks)

        if not chunks:
            raise ValueError("임베딩 생성에 실패했습니다.")

        await _upsert_to_pinecone(chunks, namespace)

        policy.chunk_count = len(chunks)
        policy.status = PolicyStatus.ready
        await db.commit()
        logger.info("UserPolicy %d 업서트 완료: %d 청크", policy_id, len(chunks))

    except Exception as e:
        logger.error("UserPolicy %d 처리 실패: %s", policy_id, e)
        policy.status = PolicyStatus.failed
        policy.error_message = str(e)[:500]
        await db.commit()
