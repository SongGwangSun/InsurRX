"""
보험 약관 PDF 수집 → 텍스트 추출 → JSON 변환 스크립트

사용법:
    python scripts/collect_policies.py

출력:
    data/policies/raw/<policy_id>.json
    형식: { "policy_id": "...", "policy_name": "...", "insurer": "...",
             "product_type": "...", "content": "...", "source_url": "..." }
"""
import json
import re
import sys
import time
from pathlib import Path

import pdfplumber
import requests

# ── 수집 대상 정의 ────────────────────────────────────────────────────────────
POLICIES = [
    {
        "policy_id": "hyundai-silson-v4",
        "policy_name": "무배당 현대해상다이렉트 실손의료비보장보험(갱신형)",
        "insurer": "현대해상",
        "product_type": "실손의료보험",
        "url": (
            "https://www.hi.co.kr/FileActionServlet/preview/0/data/202306/"
            "2a1b00ded56c81fa672e98baeeb1d2c0.pdf"
        ),
    },
    {
        "policy_id": "hyundai-cancer-2401",
        "policy_name": "무배당 현대해상다이렉트 계속받는암보험(Hi2401)",
        "insurer": "현대해상",
        "product_type": "정액형(암·수술비)",
        "url": (
            "https://direct.hi.co.kr/dhNAS/terms/CM171K_20240101.pdf"
        ),
    },
    {
        "policy_id": "samsung-child-mykids",
        "policy_name": "삼성화재 다이렉트 어린이보험(My아이플러스)",
        "insurer": "삼성화재",
        "product_type": "어린이보험",
        "url": (
            "https://direct.samsungfire.com/CR_MyAnycarWeb/mall/pdf/mykids.pdf"
        ),
    },
    {
        "policy_id": "kb-dental-healthy",
        "policy_name": "KB The건강한 치아보험",
        "insurer": "KB손해보험",
        "product_type": "치아보험",
        "url": (
            "http://www.kbinsure.co.kr/images/pban_info/pdf/2025_04_01.pdf"
        ),
    },
]

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "policies" / "raw"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,*/*",
    "Referer": "https://www.hi.co.kr/",
}


# ── 유틸 함수 ─────────────────────────────────────────────────────────────────

def download_pdf(url: str, dest: Path, timeout: int = 60) -> bool:
    """URL에서 PDF를 다운로드합니다. 성공 여부 반환."""
    headers = dict(HEADERS)
    # 도메인별 Referer 조정
    if "samsungfire" in url:
        headers["Referer"] = "https://direct.samsungfire.com/"
    elif "kbinsure" in url:
        headers["Referer"] = "https://www.kbinsure.co.kr/"

    try:
        resp = requests.get(url, headers=headers, timeout=timeout, stream=True)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if "html" in content_type.lower():
            print(f"    ⚠ HTML 응답 (로그인 필요 또는 잘못된 URL): {url}")
            return False
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        size_kb = dest.stat().st_size // 1024
        print(f"    ✓ 다운로드 완료 ({size_kb} KB): {dest.name}")
        return True
    except requests.RequestException as e:
        print(f"    ✗ 다운로드 실패: {e}")
        return False


def extract_text_from_pdf(pdf_path: Path) -> str:
    """pdfplumber로 PDF 전체 텍스트를 추출합니다."""
    texts = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total = len(pdf.pages)
            print(f"    → {total}페이지 처리 중...")
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    texts.append(text.strip())
                if (i + 1) % 20 == 0:
                    print(f"       {i+1}/{total} 페이지 완료")
    except Exception as e:
        print(f"    ✗ PDF 추출 실패: {e}")
        return ""
    return "\n\n".join(texts)


def clean_text(text: str) -> str:
    """불필요한 공백/특수문자를 정리합니다."""
    # 연속 공백 → 단일 공백
    text = re.sub(r"[ \t]{2,}", " ", text)
    # 3줄 이상 빈 줄 → 2줄로
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 페이지 번호 패턴 제거 (예: "- 1 -", "1 / 50")
    text = re.sub(r"[-–]\s*\d+\s*[-–]", "", text)
    text = re.sub(r"\d+\s*/\s*\d+\s*\n", "\n", text)
    return text.strip()


def save_policy_json(meta: dict, content: str):
    """약관 정보를 JSON으로 저장합니다."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "policy_id": meta["policy_id"],
        "policy_name": meta["policy_name"],
        "insurer": meta["insurer"],
        "product_type": meta["product_type"],
        "source_url": meta["url"],
        "content": content,
    }
    out_path = OUTPUT_DIR / f"{meta['policy_id']}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    size_kb = out_path.stat().st_size // 1024
    char_count = len(content)
    print(f"    ✓ JSON 저장: {out_path.name} ({size_kb} KB, {char_count:,}자)")


# ── 메인 ─────────────────────────────────────────────────────────────────────

def process_policy(meta: dict):
    """단일 약관 처리: 다운로드 → 추출 → 저장."""
    pid = meta["policy_id"]
    print(f"\n[{pid}] {meta['policy_name']}")

    # 이미 JSON이 있으면 스킵
    json_path = OUTPUT_DIR / f"{pid}.json"
    if json_path.exists():
        print(f"    ⏭ 이미 존재, 스킵: {json_path.name}")
        return

    pdf_path = OUTPUT_DIR / f"{pid}.pdf"

    # 1. 다운로드
    print(f"  1. 다운로드: {meta['url'][:80]}...")
    if not pdf_path.exists():
        ok = download_pdf(meta["url"], pdf_path)
        if not ok:
            return
    else:
        print(f"    ⏭ PDF 이미 존재, 스킵")

    # 2. 텍스트 추출
    print("  2. 텍스트 추출 중...")
    raw_text = extract_text_from_pdf(pdf_path)
    if not raw_text:
        print("    ✗ 텍스트가 비어있습니다. 스캔 PDF일 수 있음.")
        return

    cleaned = clean_text(raw_text)
    print(f"    → 추출된 텍스트: {len(cleaned):,}자")

    # 3. JSON 저장
    print("  3. JSON 저장...")
    save_policy_json(meta, cleaned)

    # PDF는 삭제하지 않고 보관 (재사용 가능)
    time.sleep(1)  # 서버 부하 방지


def main():
    print("=" * 60)
    print("InsurRX 약관 수집기")
    print("=" * 60)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    failed = []
    for meta in POLICIES:
        try:
            process_policy(meta)
        except Exception as e:
            print(f"    ✗ 예외 발생: {e}")
            failed.append(meta["policy_id"])

    print("\n" + "=" * 60)
    print("완료 요약")
    print("=" * 60)
    jsons = list(OUTPUT_DIR.glob("*.json"))
    print(f"저장된 JSON: {len(jsons)}개")
    for j in jsons:
        with open(j, encoding="utf-8") as f:
            d = json.load(f)
        print(f"  - {j.name}: {d['policy_name']} ({len(d['content']):,}자)")
    if failed:
        print(f"\n실패: {failed}")
        print("→ 해당 URL을 직접 브라우저에서 확인하거나 수동으로 PDF를 다운받아 주세요.")
    print(f"\n다음 단계:\n  python -m ai.embeddings.embed_policies --policy-dir data/policies/raw")


if __name__ == "__main__":
    main()
