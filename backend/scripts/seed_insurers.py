"""
보험사 및 상품 초기 데이터 시드 스크립트
사용법: cd backend && python -m scripts.seed_insurers

이미 존재하는 항목은 건너뛰고 신규만 추가합니다 (idempotent).
"""
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import AsyncSessionLocal, create_tables
from app.models.insurer import Insurer, InsuranceProduct
import app.models.waitlist        # noqa – Base.metadata 등록
import app.models.analysis_result # noqa
import app.models.user            # noqa
import app.models.user_policy     # noqa

SEED_DATA = [
    {
        "name": "현대해상",
        "code": "hyundai",
        "products": [
            {"name": "실손의료보험 Hi2204",     "product_code": "Hi2204", "product_type": "실손",   "description": "현대해상 표준형 실손의료비 4세대"},
            {"name": "암보험 Hi2401",           "product_code": "Hi2401", "product_type": "암",     "description": "현대해상 정액형 암보험"},
            {"name": "어린이보험 굿앤굿",        "product_code": "GNG2301","product_type": "어린이", "description": "0~30세 어린이·청소년 종합보험"},
        ],
    },
    {
        "name": "삼성화재",
        "code": "samsung",
        "products": [
            {"name": "My 아이플러스",            "product_code": "MYK2301","product_type": "어린이", "description": "삼성화재 어린이 종합보험"},
            {"name": "실손의료비보험 4세대",      "product_code": "SM4GEN", "product_type": "실손",   "description": "삼성화재 4세대 실손의료비"},
        ],
    },
    {
        "name": "AXA손해보험",
        "code": "axa",
        "products": [
            {"name": "치아보험 갱신형 2501",     "product_code": "AXA2501","product_type": "치아",   "description": "스케일링·충치치료·보철 보장"},
        ],
    },
    {
        "name": "DB손해보험",
        "code": "db",
        "products": [
            {"name": "프로미라이프 실손",         "product_code": "DBL2401","product_type": "실손",   "description": "DB손해보험 4세대 실손의료비"},
            {"name": "암보험 프로미",             "product_code": "DBC2301","product_type": "암",     "description": "DB손해보험 암진단 정액형"},
        ],
    },
    {
        "name": "KB손해보험",
        "code": "kb",
        "products": [
            {"name": "KB골든라이프 실손",         "product_code": "KBL2401","product_type": "실손",   "description": "KB손해보험 실손의료비"},
        ],
    },
    {
        "name": "메리츠화재",
        "code": "meritz",
        "products": [
            {"name": "메리츠 실손의료비",         "product_code": "MRZ4GEN","product_type": "실손",   "description": "메리츠 4세대 실손의료비"},
            {"name": "어린이보험 굿모닝",         "product_code": "MRZK23", "product_type": "어린이", "description": "메리츠 어린이 종합보험"},
        ],
    },
]


async def seed():
    await create_tables()
    async with AsyncSessionLocal() as db:
        total_ins = 0; total_prod = 0
        for ins_data in SEED_DATA:
            products = ins_data.pop("products")

            # 보험사 존재 여부 확인
            result = await db.execute(select(Insurer).where(Insurer.code == ins_data["code"]))
            insurer = result.scalar_one_or_none()
            if not insurer:
                insurer = Insurer(**ins_data)
                db.add(insurer)
                await db.flush()  # ID 확보
                total_ins += 1
                print(f"  ✅ 보험사 추가: {insurer.name}")
            else:
                print(f"  ⏭  보험사 이미 존재: {insurer.name}")

            # 상품 추가
            for prod_data in products:
                existing = await db.execute(
                    select(InsuranceProduct).where(
                        InsuranceProduct.insurer_id == insurer.id,
                        InsuranceProduct.product_code == prod_data["product_code"],
                    )
                )
                if existing.scalar_one_or_none():
                    print(f"      ⏭  상품 이미 존재: {prod_data['name']}")
                    continue
                prod = InsuranceProduct(insurer_id=insurer.id, **prod_data)
                db.add(prod)
                total_prod += 1
                print(f"      ➕ 상품 추가: {prod_data['name']}")

            ins_data["products"] = products  # 원상복구

        await db.commit()
        print(f"\n완료: 보험사 {total_ins}개, 상품 {total_prod}개 추가")


if __name__ == "__main__":
    asyncio.run(seed())
