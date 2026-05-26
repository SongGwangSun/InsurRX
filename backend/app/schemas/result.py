from app.schemas.analysis import AnalyzeResponse


class ResultResponse(AnalyzeResponse):
    """분석 결과 조회 응답 — AnalyzeResponse에 저장 시각을 추가합니다."""
    created_at: str
