import uuid
from app.schemas.upload import ParsedDocument
from app.schemas.analysis import AnalyzeResponse, CoverageItem
from app.services.rag.retriever import retrieve_relevant_clauses
from app.services.rag.embedder import get_query_embedding

from ai.rag.chain import run_coverage_chain


async def run_rag_pipeline(
    parsed_doc: ParsedDocument,
    policy_ids: list[str],
    user_namespaces: list[str] | None = None,
) -> AnalyzeResponse:
    """
    1. 파싱된 의료 문서를 쿼리 텍스트로 변환
    2. Vector DB에서 관련 약관 조항 검색
    3. LangChain + Claude로 보상 여부 및 예상 금액 추론
    """
    query = _build_query(parsed_doc)
    embedding = await get_query_embedding(query)
    clauses = await retrieve_relevant_clauses(embedding, policy_ids, user_namespaces)

    document_info = _format_document_info(parsed_doc)
    clauses_text = _format_clauses(clauses)

    result = await run_coverage_chain(document_info, clauses_text)

    return AnalyzeResponse(
        session_id=str(uuid.uuid4()),
        is_claimable=result["is_claimable"],
        estimated_payout=result["estimated_payout"],
        breakdown=result["breakdown"],
        coverage_items=[CoverageItem(**item) for item in result["coverage_items"]],
        confidence=result["confidence"],
        llm_summary=result["llm_summary"],
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


def _format_document_info(doc: ParsedDocument) -> str:
    lines = []
    if doc.hospital:
        lines.append(f"병원: {doc.hospital}")
    if doc.department:
        lines.append(f"진료과: {doc.department}")
    if doc.icd_code:
        lines.append(f"상병코드: {doc.icd_code}")
    if doc.diagnosis:
        lines.append(f"진단명: {doc.diagnosis}")
    if doc.prescription_date:
        lines.append(f"처방일: {doc.prescription_date}")
    if doc.total_amount:
        lines.append(f"총 진료비: {doc.total_amount:,}원")
    if doc.drugs:
        lines.append("처방 약품:")
        for drug in doc.drugs:
            flag = " [비급여]" if drug.is_nonbenefit else ""
            lines.append(f"  - {drug.name}{flag}")
    return "\n".join(lines) if lines else "문서 정보 없음"


def _format_clauses(clauses: list[dict]) -> str:
    if not clauses:
        return "검색된 약관 조항 없음"
    parts = []
    for i, c in enumerate(clauses, 1):
        parts.append(
            f"[{i}] {c.get('policy_name', '')} / {c.get('article', '')}\n"
            f"    {c.get('content', c.get('text', ''))}"
        )
    return "\n\n".join(parts)
