"""
OCR 원문 텍스트 → ParsedDocument 변환기

Stage 1: 정규식 기반 고속 추출 (병원명, 진료과, 진단명, 총액, 약품)
Stage 2: LLM 폴백 — 핵심 필드 누락 시 GPT-4o로 JSON 추출 (비동기)
"""
import re
import json
import logging
from app.schemas.upload import ParsedDocument, ParsedDrug

logger = logging.getLogger(__name__)

# ── 정규식 패턴 ────────────────────────────────────────────────────────────────

ICD_PATTERN  = re.compile(r'\b([A-Z]\d{2}(?:\.\d{1,2})?)\b')
DATE_PATTERN = re.compile(r'(\d{4}[-./년]\s*\d{1,2}[-./월]\s*\d{1,2})')

# 진단명: 레이블 뒤 한글 텍스트 (상병/진단/병명 등)
DIAGNOSIS_PATTERN = re.compile(
    r'(?:진단명|상병명|상병|병명|진단)\s*[:：]\s*([가-힣a-zA-Z()\s·,·]+?)(?:\n|$|[0-9])',
    re.IGNORECASE
)

# ICD 코드 바로 뒤에 오는 진단명 (예: "J06.9 급성상기도감염") — 같은 줄만 허용
ICD_WITH_NAME_PATTERN = re.compile(
    r'[A-Z]\d{2}(?:\.\d{1,2})?[^\S\n]+([가-힣]{2,}(?:[^\S\n]*[가-힣]+){0,2})'
)

# 진료과
DEPT_PATTERN = re.compile(
    r'(?:진료과|진료\s*과목|과)\s*[:：]\s*([가-힣]+(?:과|과목)?)',
    re.IGNORECASE
)

# 병원명: 첫 줄 중 의원/병원 등으로 끝나는 이름
HOSPITAL_PATTERN = re.compile(
    r'^([가-힣a-zA-Z0-9\s·]+(?:의원|병원|클리닉|의료원|보건소|약국|센터|외래|한의원))',
    re.MULTILINE
)

# ── 총액 패턴 (우선순위 순) ──────────────────────────────────────────────────
# 1순위: 본인부담금 (실제 환자 납부액 = 실손 청구 기준)
PATIENT_AMOUNT_PATTERN = re.compile(
    r'(?:본인부담금|환자부담금|실부담금|본인일부부담금|납부금액|수납금액|청구금액)\s*[:：]?\s*'
    r'[₩\\]?\s*([0-9,]+)\s*원?',
    re.IGNORECASE
)
# 2순위: 총 진료비 합계
TOTAL_AMOUNT_PATTERN = re.compile(
    r'(?:합계|총\s*진료비|총액|진료비\s*합계)\s*[:：]?\s*'
    r'[₩\\]?\s*([0-9,]+)\s*원?',
    re.IGNORECASE
)

# 약품 패턴
DRUG_KEYWORDS = ('mg', 'mL', '㎎', '정', '캡슐', '시럽', '크림', '연고',
                 '겔', '액', '패치', '주사', '점안', '안약', '좌약')
# 약품 줄에서 제외할 키워드 (금액·레이블 등 오인 방지)
DRUG_EXCLUDE_KW = ('금액', '합계', '부담금', '납부', '수납', '청구', '영수', '원정',
                   '진료비', '처방', '성명', '주민', '생년', '병원', '의원', '약국')
DOSAGE_PATTERN  = re.compile(r'(\d+(?:\.\d+)?)\s*(?:mg|mL|㎎|mcg|g)\b', re.IGNORECASE)
DAYS_PATTERN    = re.compile(r'(\d+)\s*일(?:분|치)?')
NON_BENEFIT_KW  = ['비급여', '비보험', '급여외', '100%']

# 흔한 진료과 목록 (레이블 없을 때 직접 탐색)
COMMON_DEPTS = [
    '내과', '외과', '정형외과', '신경외과', '소아과', '소아청소년과',
    '피부과', '안과', '이비인후과', '산부인과', '비뇨기과', '정신건강의학과',
    '신경과', '재활의학과', '마취통증의학과', '응급의학과', '가정의학과',
    '치과', '한의원', '한방과',
]


# ── Stage 1: 정규식 추출 ───────────────────────────────────────────────────────

def _extract_icd(text: str) -> str | None:
    m = ICD_PATTERN.findall(text)
    return m[0] if m else None


def _extract_date(text: str) -> str | None:
    m = DATE_PATTERN.findall(text)
    if not m:
        return None
    return re.sub(r'[년월]\s*', '-', m[0]).replace('일', '').strip()


def _extract_diagnosis(text: str) -> str | None:
    # 레이블 뒤 진단명
    m = DIAGNOSIS_PATTERN.search(text)
    if m:
        val = m.group(1).strip().rstrip('·,·')
        if val:
            return val

    # ICD 코드 + 한글 진단명 패턴
    m2 = ICD_WITH_NAME_PATTERN.search(text)
    if m2:
        val = m2.group(1).strip()
        if len(val) >= 2:
            return val

    return None


def _extract_department(text: str) -> str | None:
    m = DEPT_PATTERN.search(text)
    if m:
        dept = m.group(1).strip()
        return dept if len(dept) <= 12 else None
    for dept in COMMON_DEPTS:
        if dept in text:
            return dept
    return None


