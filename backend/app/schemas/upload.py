from pydantic import BaseModel
from typing import Optional, List


class ParsedDrug(BaseModel):
    name: str
    dosage: Optional[str] = None
    days: Optional[int] = None
    is_nonbenefit: bool = False
    confidence: float = 1.0


class ParsedDocument(BaseModel):
    patient_name: Optional[str] = None
    hospital: Optional[str] = None
    department: Optional[str] = None
    icd_code: Optional[str] = None
    diagnosis: Optional[str] = None
    prescription_date: Optional[str] = None
    drugs: List[ParsedDrug] = []
    total_amount: Optional[int] = None


class UploadResponse(BaseModel):
    filename: str
    ocr_raw: str
    parsed: ParsedDocument
