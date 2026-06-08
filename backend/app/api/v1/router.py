from fastapi import APIRouter
from app.api.v1 import (
    endpoints_upload, endpoints_analyze,
    endpoints_result, endpoints_waitlist, endpoints_prompts,
    endpoints_auth, endpoints_user_policies, endpoints_insurers,
    endpoints_history, endpoints_bootstrap, endpoints_admin,
    endpoints_kakao, endpoints_mydata,
)

api_router = APIRouter()

api_router.include_router(endpoints_upload.router,          prefix="/upload",          tags=["upload"])
api_router.include_router(endpoints_analyze.router,         prefix="/analyze",         tags=["analyze"])
api_router.include_router(endpoints_result.router,          prefix="/result",          tags=["result"])
api_router.include_router(endpoints_waitlist.router,        prefix="/waitlist",        tags=["waitlist"])
api_router.include_router(endpoints_prompts.router,                                    tags=["prompts"])
api_router.include_router(endpoints_auth.router,            prefix="/auth",            tags=["auth"])
api_router.include_router(endpoints_user_policies.router,   prefix="/my/policies",     tags=["my-policies"])
api_router.include_router(endpoints_insurers.router,        prefix="/insurers",        tags=["insurers"])
api_router.include_router(endpoints_history.router,         prefix="/my/analyses",     tags=["my-analyses"])
api_router.include_router(endpoints_bootstrap.router,       prefix="/admin/bootstrap", tags=["bootstrap"])
api_router.include_router(endpoints_admin.router,           prefix="/admin",           tags=["admin"])
api_router.include_router(endpoints_kakao.router,           prefix="/kakao",            tags=["kakao"])
api_router.include_router(endpoints_mydata.router,          prefix="/mydata",           tags=["mydata"])
