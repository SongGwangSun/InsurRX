"""카카오 i 오픈빌더 응답 포맷 빌더 (API v2)."""

DASHBOARD_URL = "https://songgwangsun.github.io/InsurRX/dashboard.html"


# ── 공통 빠른 답변 ──────────────────────────────────────────────────────────────

def qr(label: str, msg: str = "") -> dict:
    return {"label": label, "action": "message", "messageText": msg or label}

def qr_block(label: str, block_id: str) -> dict:
    return {"label": label, "action": "block", "blockId": block_id, "messageText": label}

BACK_QR    = [qr("🏠 처음으로", "처음으로")]

DISCLAIMER = "※ AI 추정치이며, 최종 지급 여부·금액은 보험사 심사로 결정됩니다."
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
        desc="처방전·영수증·약봉투 사진으로 보험금 청구 여부를\nAI가 1분 안에 알려드립니다.\n내 보험증권을 등록하면 더 정확해져요.",
        buttons=[
            msg_btn("📊 보험금 분석 시작", "보험금 분석"),
            msg_btn("📂 내 보험 관리",    "내 보험"),
            web_btn("💻 대시보드 열기",   DASHBOARD_URL),
        ],
        quick_replies=[
            qr("📊 보험금 분석", "보험금 분석"),
            qr("📂 내 보험",    "내 보험"),
            qr("📋 최근 결과",  "최근 결과"),
            qr("❓ 도움말",    "도움말"),
        ],
    )


# ── 이미지 요청 ────────────────────────────────────────────────────────────────

def request_image() -> dict:
    return text(
        "📷 처방전·진료비 영수증·약봉투 사진을 전송해 주세요.\n\n"
        "• 여러 장을 한 번에 보내면 하나로 합쳐 분석합니다 (최대 5장)\n"
        "  예) 처방전 + 약봉투\n"
        "• 금액·상병코드·약품명이 잘 보이게 촬영해 주세요",
        quick_replies=CANCEL_QR,
    )


# ── 보험 선택 ──────────────────────────────────────────────────────────────────

POLICY_OPTIONS = [
    ("현대해상 실손",  "hyundai-silson-v4"),
    ("현대해상 암보험","hyundai-cancer-2401"),
    ("삼성화재 아이플러스", "samsung-child-mykids"),
    ("AXA 치아보험",   "axa-dental-2501"),
]

def select_policy(image_count: int = 1, has_own: bool = False) -> dict:
    qrs = [qr("📂 내 보험으로", "약관선택:mine")] if has_own else []
    qrs += [qr(f"⬜ {name}", f"약관선택:{pid}") for name, pid in POLICY_OPTIONS]
    qrs += [qr("🔍 전체 검색", "약관선택:all"), *CANCEL_QR]
    head = f"📥 사진 {image_count}장을 받았습니다.\n\n" if image_count > 1 else ""
    guide = (
        "등록하신 내 보험은 어떤 약관을 골라도 함께 확인합니다."
        if has_own else
        "(복수 선택 없이 가장 관련 있는 보험 하나를 선택해 주세요)"
    )
    return text(f"{head}📑 어떤 보험 약관으로 확인할까요?\n{guide}", quick_replies=qrs)


# ── 처리 중 ────────────────────────────────────────────────────────────────────

def processing_notice() -> dict:
    return text(
        "⏳ AI가 문서를 분석하고 있습니다.\n\n"
        "약 10~20초 후 아래 버튼을 눌러 결과를 확인하세요.",
        quick_replies=[qr("🔎 결과 확인", "결과 확인"), *BACK_QR],
    )


# ── 분석 결과 카드 ────────────────────────────────────────────────────────────

PILL_ENVELOPE_NOTICE = (
    "💊 약봉투만으로 분석했어요\n\n"
    "약봉투에는 보통 진단명·상병코드가 없어 정확도가 낮을 수 있습니다.\n"
    "실손보험 약제비 청구에는 약제비 영수증(약제비 계산서)과 처방전이 필요하니 함께 챙겨 주세요."
)


