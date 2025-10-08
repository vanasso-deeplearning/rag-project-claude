"""
RAG 채팅 인터페이스
사용자가 지식베이스를 선택하고 질문할 수 있는 페이지
"""

import streamlit as st
import requests
from typing import List, Dict, Any


# 페이지 설정
st.set_page_config(
    page_title="RAG 채팅",
    page_icon="💬",
    layout="wide"
)

# API 베이스 URL
API_BASE_URL = "http://localhost:8000"


def get_available_knowledge() -> List[Dict[str, str]]:
    """임베딩이 완료된 지식베이스 목록 가져오기"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/user/available-knowledge")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"지식 목록을 불러올 수 없습니다: {str(e)}")
        return []


def ask_question(
    knowledge_names: List[str],
    question: str,
    top_k_per_knowledge: int = 3,
    final_top_k: int = 5,
    use_reasoning_model: bool = False
) -> Dict[str, Any]:
    """질문하고 답변 받기"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/user/ask",
            json={
                "knowledge_names": knowledge_names,
                "question": question,
                "top_k_per_knowledge": top_k_per_knowledge,
                "final_top_k": final_top_k,
                "use_reasoning_model": use_reasoning_model
            }
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPException as e:
        st.error(f"API 오류: {e.response.text if hasattr(e, 'response') else str(e)}")
        return None
    except Exception as e:
        st.error(f"질문 처리 중 오류 발생: {str(e)}")
        return None


def display_sources(sources: List[Dict[str, Any]]):
    """출처 정보 표시"""
    st.markdown("---")
    st.subheader("📚 참고 출처")
    
    for source in sources:
        st.markdown(f"**출처 {source['index']}: {source['knowledge_name']} - {source['source_file']}**")

        cols = st.columns([1, 1, 2])
        
        with cols[0]:
            st.write(f"**페이지:** {source['page']}")
        
        with cols[1]:
            score = source.get('score', 0)
            st.write(f"**유사도:** {score:.4f}")
        
        with cols[2]:
            st.write(f"**지식:** {source['knowledge_name']}")
        
        st.markdown("**내용 미리보기:**")
        st.info(source['content_preview'])


def display_knowledge_stats(stats: Dict[str, int]):
    """지식별 사용 통계 표시"""
    if not stats or sum(stats.values()) == 0:
        return
    
    st.markdown("---")
    st.markdown("##### 📊 사용된 지식베이스")
    
    cols = st.columns(len(stats))
    for i, (knowledge_name, count) in enumerate(stats.items()):
        with cols[i]:
            st.markdown(f"""
                <div style="
                    padding: 12px;
                    background: #f0fdf4;
                    border: 1px solid #bbf7d0;
                    border-radius: 8px;
                    text-align: center;
                ">
                    <div style="
                        font-size: 18px;
                        font-weight: 700;
                        color: #15803d;
                        margin-bottom: 4px;
                    ">{knowledge_name}</div>
                    <div style="
                        font-size: 14px;
                        color: #16a34a;
                    ">{count}개 문서</div>
                </div>
            """, unsafe_allow_html=True)


# 메인 UI
st.title("💬 RAG 채팅")
st.markdown("지식베이스를 선택하고 질문해보세요!")

