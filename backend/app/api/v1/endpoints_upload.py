from fastapi import APIRouter, UploadFile, File, HTTPException
from app.schemas.upload import UploadResponse
from app.services.ocr.clova_ocr import run_ocr
from app.services.ocr.parser import parse_medical_document_async

router = APIRouter()

# Clova OCR이 처리 가능한 MIME 타입 (HEIC/HEIF는 jpg로 변환 전달)
ALLOWED_TYPES = {
    "image/jpeg", "image/jpg", "image/png", "image/webp",
    "image/heic", "image/heif", "image/gif", "image/bmp",
    "image/tiff", "application/pdf",
}


@router.post("/", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """처방전/영수증 이미지 업로드 → Clova OCR → 파싱 결과 반환."""
    content_type = (file.content_type or "image/jpeg").lower()
    # content_type이 없거나 octet-stream이면 확장자로 추정
    if content_type in ("application/octet-stream", ""):
        ext = (file.filename or "").rsplit(".", 1)[-1].lower()
        ext_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                   "webp": "image/webp", "heic": "image/heic", "pdf": "application/pdf"}
        content_type = ext_map.get(ext, "image/jpeg")

    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다. (받은 타입: {content_type})"
        )

    image_bytes = await file.read()
    raw_text = await run_ocr(image_bytes, content_type=content_type)
    parsed = await parse_medical_document_async(raw_text)

    return UploadResponse(filename=file.filename or "upload", ocr_raw=raw_text, parsed=parsed)
