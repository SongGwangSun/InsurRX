
from pydantic import BaseModel


class ParsedDrug(BaseModel):
    name: str
    dosage: str | None = None
    days: int | None = None
    is_nonbenefit: bool = False
    confidence: float = 1.0


# 문서 종류 코드 → 표시명
DOC_TYPE_LABELS = {
    "prescription":  "처방전",
    "receipt":       "진료비 영수증",
    "pill_envelope": "약봉투",
}


class ParsedDocument(BaseModel):
    patient_name: str | None = None
    hospital: str | None = None
    department: str | None = None
    icd_code: str | None = None
    diagnosis: str | None = None
    prescription_date: str | None = None
    drugs: list[ParsedDrug] = []
    total_amount: int | None = None
    doc_types: list[str] = []   # 인식된 문서 종류 (prescription/receipt/pill_envelope), 여러 장이면 복수


class UploadResponse(BaseModel):
    filename: str
    ocr_raw: str
    parsed: ParsedDocument
