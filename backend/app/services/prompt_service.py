"""
프롬프트 레지스트리

- 앱 시작 시 DB에서 로드 → 메모리 캐시 (_registry)
- DB에 레코드가 없으면 DEFAULT_PROMPTS로 자동 시드
- get_prompt(key)는 DB 세션 없이 호출 가능 (동기)
- update_prompt / reset_prompt는 DB + 캐시를 함께 갱신
"""
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prompt_template import PromptTemplate

logger = logging.getLogger(__name__)

# ── 기본값 (코드 레벨 fallback) ───────────────────────────────────────────────

DEFAULT_PROMPTS: dict[str, dict] = {
    "ocr_llm_parse": {
        "name": "OCR LLM 파서 프롬프트",
        "content": """\
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

JSON만 출력하세요.""",
    },

    "rag_system": {
        "name": "RAG 시스템 프롬프트 (보험 전문가 역할 정의)",
        "content": """\
당신은 한국 실손/정액 보험 약관 전문가입니다.
사용자의 의료 문서(처방전, 진료비 영수증)와 보험 약관 조항을 비교하여
보상 여부와 예상 지급액을 정확하게 분석합니다.

분석 규칙:
- 면책 조항(자기부담금, 비급여 항목, 선천성 질환 등)을 반드시 확인합니다.
- 상병코드(ICD)를 기준으로 해당 약관 조항의 적용 여부를 판단합니다.
- 약품명이 비급여인 경우 실손 보상 제외 여부를 확인합니다.
- 예상 금액 산출 시 공제금액(의원 1만원, 약국 8천원 등)을 적용합니다.
- 불확실한 경우 confidence를 낮게 설정하고 이유를 명시합니다.

반드시 JSON 형식으로만 응답하세요.""",
    },

    "rag_human": {
        "name": "RAG 사용자 프롬프트 (문서 + 약관 조항 분석 요청)",
        "content": """\
## 의료 문서 정보
{document_info}

## 관련 약관 조항
{clauses}

위 정보를 바탕으로 보험 보상 분석 결과를 다음 JSON 형식으로 반환하세요:
{{
  "is_claimable": true/false,
  "estimated_payout": 예상지급액(정수, 원단위),
  "breakdown": {{
    "항목명": 금액
  }},
  "coverage_items": [
    {{
      "clause_id": "약관ID",
      "policy_name": "보험상품명",
      "article": "조항명",
      "is_covered": true/false,
      "reason": "판단 근거",
      "citation": "약관 원문 발췌"
    }}
  ],
  "confidence": 0.0~1.0,
  "llm_summary": "사용자에게 보여줄 자연어 요약 (1~2문장)"
}}""",
    },
}

# ── 메모리 캐시 ───────────────────────────────────────────────────────────────

_registry: dict[str, str] = {}


def get_prompt(key: str) -> str:
    """캐시에서 프롬프트를 반환합니다. 없으면 기본값을 반환합니다."""
    if key in _registry:
        return _registry[key]
    default = DEFAULT_PROMPTS.get(key, {}).get("content", "")
    logger.warning("프롬프트 '%s'가 캐시에 없어 기본값을 사용합니다.", key)
    return default


# ── DB 연동 ───────────────────────────────────────────────────────────────────

async def seed_and_load(db: AsyncSession) -> None:
    """앱 시작 시 호출. DB에 없는 프롬프트를 시드하고 전체를 캐시에 로드합니다."""
    for key, meta in DEFAULT_PROMPTS.items():
        result = await db.execute(
            select(PromptTemplate).where(PromptTemplate.key == key)
        )
        row = result.scalar_one_or_none()
        if row is None:
            db.add(PromptTemplate(
                key=key,
                name=meta["name"],
                content=meta["content"],
            ))
            logger.info("프롬프트 시드: %s", key)

    await db.commit()

    # 전체 로드
    result = await db.execute(
        select(PromptTemplate).where(PromptTemplate.is_active.is_(True))
    )
    for row in result.scalars().all():
        _registry[row.key] = row.content

    logger.info("프롬프트 %d개 캐시 로드 완료", len(_registry))


async def list_prompts(db: AsyncSession) -> list[PromptTemplate]:
    result = await db.execute(select(PromptTemplate).order_by(PromptTemplate.id))
    return list(result.scalars().all())


async def get_prompt_row(key: str, db: AsyncSession) -> PromptTemplate | None:
    result = await db.execute(
        select(PromptTemplate).where(PromptTemplate.key == key)
    )
    return result.scalar_one_or_none()


async def update_prompt(key: str, name: str | None, content: str, db: AsyncSession) -> PromptTemplate:
    result = await db.execute(
        select(PromptTemplate).where(PromptTemplate.key == key)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise ValueError(f"프롬프트 키 '{key}'를 찾을 수 없습니다.")

    row.content = content
    row.version += 1
    if name:
        row.name = name

    await db.commit()
    await db.refresh(row)

    _registry[key] = content
    logger.info("프롬프트 업데이트: %s (v%d)", key, row.version)
    return row


async def reset_prompt(key: str, db: AsyncSession) -> PromptTemplate:
    """기본값으로 초기화합니다."""
    default = DEFAULT_PROMPTS.get(key)
    if default is None:
        raise ValueError(f"프롬프트 키 '{key}'의 기본값이 없습니다.")
    return await update_prompt(key, default["name"], default["content"], db)
