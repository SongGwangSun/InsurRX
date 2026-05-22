import json
from pathlib import Path

POLICY_DATA_DIR = Path(__file__).parent.parent.parent.parent.parent / "data" / "policies"


def load_policy_metadata(policy_id: str) -> dict:
    """보험 상품 메타데이터를 로드합니다."""
    path = POLICY_DATA_DIR / f"{policy_id}.json"
    if not path.exists():
        return {"policy_id": policy_id, "policy_name": policy_id}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def list_available_policies() -> list[dict]:
    """사용 가능한 보험 상품 목록을 반환합니다."""
    if not POLICY_DATA_DIR.exists():
        return _default_policies()
    return [
        load_policy_metadata(p.stem)
        for p in POLICY_DATA_DIR.glob("*.json")
    ]


def _default_policies() -> list[dict]:
    return [
        {"policy_id": "hyundai-silson-v4", "policy_name": "현대해상 실손의료비 4세대", "type": "실손"},
        {"policy_id": "samsung-silson-v4", "policy_name": "삼성화재 실손의료비 4세대", "type": "실손"},
        {"policy_id": "kb-silson-v4", "policy_name": "KB손보 실손의료비 4세대", "type": "실손"},
    ]
