"""
OCR 원문 텍스트 → ParsedDocument 변환기

Stage 1: 정규식 기반 고속 추출 (병원명, 진료과, 진단명, 총액, 약품)
Stage 2: LLM 폴백 — 핵심 필드 누락 시 GPT-4o로 JSON 추출 (비동기)
"""
import os
import re
import json
import logging
from app.schemas.upload import ParsedDocument, ParsedDrug

logger = logging.getLogger(__name__)

# ── 인식 키워드 사전 (편집 가능: ocr_keywords.json) ───────────────────────────

_KEYWORDS_PATH = os.path.join(os.path.dirname(__file__), "ocr_keywords.json")

_DEFAULT_KEYWORDS = {
    "patient_name_labels": ["환자성명", "환자명", "수진자", "성명", "이름", "피보험자"],
    "hospital_labels": ["요양기관명", "의료기관명", "의료기관", "병원명", "기관명", "병원정보"],
    "hospital_suffixes": ["의원", "병원", "클리닉", "의료원", "보건소", "약국", "센터", "외래", "한의원", "치과"],
    "department_labels": ["진료과목", "진료과", "진료부서", "과목"],
    "diagnosis_labels": ["진단명", "상병명", "상병", "병명", "진단"],
    "patient_amount_labels": ["본인부담금", "환자부담금", "실부담금", "본인일부부담금", "납부금액", "수납금액", "청구금액"],
    "total_amount_labels": ["합계", "총진료비", "총액", "진료비합계"],
    "name_stopwords": ["홍길동", "성명", "환자명", "수진자", "보호자", "발급", "병원", "의원", "약국", "주민", "번호", "구분", "등록", "정보", "생년"],
}


