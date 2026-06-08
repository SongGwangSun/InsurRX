"""카카오 i 오픈빌더 응답 포맷 빌더 (API v2)."""

DASHBOARD_URL = "https://songgwangsun.github.io/InsurRX/dashboard.html"


# ── 공통 빠른 답변 ──────────────────────────────────────────────────────────────

def qr(label: str, msg: str = "") -> dict:
    return {"label": label, "action": "message", "messageText": msg or label}

def qr_block(label: str, block_id: str) -> dict:
    return {"label": label, "action": "block", "blockId": block_id, "messageText": label}

BACK_QR    = [qr("🏠 처음으로", "처음으로")]
CANCEL_QR  = [qr("✖ 취소", "취소"), qr("🏠 처음으로", "처음으로")]


# ── 응답 래퍼 ──────────────────────────────────────────────────────────────────

def build(outputs: list, quick_replies: list | None = None) -> dict:
    resp: dict = {"version": "2.0", "template": {"outputs": outputs}}
    if quick_replies:
        resp["template"]["quickReplies"] = quick_replies
    return resp


def text(msg: str, quick_replies: list | None = None) -> dict:
    return build([{"simpleText": {"text": msg}}], quick_replies)


def card(title: str, desc: str, buttons: list | None = None,
         thumbnail: str | None = None, quick_replies: list | None = None) -> dict:
    c: dict = {"title": title, "description": desc}
    if thumbnail:
        c["thumbnail"] = {"imageUrl": thumbnail}
    if buttons:
        c["buttons"] = buttons
    return build([{"basicCard": c}], quick_replies)


def web_btn(label: str, url: str) -> dict:
    return {"label": label, "action": "webLink", "webLinkUrl": url}

def msg_btn(label: str, msg: str) -> dict:
    return {"label": label, "action": "message", "messageText": msg}


# ── 메인 메뉴 ──────────────────────────────────────────────────────────────────

def main_menu() -> dict:
    return card(
        title="👋 안녕하세요! InsurRX입니다",
        desc="처방전·영수증 사진 한 장으로 보험금 청구 여부를\nAI가 1분 안에 알려드립니다.",
        buttons=[
            msg_btn("📊 보험금 분석 시작", "보험금 분석"),
            msg_btn("📋 최근 분석 결과",  "최근 결과"),
            web_btn("💻 대시보드 열기",   DASHBOARD_URL),
        ],
        quick_replies=[
            qr("📊 보험금 분석", "보험금 분석"),
            qr("📋 최근 결과",  "최근 결과"),
            qr("❓ 도움말",    "도움말"),
        ],
    )


# ── 이미지 요청 ────────────────────────────────────────────────────────────────

def request_image() -> dict:
    return text(
        "📷 처방전 또는 진료비 영수증 사진을 전송해 주세요.\n\n"
        "• 갤러리에서 선택하거나 카메라로 직접 촬영하세요\n"
        "• 금액·상병코드가 잘 보이게 촬영해 주세요",
        quick_replies=CANCEL_QR,
    )


# ── 보험 선택 ──────────────────────────────────────────────────────────────────

POLICY_OPTIONS = [
    ("현대해상 실손",  "hyundai-silson-v4"),
    ("현대해상 암보험","hyundai-cancer-2401"),
    ("삼성화재 아이플러스", "samsung-child-mykids"),
    ("AXA 치아보험",   "axa-dental-2501"),
]

def select_policy() -> dict:
    qrs = [qr(f"{'✅' if i==0 else '⬜'} {name}", f"약관선택:{pid}")
           for i, (name, pid) in enumerate(POLICY_OPTIONS)]
    qrs += [qr("🔍 전체 검색", "약관선택:all"), *CANCEL_QR]
    return text(
        "📑 어떤 보험 약관으로 확인할까요?\n"
        "(복수 선택 없이 가장 관련 있는 보험 하나를 선택해 주세요)",
        quick_replies=qrs,
    )


# ── 처리 중 ────────────────────────────────────────────────────────────────────

def processing_notice() -> dict:
    return text(
        "⏳ AI가 문서를 분석하고 있습니다.\n\n"
        "약 10~20초 후 아래 버튼을 눌러 결과를 확인하세요.",
        quick_replies=[qr("🔎 결과 확인", "결과 확인"), *BACK_QR],
    )


# ── 분석 결과 카드 ────────────────────────────────────────────────────────────

def result_card(result: dict) -> dict:
    is_ok     = result.get("is_claimable", False)
    payout    = result.get("estimated_payout", 0)
    summary   = result.get("llm_summary", "분석 결과를 확인하세요.")
    confidence= int((result.get("confidence", 0)) * 100)

    if is_ok:
        title = f"✅ 보험금 청구 가능 — ₩{payout:,}"
        desc  = f"{summary}\n\n신뢰도: {confidence}%"
    else:
        title = "❌ 보험금 청구가 어렵습니다"
        desc  = f"{summary}\n\n신뢰도: {confidence}%"

    # 약관별 세부 항목 (최대 3개)
    items = result.get("coverage_items", [])[:3]
    if items:
        detail = "\n".join(
            f"{'✔' if c['is_covered'] else '✘'} {c['policy_name']}: {c['reason'][:30]}"
            for c in items
        )
        desc = f"{desc}\n\n{detail}"

    return card(
        title=title,
        desc=desc,
        buttons=[
            web_btn("📄 상세 결과 보기", DASHBOARD_URL),
            msg_btn("🔄 다시 분석하기",  "보험금 분석"),
        ],
        quick_replies=[
            qr("🔄 다시 분석", "보험금 분석"),
            qr("🏠 처음으로",  "처음으로"),
        ],
    )


# ── 도움말 ────────────────────────────────────────────────────────────────────

def help_card() -> dict:
    return card(
        title="❓ InsurRX 사용 가이드",
        desc=(
            "1️⃣ '보험금 분석'을 누르세요\n"
            "2️⃣ 처방전·영수증 사진을 전송하세요\n"
            "3️⃣ 보험 종류를 선택하세요\n"
            "4️⃣ AI 분석 결과를 확인하세요\n\n"
            "💡 더 정확한 분석을 원하시면\n"
            "대시보드에서 내 보험증권을 직접 등록해 보세요!"
        ),
        buttons=[
            web_btn("💻 대시보드에서 보험증권 등록", DASHBOARD_URL),
        ],
        quick_replies=[
            qr("📊 보험금 분석", "보험금 분석"),
            qr("🏠 처음으로",   "처음으로"),
        ],
    )


# ── 오류 / 미지원 ─────────────────────────────────────────────────────────────

def error_msg(detail: str = "일시적 오류가 발생했습니다.") -> dict:
    return text(
        f"⚠️ {detail}\n잠시 후 다시 시도해 주세요.",
        quick_replies=BACK_QR,
    )

def fallback() -> dict:
    return text(
        "죄송합니다, 이해하지 못했어요. 😅\n아래 버튼으로 시작해 주세요.",
        quick_replies=[
            qr("📊 보험금 분석", "보험금 분석"),
            qr("❓ 도움말",    "도움말"),
            qr("🏠 처음으로",  "처음으로"),
        ],
    )
