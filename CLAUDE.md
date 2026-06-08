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

### 백엔드 API
- [x] `POST /api/v1/upload/` — 이미지 업로드 → GPT-4o Vision OCR → 파싱 결과 반환 ✅
- [x] `POST /api/v1/analyze/` — 파싱 문서 → 공개 약관 + 개인 보험증권 통합 RAG → 보상 분석
  - JWT 선택 인증: 비로그인(공개 약관만) / 로그인(개인 업로드 보험증권 자동 포함)
  - `policy_ids` 선택사항으로 변경 (기본값 빈 배열)
- [x] `POST /api/v1/waitlist/` — Waitlist 이메일 저장 (중복 방지 포함)
- [x] `GET  /api/v1/result/{session_id}` — 분석 결과 조회 ✅
- [x] `POST /api/v1/auth/register` — 회원가입 (JWT 토큰 반환)
- [x] `POST /api/v1/auth/login`    — 로그인 (OAuth2PasswordBearer)
- [x] `GET  /api/v1/auth/me`       — 내 정보 조회
- [x] `POST /api/v1/my/policies/upload` — 보험증권 업로드 → OCR/PDF → 임베딩 → Pinecone (백그라운드)
- [x] `GET/DELETE /api/v1/my/policies/` — 내 보험증권 목록·삭제 + Pinecone 네임스페이스 정리
- [x] `GET/POST/PATCH/DELETE /api/v1/insurers/` — 보험사 CRUD (관리자 쓰기 전용)
- [x] `GET/POST/PATCH/DELETE /api/v1/insurers/{id}/products/` — 상품 CRUD

### AI / RAG 파이프라인
- [x] LangChain RAG 체인 (`ai/rag/chain.py`) — Claude Sonnet 4.6 / GPT-4o 선택 가능
- [x] 보상 분석 프롬프트 템플릿 (`ai/rag/prompt_templates.py`)
- [x] 임베딩 서비스 (`app/services/rag/embedder.py`) — OpenAI text-embedding-3-small
- [x] Vector DB 검색 (`app/services/rag/retriever.py`) — Pinecone 연동 + **개인 네임스페이스 통합 검색**
- [x] RAG 파이프라인 오케스트레이터 (`app/services/rag/pipeline.py`) — `user_namespaces` 파라미터 추가
- [x] 약관 임베딩 스크립트 (`ai/embeddings/embed_policies.py`) — CLI 실행 가능
- [x] Vectorstore 클라이언트 (`ai/rag/vectorstore.py`) — Pinecone upsert 완성
- [x] 사용자 보험증권 임베딩 서비스 (`app/services/user_policy_service.py`) — PDF/이미지 → 청킹 → Pinecone

### OCR ✅ 실서비스 인식 확인 완료 (2026-05-27)
- [x] **GPT-4o Vision OCR** (`app/services/ocr/clova_ocr.py`) — gpt-4o-mini, 한글·영문·숫자 인식 완료
- [x] OCR 텍스트 파서 (`app/services/ocr/parser.py`) — ICD코드, 날짜, 약품명 정규식 + LLM 폴백
- [x] 랜딩페이지 OCR 업로드 섹션 (`index.html #try`)

### 인증 / 회원
- [x] JWT 인증 (`app/core/security.py`) — bcrypt 해싱, python-jose 토큰
- [x] User 모델 (`app/models/user.py`) — email, name, password_hash, is_admin
- [x] `get_optional_user` 의존성 — 비로그인도 허용하는 선택적 인증

### 보험사 / 상품 관리
- [x] Insurer + InsuranceProduct 모델 (`app/models/insurer.py`)
- [x] 관리자 패널 (`admin.html`) — 보험사·상품 CRUD
- [x] 초기 데이터 시드 (`scripts/seed_insurers.py`) — 현대해상·삼성화재·AXA·DB·KB·메리츠
- [x] 관리자 계정 생성 CLI (`scripts/create_admin.py`)

### DB 모델 / 스키마
- [x] `models/user.py`, `models/insurer.py`, `models/user_policy.py`
- [x] `models/claim.py`, `models/session.py`, `models/waitlist.py`, `models/analysis_result.py`
- [x] `schemas/user.py`, `schemas/insurer.py`, `schemas/user_policy.py`
- [x] `schemas/upload.py`, `schemas/analysis.py`, `schemas/result.py`, `schemas/waitlist.py`

### 카카오톡 챗봇 연동 ✅ (2026-06-08)
- [x] `KakaoSession` 모델 — 대화 상태 관리 (idle/wait_image/processing/done/error)
- [x] `POST /api/v1/kakao/skill` — 카카오 i 오픈빌더 스킬 서버
  - 이미지 수신 → 약관 선택 → 비동기 OCR+RAG → 결과 확인 폴링
  - 카카오 5초 응답 제한 대응: BackgroundTasks 비동기 파이프라인
- [x] response_builder — basicCard/simpleText/quickReplies 포맷 빌더
- [x] 랜딩페이지: 히어로 CTA 카카오 채팅 직링크 + 웹 대시보드 병렬 버튼

