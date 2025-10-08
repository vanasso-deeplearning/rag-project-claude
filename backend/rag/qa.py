"""
RAG 질의응답 모듈
Multi-Knowledge Retrieval 방식으로 복수 지식베이스에서 검색 및 답변 생성
"""

import os
from typing import List, Dict, Any, Tuple
from pathlib import Path
import hashlib

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain.schema import Document
from langchain.prompts import ChatPromptTemplate


def get_collection_name(knowledge_name: str) -> str:
    """지식명으로부터 ChromaDB collection 이름 생성"""
    hash_suffix = hashlib.md5(knowledge_name.encode('utf-8')).hexdigest()[:8]
    return f"kb_{hash_suffix}"


def get_retriever(knowledge_name: str, top_k: int = 3):
    """단일 지식베이스의 retriever 생성"""
    base_dir = Path("document_sets") / knowledge_name
    chroma_dir = base_dir / "chroma_db"
    
    if not chroma_dir.exists():
        raise ValueError(f"지식 '{knowledge_name}'의 임베딩이 존재하지 않습니다.")
    
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    collection_name = get_collection_name(knowledge_name)
    
    vectorstore = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=str(chroma_dir)
    )
    
    # as_retriever() 대신 직접 검색하기 위해 vectorstore 반환
    return vectorstore


def merge_and_rerank_documents(
    docs_list: List[List[Document]], 
    top_k: int = 5
) -> List[Document]:
    """
    여러 지식베이스에서 검색된 문서들을 병합하고 유사도 기준으로 재정렬
    
    Args:
        docs_list: 각 지식베이스에서 검색된 문서 리스트들
        top_k: 최종 반환할 문서 개수
    
    Returns:
        유사도 순으로 정렬된 상위 k개 문서
    """
    all_docs = []
    
    # 모든 문서 수집 (유사도 점수 포함)
    for docs in docs_list:
        all_docs.extend(docs)
    
    # 유사도 점수로 정렬 (Document 객체에 metadata['score'] 있다고 가정)
    # ChromaDB의 similarity_search_with_score 사용 시 score 포함됨
    sorted_docs = sorted(
        all_docs, 
        key=lambda x: x.metadata.get('score', 0),
        reverse=True
    )
    
    return sorted_docs[:top_k]


def retrieve_documents(
    knowledge_names: List[str], 
    question: str, 
    top_k_per_knowledge: int = 3,
    final_top_k: int = 5
) -> Tuple[List[Document], Dict[str, int]]:
    """
    Multi-Knowledge Retrieval: 복수 지식베이스에서 문서 검색 및 병합
    
    Args:
        knowledge_names: 검색할 지식베이스 이름 리스트
        question: 사용자 질문
        top_k_per_knowledge: 각 지식베이스에서 가져올 문서 개수
        final_top_k: 최종 반환할 문서 개수
    
    Returns:
        (검색된 문서 리스트, 지식별 문서 개수 통계)
    """
    docs_list = []
    knowledge_stats = {name: 0 for name in knowledge_names}
    
    # 각 지식베이스에서 검색
    for knowledge_name in knowledge_names:
        try:
            vectorstore = get_retriever(knowledge_name, top_k_per_knowledge)
            
            # 유사도 점수와 함께 검색
            docs_with_scores = vectorstore.similarity_search_with_score(
                question, 
                k=top_k_per_knowledge
            )
            
            # Document 객체에 score 메타데이터 추가
            docs = []
            for doc, score in docs_with_scores:
                doc.metadata['score'] = score
                doc.metadata['knowledge_name'] = knowledge_name
                docs.append(doc)
            
            docs_list.append(docs)
            
        except Exception as e:
            print(f"Warning: '{knowledge_name}'에서 검색 실패 - {str(e)}")
            continue
    
    # 문서 병합 및 재정렬
    if not docs_list:
        return [], knowledge_stats
    
    final_docs = merge_and_rerank_documents(docs_list, final_top_k)
    
    # 통계 집계
    for doc in final_docs:
        kb_name = doc.metadata.get('knowledge_name', 'unknown')
        if kb_name in knowledge_stats:
            knowledge_stats[kb_name] += 1
    
    return final_docs, knowledge_stats


