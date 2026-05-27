# InsurRX — Claude Code 작업 가이드

> 처방전/영수증 사진 기반 AI 맞춤형 보험 보상 확인 챗봇 (2026ICT 과정 프로젝트)

---

## 📌 프로젝트 한 줄 요약
OCR + RAG로 **3초 이내** 실손/정액 보상 여부 및 예상 지급액 산출. 미청구 보험금 발굴.

---

## ✅ 완료된 작업

### 인프라 / 설정
- [x] 프로젝트 디렉터리 구조 설계 (`backend/`, `ai/`, `data/`, `infra/`)
- [x] FastAPI 앱 초기화 (`backend/app/main.py`) — lifespan, CORS, 라우터 등록
- [x] Pydantic-settings 기반 통합 설정 (`app/core/config.py`)
- [x] SQLAlchemy Async DB 연결 (`app/database.py`) — SQLite(개발) / PostgreSQL(운영)
- [x] Docker / docker-compose 설정 (`infra/docker/`)
- [x] Kubernetes 설정 (`infra/k8s/deployment.yaml`, `service.yaml`)
- [x] CI 파이프라인 (`.github/workflows/ci.yml`) — pytest on push/PR
- [x] CD 파이프라인 (`.github/workflows/deploy.yml`) — GitHub Pages 자동 배포
- [x] **Railway 백엔드 배포 완료** ✅ (2026-05-26)
  - URL: https://magnificent-celebration-production-2dd9.up.railway.app
  - `GET /health` → `{"status":"ok","service":"InsurRX"}` 확인
  - `POST /api/v1/waitlist/` → PostgreSQL 저장 확인
  - 핵심 수정: langchain 0.2→0.3.25, pydantic 2.7.0→2.11.6 (Python 3.12 호환)
  - GitHub Pages → Railway API 직접 연결 (CORS 설정 완료)

### 백엔드 API (4개 엔드포인트)
- [x] `POST /api/v1/upload/` — 이미지 업로드 → GPT-4o Vision OCR → 파싱 결과 반환 ✅ 실서비스 동작 확인
- [x] `POST /api/v1/analyze/` — 파싱 문서 + 보험 ID → RAG 파이프라인 → 보상 분석
- [x] `POST /api/v1/waitlist/` — Waitlist 이메일 저장 (중복 방지 포함)
- [x] `GET  /api/v1/result/{session_id}` — 분석 결과 조회 (라우터 등록됨, 구현 미완)

### AI / RAG 파이프라인
- [x] LangChain RAG 체인 (`ai/rag/chain.py`) — Claude Sonnet 4.6 / GPT-4o 선택 가능
- [x] 보상 분석 프롬프트 템플릿 (`ai/rag/prompt_templates.py`)
- [x] 임베딩 서비스 (`app/services/rag/embedder.py`) — OpenAI text-embedding-3-small
- [x] Vector DB 검색 (`app/services/rag/retriever.py`) — Pinecone 연동 완성
- [x] RAG 파이프라인 오케스트레이터 (`app/services/rag/pipeline.py`)
- [x] 약관 임베딩 스크립트 (`ai/embeddings/embed_policies.py`) — CLI 실행 가능
- [x] Vectorstore 클라이언트 (`ai/rag/vectorstore.py`) — Pinecone upsert 완성

### OCR ✅ 실서비스 인식 확인 완료 (2026-05-27)
- [x] **GPT-4o Vision OCR** (`app/services/ocr/clova_ocr.py`) — gpt-4o-mini, 한글·영문·숫자 인식 완료
  - Clova OCR → GPT-4o Vision으로 교체 (Clova ConnectTimeout 문제 해결)
  - base64 인코딩, 의료 문서 최적화 프롬프트, JPEG/PNG/WEBP 지원
  - OPENAI_API_KEY 재사용, 추가 설정 불필요
- [x] OCR 텍스트 파서 (`app/services/ocr/parser.py`) — ICD코드, 날짜, 약품명 정규식 + LLM 폴백
- [x] 랜딩페이지 OCR 업로드 섹션 (`index.html #try`) — 카메라/갤러리 선택 → 4단계 플로우

