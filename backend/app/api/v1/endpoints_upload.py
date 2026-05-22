from fastapi import APIRouter, UploadFile, File, HTTPException
from app.schemas.upload import UploadResponse
from app.services.ocr.clova_ocr import run_ocr
from app.services.ocr.parser import parse_medical_document

router = APIRouter()


@router.post("/", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """처방전/영수증 이미지 업로드 → OCR → 파싱 결과 반환. 이미지는 30초 후 자동 삭제."""
    allowed_types = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="지원하지 않는 파일 형식입니다.")

    image_bytes = await file.read()
    raw_text = await run_ocr(image_bytes)
    parsed = parse_medical_document(raw_text)

    return UploadResponse(filename=file.filename, ocr_raw=raw_text, parsed=parsed)
