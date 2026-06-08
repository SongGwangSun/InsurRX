from app.core.config import settings


async def retrieve_relevant_clauses(
    embedding: list[float],
    policy_ids: list[str],
    user_namespaces: list[str] | None = None,
) -> list[dict]:
    """Vector DB에서 관련 약관 조항을 검색합니다.

    - policy_ids: 공개 보험 약관 ID (기존 insurrx-policies 인덱스, 기본 네임스페이스)
    - user_namespaces: 사용자 업로드 문서 네임스페이스 (user-{id}-xxxx)
    """
    if settings.VECTOR_DB_TYPE == "pinecone":
        return await _query_pinecone(embedding, policy_ids, user_namespaces or [])
    return await _query_milvus(embedding, policy_ids)


async def _query_pinecone(
    embedding: list[float],
    policy_ids: list[str],
    user_namespaces: list[str],
) -> list[dict]:
    from pinecone import Pinecone

    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    index = pc.Index(settings.PINECONE_INDEX)
    results: list[dict] = []

    # 1. 공개 약관 검색 (policy_ids 있을 때만)
    if policy_ids:
        public = index.query(
            vector=embedding,
            top_k=5,
            filter={"policy_id": {"$in": policy_ids}},
            include_metadata=True,
        )
        results.extend(m.metadata for m in public.matches)

    # 2. 사용자 개인 보험증권 검색 (네임스페이스별)
    for ns in user_namespaces:
        try:
            ns_result = index.query(
                vector=embedding,
                top_k=3,
                namespace=ns,
                include_metadata=True,
            )
            for m in ns_result.matches:
                meta = dict(m.metadata)
                meta.setdefault("policy_name", "내 보험증권")
                meta.setdefault("article", "-")
                results.append(meta)
        except Exception:
            pass  # 네임스페이스 없음 등은 무시

    # policy_ids 도 user_namespaces 도 없으면 전체 검색 fallback
    if not policy_ids and not user_namespaces:
        fallback = index.query(
            vector=embedding,
            top_k=5,
            include_metadata=True,
        )
        results.extend(m.metadata for m in fallback.matches)

    return results


async def _query_milvus(embedding: list[float], policy_ids: list[str]) -> list[dict]:
    # TODO: Milvus 연동
    return []
