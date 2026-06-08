from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    email        = Column(String(255), unique=True, nullable=False, index=True)
    name         = Column(String(100), nullable=False)
    password_hash= Column(String(255), nullable=False)
    is_active    = Column(Boolean, default=True, nullable=False)
    is_admin     = Column(Boolean, default=False, nullable=False)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
