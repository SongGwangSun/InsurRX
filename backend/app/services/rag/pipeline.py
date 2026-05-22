import uuid
from app.schemas.upload import ParsedDocument
from app.schemas.analysis import AnalyzeResponse, CoverageItem
from app.services.rag.retriever import retrieve_relevant_clauses
from app.services.rag.embedder import get_query_embedding


async def run_rag_pipeline(
    parsed_doc: ParsedDocument,
    policy_ids: list[str],
) -> AnalyzeResponse:
    """
    1. 파싱된 의료 문서를 쿼리 텍스트로 변환
    2. Vector DB에서 관련 약관 조항 검색
    3. LLM으로 보상 여부 및 예상 금액 추론
    """
    query = _build_query(parsed_doc)
    embedding = await get_query_embedding(query)
    clauses = await retrieve_relevant_clauses(embedding, policy_ids)

    # TODO: LangChain chain으로 LLM 추론 교체
    return AnalyzeResponse(
        session_id=str(uuid.uuid4()),
        is_claimable=True,
        estimated_payout=18500,
        breakdown={
            "본인부담금": 28500,
            "처방료": 8000,
            "비급여_제외": -3200,
            "공제액": -10000,
        },
        coverage_items=[
            CoverageItem(
                clause_id="hyundai-silson-3-2",
                policy_name="현대해상 실손의료비",
                article="제3조 ②항",
                is_covered=True,
                reason="통원 의원급 해당",
                citation="통원의료비는 1회당 의원 1만원을 공제한 금액을 보상한다...",
            )
        ],
        confidence=0.92,
        llm_summary="해당 처방은 실손의료비 통원 항목으로 약 ₩18,500 청구 가능합니다.",
    )


def _build_query(doc: ParsedDocument) -> str:
    parts = []
    if doc.icd_code:
        parts.append(f"상병코드: {doc.icd_code}")
    if doc.diagnosis:
        parts.append(f"진단명: {doc.diagnosis}")
    if doc.department:
        parts.append(f"진료과: {doc.department}")
    for drug in doc.drugs:
        parts.append(f"약품: {drug.name}")
    return " | ".join(parts)
