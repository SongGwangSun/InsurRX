"""JSON 키워드 사전 기반 환자명·병원명 인식 테스트"""
from app.services.ocr.parser import parse_medical_document


def _name(text):
    return parse_medical_document(text).patient_name


def _hospital(text):
    return parse_medical_document(text).hospital


# ── 환자명 ──────────────────────────────────────────────────────────────────

def test_patient_name_same_line():
    assert _name("성명: 김철수\n진료일: 2024-01-01") == "김철수"


def test_patient_name_label_variants():
    assert _name("환자명 이영희") == "이영희"
    assert _name("수진자 : 박민수") == "박민수"
    assert _name("피보험자 최지우") == "최지우"


def test_patient_name_spaced():
    # 라벨과 이름 모두 글자 사이 공백
    assert _name("성 명 : 이 영 희") == "이영희"


def test_patient_name_next_line():
    assert _name("환자정보\n홍길순\n생년월일 900101") == "홍길순"


def test_patient_name_ignores_number_field():
    # '환자번호' 같은 필드는 이름으로 오인식하지 않아야 함
    assert _name("환자번호: 12345\n성명: 강하늘") == "강하늘"


# ── 병원명 ──────────────────────────────────────────────────────────────────

def test_hospital_by_label():
    assert _hospital("요양기관명: 서울대학교병원\n환자명: 김철수") == "서울대학교병원"


def test_hospital_by_suffix_midline():
    # 라벨 없이 줄 중간에 등장하는 접미사(의원) 인식
    assert _hospital("발행 연세이비인후과의원 02-123-4567") == "연세이비인후과의원"


def test_hospital_label_prefix_stripped():
    assert _hospital("병원명 강남365의원") == "강남365의원"
