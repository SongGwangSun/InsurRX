import httpx
import uuid
import json
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


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

    # http:// → https:// 자동 교정 (Clova API는 HTTPS 필수)
    api_url = settings.CLOVA_OCR_API_URL
    if api_url.startswith("http://"):
        api_url = "https://" + api_url[7:]
        logger.warning("CLOVA_OCR_API_URL을 http→https로 자동 교정: %s", api_url)

    logger.info("Clova OCR 호출: url=%s fmt=%s size=%dB", api_url, fmt, len(image_bytes))

    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
        response = await client.post(
            api_url,
            headers={"X-OCR-SECRET": settings.CLOVA_OCR_SECRET_KEY},
            data={"message": json.dumps(request_json)},
            files={"file": (f"document.{fmt}", image_bytes, mime)},
        )
        response.raise_for_status()

    data = response.json()

    # 인식 실패 이미지 로그
    for img in data.get("images", []):
        if img.get("inferResult") != "SUCCESS":
            logger.warning("Clova OCR 이미지 인식 실패: %s", img.get("message"))

    texts = [
        field.get("inferText", "")
        for image in data.get("images", [])
        for field in image.get("fields", [])
    ]
    raw_text = "\n".join(texts)
    logger.info("Clova OCR 완료: %d줄 추출", len(texts))
    return raw_text
