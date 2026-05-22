from fastapi import APIRouter, Path
from app.schemas.result import ResultResponse

router = APIRouter()


@router.get("/{session_id}", response_model=ResultResponse)
async def get_result(session_id: str = Path(..., description="분석 세션 ID")):
    """세션 ID로 분석 결과 조회."""
    # TODO: DB에서 session_id로 결과 조회
    raise NotImplementedError
