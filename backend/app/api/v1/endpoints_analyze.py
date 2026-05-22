from fastapi import APIRouter
from app.schemas.analysis import AnalyzeRequest, AnalyzeResponse
from app.services.rag.pipeline import run_rag_pipeline

router = APIRouter()


@router.post("/", response_model=AnalyzeResponse)
async def analyze_coverage(request: AnalyzeRequest):
    """파싱된 의료 문서 + 사용자 보험 정보 → RAG 파이프라인 → 보상 여부·예상 금액 반환."""
    return await run_rag_pipeline(parsed_doc=request.parsed, policy_ids=request.policy_ids)
