"""
OCR 파서 단위 테스트

Stage 1(정규식) 케이스:
- 처방전 기본 파싱 (ICD, 날짜, 진단명, 병원명, 진료과, 약품)
- 진료비 영수증 파싱 (총액, 본인부담금)
- 비급여 약품 플래그
- 약품 용량/일수 추출
- 빈 텍스트 방어

Stage 2(비동기 LLM 폴백) 케이스:
- 핵심 필드 누락 시 LLM 보완 확인
"""
import pytest
from unittest.mock import AsyncMock, patch
from app.services.ocr.parser import (
    parse_medical_document,
    parse_medical_document_async,
    _needs_llm_fallback,
)


# ── 샘플 OCR 텍스트 ────────────────────────────────────────────────────────────

SAMPLE_PRESCRIPTION = """
서울내과의원
진료일: 2024-03-15
진료과: 내과
상병코드: J06.9
진단명: 급성상기도감염
처방의약품
아목시실린캡슐 500mg 3정/일 5일
타이레놀정 500mg 2정/일 3일
본인부담금: 18,500원
"""

SAMPLE_RECEIPT = """
강남정형외과의원
진료과: 정형외과
진단명: 요추 추간판 탈출증
상병코드: M51.1
진료일: 2024-05-20
진료비 내역
급여 진찰료 15,000
급여 물리치료 8,000
비급여 도수치료 80,000
합계: 103,000원
본인부담금: 30,000원
"""

SAMPLE_NONBENEFIT = """
강남피부과
진료일: 2024-03-20
진료과: 피부과
처방의약품
레티놀크림 0.1% 비급여 1개
히알루론산겔 5mL 비보험
"""

SAMPLE_PEDIATRIC = """
행복어린이의원
진료일: 2025-01-10
진료과: 소아청소년과
상병코드: J02.9
진단명: 급성인두염
처방의약품
세티리진시럽 5mg/5mL 1회 5mL 5일
부루펜시럽 200mg/5mL 1회 5mL 4일
본인부담금 8,200원
"""

SAMPLE_MINIMAL = """
홍길동내과
J45.9
2024-06-01
살부타몰흡입액 2.5mg
"""

SAMPLE_EMPTY = ""

# ── Stage 1: 정규식 기반 테스트 ────────────────────────────────────────────────

class TestRegexParser:

    def test_parse_icd_code(self):
        result = parse_medical_document(SAMPLE_PRESCRIPTION)
        assert result.icd_code == "J06.9"

    def test_parse_prescription_date(self):
        result = parse_medical_document(SAMPLE_PRESCRIPTION)
        assert result.prescription_date == "2024-03-15"

    def test_parse_diagnosis(self):
        result = parse_medical_document(SAMPLE_PRESCRIPTION)
        assert result.diagnosis is not None
        assert "상기도감염" in result.diagnosis or "급성" in result.diagnosis

    def test_parse_hospital(self):
        result = parse_medical_document(SAMPLE_PRESCRIPTION)
        assert result.hospital is not None
        assert "내과의원" in result.hospital or "서울" in result.hospital

    def test_parse_department(self):
        result = parse_medical_document(SAMPLE_PRESCRIPTION)
        assert result.department is not None
        assert "내과" in result.department

    def test_parse_total_amount_from_receipt(self):
        result = parse_medical_document(SAMPLE_RECEIPT)
        assert result.total_amount is not None
        # 본인부담금 30,000 또는 합계 103,000 중 최댓값
        assert result.total_amount >= 30000

    def test_parse_drugs_basic(self):
        result = parse_medical_document(SAMPLE_PRESCRIPTION)
        assert len(result.drugs) >= 1
        drug_names = [d.name for d in result.drugs]
        assert any("아목시실린" in n or "타이레놀" in n for n in drug_names)

    def test_parse_drug_dosage(self):
        result = parse_medical_document(SAMPLE_PRESCRIPTION)
        drugs_with_dosage = [d for d in result.drugs if d.dosage]
        assert len(drugs_with_dosage) >= 1
        assert "mg" in drugs_with_dosage[0].dosage

    def test_parse_drug_days(self):
        result = parse_medical_document(SAMPLE_PRESCRIPTION)
        drugs_with_days = [d for d in result.drugs if d.days]
        assert len(drugs_with_days) >= 1
        assert drugs_with_days[0].days in (3, 5)

    def test_nonbenefit_drug_flag(self):
        result = parse_medical_document(SAMPLE_NONBENEFIT)
        nonbenefit = [d for d in result.drugs if d.is_nonbenefit]
        assert len(nonbenefit) >= 1

    def test_parse_pediatric(self):
        result = parse_medical_document(SAMPLE_PEDIATRIC)
        assert result.icd_code == "J02.9"
        assert result.hospital is not None
        assert result.department is not None
        assert len(result.drugs) >= 1

    def test_parse_minimal(self):
        """필드 일부만 있어도 오류 없이 동작해야 함."""
        result = parse_medical_document(SAMPLE_MINIMAL)
        assert result.icd_code == "J45.9"
        assert result.prescription_date is not None

    def test_empty_text(self):
        result = parse_medical_document(SAMPLE_EMPTY)
        assert result.icd_code is None
        assert result.drugs == []
        assert result.hospital is None
        assert result.total_amount is None

    def test_needs_llm_fallback_true(self):
        """병원명·진단명·총액 모두 없으면 LLM 필요."""
        result = parse_medical_document("J06.9\n2024-01-01\n")
        assert _needs_llm_fallback(result) is True

    def test_needs_llm_fallback_false(self):
        """풍부한 텍스트면 LLM 불필요."""
        result = parse_medical_document(SAMPLE_PRESCRIPTION)
        assert _needs_llm_fallback(result) is False


