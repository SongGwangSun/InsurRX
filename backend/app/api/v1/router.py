from fastapi import APIRouter
from app.api.v1 import endpoints_upload, endpoints_analyze, endpoints_result

api_router = APIRouter()

api_router.include_router(endpoints_upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(endpoints_analyze.router, prefix="/analyze", tags=["analyze"])
api_router.include_router(endpoints_result.router, prefix="/result", tags=["result"])