def _extract_hospital(text: str) -> str | None:
    lines = text.split('\n')[:20]   # 상단 20줄 탐색 (여유 확대)
    for line in lines:
        line = line.strip()
        if not line or len(line) > 50:
            continue
        m = HOSPITAL_PATTERN.match(line)
        if m:
            return m.group(1).strip()
    return None


def _extract_amount(text: str) -> int | None:
    """본인부담금 우선 → 없으면 합계 금액 반환."""
    def _parse_amounts(pattern: re.Pattern) -> list[int]:
        out = []
        for raw in pattern.findall(text):
            try:
                out.append(int(raw.replace(',', '')))
            except ValueError:
                pass
        return out

    # 1순위: 본인부담금
    patient_amts = _parse_amounts(PATIENT_AMOUNT_PATTERN)
    if patient_amts:
        # 여러 개면 가장 큰 값 (세목 합계)
        return max(patient_amts)

    # 2순위: 총 진료비
    total_amts = _parse_amounts(TOTAL_AMOUNT_PATTERN)
    if total_amts:
        return max(total_amts)

    return None


def _extract_drugs(text: str) -> list[ParsedDrug]:
    drugs, seen = [], set()
    for line in text.split('\n'):
        line = line.strip()
        if not line or not any(kw in line for kw in DRUG_KEYWORDS):
            continue
        if any(ex in line for ex in DRUG_EXCLUDE_KW):
            continue
        if len(line) > 80 or len(line) < 4:
            continue
        if line in seen:
            continue
        seen.add(line)

        dosage_m = DOSAGE_PATTERN.search(line)
        days_m   = DAYS_PATTERN.search(line)
        drugs.append(ParsedDrug(
            name=line,
            dosage=dosage_m.group(0) if dosage_m else None,
            days=int(days_m.group(1)) if days_m else None,
            is_nonbenefit=any(kw in line for kw in NON_BENEFIT_KW),
            confidence=0.85,
        ))
    return drugs


def _regex_parse(text: str) -> ParsedDocument:
    return ParsedDocument(
        hospital=_extract_hospital(text),
        department=_extract_department(text),
        icd_code=_extract_icd(text),
        diagnosis=_extract_diagnosis(text),
        prescription_date=_extract_date(text),
        total_amount=_extract_amount(text),
        drugs=_extract_drugs(text),
    )


def _needs_llm_fallback(doc: ParsedDocument) -> bool:
    """핵심 필드가 2개 이상 누락되면 LLM 폴백 필요."""
    missing = sum([
        doc.hospital is None,
        doc.diagnosis is None,
        doc.total_amount is None,
    ])
    return missing >= 2


# ── Stage 2: LLM 폴백 ─────────────────────────────────────────────────────────

from app.services.prompt_service import get_prompt as _get_prompt


async def _llm_parse(text: str) -> dict:
    try:
        from openai import AsyncOpenAI
        import re as _re
        from app.core.config import settings

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        snippet = text[:2000]
        prompt  = _get_prompt("ocr_llm_parse").format(ocr_text=snippet)
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=800,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.choices[0].message.content.strip()
        raw = _re.sub(r'^```(?:json)?\s*', '', raw)
        raw = _re.sub(r'\s*```$', '', raw)
        return json.loads(raw)
    except Exception as e:
        logger.warning("LLM 파서 폴백 실패: %s", e)
        return {}


def _merge_with_llm(base: ParsedDocument, llm: dict) -> ParsedDocument:
    drugs = base.drugs
    if not drugs and llm.get("drugs"):
        drugs = [
            ParsedDrug(
                name=d.get("name", ""),
                dosage=d.get("dosage"),
                days=d.get("days"),
                is_nonbenefit=d.get("is_nonbenefit", False),
                confidence=0.75,
            )
            for d in llm["drugs"] if d.get("name")
        ]
    return ParsedDocument(
        hospital          = base.hospital          or llm.get("hospital"),
        department        = base.department         or llm.get("department"),
        icd_code          = base.icd_code           or llm.get("icd_code"),
        diagnosis         = base.diagnosis          or llm.get("diagnosis"),
        prescription_date = base.prescription_date  or llm.get("prescription_date"),
        total_amount      = base.total_amount       or llm.get("total_amount"),
        drugs             = drugs,
    )


# ── 공개 인터페이스 ────────────────────────────────────────────────────────────

def parse_medical_document(raw_text: str) -> ParsedDocument:
    """동기 파서 — Stage 1(정규식)만 실행."""
    if not raw_text:
        return ParsedDocument()
    return _regex_parse(raw_text)


async def parse_medical_document_async(raw_text: str) -> ParsedDocument:
    """비동기 파서 — Stage 1(정규식) + Stage 2(LLM 폴백)."""
    if not raw_text:
        return ParsedDocument()
    doc = _regex_parse(raw_text)
    if _needs_llm_fallback(doc):
        logger.info("LLM 폴백 파서 실행 (누락 필드 보완)")
        llm_result = await _llm_parse(raw_text)
        doc = _merge_with_llm(doc, llm_result)
    return doc
