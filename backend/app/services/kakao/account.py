"""
카카오톡 사용자 ↔ InsurRX 회원 연결

- 카카오 전용 회원: 카톡에서 처음 보험증권을 등록할 때 자동 생성 (웹 로그인 불가)
- 계정 연결: 웹 대시보드에서 발급한 1회용 코드를 카톡에서 '연결 <코드>'로 입력
  → 카카오 전용 회원의 보험증권·분석 이력을 웹 회원으로 옮기고 전용 회원은 삭제
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.analysis_result import AnalysisResult
from app.models.kakao_link_code import KakaoLinkCode
from app.models.kakao_session import KakaoSession
from app.models.user import User
from app.models.user_policy import UserPolicy

LINK_CODE_EXPIRE_MINUTES = 10
LINK_CODE_LENGTH         = 8
# 혼동되는 글자(0/O, 1/I/L) 제외
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

# 카카오 전용 회원 식별용 이메일 도메인 (실제 메일 수신 없음)
KAKAO_EMAIL_DOMAIN = "kakao.song2nes.com"


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def normalize_link_code(raw: str) -> str:
    return "".join(ch for ch in raw.upper() if ch.isalnum())


def is_kakao_only_user(user: User) -> bool:
    return user.email.endswith("@" + KAKAO_EMAIL_DOMAIN)


async def get_or_create_kakao_user(db: AsyncSession, session: KakaoSession) -> User:
    """세션에 연결된 회원을 반환. 없으면 카카오 전용 회원을 만들어 연결합니다."""
    if session.user_id:
        user = await db.get(User, session.user_id)
        if user and user.is_active:
            return user

    user = User(
        email=f"kakao-{_hash(session.kakao_user_id)[:20]}@{KAKAO_EMAIL_DOMAIN}",
        name="카카오 사용자",
        # 사용할 수 없는 임의 비밀번호 — 웹 로그인은 계정 연결 후 웹 계정으로
        password_hash=hash_password(secrets.token_urlsafe(32)),
    )
    db.add(user)
    await db.flush()
    session.user_id = user.id
    return user


async def issue_link_code(db: AsyncSession, user_id: int) -> str:
    """웹 회원용 1회용 연결 코드 발급. 원문 반환, DB엔 해시만 저장."""
    code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(LINK_CODE_LENGTH))
    db.add(KakaoLinkCode(
        user_id=user_id,
        code_hash=_hash(code),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=LINK_CODE_EXPIRE_MINUTES),
    ))
    await db.commit()
    return code


async def link_kakao_account(db: AsyncSession, session: KakaoSession, raw_code: str) -> User | None:
    """연결 코드 검증 후 카카오 세션을 웹 회원에 연결. 실패 시 None."""
    result = await db.execute(
        select(KakaoLinkCode).where(
            KakaoLinkCode.code_hash == _hash(normalize_link_code(raw_code)),
            KakaoLinkCode.is_used == False,  # noqa: E712
            KakaoLinkCode.expires_at > datetime.now(timezone.utc),
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        return None

    target = await db.get(User, link.user_id)
    if not target or not target.is_active:
        return None

    link.is_used = True

    # 기존 카카오 전용 회원의 데이터를 웹 회원으로 이전
    if session.user_id and session.user_id != target.id:
        old = await db.get(User, session.user_id)
        if old and is_kakao_only_user(old):
            await db.execute(
                update(UserPolicy).where(UserPolicy.user_id == old.id).values(user_id=target.id)
            )
            await db.execute(
                update(AnalysisResult).where(AnalysisResult.user_id == old.id).values(user_id=target.id)
            )
            await db.delete(old)

    session.user_id = target.id
    await db.commit()
    return target
