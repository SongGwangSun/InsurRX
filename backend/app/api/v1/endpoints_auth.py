from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.database import get_db
from app.models.user import User
from app.models.login_history import LoginHistory
from app.schemas.user import (
    UserCreate, UserResponse, Token, UserUpdate, PasswordChange,
    RefreshRequest, LogoutRequest, LoginHistoryResponse,
)
from app.core.security import (
    hash_password, verify_password, create_access_token,
    get_current_user, issue_refresh_token, rotate_refresh_token,
    revoke_refresh_token, record_login,
)

router = APIRouter()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate, request: Request, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="이미 등록된 이메일입니다.")

    user = User(
        email=body.email,
        name=body.name,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    ip = _client_ip(request)
    ua = request.headers.get("User-Agent")
    await record_login(db, status="success", user_id=user.id, email=user.email, ip_address=ip, user_agent=ua)

    access_token = create_access_token(user.id, user.is_admin)
    refresh_token = await issue_refresh_token(user.id, remember_me=True, db=db)
    return Token(access_token=access_token, refresh_token=refresh_token, user=UserResponse.model_validate(user))


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    remember_me: bool = Query(default=False, description="로그인 상태 유지 (30일)"),
    db: AsyncSession = Depends(get_db),
):
    ip = _client_ip(request)
    ua = request.headers.get("User-Agent")

    result = await db.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form.password, user.password_hash):
        await record_login(db, status="failed", email=form.username, ip_address=ip, user_agent=ua)
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다.")
    if not user.is_active:
        await record_login(db, status="failed", user_id=user.id, email=user.email, ip_address=ip, user_agent=ua)
        raise HTTPException(status_code=403, detail="비활성화된 계정입니다.")

    await record_login(db, status="success", user_id=user.id, email=user.email, ip_address=ip, user_agent=ua)

    access_token = create_access_token(user.id, user.is_admin)
    refresh_token = await issue_refresh_token(user.id, remember_me=remember_me, db=db)
    return Token(access_token=access_token, refresh_token=refresh_token, user=UserResponse.model_validate(user))


@router.post("/refresh", response_model=Token)
async def refresh_token_endpoint(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    user, new_refresh = await rotate_refresh_token(body.refresh_token, db)
    if not user:
        raise HTTPException(status_code=401, detail="Refresh token이 유효하지 않거나 만료되었습니다.")

    access_token = create_access_token(user.id, user.is_admin)
    return Token(access_token=access_token, refresh_token=new_refresh, user=UserResponse.model_validate(user))


@router.post("/logout", status_code=200)
async def logout(body: LogoutRequest, db: AsyncSession = Depends(get_db)):
    if body.refresh_token:
        await revoke_refresh_token(body.refresh_token, db)
    return {"message": "로그아웃 되었습니다."}


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.name:
        current_user.name = body.name
    await db.commit()
    await db.refresh(current_user)
    return UserResponse.model_validate(current_user)


@router.post("/me/change-password", status_code=200)
async def change_password(
    body: PasswordChange,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="현재 비밀번호가 올바르지 않습니다.")
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="새 비밀번호는 6자 이상이어야 합니다.")
    current_user.password_hash = hash_password(body.new_password)
    await db.commit()
    return {"message": "비밀번호가 변경되었습니다."}


@router.get("/login-history", response_model=List[LoginHistoryResponse])
async def login_history(
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(LoginHistory)
        .where(LoginHistory.user_id == current_user.id)
        .order_by(desc(LoginHistory.created_at))
        .limit(limit)
    )
    return result.scalars().all()
