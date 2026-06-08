"""
일회성 초기 데이터 설정 엔드포인트.
BOOTSTRAP_SECRET 환경변수가 설정된 경우에만 동작하며,
Header: X-Bootstrap-Key 값이 일치해야 실행됩니다.

Railway 배포 후 1회 호출 → 완료 후 Railway 대시보드에서 BOOTSTRAP_SECRET 삭제.
"""
import os
from fastapi import APIRouter, Header, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.models.insurer import Insurer, InsuranceProduct
from app.core.security import hash_password

router = APIRouter()

SEED_DATA = [
    {
        "name": "현대해상", "code": "hyundai",
        "products": [
            {"name": "실손의료보험 Hi2204",   "product_code": "Hi2204",  "product_type": "실손",   "description": "현대해상 표준형 실손의료비 4세대", "vector_policy_id": "hyundai-silson-v4"},
            {"name": "암보험 Hi2401",         "product_code": "Hi2401",  "product_type": "암",     "description": "현대해상 정액형 암보험",           "vector_policy_id": "hyundai-cancer-2401"},
            {"name": "어린이보험 굿앤굿",      "product_code": "GNG2301", "product_type": "어린이", "description": "0~30세 어린이·청소년 종합보험",    "vector_policy_id": None},
        ],
    },
    {
        "name": "삼성화재", "code": "samsung",
        "products": [
            {"name": "My 아이플러스",          "product_code": "MYK2301", "product_type": "어린이", "description": "삼성화재 어린이 종합보험",         "vector_policy_id": "samsung-child-mykids"},
            {"name": "실손의료비보험 4세대",    "product_code": "SM4GEN",  "product_type": "실손",   "description": "삼성화재 4세대 실손의료비",        "vector_policy_id": None},
        ],
    },
    {
        "name": "AXA손해보험", "code": "axa",
        "products": [
            {"name": "치아보험 갱신형 2501",   "product_code": "AXA2501", "product_type": "치아",   "description": "스케일링·충치치료·보철 보장",     "vector_policy_id": "axa-dental-2501"},
        ],
    },
    {
        "name": "DB손해보험", "code": "db",
        "products": [
            {"name": "프로미라이프 실손",       "product_code": "DBL2401", "product_type": "실손",   "description": "DB손해보험 4세대 실손의료비",     "vector_policy_id": None},
            {"name": "암보험 프로미",           "product_code": "DBC2301", "product_type": "암",     "description": "DB손해보험 암진단 정액형",        "vector_policy_id": None},
        ],
    },
    {
        "name": "KB손해보험", "code": "kb",
        "products": [
            {"name": "KB골든라이프 실손",       "product_code": "KBL2401", "product_type": "실손",   "description": "KB손해보험 실손의료비",           "vector_policy_id": None},
        ],
    },
    {
        "name": "메리츠화재", "code": "meritz",
        "products": [
            {"name": "메리츠 실손의료비",       "product_code": "MRZ4GEN", "product_type": "실손",   "description": "메리츠 4세대 실손의료비",         "vector_policy_id": None},
            {"name": "어린이보험 굿모닝",       "product_code": "MRZK23",  "product_type": "어린이", "description": "메리츠 어린이 종합보험",          "vector_policy_id": None},
        ],
    },
]


def _check_secret(x_bootstrap_key: str = Header(...)):
    secret = os.getenv("BOOTSTRAP_SECRET", "")
    if not secret:
        raise HTTPException(503, detail="BOOTSTRAP_SECRET 환경변수가 설정되지 않았습니다.")
    if x_bootstrap_key != secret:
        raise HTTPException(403, detail="잘못된 Bootstrap 키입니다.")


@router.post("/")
async def bootstrap(
    admin_email:    str = "songgs33@gmail.com",
    admin_name:     str = "관리자",
    admin_password: str = "InsurRX2026!",
    db: AsyncSession = Depends(get_db),
    _=Depends(_check_secret),
):
    """
    관리자 계정 생성 + 보험사·상품 시드 데이터 삽입 (idempotent).

    Query params:
      admin_email    — 관리자 이메일 (기본: songgs33@gmail.com)
      admin_name     — 관리자 이름  (기본: 관리자)
      admin_password — 초기 비밀번호 (기본: InsurRX2026!)
    """
    report = {"admin": None, "insurers_added": 0, "products_added": 0, "products_updated": 0}

    # ── 관리자 계정 ────────────────────────────────────────
    existing_user = await db.execute(select(User).where(User.email == admin_email))
    user = existing_user.scalar_one_or_none()
    if user:
        user.is_admin = True
        report["admin"] = f"기존 계정 '{admin_email}' → 관리자 권한 부여"
    else:
        user = User(
            email=admin_email,
            name=admin_name,
            password_hash=hash_password(admin_password),
            is_active=True,
            is_admin=True,
        )
        db.add(user)
        report["admin"] = f"관리자 계정 생성: {admin_email}"

    # ── 보험사·상품 시드 ────────────────────────────────────
    for ins_data in SEED_DATA:
        products = ins_data.pop("products")

        ins_result = await db.execute(select(Insurer).where(Insurer.code == ins_data["code"]))
        insurer = ins_result.scalar_one_or_none()
        if not insurer:
            insurer = Insurer(**ins_data)
            db.add(insurer)
            await db.flush()
            report["insurers_added"] += 1

        for prod_data in products:
            p_result = await db.execute(
                select(InsuranceProduct).where(
                    InsuranceProduct.insurer_id == insurer.id,
                    InsuranceProduct.product_code == prod_data["product_code"],
                )
            )
            prod = p_result.scalar_one_or_none()
            if prod:
                if prod_data.get("vector_policy_id") and not prod.vector_policy_id:
                    prod.vector_policy_id = prod_data["vector_policy_id"]
                    report["products_updated"] += 1
            else:
                db.add(InsuranceProduct(insurer_id=insurer.id, **prod_data))
                report["products_added"] += 1

        ins_data["products"] = products   # 원상복구

    await db.commit()
    report["message"] = "✅ 초기 설정 완료. Railway 대시보드에서 BOOTSTRAP_SECRET 환경변수를 삭제하세요."
    return report
