"""
관리자 API - 지식 기반 문서 관리 및 표 추출
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from typing import List, Dict, Optional
import shutil
from pathlib import Path
import sys
import os
import fitz  # PyMuPDF
import base64
from io import BytesIO
import pandas as pd
import json
from datetime import datetime

# pdf_processor 모듈 import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pdf_processor.table_extractor import TableExtractor

router = APIRouter(prefix="/api/admin", tags=["admin"])

# 기본 디렉토리
BASE_DIR = Path("./document_sets")
BASE_DIR.mkdir(parents=True, exist_ok=True)


def get_knowledge_dir(knowledge_name: str) -> Path:
    """지식명에 해당하는 디렉토리 경로 반환"""
    knowledge_dir = BASE_DIR / knowledge_name
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    
    # 하위 폴더 생성
    (knowledge_dir / "pdf").mkdir(exist_ok=True)
    (knowledge_dir / "csv").mkdir(exist_ok=True)
    (knowledge_dir / "images").mkdir(exist_ok=True)
    
    return knowledge_dir


@router.post("/save-knowledge-metadata")
async def save_knowledge_metadata(request: dict):
    """지식 메타데이터(간략소개) 저장"""
    try:
        knowledge_name = request.get('knowledge_name')
        description = request.get('description')
        
        if not knowledge_name:
            raise HTTPException(status_code=400, detail="지식명이 필요합니다.")
        
        knowledge_dir = get_knowledge_dir(knowledge_name)
        
        # 기존 메타데이터 로드 (있다면)
        metadata_path = knowledge_dir / "metadata.json"
        if metadata_path.exists():
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        else:
            metadata = {
                "name": knowledge_name,
                "created_at": datetime.now().isoformat()
            }
        
        # 설명 업데이트
        metadata["description"] = description
        metadata["updated_at"] = datetime.now().isoformat()
        
        # 저장
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        return {
            "status": "success",
            "message": "메타데이터가 저장되었습니다.",
            "metadata": metadata
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"메타데이터 저장 실패: {str(e)}")


@router.get("/get-knowledge-metadata/{knowledge_name}")
async def get_knowledge_metadata(knowledge_name: str):
    """지식 메타데이터 조회"""
    try:
        knowledge_dir = get_knowledge_dir(knowledge_name)
        metadata_path = knowledge_dir / "metadata.json"
        
        if not metadata_path.exists():
            return {
                "name": knowledge_name,
                "description": "",
                "exists": False
            }
        
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        metadata["exists"] = True
        return metadata
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"메타데이터 조회 실패: {str(e)}")


@router.get("/list-knowledge")
async def list_knowledge():
    """지식 목록 조회"""
    try:
        knowledge_list = []
        
        for knowledge_dir in BASE_DIR.iterdir():
            if knowledge_dir.is_dir():
                pdf_count = len(list((knowledge_dir / "pdf").glob("*.pdf")))
                csv_count = len(list((knowledge_dir / "csv").glob("*.csv")))
                
                # 메타데이터 로드
                metadata_path = knowledge_dir / "metadata.json"
                description = ""
                if metadata_path.exists():
                    with open(metadata_path, "r", encoding="utf-8") as f:
                        metadata = json.load(f)
                        description = metadata.get("description", "")
                
                knowledge_list.append({
                    "name": knowledge_dir.name,
                    "description": description,
                    "pdf_count": pdf_count,
                    "csv_count": csv_count
                })
        
        return {"knowledge_list": knowledge_list}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"목록 조회 실패: {str(e)}")


@router.post("/upload-pdf")
async def upload_pdf(knowledge_name: str, file: UploadFile = File(...)):
    """PDF 파일 업로드"""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")
    
    knowledge_dir = get_knowledge_dir(knowledge_name)
    pdf_dir = knowledge_dir / "pdf"
    file_path = pdf_dir / file.filename
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        file_size = file_path.stat().st_size
        
        return {
            "filename": file.filename,
            "knowledge_name": knowledge_name,
            "path": str(file_path),
            "size": file_size
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 업로드 실패: {str(e)}")


@router.post("/extract-tables")
async def extract_tables(knowledge_name: str, pdf_filename: str):
    """업로드된 PDF에서 표 추출"""
    knowledge_dir = get_knowledge_dir(knowledge_name)
    pdf_path = knowledge_dir / "pdf" / pdf_filename
    
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF 파일을 찾을 수 없습니다.")
    
    try:
        csv_dir = knowledge_dir / "csv"
        extractor = TableExtractor(output_dir=str(csv_dir))
        tables_info = extractor.extract_tables_from_pdf(str(pdf_path))
        
        # DataFrame 데이터를 JSON으로 변환
        tables_response = []
        for table in tables_info:
            # DataFrame을 리스트로 변환 (편집용)
            data_list = table['data'].values.tolist()
            columns = table['data'].columns.tolist()
            
            tables_response.append({
                "page": table['page'],
                "table_index": table['table_index'],
                "shape": list(table['shape']),
                "preview": table['preview'],
                "columns": columns,
                "data": data_list
            })
        
        return {
            "total_tables": len(tables_response),
            "tables": tables_response
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"표 추출 실패: {str(e)}")


@router.get("/get-pdf-page-image/{knowledge_name}/{pdf_filename}/{page_number}")
async def get_pdf_page_image(knowledge_name: str, pdf_filename: str, page_number: int):
    """PDF 특정 페이지를 이미지로 변환"""
    knowledge_dir = get_knowledge_dir(knowledge_name)
    pdf_path = knowledge_dir / "pdf" / pdf_filename
    
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF 파일을 찾을 수 없습니다.")
    
    try:
        doc = fitz.open(str(pdf_path))
        
        if page_number < 1 or page_number > len(doc):
            raise HTTPException(status_code=400, detail="잘못된 페이지 번호입니다.")
        
        page = doc[page_number - 1]
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        img_bytes = pix.tobytes("png")
        img_base64 = base64.b64encode(img_bytes).decode()
        
        doc.close()
        
        return {
            "image_base64": img_base64,
            "page": page_number
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"이미지 변환 실패: {str(e)}")


@router.post("/save-table-to-csv")
async def save_table_to_csv(
    knowledge_name: str,
    pdf_filename: str,
    page: int,
    table_index: int,
    table_data: dict,
    description: str
):
    """편집된 표 데이터를 CSV로 저장"""
    try:
        knowledge_dir = get_knowledge_dir(knowledge_name)
        csv_dir = knowledge_dir / "csv"
        
        data = table_data.get("data", [])
        columns = table_data.get("columns", [])
        
        if not data:
            raise HTTPException(status_code=400, detail="표 데이터가 비어있습니다.")
        
        # DataFrame 생성
        df = pd.DataFrame(data, columns=columns)
        
        # CSV 파일명 생성
        base_name = Path(pdf_filename).stem
        if description:
            filename = f"{base_name}_표{table_index}_{description}.csv"
        else:
            filename = f"{base_name}_표{table_index}_페이지{page}.csv"
        
        filepath = csv_dir / filename
        
        # CSV 저장 (UTF-8 with BOM for Excel compatibility)
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        
        return {
            "csv_filename": filename,
            "csv_path": str(filepath),
            "download_url": f"/api/admin/download-csv/{knowledge_name}/{filename}"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CSV 저장 실패: {str(e)}")


@router.get("/download-csv/{knowledge_name}/{filename}")
async def download_csv(knowledge_name: str, filename: str):
    """CSV 파일 다운로드"""
    knowledge_dir = get_knowledge_dir(knowledge_name)
    file_path = knowledge_dir / "csv" / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="text/csv"
    )


@router.get("/list-files/{knowledge_name}")
async def list_files(knowledge_name: str):
    """특정 지식의 파일 목록 조회"""
    try:
        knowledge_dir = get_knowledge_dir(knowledge_name)
        
        pdfs = []
        for pdf_path in (knowledge_dir / "pdf").glob("*.pdf"):
            pdfs.append({
                "filename": pdf_path.name,
                "size": pdf_path.stat().st_size,
                "uploaded_at": pdf_path.stat().st_mtime
            })
        
        csvs = []
        for csv_path in (knowledge_dir / "csv").glob("*.csv"):
            csvs.append({
                "filename": csv_path.name,
                "size": csv_path.stat().st_size,
                "created_at": csv_path.stat().st_mtime
            })
        
        pdfs.sort(key=lambda x: x['uploaded_at'], reverse=True)
        csvs.sort(key=lambda x: x['created_at'], reverse=True)
        
        return {
            "pdfs": pdfs,
            "csvs": csvs
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"목록 조회 실패: {str(e)}")

@router.post("/start-embedding")
async def start_embedding(knowledge_name: str, force_recreate: bool = False):
    """지식 임베딩 시작"""
    try:
        from rag.embeddings import embed_knowledge
        
        result = embed_knowledge(
            knowledge_name=knowledge_name,
            force_recreate=force_recreate
        )
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"임베딩 실패: {str(e)}")