
from pydantic import BaseModel

from app.schemas.upload import ParsedDocument


class AnalyzeRequest(BaseModel):
    parsed: ParsedDocument


class CoverageItem(BaseModel):
    clause_id: str
    policy_name: str
    article: str
    is_covered: bool
    reason: str
    citation: str


class AnalyzeResponse(BaseModel):
    session_id: str
    is_claimable: bool
    estimated_payout: int
    breakdown: dict
    coverage_items: list[CoverageItem]
    confidence: float
    llm_summary: str
    # 추적 정보 — 같은 입력의 결과가 달라졌을 때 원인 확인용
    llm_model: str | None = None
    prompt_version: str | None = None
    latency_ms: int | None = None
