from pydantic import BaseModel
from typing import List
from app.schemas.upload import ParsedDocument


class AnalyzeRequest(BaseModel):
    parsed: ParsedDocument
    policy_ids: List[str] = []   # 공개 약관 ID 목록 (선택사항)


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
    coverage_items: List[CoverageItem]
    confidence: float
    llm_summary: str
