from datetime import datetime

from pydantic import BaseModel

from app.models.user_policy import PolicyStatus


class UserPolicyResponse(BaseModel):
    id: int
    user_id: int
    product_id: int | None
    file_name: str
    original_name: str
    vector_namespace: str
    chunk_count: int
    status: PolicyStatus
    error_message: str | None
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class UserPolicyUploadResult(BaseModel):
    policy_id: int
    original_name: str
    chunk_count: int
    status: PolicyStatus
    message: str
