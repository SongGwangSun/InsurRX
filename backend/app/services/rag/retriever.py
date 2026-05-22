from app.core.config import settings


async def retrieve_relevant_clauses(embedding: list[float], policy_ids: list[str]) -> list[dict]:
    """Vector DB에서 관련 약관 조항을 검색합니다."""
    if settings.VECTOR_DB_TYPE == "pinecone":
        return await _query_pinecone(embedding, policy_ids)
    return await _query_milvus(embedding, policy_ids)


async def _query_pinecone(embedding: list[float], policy_ids: list[str]) -> list[dict]:
    from pinecone import Pinecone
    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    index = pc.Index(settings.PINECONE_INDEX)
    result = index.query(
        vector=embedding,
        top_k=5,
        filter={"policy_id": {"$in": policy_ids}},
        include_metadata=True,
    )
    return [m.metadata for m in result.matches]


async def _query_milvus(embedding: list[float], policy_ids: list[str]) -> list[dict]:
    # TODO: Milvus 연동
    return []
