from pydantic import BaseModel
from datetime import datetime


class PromptTemplateRead(BaseModel):
    key: str
    name: str
    content: str
    version: int
    is_active: bool
    updated_at: datetime

    model_config = {"from_attributes": True}


class PromptTemplateUpdate(BaseModel):
    name: str | None = None
    content: str
