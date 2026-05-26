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

# 진단명: "진단명:", "상병명:", "병명:" 뒤 한글 텍스트
DIAGNOSIS_PATTERN = re.compile(
    r'(?:진단명|상병명|병명|진단)\s*[:：]\s*([가-힣a-zA-Z()\s·,]+)',
    re.IGNORECASE
)

# 진료과: "진료과:", "과:" 뒤 한글
DEPT_PATTERN = re.compile(
    r'(?:진료과|진료\s*과목|과)\s*[:：]\s*([가-힣]+(?:과|과목)?)',
    re.IGNORECASE
)

# 병원명: 줄 중 의원/병원/클리닉/의료원/센터로 끝나는 패턴
HOSPITAL_PATTERN = re.compile(
    r'^([가-힣a-zA-Z0-9\s]+(?:의원|병원|클리닉|의료원|보건소|약국|센터|외래))',
    re.MULTILINE
)

# 총 진료비: 본인부담금, 합계, 총진료비 뒤 숫자(콤마 포함)
AMOUNT_PATTERN = re.compile(
    r'(?:본인부담금|합계|총\s*진료비|환자부담금|실부담금|납부금액)\s*[:：]?\s*'
    r'[₩\\\s]*([0-9,]+)\s*원?',
    re.IGNORECASE
)

# 약품: mg/mL/정/캡슐/시럽/크림 등 포함 줄
DRUG_LINE_PATTERN = re.compile(
    r'.+?(?:mg|mL|㎎|정|캡슐|시럽|크림|연고|겔|액|패치|주사|점안|안약|좌약).+'
    r'|.+?(?:mg|mL|㎎|정|캡슐|시럽|크림|연고|겔|액|패치|주사|점안|안약|좌약)',
    re.IGNORECASE
)
# 용량: "500mg", "10mL"
DOSAGE_PATTERN = re.compile(r'(\d+(?:\.\d+)?)\s*(?:mg|mL|㎎|mcg|g)\b', re.IGNORECASE)
# 복용 일수: "5일", "3일분"
DAYS_PATTERN   = re.compile(r'(\d+)\s*일(?:분|치)?')
# 비급여 여부
NON_BENEFIT_KEYWORDS = ['비급여', '비보험', '급여외', '100%']

# 일반적인 의약품 키워드 (약품 라인 감지에만 사용)
DRUG_KEYWORDS = ('mg', 'mL', '㎎', '정', '캡슐', '시럽', '크림', '연고',
                 '겔', '액', '패치', '주사', '점안', '안약', '좌약')

# ── Stage 1: 정규식 추출 ───────────────────────────────────────────────────────

def _extract_icd(text: str) -> str | None:
    m = ICD_PATTERN.findall(text)
    return m[0] if m else None


def _extract_date(text: str) -> str | None:
    m = DATE_PATTERN.findall(text)
    if not m:
        return None
    # 년/월/일 한글을 - 로 정규화
    return re.sub(r'[년월]\s*', '-', m[0]).replace('일', '').strip()


def _extract_diagnosis(text: str) -> str | None:
    m = DIAGNOSIS_PATTERN.search(text)
    if m:
        return m.group(1).strip()
    return None


def _extract_department(text: str) -> str | None:
    m = DEPT_PATTERN.search(text)
    if m:
        dept = m.group(1).strip()
        return dept if len(dept) <= 12 else None   # 너무 길면 오추출
    # 일반 진료과명 직접 탐색
    common_depts = [
        '내과', '외과', '정형외과', '신경외과', '소아과', '소아청소년과',
        '피부과', '안과', '이비인후과', '산부인과', '비뇨기과', '정신건강의학과',
        '신경과', '재활의학과', '마취통증의학과', '응급의학과', '가정의학과',
        '치과', '한의원', '한방과',
    ]
    for dept in common_depts:
        if dept in text:
            return dept
    return None


def _extract_hospital(text: str) -> str | None:
    # 첫 몇 줄에서 병원명 탐색 (OCR 상단에 보통 위치)
    for line in text.split('\n')[:15]:
        line = line.strip()
        if not line or len(line) > 40:
            continue
        m = HOSPITAL_PATTERN.match(line)
        if m:
            return m.group(1).strip()
    return None


def _extract_amount(text: str) -> int | None:
    matches = AMOUNT_PATTERN.findall(text)
    if not matches:
        return None
    # 가장 큰 금액을 총액으로 선택 (공제 전 기준)
    amounts = []
    for raw in matches:
        try:
            amounts.append(int(raw.replace(',', '')))
        except ValueError:
            pass
    return max(amounts) if amounts else None


