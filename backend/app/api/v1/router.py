from fastapi import APIRouter
from app.api.v1 import (
    endpoints_upload, endpoints_analyze,
    endpoints_result, endpoints_waitlist, endpoints_prompts,
)

api_router = APIRouter()

api_router.include_router(endpoints_upload.router,   prefix="/upload",   tags=["upload"])
api_router.include_router(endpoints_analyze.router,  prefix="/analyze",  tags=["analyze"])
api_router.include_router(endpoints_result.router,   prefix="/result",   tags=["result"])
api_router.include_router(endpoints_waitlist.router, prefix="/waitlist", tags=["waitlist"])
api_router.include_router(endpoints_prompts.router,                      tags=["prompts"])
