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


class TreatmentVerifyRequest(BaseModel):
    """OCR로 인식한 의료 정보로 의료 마이데이터 진료내역을 대조 요청."""
    patient_name: Optional[str] = None
    hospital: Optional[str] = None
    treatment_date: Optional[str] = None   # 조제일/처방일 YYYY-MM-DD
    birth_date: Optional[str] = None        # 있으면 금융 마이데이터 연동에 사용


class TreatmentRecord(BaseModel):
    patient_name: str
    hospital: str
    treatment_date: Optional[str] = None
    source: str


class TreatmentVerifyResult(BaseModel):
    verified: bool
    message: str
    treatment: Optional[TreatmentRecord] = None
    insurance_connected: int = 0           # 자동 연결된 금융 마이데이터 보험 수
    policies: List[MydataPolicyResponse] = []
