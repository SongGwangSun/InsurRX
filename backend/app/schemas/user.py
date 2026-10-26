from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    refresh_token: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class UserUpdate(BaseModel):
    name: str | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class ForgotPasswordRequest(BaseModel):
    """재설정 메일 발송 요청 (1단계)."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """메일 링크 토큰으로 새 비밀번호 설정 (2단계)."""
    token: str
    new_password: str


class LoginHistoryResponse(BaseModel):
    id: int
    ip_address: str | None
    user_agent: str | None
    device_type: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminUserResponse(UserResponse):
    is_active: bool
    policy_count: int = 0
    analysis_count: int = 0
