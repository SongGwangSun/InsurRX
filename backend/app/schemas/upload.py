from pydantic import BaseModel
from typing import Optional, List


class ParsedDrug(BaseModel):
    name: str
    dosage: Optional[str] = None
    days: Optional[int] = None
    is_nonbenefit: bool = False
    confidence: float = 1.0


# 문서 종류 코드 → 표시명
DOC_TYPE_LABELS = {
    "prescription":  "처방전",
    "receipt":       "진료비 영수증",
    "pill_envelope": "약봉투",
}


class ParsedDocument(BaseModel):
    patient_name: Optional[str] = None
    hospital: Optional[str] = None
    department: Optional[str] = None
    icd_code: Optional[str] = None
    diagnosis: Optional[str] = None
    prescription_date: Optional[str] = None
    drugs: List[ParsedDrug] = []
    total_amount: Optional[int] = None
    doc_types: List[str] = []   # 인식된 문서 종류 (prescription/receipt/pill_envelope), 여러 장이면 복수


class UploadResponse(BaseModel):
    filename: str
    ocr_raw: str
    parsed: ParsedDocument