# 세션 상태 초기화
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# 사이드바: 설정
with st.sidebar:
    st.header("⚙️ 설정")
    
    # 지식베이스 선택
    st.subheader("1. 지식베이스 선택")
    available_knowledge = get_available_knowledge()
    
    if not available_knowledge:
        st.warning("사용 가능한 지식베이스가 없습니다. 먼저 관리자 페이지에서 지식을 등록하고 임베딩하세요.")
        st.stop()
    
    # 복수 선택 체크박스
    selected_knowledge = []
    
    st.markdown("**사용할 지식 선택 (복수 선택 가능):**")
    for kb in available_knowledge:
        is_selected = st.checkbox(
            label=kb['name'],
            value=False,
            key=f"kb_{kb['name']}",
            help=kb['description'] if kb['description'] else "설명 없음"
        )
        if is_selected:
            selected_knowledge.append(kb['name'])
    
    if not selected_knowledge:
        st.warning("⚠️ 최소 1개 이상의 지식을 선택하세요")
    
    st.markdown("---")
    
    # 고급 설정
    st.subheader("2. 검색 설정")
    
    top_k_per_knowledge = st.slider(
        "각 지식에서 검색할 문서 수",
        min_value=1,
        max_value=10,
        value=5,
        help="각 지식베이스에서 가져올 관련 문서 개수"
    )
    
    final_top_k = st.slider(
        "최종 사용할 문서 수",
        min_value=1,
        max_value=20,
        value=7,
        help="답변 생성에 사용할 최종 문서 개수"
    )

    st.subheader("3. 모델 설정")
    
    use_reasoning_model = st.checkbox(
        "🧠 추론 모드 (GPT-4)",
        value=False,
        help="복잡한 추론이 필요한 질문에 사용 (비용 약 20배 증가)"
    )
    
    if use_reasoning_model:
        st.warning("⚠️ GPT-4는 gpt-4o-mini보다 약 20배 비쌉니다")    
    
    st.markdown("---")
    
    # 채팅 기록 초기화
    if st.button("🗑️ 채팅 기록 초기화", type="secondary"):
        st.session_state.chat_history = []
        st.rerun()

# 메인 영역: 채팅
st.markdown("---")

# 채팅 기록 표시
for chat in st.session_state.chat_history:
    # 사용자 질문
    with st.chat_message("user"):
        st.write(chat['question'])
    
    # AI 답변
    with st.chat_message("assistant"):
        st.write(chat['answer'])
        
        # 출처 표시
        if chat.get('sources'):
            with st.expander("📚 출처 보기"):
                display_sources(chat['sources'])
        
        # 통계 표시
        if chat.get('knowledge_stats'):
            display_knowledge_stats(chat['knowledge_stats'])

# 질문 입력
question = st.chat_input(
    "질문을 입력하세요...",
    disabled=len(selected_knowledge) == 0
)

if question:
    if not selected_knowledge:
        st.error("❌ 지식베이스를 선택해주세요!")
    else:
        # 사용자 질문 표시
        with st.chat_message("user"):
            st.write(question)
        
        # 답변 생성
        with st.chat_message("assistant"):
            with st.spinner("답변 생성 중..."):
                result = ask_question(
                    knowledge_names=selected_knowledge,
                    question=question,
                    top_k_per_knowledge=top_k_per_knowledge,
                    final_top_k=final_top_k,
                    use_reasoning_model=use_reasoning_model
                )
            
            if result:
                # 답변 표시
                st.write(result['answer'])
                
                # 출처 표시
                if result.get('sources'):
                    with st.expander("📚 출처 보기"):
                        display_sources(result['sources'])
                
                # 통계 표시
                if result.get('knowledge_stats'):
                    display_knowledge_stats(result['knowledge_stats'])
                
                # 채팅 기록에 추가
                st.session_state.chat_history.append({
                    'question': question,
                    'answer': result['answer'],
                    'sources': result.get('sources', []),
                    'knowledge_stats': result.get('knowledge_stats', {})
                })
            else:
                st.error("답변을 생성할 수 없습니다.")

# 사용 팁
st.markdown("---")
with st.expander("💡 사용 팁"):
    st.markdown("""
    ### 효과적인 질문 방법
    
    1. **구체적으로 질문하세요**
       - ❌ "스테이블코인이 뭐야?"
       - ✅ "스테이블코인의 주요 특징 3가지와 각각의 장단점은?"
    
    2. **복수 지식 활용**
       - 관련된 여러 지식베이스를 선택하면 더 풍부한 답변을 얻을 수 있습니다
       - 예: "블록체인"과 "스테이블코인" 동시 선택
    
    3. **출처 확인**
       - 답변 아래 "출처 보기"를 클릭하면 정보의 근거를 확인할 수 있습니다
    
    4. **검색 설정 조정**
       - 답변이 불충분하면 "최종 사용할 문서 수"를 늘려보세요
       - 응답이 너무 느리면 수치를 줄여보세요
    """)