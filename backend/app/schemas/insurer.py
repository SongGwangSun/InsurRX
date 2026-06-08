from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class InsurerCreate(BaseModel):
    name: str
    code: str
    logo_url: Optional[str] = None


class InsurerUpdate(BaseModel):
    name: Optional[str] = None
    logo_url: Optional[str] = None
    is_active: Optional[bool] = None


class InsurerResponse(BaseModel):
    id: int
    name: str
    code: str
    logo_url: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductCreate(BaseModel):
    name: str
    product_code: str
    product_type: str
    description: Optional[str] = None
    vector_policy_id: Optional[str] = None   # Pinecone policy_id


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    product_code: Optional[str] = None
    product_type: Optional[str] = None
    description: Optional[str] = None
    vector_policy_id: Optional[str] = None
    is_active: Optional[bool] = None


class ProductResponse(BaseModel):
    id: int
    insurer_id: int
    name: str
    product_code: str
    product_type: str
    description: Optional[str]
    vector_policy_id: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class InsurerWithProducts(InsurerResponse):
    products: List[ProductResponse] = []
