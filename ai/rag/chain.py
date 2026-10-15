import hashlib
import json
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.config import settings
from app.services.prompt_service import get_prompt


_OPENAI_MODEL = "gpt-4o"


def current_model_name() -> str:
    """실제 호출되는 LLM 모델명 (결과 추적용)."""
    if settings.LLM_PROVIDER == "anthropic":
        return settings.LLM_MODEL
    return _OPENAI_MODEL


def current_prompt_version() -> str:
    """rag_system + rag_human 프롬프트 내용 해시 (관리자 수정 시 자동 변경)."""
    content = get_prompt("rag_system") + "\n---\n" + get_prompt("rag_human")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]


def _get_llm():
    if settings.LLM_PROVIDER == "anthropic":
        return ChatAnthropic(
            model=settings.LLM_MODEL,
            api_key=settings.ANTHROPIC_API_KEY,
            max_tokens=2048,
        )
    return ChatOpenAI(
        model=_OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        max_tokens=2048,
    )


async def run_coverage_chain(document_info: str, clauses: str) -> dict:
    """약관 조항과 의료 문서를 비교하여 보상 분석 결과를 반환합니다."""
    llm = _get_llm()
    messages = [
        SystemMessage(content=get_prompt("rag_system")),
        HumanMessage(content=get_prompt("rag_human").format(
            document_info=document_info,
            clauses=clauses,
        )),
    ]
    response = await llm.ainvoke(messages)
    raw = response.content.strip()

    # JSON 블록 추출 (```json ... ``` 감싸인 경우 대응)
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    return json.loads(raw.strip())
