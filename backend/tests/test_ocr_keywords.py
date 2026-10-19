"""JSON 키워드 사전 기반 환자명·병원명 인식 테스트"""
from app.services.ocr.parser import (
    _extract_patient_name_vertical,
    parse_medical_document,
)


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


# ── 환자명 세로쓰기 ───────────────────────────────────────────────────────────

def test_patient_name_vertical_value_only():
    # 라벨은 가로, 이름 값만 세로(글자당 한 줄)
    assert _name("환자성명\n윤\n서\n준\n생년월일 900101") == "윤서준"


def test_patient_name_vertical_label_and_value():
    # 라벨까지 세로로 이어진 경우
    assert _name("환\n자\n명\n김\n철\n수") == "김철수"


def test_patient_name_vertical_two_char():
    assert _name("성명\n남\n주") == "남주"


def test_patient_name_horizontal_takes_priority():
    # 가로 인식이 되면 세로 폴백은 동작하지 않아야 함
    assert _name("성명: 이영희\n환자정보\n홍\n길\n동") == "이영희"


def test_patient_name_vertical_ignores_random_single_chars():
    # 라벨과 무관한 단일 글자 나열은 이름으로 오인식하지 않음
    assert _name("진\n료\n비\n영\n수\n증") is None


# ── 세로쓰기 중 가로 정규식으로는 잡을 수 없는 배치 ─────────────────────────
# 아래 케이스들은 세로 폴백(_extract_patient_name_vertical)이 없으면 실패한다.
# 기존 PATIENT_NAME_PATTERN은 이름 글자 사이 공백을 `\s?`(1개)까지만 허용하므로
# 빈 줄이나 줄 끝 공백이 끼면 매칭이 끊긴다.

def test_patient_name_vertical_with_blank_lines():
    # OCR이 세로 항목 사이에 빈 줄을 끼워 넣는 경우
    assert _name("환자성명\n\n윤\n\n서\n\n준") == "윤서준"


def test_patient_name_vertical_label_and_value_with_blank_lines():
    assert _name("환\n자\n명\n\n김\n\n철\n\n수") == "김철수"


def test_patient_name_vertical_with_trailing_spaces():
    # 각 줄 끝에 공백이 남은 경우 (' \n' = 공백 2개라 가로 정규식 실패)
    assert _name("환자성명\n윤 \n서 \n준") == "윤서준"


def test_patient_name_vertical_blank_lines_still_rejects_non_name():
    assert _name("진\n\n료\n\n비\n\n영\n\n수\n\n증") is None


# ── 세로 폴백 함수 단위 테스트 ───────────────────────────────────────────────

def test_vertical_helper_label_then_value():
    assert _extract_patient_name_vertical(["환자성명", "윤", "서", "준"]) == "윤서준"


def test_vertical_helper_label_inside_run():
    assert _extract_patient_name_vertical(["환", "자", "명", "김", "철", "수"]) == "김철수"


def test_vertical_helper_requires_label():
    # 앞에 라벨이 없으면 단순 글자 나열은 이름이 아니다
    assert _extract_patient_name_vertical(["김", "철", "수"]) is None


def test_vertical_helper_ignores_unrelated_run():
    assert _extract_patient_name_vertical(["합", "계", "금", "액"]) is None


def test_vertical_helper_empty_input():
    assert _extract_patient_name_vertical([]) is None


def test_vertical_helper_picks_run_after_label_among_many():
    # 라벨과 무관한 세로 나열이 먼저 나와도 라벨 뒤 나열을 찾아낸다
    lines = ["진", "료", "비", "환자성명", "남", "주"]
    assert _extract_patient_name_vertical(lines) == "남주"


# ── 병원명 ──────────────────────────────────────────────────────────────────

def test_hospital_by_label():
    assert _hospital("요양기관명: 서울대학교병원\n환자명: 김철수") == "서울대학교병원"


def test_hospital_by_suffix_midline():
    # 라벨 없이 줄 중간에 등장하는 접미사(의원) 인식
    assert _hospital("발행 연세이비인후과의원 02-123-4567") == "연세이비인후과의원"


def test_hospital_label_prefix_stripped():
    assert _hospital("병원명 강남365의원") == "강남365의원"