def result_card(result: dict) -> dict:
    is_ok     = result.get("is_claimable", False)
    payout    = result.get("estimated_payout", 0)
    summary   = result.get("llm_summary", "분석 결과를 확인하세요.")
    confidence= int((result.get("confidence", 0)) * 100)

    if is_ok:
        title = f"✅ 보험금 청구 가능 — 예상 ₩{payout:,}"
    else:
        title = "❌ 보험금 청구가 어렵습니다"
    desc = f"{summary}\n\n신뢰도: {confidence}%\n{DISCLAIMER}"

    # 약관별 세부 항목 (최대 3개)
    items = result.get("coverage_items", [])[:3]
    if items:
        detail = "\n".join(
            f"{'✔' if c['is_covered'] else '✘'} {c['policy_name']}: {c['reason'][:30]}"
            for c in items
        )
        desc = f"{desc}\n\n{detail}"

    resp = card(
        title=title,
        desc=desc,
        buttons=[
            web_btn("📄 상세 결과 보기", DASHBOARD_URL),
            msg_btn("🔄 다시 분석하기",  "보험금 분석"),
        ],
        quick_replies=[
            qr("❓ 결과가 다를 때", "결과가 다를 때"),
            qr("🔄 다시 분석", "보험금 분석"),
            qr("🏠 처음으로",  "처음으로"),
        ],
    )
    if result.get("doc_types") == ["pill_envelope"]:
        resp["template"]["outputs"].append({"simpleText": {"text": PILL_ENVELOPE_NOTICE}})
    return resp


# ── 내 보험 관리 ──────────────────────────────────────────────────────────────

MY_INSURANCE_QR = [
    qr("📄 증권 등록", "보험증권 등록"),
    qr("📑 약관 연결", "약관 연결"),
    qr("🔗 계정 연결", "계정 연결"),
    qr("🏠 처음으로", "처음으로"),
]

_STATUS_ICON = {"ready": "✅", "pending": "⏳", "processing": "⏳", "failed": "⚠️"}


def my_insurance(policies: list[dict], linked_web: bool) -> dict:
    """policies: [{"name": str, "status": str}] (최신순)"""
    if policies:
        rows = "\n".join(
            f"{_STATUS_ICON.get(p['status'], '•')} {p['name']}" for p in policies[:10]
        )
        body = f"📂 등록된 내 보험 ({len(policies)}건)\n\n{rows}\n\n✅ 사용 가능  ⏳ 처리 중  ⚠️ 실패"
    else:
        body = (
            "📂 아직 등록된 보험이 없습니다.\n\n"
            "• 증권 등록: 보험증권 사진을 보내면 AI가 읽어 둡니다\n"
            "• 약관 연결: 가입한 보험 상품을 골라 공개 약관을 연결합니다"
        )
    if linked_web:
        body += "\n\n🔗 웹 계정과 연결되어 있습니다."
    return text(body, quick_replies=MY_INSURANCE_QR)


def request_policy_image() -> dict:
    return text(
        "📄 보험증권 사진을 전송해 주세요.\n\n"
        "• 여러 장이면 한 번에 선택해 보내 주세요 (최대 10장)\n"
        "• 보험사·상품명·담보(특약)·가입금액이 보이는 면이 중요합니다\n"
        "• 주민번호·전화번호는 저장 전에 자동으로 가려집니다\n\n"
        "📚 약관(수십 쪽)은 사진 대신 '약관 연결'로 상품을 고르거나\n"
        "대시보드에서 PDF로 올려 주세요.",
        quick_replies=CANCEL_QR,
    )


def policy_registering(image_count: int) -> dict:
    return text(
        f"📥 보험증권 사진 {image_count}장을 받았습니다.\n\n"
        "AI가 내용을 읽어 등록하고 있어요 (약 30초~1분).\n"
        "'내 보험'에서 처리 상태를 확인할 수 있습니다.",
        quick_replies=[
            qr("📂 내 보험", "내 보험"),
            qr("📄 더 등록", "보험증권 등록"),
            qr("📊 보험금 분석", "보험금 분석"),
        ],
    )


def select_insurer(insurers: list[tuple[int, str]]) -> dict:
    if not insurers:
        return text("등록된 보험사가 없습니다.", quick_replies=MY_INSURANCE_QR)
    qrs = [qr(name, f"보험사:{iid}") for iid, name in insurers[:9]] + [qr("✖ 취소", "내 보험")]
    return text("🏢 가입한 보험사를 선택해 주세요.", quick_replies=qrs)


