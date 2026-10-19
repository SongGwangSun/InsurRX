"""
Vision OCR — GPT-4o Vision 기반 텍스트 추출

Clova OCR 대신 OpenAI GPT-4o Vision을 사용합니다.
한글·영문·숫자·특수문자를 정확하게 인식하며 의료 문서에 최적화된 프롬프트를 사용합니다.

기존 함수 시그니처(run_ocr)를 그대로 유지하므로 호출부 변경 불필요.
"""

import base64
import logging

from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

# OpenAI Vision API가 지원하는 MIME 타입
_SUPPORTED = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"}

_OCR_PROMPT = """\
이 의료 문서(처방전, 진료비 영수증 또는 약국 약봉투·복약안내문)에서 보이는 모든 텍스트를 추출해주세요.

규칙:
1. 한글, 영문, 숫자, 특수문자를 원문 그대로 출력
2. 줄바꿈과 들여쓰기를 원문과 최대한 동일하게 유지
3. 상병코드(예: J06.9 급성상기도감염), 약품명(예: 아목시실린 500mg), 금액은 특히 정확하게 추출
4. 도장·서명·스탬프 영역의 글자도 포함
   약봉투라면 약국명, 조제일자, 약품명·용량, 1회 투약량·1일 투여횟수·총 투약일수, 복용법, 약제비 금액을 빠짐없이 추출
5. 세로쓰기(글자가 위→아래로 배치)된 항목은 위에서 아래 순서대로 각 글자를 한 줄에 하나씩 출력. 특히 환자 성명이 세로로 적혀 있으면 라벨과 이름 글자를 순서대로 빠짐없이 출력
6. 추가 설명, 해석, 요약 없이 추출된 텍스트만 출력
"""

_POLICY_OCR_PROMPT = """\
이 보험 문서(보험증권 또는 보험약관 페이지)에서 보이는 모든 텍스트를 추출해주세요.

규칙:
1. 한글, 영문, 숫자, 특수문자를 원문 그대로 출력
2. 보험사명, 상품명, 증권번호, 계약일·보험기간, 담보(특약)명과 가입금액, 보험료는 특히 정확하게 추출
3. 표는 한 행을 한 줄로, 칸 사이는 ' | '로 구분해 출력
4. 조항 번호(제○조)와 제목, 본문 순서를 유지
5. 추가 설명, 해석, 요약 없이 추출된 텍스트만 출력
"""

# doc_kind → (프롬프트, 최대 출력 토큰)
_PROMPTS = {
    "medical": (_OCR_PROMPT, 2000),
    "policy":  (_POLICY_OCR_PROMPT, 4096),
}


async def run_ocr(image_bytes: bytes, content_type: str = "image/jpeg", doc_kind: str = "medical") -> str:
    """
    GPT-4o Vision으로 이미지에서 텍스트를 추출합니다.

    Args:
        image_bytes: 이미지 바이트
        content_type: MIME 타입 (image/jpeg, image/png, image/webp 등)
        doc_kind: "medical"(처방전·영수증·약봉투) 또는 "policy"(보험증권·약관)

    Returns:
        추출된 텍스트 (줄바꿈 포함)
    """
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다.")

    # HEIC·HEIF·BMP 등 미지원 포맷 → JPEG로 재시도
    mime = content_type if content_type in _SUPPORTED else "image/jpeg"
    if mime != content_type:
        logger.warning("Vision OCR: 미지원 MIME %s → image/jpeg 로 처리", content_type)

    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime};base64,{b64}"

    prompt, max_tokens = _PROMPTS.get(doc_kind, _PROMPTS["medical"])

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    logger.info("Vision OCR 시작: kind=%s mime=%s size=%dB", doc_kind, mime, len(image_bytes))

    response = await client.chat.completions.create(
        model="gpt-4o-mini",   # vision 지원, 빠르고 저렴
        max_tokens=max_tokens,
        temperature=0,         # 재현성 최대화
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url, "detail": "high"},
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            }
        ],
    )

    raw_text = response.choices[0].message.content.strip()
    logger.info(
        "Vision OCR 완료: %d자 추출 (tokens: %s)",
        len(raw_text),
        response.usage.total_tokens if response.usage else "?",
    )
    return raw_text