### 테스트 **55/55 통과** ✅ (2026-06-08)
- [x] `tests/test_api.py` — health check, analyze, 파일 형식 검증
- [x] `tests/test_rag.py` — RAG 파이프라인 단위 테스트
- [x] `tests/test_waitlist.py` — waitlist 등록 및 중복 처리
- [x] `tests/test_ocr.py` — OCR 파서 단위 테스트 (19개)
- [x] `tests/test_result.py` — 결과 조회 엔드포인트
- [x] `tests/test_auth.py` — 회원가입·로그인·인증 (6개)
- [x] `tests/test_insurers.py` — 보험사·상품 CRUD (6개)
- [x] `tests/test_user_policies.py` — 업로드·목록·삭제·접근제어 (6개)

### 프론트엔드
- [x] `index.html` — 랜딩페이지 (GitHub Pages 자동 배포)
- [x] `dashboard.html` — 회원 대시보드
  - **탭 1: 보상 분석** — 처방전 드래그&드롭 → OCR → 결과 확인 → AI 분석 → 결과 카드
  - **탭 2: 내 보험증권** — 업로드(상품 선택+파일) / 목록(상태 배지) / 삭제
- [x] `admin.html` — 관리자 패널 (보험사·상품 CRUD)

---

## ❌ 미완료 작업 (우선순위 순)

### 🔴 높음

1. **카카오 i 오픈빌더 시나리오 수동 설정** (외부 작업)
   - 스킬 URL: `POST https://magnificent-celebration-production-2dd9.up.railway.app/api/v1/kakao/skill`
   - 발화 블록 연결: 처음으로, 보험금 분석, 결과 확인, 도움말, 이미지 수신 이벤트
   - 카카오 비즈니스 채널 → 오픈빌더 연결: business.kakao.com

2. **CBT (클로즈드 베타 테스트)**
   - Waitlist 유저 초대 → 실제 처방전으로 테스트
   - 쿼리 로그 분석 → RAG 응답 정확도 개선

### 🟢 낮음

3. **마이데이터 API 연동** — 금융위 마이데이터로 내 보험 자동 불러오기
4. **원클릭 청구 대행** — 보험사 API 연동 (파일럿)
5. **가족 계정 통합 관리**
6. **Milvus 연동** (`app/services/rag/retriever.py` — 자체 호스팅 원할 때)

---

## 🏗️ 아키텍처 요약

```
index.html / dashboard.html (GitHub Pages)
       │ POST /api/v1/...  (+ Bearer Token)
       ▼
FastAPI (backend/app/main.py)
  ├── /auth         → JWT 회원가입·로그인
  ├── /upload       → GPT-4o Vision OCR → ParsedDocument
  ├── /analyze      → 공개 약관 + 개인 보험증권 통합 RAG → 보상 분석
  │     ├── embedder    (OpenAI text-embedding-3-small)
  │     ├── retriever   (Pinecone: 공개 네임스페이스 + user-{id}-xxx 네임스페이스)
  │     └── chain       (LangChain + GPT-4o)
  ├── /my/policies  → 개인 보험증권 업로드 → 임베딩 → Pinecone (백그라운드)
  ├── /insurers     → 보험사·상품 관리 (관리자)
  ├── /result       → DB 조회
  └── /waitlist     → PostgreSQL 저장

data/policies/raw/*.json
       │ python -m ai.embeddings.embed_policies
       ▼
Pinecone Index "insurrx-policies"
  ├── (기본 네임스페이스) 공개 약관 1,358 벡터
  └── user-{id}-xxxx      개인 보험증권 (사용자별 격리)
```

---

## 🔧 로컬 개발 환경 실행

```bash
# 1. 의존성 설치
cd backend && pip install -r requirements.txt

# 2. .env 설정 (backend/.env)
cp .env.example .env
# OPENAI_API_KEY, PINECONE_API_KEY, SECRET_KEY 입력

# 3. 서버 실행
uvicorn app.main:app --reload --port 8000

# 4. 테스트 실행
pytest tests/ -v

# 5. 초기 데이터 (최초 1회)
python -m scripts.create_admin
python -m scripts.seed_insurers
```

---

## 📁 핵심 파일 맵

| 파일 | 역할 |
|------|------|
| `backend/app/main.py` | FastAPI 앱 진입점 |
| `backend/app/core/config.py` | 전체 설정 (env 기반) |
| `backend/app/core/security.py` | JWT·bcrypt·get_optional_user |
| `backend/app/services/rag/pipeline.py` | RAG 오케스트레이터 |
| `backend/app/services/rag/retriever.py` | Pinecone 공개+개인 통합 검색 |
| `backend/app/services/user_policy_service.py` | 개인 보험증권 임베딩 파이프라인 |
| `ai/rag/chain.py` | LangChain + LLM 호출 |
| `ai/embeddings/embed_policies.py` | 공개 약관 임베딩 CLI |
| `backend/scripts/seed_insurers.py` | 보험사·상품 초기 데이터 |
| `backend/scripts/create_admin.py` | 관리자 계정 생성 CLI |
| `backend/app/services/ocr/parser.py` | OCR 텍스트 파싱 |
| `index.html` | 랜딩페이지 (GitHub Pages) |
| `dashboard.html` | 회원 대시보드 (분석+보험증권 관리) |
| `admin.html` | 관리자 패널 |
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
OPENAI_API_KEY=<임베딩·OCR용 필요>
ANTHROPIC_API_KEY=<LLM용, 선택>
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
SECRET_KEY=<JWT 서명키, 운영 시 필수 변경>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080
```
