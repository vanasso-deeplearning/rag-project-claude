"""
FastAPI Backend 메인 애플리케이션
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

# 환경변수 로드
load_dotenv()

# API 라우터 import
from api.admin import router as admin_router
from api.user import router as user_router

# FastAPI 앱 생성
app = FastAPI(
    title="RAG Knowledge Base API",
    description="스테이블코인 지식 기반 RAG 시스템",
    version="1.0.0"
)

# CORS 설정 (Streamlit과 통신하기 위해 필요)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발 환경에서는 모든 origin 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(admin_router)
app.include_router(user_router, prefix="/api/user", tags=["user"])

# 루트 엔드포인트
@app.get("/")
async def root():
    """API 상태 확인"""
    return {
        "message": "RAG Knowledge Base API",
        "status": "running",
        "version": "1.0.0"
    }

# Health check
@app.get("/health")
async def health_check():
    """서버 상태 체크"""
    return {
        "status": "healthy",
        "backend": "ok"
    }


if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("BACKEND_HOST", "localhost")
    port = int(os.getenv("BACKEND_PORT", 8000))
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True  # 개발 모드에서 코드 변경 시 자동 재시작
    )