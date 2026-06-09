import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: int, is_admin: bool = False) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "admin": is_admin, "exp": expire},
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


# ── Refresh Token ────────────────────────────────────────────────────────────

def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def issue_refresh_token(user_id: int, remember_me: bool, db: AsyncSession) -> str:
    from app.models.refresh_token import RefreshToken

    raw = secrets.token_hex(32)
    days = settings.REFRESH_TOKEN_EXPIRE_DAYS if remember_me else settings.REFRESH_TOKEN_SHORT_DAYS
    rt = RefreshToken(
        user_id=user_id,
        token_hash=_hash_token(raw),
        expires_at=datetime.now(timezone.utc) + timedelta(days=days),
    )
    db.add(rt)
    await db.commit()
    return raw


async def rotate_refresh_token(raw_token: str, db: AsyncSession):
    """검증 후 새 Refresh Token 반환 (rotation). 실패 시 (None, None)."""
    from app.models.refresh_token import RefreshToken
    from app.models.user import User

    token_hash = _hash_token(raw_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.is_revoked == False,
            RefreshToken.expires_at > datetime.now(timezone.utc),
        )
    )
    rt = result.scalar_one_or_none()
    if not rt:
        return None, None

    user_result = await db.execute(select(User).where(User.id == rt.user_id))
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        rt.is_revoked = True
        await db.commit()
        return None, None

    # 기존 토큰 폐기 후 새 토큰 발급 (rotation)
    rt.is_revoked = True
    new_raw = secrets.token_hex(32)
    new_rt = RefreshToken(
        user_id=user.id,
        token_hash=_hash_token(new_raw),
        expires_at=rt.expires_at,   # 만료 시각 유지
    )
    db.add(new_rt)
    await db.commit()
    return user, new_raw


async def revoke_refresh_token(raw_token: str, db: AsyncSession) -> bool:
    from app.models.refresh_token import RefreshToken

    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == _hash_token(raw_token))
    )
    rt = result.scalar_one_or_none()
    if rt:
        rt.is_revoked = True
        await db.commit()
        return True
    return False


# ── User Agent 파싱 ──────────────────────────────────────────────────────────

def detect_device(user_agent: Optional[str]) -> str:
    if not user_agent:
        return "Unknown"
    ua = user_agent.lower()
    if any(k in ua for k in ("mobile", "android", "iphone", "ipad")):
        return "Mobile"
    if any(k in ua for k in ("windows", "macintosh", "linux", "x11")):
        return "Desktop"
    return "Other"


# ── 로그인 이력 기록 ─────────────────────────────────────────────────────────

async def record_login(
    db: AsyncSession,
    status: str,
    user_id: Optional[int] = None,
    email: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    from app.models.login_history import LoginHistory

    record = LoginHistory(
        user_id=user_id,
        email=email,
        ip_address=ip_address,
        user_agent=user_agent,
        device_type=detect_device(user_agent),
        status=status,
    )
    db.add(record)
    await db.commit()


# ── JWT 인증 의존성 ──────────────────────────────────────────────────────────

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    from app.models.user import User

    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증 정보가 유효하지 않습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exc
    return user


async def get_current_admin(current_user=Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자 권한이 필요합니다.")
    return current_user


_optional_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_optional_user(
    token: Optional[str] = Depends(_optional_scheme),
    db: AsyncSession = Depends(get_db),
):
    if not token:
        return None
    try:
        return await get_current_user(token=token, db=db)
    except HTTPException:
        return None
