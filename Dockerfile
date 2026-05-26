FROM python:3.12-slim

# 시스템 의존성 (pdfplumber, asyncpg 등)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# backend + ai 모두 복사
COPY backend/ ./backend/
COPY ai/      ./ai/

# Python 경로 설정
# /app      → ai.rag.chain 등 ai/ 패키지
# /app/backend → app.core.config 등 FastAPI 패키지
ENV PYTHONPATH=/app:/app/backend

# 의존성 설치
RUN pip install --no-cache-dir -r backend/requirements.txt

WORKDIR /app/backend

# Railway는 $PORT 환경변수를 주입
EXPOSE 8000

CMD ["sh", "-c", "echo 'PORT='$PORT && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level info"]
