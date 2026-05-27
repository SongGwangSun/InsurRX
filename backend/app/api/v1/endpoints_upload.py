import logging
from fastapi import APIRouter, UploadFile, File, HTTPException
from openai import APIError as OpenAIAPIError, APITimeoutError, APIConnectionError
from app.schemas.upload import UploadResponse
from app.services.ocr.clova_ocr import run_ocr
from app.services.ocr.parser import parse_medical_document_async

router = APIRouter()
logger = logging.getLogger(__name__)

# GPT-4o Vision이 처리 가능한 MIME 타입
ALLOWED_TYPES = {
    "image/jpeg", "image/jpg", "image/png", "image/webp",
    "image/heic", "image/heif", "image/gif", "image/bmp",
    "image/tiff", "application/pdf",
}


@router.post("/", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """처방전/영수증 이미지 업로드 → GPT-4o Vision OCR → 파싱 결과 반환."""
    content_type = (file.content_type or "image/jpeg").lower()

    # content_type이 없거나 octet-stream이면 확장자로 추정
    if content_type in ("application/octet-stream", ""):
        ext = (file.filename or "").rsplit(".", 1)[-1].lower()
        ext_map = {
            "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png",  "webp": "image/webp",
            "heic": "image/heic", "pdf": "application/pdf",
        }
        content_type = ext_map.get(ext, "image/jpeg")

    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다. (받은 타입: {content_type})"
        )

    image_bytes = await file.read()
    logger.info("업로드: %s %s %dB", file.filename, content_type, len(image_bytes))

    try:
        raw_text = await run_ocr(image_bytes, content_type=content_type)
    except APITimeoutError:
        raise HTTPException(status_code=503, detail="OCR 요청 시간 초과. 잠시 후 다시 시도해주세요.")
    except APIConnectionError as e:
        raise HTTPException(status_code=503, detail=f"OCR 서버 연결 실패: {e}")
    except OpenAIAPIError as e:
        raise HTTPException(status_code=502, detail=f"OCR API 오류 ({e.status_code}): {e.message}")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("OCR 처리 중 예외")
        raise HTTPException(status_code=502, detail=f"OCR 처리 실패: {type(e).__name__}: {e}")

    parsed = await parse_medical_document_async(raw_text)
    return UploadResponse(
        filename=file.filename or "upload",
        ocr_raw=raw_text,
        parsed=parsed,
    )
