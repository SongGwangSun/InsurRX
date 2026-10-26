"""
Railway Railpack 진입점.
Railpack이 FastAPI를 감지하여 uvicorn으로 자동 실행합니다.
"""
import os
import sys

# backend/ 와 루트를 Python 경로에 추가
_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_root, "backend"))
sys.path.insert(0, _root)

from app.main import app

__all__ = ["app"]
