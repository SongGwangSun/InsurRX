import json
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.config import settings
from app.services.prompt_service import get_prompt


def _get_llm():
    if settings.LLM_PROVIDER == "anthropic":
        return ChatAnthropic(
            model=settings.LLM_MODEL,
            api_key=settings.ANTHROPIC_API_KEY,
            max_tokens=2048,
        )
    return ChatOpenAI(
        model="gpt-4o",
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
