"""
RAG 임베딩 모듈
PDF/CSV 문서를 로드하고 청크로 분할한 후 ChromaDB에 임베딩
"""
import os
import re
import hashlib
from pathlib import Path
from typing import List, Dict
import pandas as pd
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.schema import Document
import fitz  # PyMuPDF


class KnowledgeEmbedder:
    """지식 베이스 임베딩 클래스"""
    
    def __init__(self, knowledge_name: str, base_dir: str = "./document_sets"):
        """
        Args:
            knowledge_name: 지식명
            base_dir: 문서 저장 기본 디렉토리
        """
        self.knowledge_name = knowledge_name
        self.base_dir = Path(base_dir)
        self.knowledge_dir = self.base_dir / knowledge_name
        
        hash_suffix = hashlib.md5(knowledge_name.encode('utf-8')).hexdigest()[:8]
        self.collection_name = f"kb_{hash_suffix}"
        
        # OpenAI API 키 확인
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다")
        
        # 임베딩 모델
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        
        # 텍스트 분할기
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
        )
        
        # ChromaDB 저장 경로
        self.chroma_dir = self.knowledge_dir / "chroma_db"
        self.chroma_dir.mkdir(parents=True, exist_ok=True)
    
    def load_pdf_documents(self) -> List[Document]:
        """PDF 파일들을 로드하여 Document 리스트로 변환"""
        documents = []
        pdf_dir = self.knowledge_dir / "pdf"
        
        if not pdf_dir.exists():
            return documents
        
        for pdf_path in pdf_dir.glob("*.pdf"):
            try:
                # PyMuPDF로 PDF 텍스트 추출
                doc = fitz.open(str(pdf_path))
                full_text = ""
                
                for page_num, page in enumerate(doc, start=1):
                    text = page.get_text()
                    full_text += f"\n\n--- 페이지 {page_num} ---\n\n{text}"
                
                doc.close()
                
                # Document 생성
                documents.append(Document(
                    page_content=full_text,
                    metadata={
                        "source": pdf_path.name,
                        "type": "pdf",
                        "knowledge": self.knowledge_name
                    }
                ))
                
                print(f"✓ PDF 로드: {pdf_path.name}")
                
            except Exception as e:
                print(f"✗ PDF 로드 실패 ({pdf_path.name}): {str(e)}")
        
        return documents
    
    def load_csv_documents(self) -> List[Document]:
        """CSV 파일들을 로드하여 Document 리스트로 변환"""
        documents = []
        csv_dir = self.knowledge_dir / "csv"
        
        if not csv_dir.exists():
            return documents
        
        for csv_path in csv_dir.glob("*.csv"):
            try:
                # CSV 읽기
                df = pd.read_csv(csv_path, encoding='utf-8-sig')
                
                # DataFrame을 텍스트로 변환
                rows_text = []
                for idx, row in df.iterrows():
                    row_text = " | ".join([f"{col}: {val}" for col, val in row.items() if pd.notna(val)])
                    rows_text.append(row_text)
                
                full_text = "\n".join(rows_text)
                
                # 파일명에서 설명 추출
                file_stem = csv_path.stem
                description = file_stem.split('_')[-1] if '_' in file_stem else ""
                
                # Document 생성
                documents.append(Document(
                    page_content=full_text,
                    metadata={
                        "source": csv_path.name,
                        "type": "csv",
                        "knowledge": self.knowledge_name,
                        "description": description,
                        "columns": ", ".join(df.columns)
                    }
                ))
                
                print(f"✓ CSV 로드: {csv_path.name}")
                
            except Exception as e:
                print(f"✗ CSV 로드 실패 ({csv_path.name}): {str(e)}")
        
        return documents
    
    def create_embeddings(self, force_recreate: bool = False) -> Dict:
        """
        문서를 임베딩하여 ChromaDB에 저장
        
        Args:
            force_recreate: True면 전체 재임베딩, False면 증분 임베딩(기본)
            
        Returns:
            임베딩 결과 정보
        """
        # === 전체 재임베딩 모드 ===
        if force_recreate:
            print("\n=== 전체 재임베딩 모드 ===")
            
            # 기존 DB 삭제
            if self.chroma_dir.exists():
                import shutil
                shutil.rmtree(self.chroma_dir)
                self.chroma_dir.mkdir(parents=True, exist_ok=True)
                print("✓ 기존 ChromaDB 삭제 완료")
            
            # 문서 로드
            print(f"\n=== {self.knowledge_name} 문서 로드 중 ===")
            pdf_docs = self.load_pdf_documents()
            csv_docs = self.load_csv_documents()
            all_documents = pdf_docs + csv_docs
            
            if not all_documents:
                raise ValueError("로드된 문서가 없습니다")
            
            print(f"\n총 {len(all_documents)}개 문서 로드 완료 (PDF: {len(pdf_docs)}, CSV: {len(csv_docs)})")
            
            # 문서 청크 분할
            print("\n=== 문서 청크 분할 중 ===")
            chunks = self.text_splitter.split_documents(all_documents)
            print(f"총 {len(chunks)}개 청크 생성")
            
            # ChromaDB에 임베딩 저장
            print("\n=== ChromaDB 임베딩 중 ===")
            vectorstore = Chroma.from_documents(
                documents=chunks,
                embedding=self.embeddings,
                persist_directory=str(self.chroma_dir),
                collection_name=self.collection_name
            )
            
            print(f"✓ 전체 임베딩 완료: {len(chunks)}개 청크가 ChromaDB에 저장됨")
            
            return {
                "status": "success",
                "mode": "full",
                "knowledge_name": self.knowledge_name,
                "total_documents": len(all_documents),
                "pdf_count": len(pdf_docs),
                "csv_count": len(csv_docs),
                "total_chunks": len(chunks),
                "new_chunks": len(chunks),
                "chroma_path": str(self.chroma_dir)
            }
        
        # === 증분 임베딩 모드 ===
        else:
            print("\n=== 증분 임베딩 모드 (새 파일만 추가) ===")
            
            # 기존 임베딩된 파일 목록 가져오기
            existing_sources = set()
            if self.chroma_dir.exists() and list(self.chroma_dir.glob("*")):
                try:
                    vectorstore = Chroma(
                        persist_directory=str(self.chroma_dir),
                        embedding_function=self.embeddings,
                        collection_name=self.collection_name
                    )
                    
                    # 기존 문서의 source 메타데이터 수집
                    collection = vectorstore._collection
                    all_data = collection.get()
                    
                    if all_data and 'metadatas' in all_data:
                        for metadata in all_data['metadatas']:
                            if metadata and 'source' in metadata:
                                existing_sources.add(metadata['source'])
                    
                    print(f"✓ 기존 임베딩 파일: {len(existing_sources)}개")
                    if existing_sources:
                        print(f"  파일 목록: {', '.join(sorted(existing_sources))}")
                    
                except Exception as e:
                    print(f"⚠ 기존 파일 확인 중 오류 (전체 임베딩으로 진행): {str(e)}")
                    existing_sources = set()
            else:
                print("✓ 첫 임베딩입니다")
            
            # 모든 문서 로드
            print(f"\n=== {self.knowledge_name} 문서 로드 중 ===")
            pdf_docs = self.load_pdf_documents()
            csv_docs = self.load_csv_documents()
            all_documents = pdf_docs + csv_docs
            
            if not all_documents:
                raise ValueError("로드된 문서가 없습니다")
            
            print(f"\n총 {len(all_documents)}개 문서 로드 완료 (PDF: {len(pdf_docs)}, CSV: {len(csv_docs)})")
            
            # 새 파일만 필터링
            new_documents = []
            for doc in all_documents:
                source = doc.metadata.get('source', '')
                if source not in existing_sources:
                    new_documents.append(doc)
            
            # 새 파일이 없으면 종료
            if not new_documents:
                print("\n✓ 새 문서 없음. 임베딩 건너뜀.")
                return {
                    "status": "success",
                    "mode": "incremental",
                    "knowledge_name": self.knowledge_name,
                    "total_documents": len(all_documents),
                    "pdf_count": len(pdf_docs),
                    "csv_count": len(csv_docs),
                    "total_chunks": 0,
                    "new_chunks": 0,
                    "message": "새 문서 없음",
                    "chroma_path": str(self.chroma_dir)
                }
            
            print(f"\n✓ 새 문서 발견: {len(new_documents)}개")
            new_sources = [doc.metadata.get('source') for doc in new_documents]
            print(f"  파일 목록: {', '.join(new_sources)}")
            
            # 새 문서 청크 분할
            print("\n=== 새 문서 청크 분할 중 ===")
            new_chunks = self.text_splitter.split_documents(new_documents)
            print(f"총 {len(new_chunks)}개 청크 생성")
            
            # 기존 vectorstore에 추가
            print("\n=== ChromaDB에 추가 중 ===")
            if not self.chroma_dir.exists() or not list(self.chroma_dir.glob("*")):
                # 첫 임베딩
                vectorstore = Chroma.from_documents(
                    documents=new_chunks,
                    embedding=self.embeddings,
                    persist_directory=str(self.chroma_dir),
                    collection_name=self.collection_name
                )
            else:
                # 기존에 추가
                vectorstore = Chroma(
                    persist_directory=str(self.chroma_dir),
                    embedding_function=self.embeddings,
                    collection_name=self.collection_name
                )
                vectorstore.add_documents(new_chunks)
            
            print(f"✓ 증분 임베딩 완료: {len(new_chunks)}개 청크 추가됨")
            
            return {
                "status": "success",
                "mode": "incremental",
                "knowledge_name": self.knowledge_name,
                "total_documents": len(all_documents),
                "pdf_count": len(pdf_docs),
                "csv_count": len(csv_docs),
                "total_chunks": len(existing_sources) + len(new_chunks),  # 대략적인 추정
                "new_chunks": len(new_chunks),
                "new_files": new_sources,
                "chroma_path": str(self.chroma_dir)
            }
    
    def get_retriever(self, search_kwargs: dict = None):
        """
        저장된 벡터스토어에서 retriever 반환
        
        Args:
            search_kwargs: 검색 파라미터 (예: {"k": 5})
            
        Returns:
            Retriever 객체
        """
        if not self.chroma_dir.exists():
            raise ValueError(f"{self.knowledge_name} 임베딩이 존재하지 않습니다")
        
        if search_kwargs is None:
            search_kwargs = {"k": 5}
        
        vectorstore = Chroma(
            persist_directory=str(self.chroma_dir),
            embedding_function=self.embeddings,
            collection_name=self.collection_name
        )
        
        return vectorstore.as_retriever(search_kwargs=search_kwargs)


def embed_knowledge(knowledge_name: str, force_recreate: bool = False) -> Dict:
    """
    지식 임베딩 실행 (외부 호출용)
    
    Args:
        knowledge_name: 지식명
        force_recreate: 기존 DB 재생성 여부
        
    Returns:
        임베딩 결과
    """
    embedder = KnowledgeEmbedder(knowledge_name)
    return embedder.create_embeddings(force_recreate=force_recreate)