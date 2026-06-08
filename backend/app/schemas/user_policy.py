from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from app.models.user_policy import PolicyStatus


class UserPolicyResponse(BaseModel):
    id: int
    user_id: int
    product_id: Optional[int]
    file_name: str
    original_name: str
    vector_namespace: str
    chunk_count: int
    status: PolicyStatus
    error_message: Optional[str]
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class UserPolicyUploadResult(BaseModel):
    policy_id: int
    original_name: str
    chunk_count: int
    status: PolicyStatus
    message: str