### DB 모델 / 스키마
- [x] `models/user.py`, `models/claim.py`, `models/session.py`, `models/waitlist.py`
- [x] `schemas/upload.py` (ParsedDocument, ParsedDrug), `schemas/analysis.py` (AnalyzeResponse, CoverageItem)
- [x] `schemas/result.py`, `schemas/waitlist.py`

### 테스트 (mock 기반, 외부 API 의존 없음)
- [x] `tests/test_api.py` — health check, analyze 엔드포인트, 잘못된 파일 형식
- [x] `tests/test_rag.py` — _build_query, _format_document_info, run_rag_pipeline
- [x] `tests/test_waitlist.py` — waitlist 등록 및 중복 처리
- [x] `tests/test_ocr.py` — OCR 파서 단위 테스트

### 프론트엔드 (랜딩페이지)
- [x] `index.html` — 히어로, 기능 소개, Waitlist CTA 섹션 (HTML/CSS/JS)
- [x] GitHub Pages 자동 배포 (main 브랜치 push 시)

---

## ❌ 미완료 작업 (우선순위 순)

### 🔴 높음 — 핵심 기능 동작에 필요

1. ~~**보험 약관 데이터 수집**~~ ✅ **완료** (`data/policies/raw/` 4개 JSON 수집됨)
   - `hyundai-silson-v4.json` — 현대해상 실손의료보험 Hi2204 (271,621자)
   - `hyundai-cancer-2401.json` — 현대해상 암보험 정액형 Hi2401 (368,007자)
   - `samsung-child-mykids.json` — 삼성화재 어린이보험 My아이플러스 (969,139자)
   - `axa-dental-2501.json` — AXA 치아보험 갱신형 2501 (154,757자)
   - **다음 작업**: `python3 -m ai.embeddings.embed_policies --policy-dir data/policies/raw` 실행 (Pinecone API 키 필요)

2. ~~**OCR 파서 개선**~~ ✅ **완료** (`app/services/ocr/parser.py`)
   - Stage 1 (정규식): hospital, department, diagnosis, total_amount, drug dosage/days 추출 완성
   - Stage 2 (LLM 폴백): 핵심 필드 2개 이상 누락 시 GPT-4o-mini로 자동 보완
   - `parse_medical_document_async()` 추가 — 업로드 엔드포인트에 연결 완료
   - 테스트 19/19 통과 ✅
   - Clova OCR 키/URL 저장 완료 (WSL 네트워크 제한으로 로컬 연결 불가, 배포 후 확인 필요)

3. ~~**API 키 설정 및 임베딩**~~ ✅ **완료**
   - `OPENAI_API_KEY` / `PINECONE_API_KEY` → `backend/.env` 등록 완료
   - LLM: Anthropic 계정 삭제로 **GPT-4o 전환** (`LLM_PROVIDER=openai`, `LLM_MODEL=gpt-4o`)
   - Pinecone 인덱스 `insurrx-policies` 생성 (AWS us-east-1, dim=1536)
   - 총 **1,358개 벡터** 업서트 완료 (4개 약관, 1,763,524자)
   - **엔드투엔드 테스트 통과** ✅
     - 입력: 급성상기도감염(J06.9), 28,500원, 현대해상 실손
     - 출력: `is_claimable=true`, `estimated_payout=18,500원`, confidence=0.9

4. ~~**Formspree 연결**~~ ✅ **완료**
   - `FORMSPREE_FORM_ID = xbdbyrrv` → GitHub Secret 등록 완료
   - GitHub Pages 배포 완료: https://songgwangsun.github.io/InsurRX/
   - 배포 HTML에 Formspree ID 정상 주입 확인

### 🟡 중간 — 기능 완성도

