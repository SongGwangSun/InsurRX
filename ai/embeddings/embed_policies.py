"""
표준약관 조항 JSON을 임베딩해 Pinecone 표준약관 네임스페이스에 업서트하는 스크립트.
사용법: python -m ai.embeddings.embed_policies [--policy-dir data/policies/standard]

- 입력: scripts/build_standard_terms.py가 만든 조항 단위 JSON
- 네임스페이스(settings.STANDARD_TERMS_NAMESPACE)를 비운 뒤 다시 채움 → 여러 번 실행해도 결과가 같음
- 보험사별 상품 약관(기본 네임스페이스)은 건드리지 않음
"""
import argparse
import asyncio
import json
from pathlib import Path

from openai import AsyncOpenAI

from ai.rag.vectorstore import get_vectorstore, upsert_policy_chunks
from app.core.config import settings

EMBED_BATCH = 100   # 한 번에 OpenAI API에 보내는 최대 청크 수


def build_chunks(data: dict) -> list[dict]:
    """조항 목록을 업서트용 청크로 변환합니다. 임베딩 텍스트 앞에 약관명·조항명을 붙여 검색 문맥을 줍니다."""
    chunks = []
    for i, art in enumerate(data["articles"]):
        chunks.append({
            "id": f"{data['policy_id']}-{i:03d}",
            "text": f"[{data['policy_name']}] {art['article']}\n{art['text']}",
            "metadata": {
                "policy_id":   data["policy_id"],
                "policy_name": data["policy_name"],
                "article":     art["article"],
                "page":        art["page"],
                "revised":     data.get("revised") or "",
                "content":     art["text"],
            },
        })
    return chunks


async def embed_chunks(chunks: list[dict]) -> list[dict]:
    """OpenAI 임베딩으로 각 청크를 벡터화합니다. 한 배치라도 실패하면 중단합니다(부분 업서트 방지)."""
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    for b_start in range(0, len(chunks), EMBED_BATCH):
        batch = chunks[b_start:b_start + EMBED_BATCH]
        resp = await client.embeddings.create(
            model="text-embedding-3-small",
            input=[c["text"][:8000] for c in batch],
        )
        for chunk, emb in zip(batch, resp.data, strict=True):
            chunk["embedding"] = emb.embedding
        if b_start + EMBED_BATCH < len(chunks):
            await asyncio.sleep(0.3)   # Rate limit 방지
    return chunks


def clear_namespace(namespace: str):
    """표준약관 네임스페이스만 비웁니다. 처음 실행이라 네임스페이스가 없으면 그냥 넘어갑니다."""
    index = get_vectorstore()
    stats = index.describe_index_stats()
    if namespace in (getattr(stats, "namespaces", None) or {}):
        index.delete(delete_all=True, namespace=namespace)
        print(f"기존 '{namespace}' 네임스페이스 삭제")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy-dir", default="data/policies/standard")
    args = parser.parse_args()

    files = sorted(Path(args.policy_dir).glob("*.json"))
    if not files:
        print(f"JSON 파일 없음: {args.policy_dir} — 먼저 scripts/build_standard_terms.py 실행 필요.")
        return

    chunks: list[dict] = []
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        file_chunks = build_chunks(data)
        print(f"{data['policy_name']}: {len(file_chunks)}개 청크")
        chunks.extend(file_chunks)

    namespace = settings.STANDARD_TERMS_NAMESPACE
    chunks = await embed_chunks(chunks)
    print(f"임베딩 완료: {len(chunks)}개")

    clear_namespace(namespace)
    await upsert_policy_chunks(chunks, namespace=namespace)
    print(f"완료: '{namespace}' 네임스페이스에 {len(chunks)}개 업서트")


if __name__ == "__main__":
    asyncio.run(main())
