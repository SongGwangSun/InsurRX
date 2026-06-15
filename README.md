# InsurRX — AI 보험금 청구 자동화 서비스

> 처방전·영수증 사진 한 장으로 내 보험 청구 가능 여부와 예상 지급액을 1분 안에 확인합니다.

[![CI](https://github.com/SongGwangSun/InsurRX/actions/workflows/ci.yml/badge.svg)](https://github.com/SongGwangSun/InsurRX/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-55%20passed-brightgreen)](backend/tests/)

**서비스 링크**
- 랜딩페이지: https://song2nes.com/
- 사용자 대시보드: https://song2nes.com/dashboard.html
- 관리자 패널: https://song2nes.com/admin.html
- API 서버: https://magnificent-celebration-production-2dd9.up.railway.app
- 카카오톡 채널: https://pf.kakao.com/_xmxfjxjX

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| **OCR 분석** | GPT-4o Vision으로 처방전·영수증에서 상병코드·진단명·금액 추출 |
| **RAG 보상 분석** | Pinecone 벡터 검색 + LangChain + GPT-4o로 약관 대조 분석 |
| **개인 보험증권 등록** | PDF·이미지 업로드 → 자동 임베딩 → 개인 벡터 네임스페이스 |
| **카카오톡 챗봇** | 카카오 i 오픈빌더 스킬 서버 — 사진 전송만으로 분석 완료 |
| **분석 히스토리** | 과거 분석 결과 조회·삭제 |
| **관리자 패널** | 보험사·상품 CRUD, 회원 관리, 시스템 통계 |

---

## 아키텍처

```
GitHub Pages (index / dashboard / admin)
       │  HTTPS
       ▼
FastAPI on Railway (PostgreSQL)
  ├── /upload      → GPT-4o Vision OCR
  ├── /analyze     → 공개 약관 + 개인 보험증권 통합 RAG
  ├── /auth        → JWT 회원가입·로그인
  ├── /my/policies → 개인 보험증권 업로드·임베딩
  ├── /kakao/skill → 카카오 i 오픈빌더 스킬 서버
  └── /admin       → 보험사·회원 관리

Pinecone (insurrx-policies)
  ├── 기본 네임스페이스: 공개 약관 1,358 벡터
  └── user-{id}-xxxx: 개인 보험증권 (사용자별 격리)
```

---

## 기술 스택

| 계층 | 기술 |
|------|------|
| Frontend | HTML/CSS/JS (GitHub Pages) |
| Backend | FastAPI, SQLAlchemy, Pydantic v2 |
| DB | PostgreSQL (Railway), SQLite (개발) |
| AI/OCR | OpenAI GPT-4o Vision, GPT-4o |
| Vector DB | Pinecone (text-embedding-3-small, 1536차원) |
| RAG | LangChain 0.3 |
| 인증 | JWT (python-jose + bcrypt) |
| 배포 | Railway (백엔드), GitHub Pages (프론트엔드) |

---

## 로컬 개발 환경 실행

```bash
# 1. 의존성 설치
cd backend
pip install -r requirements.txt

# 2. 환경변수 설정
cp .env.example .env
# 아래 항목 입력:
# OPENAI_API_KEY=sk-...
# PINECONE_API_KEY=pcsk_...
# SECRET_KEY=your-secret-key

# 3. 서버 실행
uvicorn app.main:app --reload --port 8000

# 4. 테스트 실행
pytest tests/ -v
```

### 초기 데이터 설정 (최초 1회)

```bash
cd backend

# 관리자 계정 생성
ADMIN_EMAIL=admin@example.com ADMIN_NAME=관리자 ADMIN_PASSWORD=비밀번호 \
  python -m scripts.create_admin

# 보험사·상품 시드 데이터
python -m scripts.seed_insurers

# 공개 약관 임베딩 (Pinecone 필요)
python -m ai.embeddings.embed_policies --policy-dir data/policies/raw
```

---

## API 엔드포인트 요약

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/api/v1/upload/` | 이미지 → OCR → ParsedDocument |
| `POST` | `/api/v1/analyze/` | RAG 보상 분석 (JWT 선택) |
| `GET`  | `/api/v1/result/{session_id}` | 분석 결과 조회 |
| `POST` | `/api/v1/auth/register` | 회원가입 |
| `POST` | `/api/v1/auth/login` | 로그인 (JWT 발급) |
| `PATCH`| `/api/v1/auth/me` | 프로필 수정 |
| `POST` | `/api/v1/auth/me/change-password` | 비밀번호 변경 |
| `POST` | `/api/v1/my/policies/upload` | 개인 보험증권 업로드 |
| `GET`  | `/api/v1/my/policies/` | 내 보험증권 목록 |
| `GET`  | `/api/v1/my/analyses/` | 분석 히스토리 |
| `GET`  | `/api/v1/insurers/` | 보험사+상품 목록 |
| `GET`  | `/api/v1/admin/stats` | 시스템 통계 (관리자) |
| `GET`  | `/api/v1/admin/users` | 회원 목록 (관리자) |
| `POST` | `/api/v1/kakao/skill` | 카카오 오픈빌더 스킬 서버 |
| `GET`  | `/health` | 서버 상태 확인 |

---

## 카카오 오픈빌더 연동

스킬 서버 URL:
```
POST https://magnificent-celebration-production-2dd9.up.railway.app/api/v1/kakao/skill
```

대화 흐름:
```
채널 진입 → 메인 메뉴
  ├─ 보험금 분석 → "사진 전송" 안내
  │     → 이미지 수신 → 약관 선택
  │           → 백그라운드 OCR+RAG (5초 제한 우회)
  │                 → 결과 확인 → 카드 출력
  └─ 최근 결과 / 도움말
```

---

## 환경변수 (backend/.env)

```env
APP_ENV=development
DATABASE_URL=sqlite+aiosqlite:///./insurrx_local.db
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=pcsk_...
PINECONE_INDEX=insurrx-policies
SECRET_KEY=your-jwt-secret
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
```

---

## 테스트

```bash
cd backend
pytest tests/ -v
# 55 passed
```

---

## 라이선스

© 2026 InsurRX — 2026ICT 과정 프로젝트
