"""
약관 텍스트를 청크로 분리하고 벡터 임베딩 후 Pinecone/Milvus에 업서트하는 스크립트.
사용법: python -m ai.embeddings.embed_policies --policy-dir data/policies/raw
"""
import asyncio
import argparse
import json
import uuid
from pathlib import Path
from openai import AsyncOpenAI

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend'))

from app.core.config import settings
from ai.rag.vectorstore import upsert_policy_chunks

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def chunk_text(text: str, policy_id: str, policy_name: str) -> list[dict]:
    """텍스트를 CHUNK_SIZE 단위로 분리합니다."""
    chunks = []
    words = text.split()
    for i in range(0, len(words), CHUNK_SIZE - CHUNK_OVERLAP):
        chunk_words = words[i:i + CHUNK_SIZE]
        chunk_text = " ".join(chunk_words)
        chunks.append({
            "id": f"{policy_id}-{i}",
            "text": chunk_text,
            "metadata": {
                "policy_id": policy_id,
                "policy_name": policy_name,
                "chunk_index": i,
                "content": chunk_text,
            },
        })
    return chunks


async def embed_chunks(chunks: list[dict]) -> list[dict]:
    """OpenAI 임베딩으로 각 청크를 벡터화합니다."""
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    texts = [c["text"] for c in chunks]
    response = await client.embeddings.create(model="text-embedding-3-small", input=texts)
    for chunk, emb in zip(chunks, response.data):
        chunk["embedding"] = emb.embedding
    return chunks


async def process_policy_file(path: Path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    policy_id = data["policy_id"]
    policy_name = data["policy_name"]
    full_text = data["content"]

    print(f"Processing {policy_name} ({policy_id})...")
    chunks = chunk_text(full_text, policy_id, policy_name)
    chunks = await embed_chunks(chunks)
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

    for json_file in policy_dir.glob("*.json"):
        await process_policy_file(json_file)

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
