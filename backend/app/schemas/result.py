from typing import Optional
from datetime import datetime
from app.schemas.analysis import AnalyzeResponse


class ResultResponse(AnalyzeResponse):
    """분석 결과 조회 응답."""
    created_at: str


class AnalysisResultResponse(AnalyzeResponse):
    """히스토리 목록용 — created_at datetime 포함."""
    user_id: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}
