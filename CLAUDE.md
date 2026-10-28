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
- [x] `POST /api/v1/analyze/` — 파싱 문서 → 표준약관 RAG → 보상 분석
  - JWT 선택 인증: 비로그인·로그인 모두 표준약관 기준 (로그인 시 업로드 증권이 있으면 함께 검색)
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
- [x] 약관 임베딩 스크립트 (`ai/embeddings/embed_policies.py`) — 표준약관 → `standard-terms` 네임스페이스
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

### 표준약관 전환 + 화면 정리 ✅ (2026-10-26)
- [x] 보험사별 상품 약관(`data/policies/raw`) 제거 → **표준약관**(보험업감독업무시행세칙 [별표15], 실손 2026.5.6. 개정) 사용
  - `scripts/build_standard_terms.py` — 별표15 PDF → 조항 단위 JSON (`data/policies/standard/`: 실손 기본형·특약1·특약2)
  - Pinecone `standard-terms` 네임스페이스. 실손 119 벡터만 `policy_id` 필터로 검색 (`retriever.SILSON_POLICY_IDS`). 질병·상해 50 벡터는 네임스페이스에 남아 있으나 검색하지 않음(재임베딩하면 지워짐). 기본 네임스페이스의 예전 보험사 약관도 미사용
  - 검색: 표준약관 상위 15건 → 조항당 2건 제한 → 6건 (`retriever.py`), `policy_ids`·보험사 선택 제거
  - RAG 시스템 프롬프트에 표준약관 보상 기준(급여 통원 공제 1만/2만원·20%, 특약1 3만원·30%, 특약2 5만원·50% 등) 명시. 예전 기본값 그대로인 DB 프롬프트는 시작 시 자동 갱신
- [x] 대시보드: 마이데이터·내 보험증권 탭, 가입 후 증권 등록 온보딩, 보험사 약관 선택, 마이데이터 진료내역 대조 제거 (백엔드 API는 유지)
- [x] 랜딩: 보험 선택 단계·보험사 추가 모달·요금제 섹션 제거, 미구현 기능(원클릭 청구·가족 관리·마이데이터) 문구 정리, 보안 문구를 실제 구현 기준으로 수정, OCR 오류 화면 버그 수정

### 멘토 의견 반영 — 실손 예상 환급금 조회 + 개인정보 ✅ (2026-10-28)
> 기획서: `docs/기획서_InsurRX_v1.2.md` (멘토 의견 11개와 반영 위치). 제출용 HWP 사업계획서는 수동 반영 필요
- [x] 실손 집중: 질병·상해 표준약관 검색 제외, 화면 용어 "예상 환급금 조회"로 통일, 결과에 "청구하는 방법"(실손24·보험사 앱, 필요 서류) 안내
- [x] 랜딩 수치를 출처 있는 실손 통계로 교체 (보유계약 3,622만 건, 미청구 약 2,500억 원, 소액 포기 80.1%), 데모의 미구현 UI(음성·채팅 입력·바로 청구) 제거
- [x] `POST /upload/`는 `health_consent=true`(Form) 없으면 400 — 랜딩·대시보드에서 민감정보·국외 이전(OpenAI) 별도 동의 체크 후에만 전송
  - ⚠ 카카오 연동을 다시 켜면 카카오 OCR 경로에도 같은 동의 절차를 넣어야 함
- [x] `privacy.html` 개인정보 처리방침 (위탁·국외 이전 표, 보유 기간, 보호책임자), 회원가입 시 동의 체크
- [x] `DELETE /auth/me` 회원 탈퇴 (비밀번호 확인) — 분석 결과·카카오 세션·보험증권(Pinecone 네임스페이스)·로그인 이력·토큰 삭제, 대시보드 계정 탭에 버튼
- [x] `app/services/retention.py` — 비회원 분석 결과 24시간(`GUEST_RESULT_RETENTION_HOURS`), 로그인 이력 1년(`LOGIN_HISTORY_RETENTION_DAYS`) 지나면 삭제. 앱 시작 시와 6시간마다 실행
- [ ] 회원 분석 결과의 진단명·병원명 원문 저장 최소화, 토큰 사용량(건당 원가) 기록

### 카카오톡 챗봇 연동 ✅ (2026-06-08)
> ⏸ **2026-10-26 임시 제외** — `KAKAO_ENABLED=false`(기본값)면 `/kakao/*`·`/auth/kakao-link*` 404, 랜딩·대시보드 카카오 UI 숨김. 다시 켜려면 Railway env `KAKAO_ENABLED=true` + `dashboard.html`의 `KAKAO_ENABLED` 상수 + `index.html` 히어로 주석 복원.
- [x] `KakaoSession` 모델 — 대화 상태 관리 (idle/wait_image/processing/done/error)
- [x] `POST /api/v1/kakao/skill` — 카카오 i 오픈빌더 스킬 서버
  - 이미지 수신 → 약관 선택 → 비동기 OCR+RAG → 결과 확인 폴링
  - 카카오 5초 응답 제한 대응: BackgroundTasks 비동기 파이프라인
- [x] response_builder — basicCard/simpleText/quickReplies 포맷 빌더
- [x] 랜딩페이지: 히어로 CTA 카카오 채팅 직링크 + 웹 대시보드 병렬 버튼

