"""
마이데이터 보험 계약 조회 서비스

실제 운영 시: 금융위 마이데이터 표준 API (https://developers.mydatakorea.org)
- 엔드포인트: GET /v2/irp/insurances (보험 계약 목록)
- 인증: 마이데이터 사업자 OAuth 2.0 액세스 토큰

현재: Mock 구현 — 실제 API 사용 시 fetch_policies() 내부만 교체하면 됩니다.

마이데이터 표준 API 보험 계약 응답 스펙 (v2.6):
  org_code       : 기관 코드 (금융결제원 기관 코드표 기준)
  prod_name      : 상품명
  contract_no    : 계약번호(증권번호)
  is_consent     : 전송 동의 여부
  is_active      : 유효계약 여부
  expire_date    : 만기일 YYYYMMDD
"""
import hashlib
import random
from datetime import date, timedelta
from typing import List

# ── 실제 금융기관 코드표 (금융결제원 제공) ─────────────────────────────────────
ORG_CODES = {
    "0001": "현대해상화재보험",
    "0002": "삼성화재해상보험",
    "0003": "AXA손해보험",
    "0004": "DB손해보험",
    "0005": "KB손해보험",
    "0006": "메리츠화재해상보험",
    "0007": "한화손해보험",
    "0008": "롯데손해보험",
}

# Pinecone에 실제 약관 데이터가 있는 상품 목록
KNOWN_PRODUCTS = [
    {
        "org_code":       "0001",
        "insurance_name": "실손의료보험 Hi2204",
        "product_type":   "실손",
        "premium":        35800,
        "vector_policy_id": "hyundai-silson-v4",
    },
    {
        "org_code":       "0001",
        "insurance_name": "암보험 Hi2401",
        "product_type":   "암",
        "premium":        28500,
        "vector_policy_id": "hyundai-cancer-2401",
    },
    {
        "org_code":       "0002",
        "insurance_name": "My 아이플러스 어린이보험",
        "product_type":   "어린이",
        "premium":        62000,
        "vector_policy_id": "samsung-child-mykids",
    },
    {
        "org_code":       "0003",
        "insurance_name": "치아보험 갱신형 2501",
        "product_type":   "치아",
        "premium":        18200,
        "vector_policy_id": "axa-dental-2501",
    },
]

# 약관 데이터 없는 추가 상품 (현실감용)
EXTRA_PRODUCTS = [
    {"org_code": "0004", "insurance_name": "프로미라이프 실손보험",   "product_type": "실손",   "premium": 31000},
    {"org_code": "0005", "insurance_name": "KB골든라이프 실손의료비", "product_type": "실손",   "premium": 33500},
    {"org_code": "0006", "insurance_name": "메리츠 실손의료비보험",   "product_type": "실손",   "premium": 29800},
    {"org_code": "0001", "insurance_name": "현대해상 상해보험",       "product_type": "상해",   "premium": 12500},
    {"org_code": "0007", "insurance_name": "한화생명 종신보험",       "product_type": "종신",   "premium": 85000},
    {"org_code": "0008", "insurance_name": "롯데 간편 실손보험",      "product_type": "실손",   "premium": 22000},
]


def _deterministic_policies(name: str, birth: str) -> List[dict]:
    """이름+생년월일 해시로 결정론적으로 보험 목록을 선택합니다.

    같은 입력이면 항상 같은 결과를 반환하므로 데모에서 일관성이 유지됩니다.
    """
    seed = int(hashlib.md5(f"{name}{birth}".encode()).hexdigest(), 16)
    rng  = random.Random(seed)

    # known products 중 1~3개 선택
    n_known = rng.randint(1, min(3, len(KNOWN_PRODUCTS)))
    chosen_known = rng.sample(KNOWN_PRODUCTS, n_known)

    # extra products 중 0~2개 추가
    n_extra = rng.randint(0, 2)
    chosen_extra = rng.sample(EXTRA_PRODUCTS, min(n_extra, len(EXTRA_PRODUCTS)))

    policies = []
    today = date.today()

    for i, prod in enumerate(chosen_known + chosen_extra):
        start = today - timedelta(days=rng.randint(180, 1800))
        end   = start + timedelta(days=rng.randint(365, 365 * 5))

        # 증권번호: 기관코드 + 랜덤 8자리
        policy_no = f"{prod['org_code']}{rng.randint(10000000, 99999999)}"

        policies.append({
            "org_code":        prod["org_code"],
            "org_name":        ORG_CODES[prod["org_code"]],
            "policy_number":   policy_no,
            "insurance_name":  prod["insurance_name"],
            "product_type":    prod["product_type"],
            "premium":         prod.get("premium", rng.randint(15000, 80000)),
            "coverage_start":  start.strftime("%Y-%m-%d"),
            "coverage_end":    end.strftime("%Y-%m-%d"),
            "status":          "정상" if end >= today else "만기",
            "vector_policy_id": prod.get("vector_policy_id"),
        })

    return policies


async def fetch_policies(name: str, birth_date: str) -> List[dict]:
    """마이데이터 허브에서 보험 계약 목록을 가져옵니다.

    실제 운영 시 이 함수 내부를 아래와 같이 교체합니다:

        access_token = await _get_mydata_token(user_mydata_auth_code)
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.mydatakorea.org/v2/irp/insurances",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"org_code": "", "search_timestamp": 0},
            )
            data = resp.json()
        return _normalize_mydata_response(data["data"]["insurance_list"])

    현재: 이름+생년월일 해시 기반 Mock 데이터 반환
    """
    # 입력 검증
    birth_date = birth_date.replace("-", "").replace(".", "").strip()
    if len(birth_date) != 8 or not birth_date.isdigit():
        raise ValueError("생년월일 형식이 올바르지 않습니다. (예: 19900115)")

    name = name.strip()
    if len(name) < 2:
        raise ValueError("이름을 2자 이상 입력해 주세요.")

    return _deterministic_policies(name, birth_date)
