"""
사용자 API 엔드포인트
질의응답 기능 제공
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any
import os
from pathlib import Path
import json

from rag.qa import answer_question

router = APIRouter()


class QuestionRequest(BaseModel):
    """질문 요청 모델"""
    knowledge_names: List[str] = Field(..., description="검색할 지식베이스 이름 리스트")
    question: str = Field(..., min_length=1, description="사용자 질문")
    top_k_per_knowledge: int = Field(default=3, ge=1, le=10, description="각 지식에서 검색할 문서 수")
    final_top_k: int = Field(default=5, ge=1, le=20, description="최종 사용할 문서 수")
    use_reasoning_model: bool = Field(default=False, description="True면 GPT-4 사용, False면 gpt-4o-mini")


class QuestionResponse(BaseModel):
    """질문 응답 모델"""
    answer: str
    sources: List[Dict[str, Any]]
    knowledge_stats: Dict[str, int]


@router.post("/ask", response_model=QuestionResponse)
async def ask_question(request: QuestionRequest):
    """
    질문에 대한 답변 생성
    
    - **knowledge_names**: 검색할 지식베이스 이름들 (복수 선택 가능)
    - **question**: 사용자 질문
    - **top_k_per_knowledge**: 각 지식에서 가져올 문서 수 (기본 3개)
    - **final_top_k**: 최종 사용할 문서 수 (기본 5개)
    """
    try:
        # 지식베이스 존재 여부 확인
        for knowledge_name in request.knowledge_names:
            base_dir = Path("document_sets") / knowledge_name
            if not base_dir.exists():
                raise HTTPException(
                    status_code=404,
                    detail=f"지식 '{knowledge_name}'이(가) 존재하지 않습니다."
                )
            
            chroma_dir = base_dir / "chroma_db"
            if not chroma_dir.exists():
                raise HTTPException(
                    status_code=400,
                    detail=f"지식 '{knowledge_name}'의 임베딩이 아직 생성되지 않았습니다."
                )
        
        # RAG 파이프라인 실행
        result = answer_question(
            knowledge_names=request.knowledge_names,
            question=request.question,
            top_k_per_knowledge=request.top_k_per_knowledge,
            final_top_k=request.final_top_k,
            use_reasoning_model=request.use_reasoning_model
        )
        
        return QuestionResponse(**result)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"답변 생성 중 오류 발생: {str(e)}"
        )


@router.get("/available-knowledge", response_model=List[Dict[str, str]])
async def get_available_knowledge():
    """
    임베딩이 완료된 사용 가능한 지식베이스 목록 조회
    
    Returns:
        [
            {
                "name": "지식명",
                "description": "간략소개"
            }
        ]
    """
    try:
        document_sets_dir = Path("document_sets")
        if not document_sets_dir.exists():
            return []
        
        available_knowledge = []
        
        for knowledge_dir in document_sets_dir.iterdir():
            if not knowledge_dir.is_dir():
                continue
            
            # 임베딩이 완료된 지식만 포함
            chroma_dir = knowledge_dir / "chroma_db"
            if not chroma_dir.exists():
                continue
            
            # 메타데이터 읽기
            metadata_path = knowledge_dir / "metadata.json"
            description = ""
            
            if metadata_path.exists():
                try:
                    with open(metadata_path, "r", encoding="utf-8") as f:
                        metadata = json.load(f)
                        description = metadata.get("description", "")
                except:
                    pass
            
            available_knowledge.append({
                "name": knowledge_dir.name,
                "description": description
            })
        
        # 이름순 정렬
        available_knowledge.sort(key=lambda x: x["name"])
        
        return available_knowledge
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"지식 목록 조회 중 오류 발생: {str(e)}"
        )