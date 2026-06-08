import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from app.database import get_db
from app.models.user import User
from app.models.user_policy import UserPolicy, PolicyStatus
from app.schemas.user_policy import UserPolicyResponse, UserPolicyUploadResult
from app.core.security import get_current_user

router = APIRouter()

ALLOWED_TYPES = {
    "image/jpeg", "image/jpg", "image/png", "image/webp",
    "application/pdf",
}
MAX_SIZE_MB = 20


@router.post("/upload", response_model=UserPolicyUploadResult, status_code=status.HTTP_202_ACCEPTED)
async def upload_user_policy(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    product_id: Optional[int] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content_type = file.content_type or ""
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(400, detail=f"지원하지 않는 파일 형식입니다: {content_type}. (JPG/PNG/WEBP/PDF 허용)")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(400, detail=f"파일 크기는 {MAX_SIZE_MB}MB 이하여야 합니다.")

    namespace = f"user-{current_user.id}-{uuid.uuid4().hex[:8]}"
    safe_name = f"{uuid.uuid4().hex}{_ext(file.filename or '')}"

    policy = UserPolicy(
        user_id=current_user.id,
        product_id=product_id,
        file_name=safe_name,
        original_name=file.filename or "upload",
        vector_namespace=namespace,
        status=PolicyStatus.pending,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)

    from app.services.user_policy_service import process_user_policy
    from app.database import AsyncSessionLocal

    async def _bg():
        async with AsyncSessionLocal() as bg_db:
            await process_user_policy(bg_db, policy.id, file_bytes, content_type, file.filename or "")

    background_tasks.add_task(_bg)

    return UserPolicyUploadResult(
        policy_id=policy.id,
        original_name=policy.original_name,
        chunk_count=0,
        status=PolicyStatus.pending,
        message="업로드 완료. 벡터 DB 임베딩이 백그라운드에서 진행됩니다.",
    )


@router.get("/", response_model=List[UserPolicyResponse])
async def list_user_policies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(UserPolicy)
        .where(UserPolicy.user_id == current_user.id)
        .order_by(UserPolicy.uploaded_at.desc())
    )
    return result.scalars().all()


@router.get("/{policy_id}", response_model=UserPolicyResponse)
async def get_user_policy(
    policy_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(UserPolicy).where(
            UserPolicy.id == policy_id,
            UserPolicy.user_id == current_user.id,
        )
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(404, detail="보험증권을 찾을 수 없습니다.")
    return policy


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_policy(
    policy_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(UserPolicy).where(
            UserPolicy.id == policy_id,
            UserPolicy.user_id == current_user.id,
        )
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(404, detail="보험증권을 찾을 수 없습니다.")

    # Pinecone 네임스페이스 삭제 (선택적)
    if policy.status == PolicyStatus.ready and settings.PINECONE_API_KEY:
        try:
            from pinecone import Pinecone
            pc = Pinecone(api_key=settings.PINECONE_API_KEY)
            index = pc.Index(settings.PINECONE_INDEX)
            index.delete(delete_all=True, namespace=policy.vector_namespace)
        except Exception:
            pass

    await db.delete(policy)
    await db.commit()


def _ext(filename: str) -> str:
    if "." in filename:
        return "." + filename.rsplit(".", 1)[-1].lower()
    return ""
