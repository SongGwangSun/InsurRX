import httpx
import uuid
import json
from app.core.config import settings


_FMT_MAP = {
    "image/jpeg": "jpg",
    "image/jpg":  "jpg",
    "image/png":  "png",
    "image/webp": "jpg",   # Clova는 webp 미지원 → jpg로 전달
    "image/heic": "jpg",
    "image/heif": "jpg",
    "image/gif":  "gif",
    "image/tiff": "tiff",
    "image/bmp":  "bmp",
    "application/pdf": "pdf",
}


async def run_ocr(image_bytes: bytes, content_type: str = "image/jpeg") -> str:
    """Clova OCR API 호출. 추출된 전체 텍스트를 반환합니다."""
    fmt = _FMT_MAP.get(content_type, "jpg")
    mime = content_type if content_type.startswith("image/") else "image/jpeg"

    request_json = {
        "images": [{"format": fmt, "name": "document"}],
        "requestId": str(uuid.uuid4()),
        "version": "V2",
        "timestamp": 0,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            settings.CLOVA_OCR_API_URL,
            headers={"X-OCR-SECRET": settings.CLOVA_OCR_SECRET_KEY},
            data={"message": json.dumps(request_json)},
            files={"file": (f"document.{fmt}", image_bytes, mime)},
        )
        response.raise_for_status()

    data = response.json()
    texts = [
        field.get("inferText", "")
        for image in data.get("images", [])
        for field in image.get("fields", [])
    ]
    return "\n".join(texts)
