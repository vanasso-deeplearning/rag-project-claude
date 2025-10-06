"""
Streamlit 메인 앱 - 로그인 페이지
"""
import streamlit as st

st.set_page_config(
    page_title="RAG 지식 기반 시스템",
    page_icon="🤖",
    layout="wide"
)

# 세션 상태 초기화
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# 로그인 페이지
if not st.session_state['logged_in']:
    st.title("🤖 스테이블코인 지식 기반 시스템")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.header("로그인")
        
        with st.form("login_form"):
            user_id = st.text_input("사용자 ID", placeholder="아이디를 입력하세요")
            password = st.text_input("비밀번호", type="password", placeholder="비밀번호를 입력하세요")
            
            col_a, col_b, col_c = st.columns(3)
            
            with col_a:
                submit = st.form_submit_button("로그인", type="primary", use_container_width=True)
            with col_b:
                st.form_submit_button("회원가입", disabled=True, use_container_width=True)
            with col_c:
                st.form_submit_button("ID/PW 찾기", disabled=True, use_container_width=True)
            
            if submit:
                # 1차 파일럿: 아무 ID/PW나 입력하면 로그인
                st.session_state['logged_in'] = True
                st.session_state['user_id'] = user_id if user_id else "guest"
                st.rerun()
        
        st.info("💡 1차 파일럿 버전: 로그인 버튼만 누르면 접속됩니다.")
        st.caption("⚠️ 회원가입 및 ID/PW 찾기 기능은 2차 개발 예정")

else:
    # 로그인 후 메인 페이지
    st.title("🤖 스테이블코인 지식 기반 시스템")
    st.markdown(f"환영합니다, **{st.session_state['user_id']}**님!")
    st.markdown("---")
    
    # 로그아웃 버튼
    if st.sidebar.button("🚪 로그아웃"):
        st.session_state['logged_in'] = False
        st.rerun()
    
    # 안내 메시지
    st.info("👈 왼쪽 사이드바에서 원하는 기능을 선택하세요.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 관리자 메뉴")
        st.markdown("""
        - **표 추출 도구**: PDF에서 표 자동 추출
        - **문서 관리**: 업로드된 파일 관리
        - **지식 베이스 생성**: 임베딩 및 검색 설정
        """)
        if st.button("📊 관리자 페이지로 이동", use_container_width=True):
            st.switch_page("pages/1_admin.py")
    
    with col2:
        st.subheader("💬 사용자 메뉴")
        st.markdown("""
        - **채팅**: AI와 대화하며 지식 검색
        - **대화 기록**: 이전 대화 불러오기
        - **출처 확인**: 답변의 근거 문서 확인
        """)
        st.button("💬 채팅 페이지로 이동 (준비중)", disabled=True, use_container_width=True)
    
    st.markdown("---")
    
    # 시스템 상태
    st.subheader("⚙️ 시스템 상태")
    
    import requests
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
    
    try:
        health_response = requests.get(f"{API_BASE_URL}/health", timeout=2)
        if health_response.status_code == 200:
            st.success("✅ Backend 서버 정상 작동 중")
        else:
            st.error("❌ Backend 서버 응답 오류")
    except:
        st.error("❌ Backend 서버에 연결할 수 없습니다.")
        st.caption("Backend 서버를 먼저 실행해주세요: `cd backend && python main.py`")