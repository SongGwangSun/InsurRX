from app.core.config import settings


def get_vectorstore():
    """설정에 따라 Pinecone 또는 Milvus 벡터스토어 클라이언트를 반환합니다."""
    if settings.VECTOR_DB_TYPE == "pinecone":
        from pinecone import Pinecone
        pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        return pc.Index(settings.PINECONE_INDEX)
    else:
        from pymilvus import connections, Collection
        connections.connect(host=settings.MILVUS_HOST, port=settings.MILVUS_PORT)
        return Collection("insurrx_policies")


PINECONE_UPSERT_BATCH = 100  # Pinecone 4MB 한도 대응: 100벡터씩 분할 업서트


async def upsert_policy_chunks(chunks: list[dict]):
    """약관 청크를 벡터스토어에 업서트합니다. chunks: [{id, embedding, metadata}]"""
    if settings.VECTOR_DB_TYPE == "pinecone":
        index = get_vectorstore()
        vectors = [(c["id"], c["embedding"], c["metadata"]) for c in chunks]
        # 배치 단위로 나눠서 upsert (대용량 파일 대응)
        for i in range(0, len(vectors), PINECONE_UPSERT_BATCH):
            batch = vectors[i:i + PINECONE_UPSERT_BATCH]
            index.upsert(vectors=batch)
        print(f"    → Pinecone upsert 완료: {len(vectors)}개 ({len(vectors)//PINECONE_UPSERT_BATCH + 1}배치)")
    else:
        raise NotImplementedError("Milvus upsert not yet implemented")
