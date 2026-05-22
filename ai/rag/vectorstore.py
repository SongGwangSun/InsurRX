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


async def upsert_policy_chunks(chunks: list[dict]):
    """약관 청크를 벡터스토어에 업서트합니다. chunks: [{id, embedding, metadata}]"""
    if settings.VECTOR_DB_TYPE == "pinecone":
        index = get_vectorstore()
        vectors = [(c["id"], c["embedding"], c["metadata"]) for c in chunks]
        index.upsert(vectors=vectors)
    else:
        raise NotImplementedError("Milvus upsert not yet implemented")