# ── Stage 2: LLM 폴백 테스트 ─────────────────────────────────────────────────

class TestLLMFallback:

    @pytest.mark.asyncio
    async def test_llm_fallback_triggered_on_missing_fields(self):
        """핵심 필드 누락 시 LLM 폴백이 호출되어야 한다."""
        minimal_text = "J18.9\n2024-01-01\n아목시실린정 500mg"
        mock_llm_result = {
            "hospital": "행복의원",
            "department": "내과",
            "diagnosis": "폐렴",
            "icd_code": "J18.9",
            "prescription_date": "2024-01-01",
            "total_amount": 45000,
            "drugs": [{"name": "아목시실린정 500mg", "dosage": "500mg",
                       "days": 7, "is_nonbenefit": False}],
        }

        with patch(
            "app.services.ocr.parser._llm_parse",
            new_callable=AsyncMock,
            return_value=mock_llm_result,
        ):
            result = await parse_medical_document_async(minimal_text)

        assert result.hospital == "행복의원"
        assert result.diagnosis == "폐렴"
        assert result.total_amount == 45000

    @pytest.mark.asyncio
    async def test_llm_not_triggered_when_regex_sufficient(self):
        """정규식이 충분하면 LLM이 호출되지 않아야 한다."""
        with patch(
            "app.services.ocr.parser._llm_parse",
            new_callable=AsyncMock,
        ) as mock_llm:
            await parse_medical_document_async(SAMPLE_PRESCRIPTION)

        mock_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_regex_takes_precedence_over_llm(self):
        """정규식 추출 값이 있으면 LLM 값을 무시해야 한다."""
        mock_llm_result = {
            "hospital": "LLM가짜병원",  # 정규식이 이미 잡은 값과 다름
            "diagnosis": None,
            "total_amount": 99999,
        }
        with patch(
            "app.services.ocr.parser._llm_parse",
            new_callable=AsyncMock,
            return_value=mock_llm_result,
        ):
            result = await parse_medical_document_async(SAMPLE_PRESCRIPTION)

        # 정규식으로 잡힌 hospital이 그대로여야 함
        assert result.hospital != "LLM가짜병원"

    @pytest.mark.asyncio
    async def test_empty_text_async(self):
        result = await parse_medical_document_async("")
        assert result.icd_code is None
        assert result.drugs == []
