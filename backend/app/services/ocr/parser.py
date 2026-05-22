import re
from app.schemas.upload import ParsedDocument, ParsedDrug

ICD_PATTERN = re.compile(r'\b([A-Z]\d{2}(?:\.\d{1,2})?)\b')
DATE_PATTERN = re.compile(r'(\d{4}[-./]\d{1,2}[-./]\d{1,2})')


def parse_medical_document(raw_text: str) -> ParsedDocument:
    """OCR 원문 텍스트에서 의료 항목을 추출합니다."""
    icd_matches = ICD_PATTERN.findall(raw_text)
    date_matches = DATE_PATTERN.findall(raw_text)

    return ParsedDocument(
        icd_code=icd_matches[0] if icd_matches else None,
        prescription_date=date_matches[0] if date_matches else None,
        drugs=_extract_drugs(raw_text),
    )


def _extract_drugs(text: str) -> list[ParsedDrug]:
    """약품명 패턴을 추출합니다. 실제 구현 시 식약처 DB와 매핑 필요."""
    drugs = []
    for line in text.split('\n'):
        if any(kw in line for kw in ('mg', 'mL', '정', '시럽', '캡슐', '크림', '연고', '액', '패치', '주사', '점안')):
            drugs.append(ParsedDrug(
                name=line.strip(),
                is_nonbenefit='비급여' in line,
                confidence=0.85,
            ))
    return drugs
