import re
from app.schemas.upload import ParsedDocument

# 실손 보험 주요 면책 조항 키워드
EXCLUSION_KEYWORDS = [
    "선천성", "미용", "성형", "비만", "치과", "한방", "건강검진",
    "예방접종", "임신", "출산", "불임", "성전환",
]

# 비급여 약품은 실손에서 제외될 수 있는 패턴
NONBENEFIT_DRUG_EXCLUSION = True


def check_exclusions(parsed_doc: ParsedDocument) -> list[str]:
    """면책 조항 해당 여부를 빠르게 사전 필터링합니다. 해당 면책 사유 목록 반환."""
    exclusions = []

    diagnosis_text = f"{parsed_doc.diagnosis or ''} {parsed_doc.icd_code or ''}"
    for kw in EXCLUSION_KEYWORDS:
        if kw in diagnosis_text:
            exclusions.append(f"면책 키워드 감지: '{kw}'")

    if NONBENEFIT_DRUG_EXCLUSION:
        nb_drugs = [d.name for d in parsed_doc.drugs if d.is_nonbenefit]
        if nb_drugs:
            exclusions.append(f"비급여 약품 포함 (실손 제외 가능): {', '.join(nb_drugs)}")

    return exclusions


def estimate_deductible(hospital_type: str = "의원") -> int:
    """통원 자기부담금 공제액 반환 (실손 기준)."""
    deductibles = {
        "의원": 10_000,
        "병원": 15_000,
        "종합병원": 20_000,
        "상급종합병원": 20_000,
        "약국": 8_000,
    }
    return deductibles.get(hospital_type, 10_000)


def classify_hospital(hospital_name: str) -> str:
    """병원명으로 의료기관 종별 추정."""
    if not hospital_name:
        return "의원"
    if any(kw in hospital_name for kw in ("대학교병원", "대학병원", "상급")):
        return "상급종합병원"
    if any(kw in hospital_name for kw in ("종합병원", "종합")):
        return "종합병원"
    if "병원" in hospital_name:
        return "병원"
    return "의원"