### 카카오톡 보험증권·약관·약봉투 업로드 ✅ (2026-10-18)
- [x] 계정 연결 — 카톡 첫 등록 시 카카오 전용 회원 자동 생성(`kakao-…@kakao.song2nes.com`), 웹 `POST /auth/kakao-link-code` 발급 코드를 카톡에 `연결 <코드>` 입력 → 보험·분석 이력 웹 계정으로 이전 (`app/services/kakao/account.py`, `KakaoLinkCode`)
- [x] 카톡 `내 보험` 메뉴 — 보험증권 사진 등록(최대 10장, 수신 즉시 다운로드 → 증권용 OCR → 주민번호·전화번호 마스킹 → 임베딩), 약관 연결(보험사→상품 선택, 파일 없는 `UserPolicy`)
- [x] 보안 이미지 플러그인 `secureUrls: List(...)` 형식 + 여러 장 수신 지원
- [x] 약봉투 — 문서 종류 판별(`detect_doc_type`), 여러 장 병합(`merge_parsed_documents`), 약봉투 단독 시 신뢰도 하향 지시·청구 서류 안내
- [x] 카톡·웹 분석 모두 `collect_policy_sources()`로 내 보험(마이데이터·연결 약관·업로드 증권) 포함
- [ ] **외부 작업**: 오픈빌더에 `내 보험`·`보험증권 등록`·`약관 연결`·`계정 연결` 발화 블록 추가(또는 폴백 블록을 스킬에 연결), 이미지 파라미터는 보안 이미지 플러그인 다중 장 허용

### 자동 로그인 / 로그인 이력 ✅ (2026-06-09)
- [x] `RefreshToken` 모델 — SHA-256 해시 저장, 만료일, 폐기 플래그
- [x] `LoginHistory` 모델 — user_id, email, IP, User-Agent, 기기유형, success/failed
- [x] `POST /api/v1/auth/refresh` — Refresh Token rotation → 새 Access Token
- [x] `POST /api/v1/auth/logout` — Refresh Token 서버 폐기
- [x] `GET  /api/v1/auth/login-history` — 최근 20건 로그인 이력 조회
- [x] Access Token 60분 / Refresh Token 30일(유지 체크) · 1일(미체크)
- [x] 프론트엔드: "로그인 상태 유지" 체크박스, `apiFetch()` 401 자동 갱신, 계정 탭 이력 카드

### 비밀번호 재설정 (메일 링크) ✅ (2026-06-15)
- [x] `PasswordResetToken` 모델 — SHA-256 1회용 토큰, 만료(기본 30분), is_used
- [x] `POST /api/v1/auth/forgot-password` — 이메일로 재설정 링크 발송. 계정 존재 노출 방지(항상 200)
- [x] `POST /api/v1/auth/reset-password` — 토큰 검증 후 새 비밀번호 설정 + Refresh Token 전부 폐기
- [x] Resend 메일 발송 (`app/services/email.py`, httpx). `RESEND_API_KEY` 미설정 시 dev 모드(링크 로그 출력)
- [x] 프론트엔드: 로그인 모달 "비밀번호를 잊으셨나요?" → 이메일 입력 / 메일 링크(`?reset_token=`) 진입 시 새 비밀번호 설정
- [x] CORS 허용 도메인에 `song2nes.com` 추가 (커스텀 도메인 이전 대응)
- [ ] **외부 작업**: Resend 가입 → API 키 발급 → `song2nes.com` 도메인 인증(SPF/DKIM) → `MAIL_FROM`을 `noreply@song2nes.com`으로 교체, Railway env에 `RESEND_API_KEY` 등록

### UX 개선 ✅ (2026-06-09)
- [x] **온보딩 플로우** — 회원가입 후 보험증권 등록 3단계 모달 (가입완료→증권등록→분석시작), 등록 완료 시 보상 분석 탭으로 자동 이동, "나중에" 시 내 보험증권 탭으로 이동
- [x] **모바일 햄버거 메뉴** — 767px 이하에서 탭바 숨김, 좌측 상단 햄버거 버튼, 슬라이드 드로어, 오버레이 클릭 닫기
- [x] 모바일 현재 탭 레이블 표시, 반응형 업로드 폼

### 테스트 **63/63 통과** ✅ (2026-06-09)
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

1. **카카오 i 오픈빌더 시나리오 수동 설정** (외부 작업) — ⏸ 카카오 연동 임시 제외 중
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
  ├── /analyze      → 실손 표준약관 RAG → 예상 환급금
  │     ├── embedder    (OpenAI text-embedding-3-small)
  │     ├── retriever   (Pinecone: 공개 네임스페이스 + user-{id}-xxx 네임스페이스)
  │     └── chain       (LangChain + GPT-4o)
  ├── /my/policies  → 개인 보험증권 업로드 → 임베딩 → Pinecone (백그라운드)
  ├── /insurers     → 보험사·상품 관리 (관리자)
  ├── /result       → DB 조회
  └── /waitlist     → PostgreSQL 저장

data/policies/standard/*.json   (scripts/build_standard_terms.py ← 별표15 PDF)
       │ python -m ai.embeddings.embed_policies
       ▼
Pinecone Index "insurrx-policies"
  ├── standard-terms        실손 표준약관 119 벡터만 검색 (질병·상해 50 벡터·기본 네임스페이스 예전 약관은 미사용)
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
| `ai/embeddings/embed_policies.py` | 표준약관 임베딩 CLI |
| `scripts/build_standard_terms.py` | 별표15 PDF → 표준약관 조항 JSON |
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
