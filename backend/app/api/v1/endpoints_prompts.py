from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.prompt_template import PromptTemplateRead, PromptTemplateUpdate
from app.services import prompt_service

router = APIRouter(prefix="/prompts", tags=["prompts"])


@router.get("/", response_model=list[PromptTemplateRead])
async def list_prompts(db: AsyncSession = Depends(get_db)):
    """등록된 프롬프트 전체 목록을 반환합니다."""
    return await prompt_service.list_prompts(db)


@router.get("/{key}", response_model=PromptTemplateRead)
async def get_prompt(key: str, db: AsyncSession = Depends(get_db)):
    row = await prompt_service.get_prompt_row(key, db)
    if row is None:
        raise HTTPException(status_code=404, detail=f"프롬프트 키 '{key}'를 찾을 수 없습니다.")
    return row


@router.put("/{key}", response_model=PromptTemplateRead)
async def update_prompt(key: str, body: PromptTemplateUpdate, db: AsyncSession = Depends(get_db)):
    """프롬프트 내용을 수정합니다. 수정 즉시 인메모리 캐시에도 반영됩니다."""
    try:
        return await prompt_service.update_prompt(key, body.name, body.content, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{key}/reset", response_model=PromptTemplateRead)
async def reset_prompt(key: str, db: AsyncSession = Depends(get_db)):
    """프롬프트를 코드 기본값으로 초기화합니다."""
    try:
        return await prompt_service.reset_prompt(key, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
