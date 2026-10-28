import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

STANDARD_TOP_K = 6       # 표준약관에서 LLM에 넘길 조각 수
STANDARD_CANDIDATES = 15 # 조항별 개수 제한 전에 가져올 후보 수
PER_ARTICLE_LIMIT = 2    # 같은 조항의 조각이 결과를 독차지하지 않도록 제한
USER_TOP_K = 3           # 개인 업로드 문서(네임스페이스)별 조각 수

# 실손의료보험만 조회 대상 (질병·상해 표준약관은 검색하지 않음)
SILSON_POLICY_IDS = ["std-silson-basic", "std-silson-rider1", "std-silson-rider2"]


async def retrieve_relevant_clauses(
    embedding: list[float],
    user_namespaces: list[str] | None = None,
) -> list[dict]:
    """Vector DB에서 관련 약관 조항을 검색합니다.

    - 실손의료보험 표준약관(별표15, 기본형·특약1·2)만 검색합니다. 보험사별 상품 약관은 쓰지 않습니다.
    - user_namespaces: 사용자 업로드 문서 네임스페이스 (user-{id}-xxxx)
    """
    if settings.VECTOR_DB_TYPE == "pinecone":
        return await _query_pinecone(embedding, user_namespaces or [])
    return await _query_milvus(embedding)


async def _query_pinecone(embedding: list[float], user_namespaces: list[str]) -> list[dict]:
    from pinecone import Pinecone

    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    index = pc.Index(settings.PINECONE_INDEX)

    # 1. 실손 표준약관
    standard = index.query(
        vector=embedding,
        top_k=STANDARD_CANDIDATES,
        namespace=settings.STANDARD_TERMS_NAMESPACE,
        filter={"policy_id": {"$in": SILSON_POLICY_IDS}},
        include_metadata=True,
    )
    results = _diversify([m.metadata for m in standard.matches])

    # 2. 사용자 개인 보험증권 (네임스페이스별)
    for ns in user_namespaces:
        try:
            ns_result = index.query(
                vector=embedding,
                top_k=USER_TOP_K,
                namespace=ns,
                include_metadata=True,
            )
            for m in ns_result.matches:
                meta = dict(m.metadata)
                meta.setdefault("policy_name", "내 보험증권")
                meta.setdefault("article", "-")
                results.append(meta)
        except Exception as e:  # 한 네임스페이스 실패가 전체 검색을 막지 않도록 건너뜀
            logger.warning("개인 네임스페이스 검색 실패 (%s): %s", ns, e)

    return results


def _diversify(candidates: list[dict]) -> list[dict]:
    """유사도 순서를 유지하면서 조항(약관+조항명)당 PER_ARTICLE_LIMIT개까지만 남긴다."""
    picked: list[dict] = []
    per_article: dict[tuple, int] = {}
    for meta in candidates:
        key = (meta.get("policy_id"), meta.get("article"))
        if per_article.get(key, 0) >= PER_ARTICLE_LIMIT:
            continue
        per_article[key] = per_article.get(key, 0) + 1
        picked.append(meta)
        if len(picked) == STANDARD_TOP_K:
            break
    return picked


async def _query_milvus(embedding: list[float]) -> list[dict]:
    # TODO: Milvus 연동
    return []
