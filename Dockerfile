FROM python:3.12-slim

# 시스템 의존성 (pdfplumber 등)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# backend + ai 모두 복사
COPY backend/ ./backend/
COPY ai/      ./ai/

# /app      → ai.rag.chain 등 ai/ 패키지 import
# /app/backend → app.core.config 등 FastAPI 패키지 import
ENV PYTHONPATH=/app:/app/backend

# 의존성 설치
RUN pip install --no-cache-dir -r backend/requirements.txt

WORKDIR /app/backend

# Railway는 $PORT 환경변수를 주입 — 없으면 8000 사용
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
