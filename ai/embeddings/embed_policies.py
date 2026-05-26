"""
약관 텍스트를 청크로 분리하고 벡터 임베딩 후 Pinecone에 업서트하는 스크립트.
사용법: python -m ai.embeddings.embed_policies --policy-dir data/policies/raw

변경사항:
- 문자(char) 기반 청킹으로 변경 → OpenAI 8192 토큰 한도 안전하게 준수
- 배치 단위 임베딩 (100개씩) → rate limit 대응
- 파일 단위 에러 격리 → 한 파일 실패해도 나머지 계속 처리
"""
import asyncio
import argparse
import json
import uuid
import time
from pathlib import Path
from openai import AsyncOpenAI

from app.core.config import settings
from ai.rag.vectorstore import upsert_policy_chunks

# 한국어 기준 1500자 ≈ 500~700 토큰 (OpenAI 8192 한도 대비 충분한 여유)
CHUNK_CHARS    = 1500
CHUNK_OVERLAP  = 150   # 앞 청크와 150자 중복 → 문맥 연결
EMBED_BATCH    = 100   # 한 번에 OpenAI API에 보내는 최대 청크 수


def chunk_text(text: str, policy_id: str, policy_name: str) -> list[dict]:
    """텍스트를 CHUNK_CHARS 단위 문자 기반으로 분리합니다."""
    chunks = []
    step = CHUNK_CHARS - CHUNK_OVERLAP
    for i in range(0, len(text), step):
        chunk = text[i:i + CHUNK_CHARS].strip()
        if not chunk:
            continue
        chunks.append({
            "id": f"{policy_id}-{i}",
            "text": chunk,
            "metadata": {
                "policy_id":   policy_id,
                "policy_name": policy_name,
                "chunk_index": i,
                "content":     chunk,
            },
        })
    return chunks


async def embed_chunks(chunks: list[dict]) -> list[dict]:
    """OpenAI 임베딩으로 각 청크를 벡터화합니다. EMBED_BATCH 단위 배치 처리."""
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    result = []

    for b_start in range(0, len(chunks), EMBED_BATCH):
        batch = chunks[b_start:b_start + EMBED_BATCH]
        texts = [c["text"] for c in batch]

        # 개별 텍스트가 8000자를 넘으면 잘라냄 (토큰 초과 방지 안전망)
        texts = [t[:8000] for t in texts]

        try:
            resp = await client.embeddings.create(
                model="text-embedding-3-small",
                input=texts,
            )
            for chunk, emb in zip(batch, resp.data):
                chunk["embedding"] = emb.embedding
            result.extend(batch)
        except Exception as e:
            print(f"    ⚠ 배치 임베딩 오류 (건너뜀): {e}")

        # Rate limit 방지: 배치 간 짧은 대기
        if b_start + EMBED_BATCH < len(chunks):
            await asyncio.sleep(0.3)

    return result


async def process_policy_file(path: Path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    policy_id   = data["policy_id"]
    policy_name = data["policy_name"]
    full_text   = data["content"]

    print(f"\nProcessing {policy_name} ({policy_id})...")
    chunks = chunk_text(full_text, policy_id, policy_name)
    print(f"  청크 수: {len(chunks)}개 (평균 {len(full_text)//max(len(chunks),1)}자/청크)")

    chunks = await embed_chunks(chunks)
    print(f"  임베딩 완료: {len(chunks)}개")

    await upsert_policy_chunks(chunks)
    print(f"  Upserted {len(chunks)} chunks.")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy-dir", default="data/policies/raw")
    args = parser.parse_args()

    policy_dir = Path(args.policy_dir)
    if not policy_dir.exists():
        print(f"Directory not found: {policy_dir}")
        return

    json_files = list(policy_dir.glob("*.json"))
    if not json_files:
        print("JSON 파일 없음. 먼저 collect_policies.py 실행 필요.")
        return

    print(f"총 {len(json_files)}개 약관 파일 처리 시작\n" + "="*50)
    success, failed = 0, []

    for json_file in sorted(json_files):
        try:
            await process_policy_file(json_file)
            success += 1
        except Exception as e:
            print(f"  ✗ 오류: {json_file.name} — {e}")
            failed.append(json_file.name)

    print("\n" + "="*50)
    print(f"완료: {success}개 성공" + (f", {len(failed)}개 실패: {failed}" if failed else ""))
    print("다음 단계: FastAPI 서버 실행 후 /api/v1/analyze/ 테스트")


if __name__ == "__main__":
    asyncio.run(main())
