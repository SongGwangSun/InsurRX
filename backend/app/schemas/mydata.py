from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class MydataConsentRequest(BaseModel):
    """마이데이터 동의 요청 (사용자 본인 확인용)."""
    name: str
    birth_date: str   # YYYYMMDD (주민번호 앞 6자리가 아닌 생년월일)


class MydataPolicyResponse(BaseModel):
    id: int
    org_code: str
    org_name: str
    policy_number: str
    insurance_name: str
    product_type: str
    premium: Optional[int]
    coverage_start: Optional[str]
    coverage_end: Optional[str]
    status: str
    vector_policy_id: Optional[str]
    has_rag_data: bool = False   # vector_policy_id 있으면 True
    connected_at: datetime
    is_active: bool

    model_config = {"from_attributes": True}


class MydataConnectResult(BaseModel):
    connected_count: int
    policies: List[MydataPolicyResponse]
    message: str