5. ~~**`GET /result/{session_id}` 구현**~~ ✅ **완료**
   - `AnalysisResult` DB 모델 생성 (`models/analysis_result.py`)
   - `POST /analyze` → 결과를 DB에 자동 저장
   - `GET /result/{session_id}` → DB 조회 + `created_at` 포함 반환, 없으면 404
   - `tests/conftest.py` 인메모리 DB 픽스처 추가
   - 전체 테스트 **27/27 통과** ✅

6. **Milvus 연동 구현** (`app/services/rag/retriever.py:26`)
   - `_query_milvus()` 가 현재 빈 배열 반환 (TODO 주석)
   - Pinecone 대신 자체 호스팅 원할 경우 필요

7. **파서 진단명/총액 추출 개선**
   - `parse_medical_document()` 에서 hospital, diagnosis, total_amount 미반환
   - RAG 정확도에 직접 영향

### 🟢 낮음 — 완성도/운영

8. **마이데이터 API 연동** (온보딩 Step 1)
   - 현재 보험 정보를 사용자가 직접 입력(policy_ids)하는 구조
   - 금융위 마이데이터 API로 내 보험 자동 불러오기

9. **카카오톡 챗봇 채널 연동**
   - 랜딩페이지 CTA에 카카오 채널 추가 버튼 있음
   - 실제 카카오 비즈니스 채널 생성 및 챗봇 시나리오 연결 필요

10. **CBT (클로즈드 베타 테스트)**
    - 로드맵 Day 8~9 목표
    - Waitlist 유저 초대 → 쿼리 로그 분석 → 응답 정확도 개선

---

## 🏗️ 아키텍처 요약

```
index.html (랜딩, GitHub Pages)
       │ POST /api/v1/...
       ▼
FastAPI (backend/app/main.py)
  ├── /upload  → Clova OCR → parser → ParsedDocument
  ├── /analyze → RAG pipeline
  │     ├── embedder (OpenAI text-embedding-3-small)
  │     ├── retriever (Pinecone vector search)
  │     └── chain (LangChain + Claude Sonnet 4.6)
  ├── /result  → DB 조회 (미구현)
  └── /waitlist → SQLite/PostgreSQL 저장

data/policies/raw/*.json
       │ python -m ai.embeddings.embed_policies
       ▼
Pinecone Index "insurrx-policies"
```

---

## 🔧 로컬 개발 환경 실행

```bash
# 1. 의존성 설치
cd backend && pip install -r requirements.txt

# 2. .env 설정 (backend/.env)
cp .env.example .env
# ANTHROPIC_API_KEY, PINECONE_API_KEY 등 입력

# 3. 서버 실행
uvicorn app.main:app --reload --port 8000

# 4. 테스트 실행
pytest tests/ -v
```

---

## 📁 핵심 파일 맵

| 파일 | 역할 |
|------|------|
| `backend/app/main.py` | FastAPI 앱 진입점 |
| `backend/app/core/config.py` | 전체 설정 (env 기반) |
| `backend/app/services/rag/pipeline.py` | RAG 오케스트레이터 |
| `ai/rag/chain.py` | LangChain + LLM 호출 |
| `ai/embeddings/embed_policies.py` | 약관 임베딩 CLI |
| `ai/rag/vectorstore.py` | Pinecone/Milvus 클라이언트 |
| `backend/app/services/ocr/parser.py` | OCR 텍스트 파싱 |
| `index.html` | 랜딩페이지 (GitHub Pages) |
| `.github/workflows/ci.yml` | CI (pytest) |
| `.github/workflows/deploy.yml` | CD (GitHub Pages) |

---

## ⚙️ 환경변수 (backend/.env)

```env
APP_ENV=development
DATABASE_URL=sqlite+aiosqlite:///./insurrx_local.db
VECTOR_DB_TYPE=pinecone
PINECONE_API_KEY=<필요>
PINECONE_INDEX=insurrx-policies
CLOVA_OCR_API_URL=<필요>
CLOVA_OCR_SECRET_KEY=<필요>
OPENAI_API_KEY=<임베딩용 필요>
ANTHROPIC_API_KEY=<LLM용 필요>
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-6
```
