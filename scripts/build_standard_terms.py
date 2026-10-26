"""
표준약관(보험업감독업무시행세칙 [별표15]) PDF → 조항 단위 JSON 변환 스크립트

사용법:
    python scripts/build_standard_terms.py "<별표15 PDF 경로>"

출력:
    data/policies/standard/<policy_id>.json
    형식: { "policy_id", "policy_name", "source", "revised",
             "articles": [ { "article": "제3조(보장종목별 보상내용)", "page": 204, "text": "..." } ] }

보험사별 상품 약관 대신, 모든 보험사가 따르는 표준약관만 사용한다.
분석에 필요한 질병·상해보험과 실손의료보험(기본형·특별약관1·2)만 추출한다.
"""
import json
import re
import sys
from pathlib import Path

import pdfplumber

SOURCE = "보험업감독업무시행세칙 [별표15] 표준약관(제5-13조제1항 관련)"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "policies" / "standard"

# PDF 쪽 번호(1부터) 기준 구간 — 문서 하단 쪽 번호와 PDF 쪽 번호가 같다
SECTIONS = [
    {
        "policy_id": "std-disease-injury",
        "policy_name": "질병·상해보험 표준약관",
        "pages": (144, 203),
        # 장해분류표 등 부표는 처방전·영수증 기반 청구 판단과 무관하고 검색 결과를 독차지한다
        "skip_appendix": True,
    },
    {
        "policy_id": "std-silson-basic",
        "policy_name": "실손의료보험 표준약관 — 기본형(급여 실손의료비)",
        "pages": (204, 253),
    },
    {
        "policy_id": "std-silson-rider1",
        "policy_name": "실손의료보험 표준약관 — 특별약관1(중증 비급여 실손의료비)",
        "pages": (254, 283),
    },
    {
        "policy_id": "std-silson-rider2",
        "policy_name": "실손의료보험 표준약관 — 특별약관2(비중증 비급여 실손의료비)",
        "pages": (284, 313),
    },
]

# 조항 시작: 줄 맨 앞의 "제3조(조항명)" 뒤에 공백·줄끝이 오는 경우만.
# "제34조(해약환급금)에 따른", "제4조([별표3] …" 같은 본문 인용은 제외
ARTICLE_RE = re.compile(r"^(제\s?\d+\s?조(?:의\s?\d+)?\s?\((?!\[)[^)]{1,40}\))(?=\s|$)")
# 붙임·별표·부표 등 조항 밖 부록
APPENDIX_RE = re.compile(r"^[<＜]\s?(붙임|별표|부표)[^>＞]{0,30}[>＞]")
PAGE_NO_RE = re.compile(r"^-\s?\d+\s?-$")
REVISED_RE = re.compile(r"(\d{4})\.\s?(\d{1,2})\.\s?(\d{1,2})\.?\s?>")

MAX_CHARS = 1500   # 임베딩 청크 상한 (한국어 1500자 ≈ 500~700 토큰)
OVERLAP = 150


def extract_lines(pdf, first: int, last: int) -> list[tuple[int, str]]:
    """(쪽 번호, 줄) 목록. 쪽 번호 줄과 빈 줄은 버린다."""
    lines = []
    for page_no in range(first, last + 1):
        text = pdf.pages[page_no - 1].extract_text() or ""
        for line in text.splitlines():
            line = line.strip()
            if not line or PAGE_NO_RE.match(line):
                continue
            lines.append((page_no, line))
    return lines


def split_articles(lines: list[tuple[int, str]]) -> list[dict]:
    """줄 목록을 조항 단위로 묶는다. 첫 조항 이전 머리말은 '개요'로 둔다."""
    articles: list[dict] = []
    current = {"article": "개요", "page": lines[0][0] if lines else 0, "lines": []}
    for page_no, line in lines:
        m = ARTICLE_RE.match(line) or APPENDIX_RE.match(line)
        if m:
            if current["lines"]:
                articles.append(current)
            current = {"article": re.sub(r"\s+", " ", m.group(0)), "page": page_no, "lines": []}
        current["lines"].append(line)
    if current["lines"]:
        articles.append(current)
    return [
        {"article": a["article"], "page": a["page"], "text": "\n".join(a["lines"])}
        for a in articles
    ]


def chunk_article(article: dict) -> list[dict]:
    """긴 조항은 MAX_CHARS 단위로 나누고, 각 조각 앞에 조항명을 붙여 문맥을 유지한다."""
    text = article["text"]
    if len(text) <= MAX_CHARS:
        return [article]
    parts = []
    step = MAX_CHARS - OVERLAP
    for i, start in enumerate(range(0, len(text), step)):
        body = text[start:start + MAX_CHARS].strip()
        if not body:
            continue
        prefix = "" if i == 0 else f"{article['article']} (계속)\n"
        parts.append({"article": article["article"], "page": article["page"], "text": prefix + body})
    return parts


def latest_revision(lines: list[tuple[int, str]]) -> str | None:
    """구간 머리말의 개정 이력에서 가장 최근 날짜 (예: 2026-05-06)."""
    head = " ".join(line for _, line in lines[:12])
    dates = [f"{y}-{int(m):02d}-{int(d):02d}" for y, m, d in REVISED_RE.findall(head)]
    dates += [f"{y}-{int(m):02d}-{int(d):02d}"
              for y, m, d in re.findall(r"(\d{4})\.\s?(\d{1,2})\.\s?(\d{1,2})\.", head)]
    return max(dates) if dates else None


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    pdf_path = Path(sys.argv[1])
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    revised = None
    with pdfplumber.open(pdf_path) as pdf:
        for section in SECTIONS:
            first, last = section["pages"]
            lines = extract_lines(pdf, first, last)
            articles = split_articles(lines)
            if section.get("skip_appendix"):
                articles = [a for a in articles if not APPENDIX_RE.match(a["article"])]
            chunks = [c for a in articles for c in chunk_article(a)]
            data = {
                "policy_id": section["policy_id"],
                "policy_name": section["policy_name"],
                "source": SOURCE,
                "pages": f"{first}-{last}",
                # 특별약관은 자체 개정 이력이 없어 바로 앞 기본형의 개정일을 따른다
                "revised": (revised := latest_revision(lines) or revised),
                "articles": chunks,
            }
            out = OUT_DIR / f"{section['policy_id']}.json"
            out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"{section['policy_name']}: {len(chunks)}개 청크 (개정 {data['revised']}) → {out}")


if __name__ == "__main__":
    main()
