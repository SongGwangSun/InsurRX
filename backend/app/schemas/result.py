from app.schemas.analysis import AnalyzeResponse


class ResultResponse(AnalyzeResponse):
    created_at: str
