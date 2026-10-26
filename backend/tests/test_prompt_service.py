"""프롬프트 시드: 손대지 않은 예전 기본값만 새 기본값으로 갱신되는지 확인."""
import pytest
from sqlalchemy import select

from app.database import get_db
from app.main import app
from app.models.prompt_template import PromptTemplate
from app.services import prompt_service


async def _session():
    gen = app.dependency_overrides[get_db]()
    return gen, await gen.__anext__()


@pytest.mark.asyncio
async def test_legacy_default_prompt_is_upgraded():
    gen, db = await _session()
    old = prompt_service.LEGACY_DEFAULTS["rag_system"][0]
    db.add(PromptTemplate(key="rag_system", name="old", content=old))
    await db.commit()

    await prompt_service.seed_and_load(db)

    row = (await db.execute(select(PromptTemplate).where(PromptTemplate.key == "rag_system"))).scalar_one()
    assert row.content == prompt_service.DEFAULT_PROMPTS["rag_system"]["content"]
    assert "표준약관" in prompt_service.get_prompt("rag_system")
    await gen.aclose()


@pytest.mark.asyncio
async def test_admin_edited_prompt_is_kept():
    gen, db = await _session()
    db.add(PromptTemplate(key="rag_system", name="custom", content="관리자가 고친 프롬프트"))
    await db.commit()

    await prompt_service.seed_and_load(db)

    row = (await db.execute(select(PromptTemplate).where(PromptTemplate.key == "rag_system"))).scalar_one()
    assert row.content == "관리자가 고친 프롬프트"
    await gen.aclose()