def generate_answer(
    documents: List[Document], 
    question: str,
    model_name: str = "gpt-4o-mini"
) -> Dict[str, Any]:
    """
    검색된 문서를 바탕으로 GPT를 이용해 답변 생성
    
    Args:
        documents: 검색된 문서 리스트
        question: 사용자 질문
        model_name: 사용할 OpenAI 모델
    
    Returns:
        {
            'answer': 생성된 답변,
            'sources': 출처 정보 리스트
        }
    """
    if not documents:
        return {
            'answer': "죄송합니다. 관련된 정보를 찾을 수 없습니다.",
            'sources': []
        }
    
    # 컨텍스트 구성
    context_parts = []
    sources = []
    
    for i, doc in enumerate(documents, 1):
        # 출처 정보 추출
        source_info = {
            'index': i,
            'knowledge_name': doc.metadata.get('knowledge_name', 'Unknown'),
            'source_file': doc.metadata.get('source', 'Unknown'),
            'page': doc.metadata.get('page', 'N/A'),
            'score': doc.metadata.get('score', 0),
            'content_preview': doc.page_content[:100] + '...' if len(doc.page_content) > 100 else doc.page_content
        }
        sources.append(source_info)
        
        # 컨텍스트 텍스트
        context_parts.append(f"[출처 {i}]\n{doc.page_content}")
    
    context = "\n\n".join(context_parts)
    
    # 프롬프트 구성
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", """당신은 제공된 문서를 기반으로 정확하게 답변하는 AI 어시스턴트입니다.

다음 규칙을 반드시 지켜주세요:
1. 제공된 컨텍스트만을 사용하여 답변하세요.
2. 컨텍스트에 없는 내용은 추측하지 마세요.
3. 답변할 때 어느 출처에서 가져온 정보인지 [출처 번호]를 명시하세요.
4. 한국어로 친절하고 명확하게 답변하세요.
5. 가능한 한 자세하고 구체적으로 설명하세요. 예시와 세부사항을 포함하세요.
6. 각 주요 포인트를 충분히 설명하고, 필요하다면 여러 문단으로 나누어 작성하세요. 
7. 컨텍스트에 답이 없다면 솔직히 "제공된 문서에서 관련 정보를 찾을 수 없습니다"라고 말하세요."""),
        ("user", """컨텍스트:
{context}

질문: {question}

답변:""")
    ])
    
    # LLM 호출
    llm = ChatOpenAI(model=model_name, temperature=0)
    chain = prompt_template | llm
    
    response = chain.invoke({
        "context": context,
        "question": question
    })
    
    return {
        'answer': response.content,
        'sources': sources
    }


def answer_question(
    knowledge_names: List[str],
    question: str,
    top_k_per_knowledge: int = 3,
    final_top_k: int = 5,
    model_name: str = "gpt-4o-mini"
) -> Dict[str, Any]:
    """
    RAG 전체 파이프라인: 질문 → 검색 → 답변 생성
    
    Args:
        knowledge_names: 검색할 지식베이스 이름 리스트
        question: 사용자 질문
        top_k_per_knowledge: 각 지식에서 검색할 문서 수
        final_top_k: 최종 사용할 문서 수
        model_name: OpenAI 모델명
    
    Returns:
        {
            'answer': 답변,
            'sources': 출처 정보,
            'knowledge_stats': 지식별 사용 문서 개수
        }
    """
    # 1. 문서 검색
    documents, knowledge_stats = retrieve_documents(
        knowledge_names=knowledge_names,
        question=question,
        top_k_per_knowledge=top_k_per_knowledge,
        final_top_k=final_top_k
    )
    
    # 2. 답변 생성
    result = generate_answer(
        documents=documents,
        question=question,
        model_name=model_name
    )
    
    # 3. 통계 추가
    result['knowledge_stats'] = knowledge_stats
    
    return result