import httpx
import uuid
import json
from app.core.config import settings


async def run_ocr(image_bytes: bytes) -> str:
    """Clova OCR API 호출. 추출된 전체 텍스트를 반환합니다."""
    request_json = {
        "images": [{"format": "jpg", "name": "document"}],
        "requestId": str(uuid.uuid4()),
        "version": "V2",
        "timestamp": 0,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            settings.CLOVA_OCR_API_URL,
            headers={"X-OCR-SECRET": settings.CLOVA_OCR_SECRET_KEY},
            data={"message": json.dumps(request_json)},
            files={"file": ("document.jpg", image_bytes, "image/jpeg")},
        )
        response.raise_for_status()

    data = response.json()
    texts = [
        field.get("inferText", "")
        for image in data.get("images", [])
        for field in image.get("fields", [])
    ]
    return "\n".join(texts)
