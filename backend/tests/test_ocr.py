import pytest
from app.services.ocr.parser import parse_medical_document


SAMPLE_PRESCRIPTION = """
서울내과의원
진료일: 2024-03-15
상병코드: J06.9
진단명: 급성상기도감염
처방의약품
아목시실린캡슐 500mg 3정/일 5일
타이레놀정 500mg 2정/일 3일
"""

SAMPLE_NONBENEFIT = """
강남피부과
진료일: 2024-03-20
처방의약품
레티놀크림 0.1% 비급여 1개
"""


def test_parse_icd_code():
    result = parse_medical_document(SAMPLE_PRESCRIPTION)
    assert result.icd_code == "J06.9"


def test_parse_prescription_date():
    result = parse_medical_document(SAMPLE_PRESCRIPTION)
    assert result.prescription_date == "2024-03-15"


def test_parse_drugs():
    result = parse_medical_document(SAMPLE_PRESCRIPTION)
    assert len(result.drugs) >= 1
    drug_names = [d.name for d in result.drugs]
    assert any("아목시실린" in name or "타이레놀" in name for name in drug_names)


def test_nonbenefit_drug_flag():
    result = parse_medical_document(SAMPLE_NONBENEFIT)
    nonbenefit_drugs = [d for d in result.drugs if d.is_nonbenefit]
    assert len(nonbenefit_drugs) >= 1


def test_empty_text():
    result = parse_medical_document("")
    assert result.icd_code is None
    assert result.drugs == []
