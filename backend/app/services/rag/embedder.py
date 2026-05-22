from app.core.config import settings


async def get_query_embedding(text: str) -> list[float]:
    """텍스트를 벡터 임베딩으로 변환합니다."""
    if settings.LLM_PROVIDER == "openai":
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.embeddings.create(model="text-embedding-3-small", input=text)
        return response.data[0].embedding
    else:
        # Anthropic은 자체 임베딩 미지원 → OpenAI 임베딩 또는 로컬 모델 사용
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.embeddings.create(model="text-embedding-3-small", input=text)
        return response.data[0].embedding
