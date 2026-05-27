import httpx
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.schemas.upload import UploadResponse
from app.services.ocr.clova_ocr import run_ocr
from app.services.ocr.parser import parse_medical_document_async

logger = logging.getLogger(__name__)

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

    try:
        raw_text = await run_ocr(image_bytes, content_type=content_type)
    except httpx.ConnectTimeout:
        raise HTTPException(
            status_code=503,
            detail="CLOVA_OCR_CONNECT_TIMEOUT: Clova OCR 서버 연결 시간 초과. "
                   "NCP 콘솔 → CLOVA OCR → API 설정에서 IP 허용 목록을 확인하세요."
        )
    except httpx.ConnectError as e:
        raise HTTPException(
            status_code=503,
            detail=f"CLOVA_OCR_CONNECT_ERROR: {e}. API URL 또는 네트워크 설정을 확인하세요."
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"CLOVA_OCR_HTTP_{e.response.status_code}: {e.response.text[:300]}"
        )
    except Exception as e:
        logger.exception("OCR 처리 중 예외 발생")
        raise HTTPException(status_code=502, detail=f"OCR_ERROR: {type(e).__name__}: {e}")

    parsed = await parse_medical_document_async(raw_text)
    return UploadResponse(filename=file.filename or "upload", ocr_raw=raw_text, parsed=parsed)