def _extract_drugs(text: str) -> list[ParsedDrug]:
    drugs = []
    seen = set()

    for line in text.split('\n'):
        line_stripped = line.strip()
        if not line_stripped:
            continue
        if not any(kw in line_stripped for kw in DRUG_KEYWORDS):
            continue
        if len(line_stripped) > 80 or len(line_stripped) < 4:
            continue

        name = line_stripped
        if name in seen:
            continue
        seen.add(name)

        # 용량 추출
        dosage_m = DOSAGE_PATTERN.search(name)
        dosage = dosage_m.group(0) if dosage_m else None

        # 복용 일수 추출
        days_m = DAYS_PATTERN.search(name)
        days = int(days_m.group(1)) if days_m else None

        # 비급여 여부
        is_nonbenefit = any(kw in name for kw in NON_BENEFIT_KEYWORDS)

        drugs.append(ParsedDrug(
            name=name,
            dosage=dosage,
            days=days,
            is_nonbenefit=is_nonbenefit,
            confidence=0.85,
        ))

    return drugs


def _regex_parse(text: str) -> ParsedDocument:
    """정규식만으로 ParsedDocument를 구성합니다."""
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

LLM_PARSE_PROMPT = """\
아래는 병원 처방전 또는 진료비 영수증의 OCR 텍스트입니다.
다음 항목을 JSON으로 추출해주세요. 없으면 null로 표기하세요.

{
  "hospital": "병원/의원 이름 (예: 강남내과의원)",
  "department": "진료과 (예: 내과)",
  "diagnosis": "진단명 (예: 급성상기도감염)",
  "icd_code": "상병코드 (예: J06.9)",
  "prescription_date": "처방일 YYYY-MM-DD (예: 2024-03-15)",
  "total_amount": 본인부담금 숫자만 (예: 28500),
  "drugs": [
    {"name": "약품명", "dosage": "용량(예: 500mg)", "days": 복용일수정수, "is_nonbenefit": false}
  ]
}

OCR 텍스트:
\"\"\"
{ocr_text}
\"\"\"

JSON만 출력하세요."""


async def _llm_parse(text: str) -> dict:
    """GPT-4o로 구조화 추출합니다."""
    try:
        from openai import AsyncOpenAI
        import re as _re
        from app.core.config import settings

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        # 텍스트가 너무 길면 앞 2000자만 사용 (토큰 절약)
        snippet = text[:2000]
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",          # 빠르고 저렴한 모델로 파싱
            max_tokens=800,
            temperature=0,
            messages=[{
                "role": "user",
                "content": LLM_PARSE_PROMPT.format(ocr_text=snippet),
            }],
        )
        raw = resp.choices[0].message.content.strip()
        # ```json ... ``` 블록 제거
        raw = _re.sub(r'^```(?:json)?\s*', '', raw)
        raw = _re.sub(r'\s*```$', '', raw)
        return json.loads(raw)
    except Exception as e:
        logger.warning("LLM 파서 폴백 실패: %s", e)
        return {}


def _merge_with_llm(base: ParsedDocument, llm: dict) -> ParsedDocument:
    """정규식 결과와 LLM 결과를 병합합니다 — 정규식 우선, LLM은 빈 칸만 채움."""
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
            for d in llm["drugs"]
            if d.get("name")
        ]

    return ParsedDocument(
        hospital        = base.hospital         or llm.get("hospital"),
        department      = base.department        or llm.get("department"),
        icd_code        = base.icd_code          or llm.get("icd_code"),
        diagnosis       = base.diagnosis         or llm.get("diagnosis"),
        prescription_date = base.prescription_date or llm.get("prescription_date"),
        total_amount    = base.total_amount      or llm.get("total_amount"),
        drugs           = drugs,
    )


# ── 공개 인터페이스 ────────────────────────────────────────────────────────────

def parse_medical_document(raw_text: str) -> ParsedDocument:
    """
    동기 파서 — Stage 1(정규식)만 실행합니다.
    테스트 및 Clova OCR 미사용 환경에서 사용합니다.
    """
    if not raw_text:
        return ParsedDocument()
    return _regex_parse(raw_text)


async def parse_medical_document_async(raw_text: str) -> ParsedDocument:
    """
    비동기 파서 — Stage 1(정규식) + Stage 2(LLM 폴백)를 실행합니다.
    실제 업로드 엔드포인트에서 사용합니다.
    """
    if not raw_text:
        return ParsedDocument()

    doc = _regex_parse(raw_text)

    if _needs_llm_fallback(doc):
        logger.info("LLM 폴백 파서 실행 (누락 필드 보완)")
        llm_result = await _llm_parse(raw_text)
        doc = _merge_with_llm(doc, llm_result)

    return doc
