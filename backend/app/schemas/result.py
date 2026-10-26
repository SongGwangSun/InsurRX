from datetime import datetime

from pydantic import ConfigDict

from app.schemas.analysis import AnalyzeResponse


class ResultResponse(AnalyzeResponse):
    """분석 결과 조회 응답."""
    created_at: str


class AnalysisResultResponse(AnalyzeResponse):
    """히스토리 목록용 — created_at datetime 포함."""
    user_id: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
