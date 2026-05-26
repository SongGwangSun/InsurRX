#!/bin/bash
# Railway 배포 시작 스크립트
# Railpack Python 빌더로 FastAPI 서버 실행

export PYTHONPATH="/app:/app/backend:${PYTHONPATH}"
cd /app/backend
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