def select_product(insurer_name: str, products: list[tuple[int, str]]) -> dict:
    if not products:
        return text(f"{insurer_name}에 등록된 상품이 없습니다.", quick_replies=MY_INSURANCE_QR)
    qrs = [qr(name[:14], f"상품연결:{pid}") for pid, name in products[:9]] + [qr("✖ 취소", "내 보험")]
    listing = "\n".join(f"• {name}" for _, name in products[:9])
    return text(f"📑 {insurer_name} — 가입한 상품을 선택해 주세요.\n\n{listing}", quick_replies=qrs)


def product_linked(name: str, has_terms: bool, already: bool = False) -> dict:
    msg = f"✅ '{name}' 약관이 {'이미 ' if already else ''}연결되어 있습니다."
    if not has_terms:
        msg += "\n\n⚠️ 이 상품은 아직 약관 데이터가 준비되지 않아 분석에는 반영되지 않습니다. 보험증권 사진을 함께 등록해 주세요."
    return text(msg, quick_replies=MY_INSURANCE_QR)


def link_guide() -> dict:
    return card(
        title="🔗 웹 계정과 연결하기",
        desc=(
            "1️⃣ 대시보드에 로그인 → '계정' 탭\n"
            "2️⃣ '카카오톡 연결 코드 발급' 클릭\n"
            "3️⃣ 여기에 '연결 코드' 형식으로 입력\n"
            "   예) 연결 AB3K9QXZ\n\n"
            "카톡에서 등록한 보험은 웹 계정으로 옮겨집니다."
        ),
        buttons=[web_btn("💻 대시보드 열기", DASHBOARD_URL)],
        quick_replies=MY_INSURANCE_QR,
    )


def link_result(ok: bool, name: str = "") -> dict:
    if ok:
        return text(
            f"🔗 {name}님 웹 계정과 연결되었습니다.\n이제 웹과 카톡에서 같은 내 보험을 사용합니다.",
            quick_replies=MY_INSURANCE_QR,
        )
    return text(
        "⚠️ 연결 코드가 올바르지 않거나 만료되었습니다.\n대시보드에서 새 코드를 발급해 주세요 (10분 유효).",
        quick_replies=MY_INSURANCE_QR,
    )


# ── 실제 결과와 차이 날 때 안내 ────────────────────────────────────────────────

def payout_dispute_guide() -> dict:
    return text(
        "📌 실제 지급 결과가 예상과 다를 때\n\n"
        "1️⃣ 차이 원인 확인\n"
        "· 실손 가입 시기(1~5세대)·특별약관 가입 여부별 공제액·자기부담률\n"
        "· 비급여 항목 포함 여부\n"
        "· 다른 보험과의 중복 보장(비례 보상)\n"
        "· 청구 서류 누락\n\n"
        "2️⃣ 보험사에 재심사 요청\n"
        "· 고객센터에 지급 산출 내역 요청\n"
        "· 진료비 영수증·세부내역서·처방전(약제비)·필요 시 진단서 보완 후 재청구\n\n"
        "3️⃣ 해결되지 않으면 분쟁조정 신청\n"
        "· 금융감독원 ☎ 1332 / e-금융민원센터(www.fcsc.kr)\n"
        "· 보험금 청구권은 3년이 지나면 소멸합니다",
        quick_replies=[qr("🔄 다시 분석", "보험금 분석"), *BACK_QR],
    )


# ── 도움말 ────────────────────────────────────────────────────────────────────

def help_card() -> dict:
    return card(
        title="❓ InsurRX 사용 가이드",
        desc=(
            "1️⃣ '보험금 분석'을 누르세요\n"
            "2️⃣ 처방전·영수증·약봉투 사진을 전송하세요\n"
            "3️⃣ 보험 종류를 선택하세요\n"
            "4️⃣ AI 분석 결과를 확인하세요\n\n"
            "💡 '내 보험'에서 보험증권 사진을 등록하거나\n"
            "가입 상품 약관을 연결하면 더 정확해져요!"
        ),
        buttons=[
            msg_btn("📂 내 보험 관리", "내 보험"),
            web_btn("💻 대시보드에서 PDF 등록", DASHBOARD_URL),
        ],
        quick_replies=[
            qr("📊 보험금 분석", "보험금 분석"),
            qr("📂 내 보험",    "내 보험"),
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
            qr("📂 내 보험",    "내 보험"),
            qr("❓ 도움말",    "도움말"),
            qr("🏠 처음으로",  "처음으로"),
        ],
    )
