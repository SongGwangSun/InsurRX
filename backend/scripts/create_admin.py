"""
관리자 계정 생성 스크립트
사용법: cd backend && python -m scripts.create_admin

환경변수 또는 대화형 입력으로 관리자 계정을 만듭니다.
이미 해당 이메일 계정이 존재하면 is_admin=True 로 업그레이드합니다.
"""
import asyncio
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import select
from app.database import AsyncSessionLocal, create_tables
from app.models.user import User
from app.core.security import hash_password
import app.models.waitlist        # noqa
import app.models.analysis_result # noqa
import app.models.insurer         # noqa
import app.models.user_policy     # noqa


async def create_admin():
    await create_tables()

    # 환경변수 우선 → 없으면 대화형
    email    = os.getenv("ADMIN_EMAIL")    or input("관리자 이메일: ").strip()
    name     = os.getenv("ADMIN_NAME")     or input("관리자 이름: ").strip()
    password = os.getenv("ADMIN_PASSWORD") or getpass.getpass("비밀번호 (6자 이상): ")

    if not email or not name or len(password) < 6:
        print("입력값이 올바르지 않습니다.")
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user:
            user.is_admin = True
            user.name = name
            await db.commit()
            print(f"✅ 기존 계정 '{email}' → 관리자 권한 부여 완료")
        else:
            user = User(
                email=email,
                name=name,
                password_hash=hash_password(password),
                is_active=True,
                is_admin=True,
            )
            db.add(user)
            await db.commit()
            print(f"✅ 관리자 계정 생성 완료: {email}")


if __name__ == "__main__":
    asyncio.run(create_admin())
