from datetime import datetime

from pydantic import BaseModel


class InsurerCreate(BaseModel):
    name: str
    code: str
    logo_url: str | None = None


class InsurerUpdate(BaseModel):
    name: str | None = None
    logo_url: str | None = None
    is_active: bool | None = None


class InsurerResponse(BaseModel):
    id: int
    name: str
    code: str
    logo_url: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductCreate(BaseModel):
    name: str
    product_code: str
    product_type: str
    description: str | None = None
    vector_policy_id: str | None = None   # Pinecone policy_id


class ProductUpdate(BaseModel):
    name: str | None = None
    product_code: str | None = None
    product_type: str | None = None
    description: str | None = None
    vector_policy_id: str | None = None
    is_active: bool | None = None


class ProductResponse(BaseModel):
    id: int
    insurer_id: int
    name: str
    product_code: str
    product_type: str
    description: str | None
    vector_policy_id: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class InsurerWithProducts(InsurerResponse):
    products: list[ProductResponse] = []
