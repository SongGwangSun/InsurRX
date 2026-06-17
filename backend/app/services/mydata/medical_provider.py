"""
의료 마이데이터 진료/조제 내역 조회 서비스 (mock)

실제 운영 시: 건강보험심사평가원 '나의 건강기록' / 의료 마이데이터 표준 API
- 진료내역, 처방·조제내역 조회 (환자 본인 인증 후)

현재: Mock 구현 — OCR로 인식한 환자명·병원·조제일자를 키로
'일치하는 진료내역이 있는지'를 결정론적으로 판단해 돌려준다.
fetch_treatment() 내부만 실제 API 호출로 교체하면 된다.
"""
import hashlib
from typing import Optional


def _mock_birth_date(name: str) -> str:
    """환자명으로부터 결정론적 생년월일(YYYYMMDD) 생성 — 금융 마이데이터 연동 키로 사용."""
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)
    year = 1960 + (h % 45)            # 1960~2004
    month = (h // 100) % 12 + 1
    day = (h // 1000) % 28 + 1
    return f"{year:04d}{month:02d}{day:02d}"


async def fetch_treatment(
    patient_name: Optional[str],
    hospital: Optional[str],
    treatment_date: Optional[str],
) -> dict:
    """진료/조제 내역 대조.

    반환:
      {"matched": False, "reason": "..."}  또는
      {"matched": True, "record": {... , "birth_date": "YYYYMMDD"}}
    """
    name = (patient_name or "").strip()
    hosp = (hospital or "").strip()

    if len(name) < 2:
        return {"matched": False, "reason": "처방전에서 환자 성명을 인식하지 못해 대조할 수 없습니다."}
    if not hosp:
        return {"matched": False, "reason": "처방전에서 병원/약국 정보를 인식하지 못해 대조할 수 없습니다."}

    # Mock: 환자명+병원이 인식되면 의료 마이데이터에 동일 내역이 있다고 간주(확인됨)
    record = {
        "patient_name":   name,
        "hospital":       hosp,
        "treatment_date": treatment_date,
        "source":         "건강보험심사평가원 진료내역",
        "birth_date":     _mock_birth_date(name),
    }
    return {"matched": True, "record": record}
