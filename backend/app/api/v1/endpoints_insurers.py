from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
from app.database import get_db
from app.models.insurer import Insurer, InsuranceProduct
from app.schemas.insurer import (
    InsurerCreate, InsurerUpdate, InsurerResponse, InsurerWithProducts,
    ProductCreate, ProductUpdate, ProductResponse,
)
from app.core.security import get_current_admin, get_current_user

router = APIRouter()


# ── 보험사 CRUD ────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[InsurerWithProducts])
async def list_insurers(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
):
    q = select(Insurer).options(selectinload(Insurer.products))
    if not include_inactive:
        q = q.where(Insurer.is_active == True)
    result = await db.execute(q.order_by(Insurer.name))
    return result.scalars().all()


@router.post("/", response_model=InsurerResponse, status_code=status.HTTP_201_CREATED)
async def create_insurer(
    body: InsurerCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    dup = await db.execute(select(Insurer).where(Insurer.code == body.code))
    if dup.scalar_one_or_none():
        raise HTTPException(400, detail=f"코드 '{body.code}'가 이미 존재합니다.")
    insurer = Insurer(**body.model_dump())
    db.add(insurer)
    await db.commit()
    await db.refresh(insurer)
    return insurer


@router.patch("/{insurer_id}", response_model=InsurerResponse)
async def update_insurer(
    insurer_id: int,
    body: InsurerUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    result = await db.execute(select(Insurer).where(Insurer.id == insurer_id))
    insurer = result.scalar_one_or_none()
    if not insurer:
        raise HTTPException(404, detail="보험사를 찾을 수 없습니다.")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(insurer, field, val)
    await db.commit()
    await db.refresh(insurer)
    return insurer


@router.delete("/{insurer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_insurer(
    insurer_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    result = await db.execute(select(Insurer).where(Insurer.id == insurer_id))
    insurer = result.scalar_one_or_none()
    if not insurer:
        raise HTTPException(404, detail="보험사를 찾을 수 없습니다.")
    await db.delete(insurer)
    await db.commit()


# ── 보험 상품 CRUD ─────────────────────────────────────────────────────────────

@router.get("/{insurer_id}/products", response_model=List[ProductResponse])
async def list_products(
    insurer_id: int,
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
):
    q = select(InsuranceProduct).where(InsuranceProduct.insurer_id == insurer_id)
    if not include_inactive:
        q = q.where(InsuranceProduct.is_active == True)
    result = await db.execute(q.order_by(InsuranceProduct.name))
    return result.scalars().all()


@router.post("/{insurer_id}/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    insurer_id: int,
    body: ProductCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    ins = await db.execute(select(Insurer).where(Insurer.id == insurer_id))
    if not ins.scalar_one_or_none():
        raise HTTPException(404, detail="보험사를 찾을 수 없습니다.")
    product = InsuranceProduct(insurer_id=insurer_id, **body.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


@router.patch("/{insurer_id}/products/{product_id}", response_model=ProductResponse)
async def update_product(
    insurer_id: int,
    product_id: int,
    body: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    result = await db.execute(
        select(InsuranceProduct).where(
            InsuranceProduct.id == product_id,
            InsuranceProduct.insurer_id == insurer_id,
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(404, detail="상품을 찾을 수 없습니다.")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(product, field, val)
    await db.commit()
    await db.refresh(product)
    return product


@router.delete("/{insurer_id}/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    insurer_id: int,
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    result = await db.execute(
        select(InsuranceProduct).where(
            InsuranceProduct.id == product_id,
            InsuranceProduct.insurer_id == insurer_id,
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(404, detail="상품을 찾을 수 없습니다.")
    await db.delete(product)
    await db.commit()