def _load_keywords() -> dict:
    """ocr_keywords.json을 로드해 기본값 위에 병합. 실패 시 기본값."""
    merged = {k: list(v) for k, v in _DEFAULT_KEYWORDS.items()}
    try:
        with open(_KEYWORDS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if isinstance(v, list):
                merged[k] = v
    except Exception as e:
        logger.warning("ocr_keywords.json 로드 실패, 기본값 사용: %s", e)
    return merged


KW = _load_keywords()


def _label_alt(labels) -> str:
    """라벨 리스트 → 정규식 대안. 긴 라벨 우선 매칭, 라벨 글자 사이 공백 허용."""
    parts = [r"\s*".join(re.escape(ch) for ch in lab) for lab in sorted(labels, key=len, reverse=True)]
    return "(?:" + "|".join(parts) + ")"

# ── 정규식 패턴 ────────────────────────────────────────────────────────────────

ICD_PATTERN  = re.compile(r'\b([A-Z]\d{2}(?:\.\d{1,2})?)\b')
DATE_PATTERN = re.compile(r'(\d{4}[-./년]\s*\d{1,2}[-./월]\s*\d{1,2})')

# 진단명: 레이블 뒤 한글 텍스트 (상병/진단/병명 등)
DIAGNOSIS_PATTERN = re.compile(
    _label_alt(KW["diagnosis_labels"]) + r'\s*[:：]\s*([가-힣a-zA-Z()\s·,·]+?)(?:\n|$|[0-9])',
    re.IGNORECASE
)

# ICD 코드 바로 뒤에 오는 진단명 (예: "J06.9 급성상기도감염") — 같은 줄만 허용
ICD_WITH_NAME_PATTERN = re.compile(
    r'[A-Z]\d{2}(?:\.\d{1,2})?[^\S\n]+([가-힣]{2,}(?:[^\S\n]*[가-힣]+){0,2})'
)

# 환자 성명: 레이블 뒤 한글 이름 2~4자 (글자 사이 공백 허용: '홍 길 동')
PATIENT_NAME_PATTERN = re.compile(
    _label_alt(KW["patient_name_labels"]) + r'\s*[:：]?\s*([가-힣](?:\s?[가-힣]){1,3})(?![가-힣])'
)
# 환자 성명 라벨이 줄 끝에 있고 값이 다음 줄에 있는 경우 탐지용
PATIENT_NAME_LABEL_EOL = re.compile(_label_alt(KW["patient_name_labels"]) + r'\s*[:：]?\s*$')
NAME_TOKEN = re.compile(r'^([가-힣](?:\s?[가-힣]){1,3})(?![가-힣])')

# 진료과
DEPT_PATTERN = re.compile(
    _label_alt(KW["department_labels"]) + r'\s*[:：]?\s*([가-힣]+(?:과|과목)?)',
    re.IGNORECASE
)

# 병원명 ① 라벨 기반 (요양기관명/병원명 등 뒤의 값)
HOSPITAL_LABEL_PATTERN = re.compile(
    _label_alt(KW["hospital_labels"]) + r'\s*[:：]?\s*([가-힣A-Za-z0-9()·\s]{2,40}?)(?:\n|$)'
)
# 병원명 ② 접미사 기반 (의원/병원 등으로 끝나는 이름 — 줄 어디에 있든)
_HOSP_SUFFIX_ALT = "(?:" + "|".join(
    re.escape(s) for s in sorted(KW["hospital_suffixes"], key=len, reverse=True)
) + ")"
HOSPITAL_SUFFIX_PATTERN = re.compile(r'([가-힣A-Za-z0-9()·]{1,30}?' + _HOSP_SUFFIX_ALT + ')')

# ── 총액 패턴 (우선순위 순) ──────────────────────────────────────────────────
# 1순위: 본인부담금 (실제 환자 납부액 = 실손 청구 기준)
PATIENT_AMOUNT_PATTERN = re.compile(
    _label_alt(KW["patient_amount_labels"]) + r'\s*[:：]?\s*[₩\\]?\s*([0-9,]+)\s*원?',
    re.IGNORECASE
)
# 2순위: 총 진료비 합계
TOTAL_AMOUNT_PATTERN = re.compile(
    _label_alt(KW["total_amount_labels"]) + r'\s*[:：]?\s*[₩\\]?\s*([0-9,]+)\s*원?',
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


_NAME_STOPWORDS = set(KW["name_stopwords"])


def _valid_name(name: str) -> bool:
    return (
        2 <= len(name) <= 4
        and name not in _NAME_STOPWORDS
        and not name.endswith(("과", "원", "국", "목"))
    )


def _extract_patient_name(text: str) -> str | None:
    # ① 같은 줄: 라벨 뒤 이름
    for m in PATIENT_NAME_PATTERN.finditer(text):
        name = re.sub(r"\s", "", m.group(1))
        if _valid_name(name):
            return name
    # ② 라벨이 줄 끝에 있고 이름이 다음 줄에 있는 경우
    lines = [ln.strip() for ln in text.split("\n")]
    for i in range(len(lines) - 1):
        if PATIENT_NAME_LABEL_EOL.search(lines[i]):
            tm = NAME_TOKEN.match(lines[i + 1])
            if tm:
                name = re.sub(r"\s", "", tm.group(1))
                if _valid_name(name):
                    return name
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
    # ① 라벨 기반: 요양기관명/병원명 등 뒤의 값
    m = HOSPITAL_LABEL_PATTERN.search(text)
    if m:
        val = m.group(1).strip().strip("·").strip()
        if len(val) >= 2:
            return val
    # ② 접미사 기반: 의원/병원 등으로 끝나는 이름 (상단 25줄 우선)
    for line in text.split("\n")[:25]:
        line = line.strip()
        if not line or len(line) > 60:
            continue
        sm = HOSPITAL_SUFFIX_PATTERN.search(line)
        if sm:
            name = sm.group(1).strip()
            # 라벨 접두어가 붙어 있으면 제거 (예: "병원명 서울병원")
            for lab in KW["hospital_labels"]:
                if name.startswith(lab):
                    name = name[len(lab):].strip(" :：").strip()
            if 2 <= len(name) <= 40:
                return name
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
        patient_name=_extract_patient_name(text),
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
        patient_name      = base.patient_name       or llm.get("patient_name"),
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
