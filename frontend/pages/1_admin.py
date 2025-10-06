"""
관리자 페이지 - 신규 지식 등록
"""
import streamlit as st
import requests
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="관리자 - 신규 지식 등록",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 사이드바 메뉴
with st.sidebar:
    st.header("관리자 메뉴")
    menu = st.radio(
        "메뉴 선택",
        ["신규 지식 등록", "등록된 지식 관리"]
    )

# ========================================
# 신규 지식 등록
# ========================================
if menu == "신규 지식 등록":
    st.title("신규 지식 등록")
    
    # 세션 상태 초기화
    if 'current_knowledge' not in st.session_state:
        st.session_state['current_knowledge'] = None
    if 'current_description' not in st.session_state:
        st.session_state['current_description'] = ''
    
    # ========================================
    # 1. 지식명 입력
    # ========================================
    st.header("1. 지식명")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        knowledge_name = st.text_input(
            "지식명을 입력하세요",
            value=st.session_state.get('current_knowledge', ''),
            placeholder="예: 스테이블 코인"
        )
    with col2:
        if st.button("등록", type="primary", use_container_width=True):
            if knowledge_name:
                st.session_state['current_knowledge'] = knowledge_name
                st.success(f"지식명 설정: {knowledge_name}")
                st.rerun()
            else:
                st.warning("지식명을 입력하세요")
    
    if st.session_state['current_knowledge']:
        st.info(f"현재 지식: **{st.session_state['current_knowledge']}**")
    
    col_desc1, col_desc2 = st.columns([1, 3])
    with col_desc1:
        st.markdown("**간략 소개:**")
    with col_desc2:
        knowledge_desc = st.text_area(
            "간략 소개",
            label_visibility="collapsed",
            value=st.session_state.get('current_description', ''),
            placeholder="간략 소개 글은 사용자 화면에서 해당 지식을 선택할때 보여지는 내용이니 유의하여 등록하시기 바랍니다",
            key="knowledge_description"
        )
        
        # 간략 소개 저장 버튼
        if st.button("간략 소개 저장", use_container_width=True):
            if st.session_state['current_knowledge'] and knowledge_desc.strip():
                try:
                    # 간략 소개 저장 API 호출
                    save_desc_response = requests.post(
                        f"{API_BASE_URL}/api/admin/save-knowledge-metadata",
                        json={
                            "knowledge_name": st.session_state['current_knowledge'],
                            "description": knowledge_desc.strip()
                        }
                    )
                    if save_desc_response.status_code == 200:
                        st.session_state['current_description'] = knowledge_desc.strip()
                        st.success("간략 소개가 저장되었습니다")
                    else:
                        st.error("간략 소개 저장 실패")
                except:
                    st.error("간략 소개 저장 중 오류 발생")
            elif not st.session_state['current_knowledge']:
                st.warning("먼저 지식명을 등록하세요")
            else:
                st.warning("간략 소개를 입력하세요")
    
    if not st.session_state['current_knowledge']:
        st.warning("⬆️ 먼저 지식명을 등록하세요")
        st.stop()
    
    current_knowledge = st.session_state['current_knowledge']
    
    st.markdown("---")
    
    # ========================================
    # 2. PDF 등록
    # ========================================
    st.header("2. PDF 등록")
    
    uploaded_file = st.file_uploader(
        "PDF 파일을 드래그하거나 선택하세요",
        type=['pdf'],
        help="Drag and Drop 또는 파일 찾기"
    )
    
    if uploaded_file:
        if st.button("표 추출 시작", type="primary"):
            with st.spinner("PDF 업로드 및 표 추출 중..."):
                files = {"file": (uploaded_file.name, uploaded_file, "application/pdf")}
                upload_response = requests.post(
                    f"{API_BASE_URL}/api/admin/upload-pdf",
                    params={"knowledge_name": current_knowledge},
                    files=files
                )
                
                if upload_response.status_code == 200:
                    extract_response = requests.post(
                        f"{API_BASE_URL}/api/admin/extract-tables",
                        params={
                            "knowledge_name": current_knowledge,
                            "pdf_filename": uploaded_file.name
                        }
                    )
                    
                    if extract_response.status_code == 200:
                        result = extract_response.json()
                        st.session_state['tables'] = result['tables']
                        st.session_state['pdf_name'] = uploaded_file.name
                        
                        # 수정: 표 개수에 따른 메시지
                        if len(result['tables']) > 0:
                            st.success(f"{len(result['tables'])}개 표 발견")
                        else:
                            st.warning("추출할 표가 없습니다")
                            st.info("표가 없는 PDF는 그대로 저장되며, Phase 3에서 전체 텍스트로 임베딩됩니다")
                        
                        st.rerun()
    
    st.markdown("---")
    
    # ========================================
    # 3. 표 추출 및 저장/삭제
    # ========================================
    if 'tables' in st.session_state:
        st.header("3. 표 추출 및 저장/삭제")
        
        # 표가 없는 경우
        if not st.session_state['tables']:
            st.info("이 PDF에는 추출 가능한 표가 없습니다")
            st.markdown("**다음 단계:**")
            st.markdown("- 다른 PDF를 추가 업로드하거나")
            st.markdown("- '4. 등록된 PDF 및 CSV 목록'으로 이동하여 'PDF 등록 완료' 버튼을 누르세요")
            
            # 완료 버튼 추가
            if st.button("이 PDF 등록 완료", type="primary", use_container_width=True):
                # 세션 정리 전에 파일명 저장
                pdf_name = st.session_state['pdf_name']
                del st.session_state['tables']
                del st.session_state['pdf_name']
                st.success(f"{pdf_name} 등록 완료")
                st.rerun()
        
        # 표가 있는 경우
        else:
            # 선택 상태 초기화
            if 'selected_tables' not in st.session_state:
                st.session_state['selected_tables'] = set()
            
            # 페이지네이션 설정
            items_per_page = 10
            total_tables = len(st.session_state['tables'])
            total_pages = (total_tables - 1) // items_per_page + 1
            
            if 'current_page' not in st.session_state:
                st.session_state['current_page'] = 0
            
            # 페이지 범위 계산
            start_idx = st.session_state['current_page'] * items_per_page
            end_idx = min(start_idx + items_per_page, total_tables)
            
            # 전체 선택 및 상단 버튼
            col_select, col_btn1, col_btn2 = st.columns([0.5, 1, 1])
            
            with col_select:
                # 현재 페이지의 전체선택 체크박스
                current_page_indices = set(range(start_idx, end_idx))
                all_current_selected = current_page_indices.issubset(st.session_state['selected_tables'])
                select_all = st.checkbox("전체 선택", value=all_current_selected, key="select_all_checkbox")
            
            # 전체선택 동작 (현재 페이지만)
            if select_all:
                st.session_state['selected_tables'].update(current_page_indices)
            else:
                if all_current_selected:
                    st.session_state['selected_tables'] -= current_page_indices
            
            selected_count = len(st.session_state['selected_tables'])
            
            with col_btn1:
                if st.button("선택 삭제", key="delete_top", use_container_width=True):
                    if selected_count == 0:
                        st.warning("삭제할 표를 선택하세요")
                    else:
                        for idx in sorted(st.session_state['selected_tables'], reverse=True):
                            st.session_state['tables'].pop(idx)
                        st.session_state['selected_tables'] = set()
                        st.success(f"{selected_count}개 표 삭제")
                        st.rerun()
            
            with col_btn2:
                if st.button("선택 CSV 저장 및 완료", key="save_top", type="primary", use_container_width=True):
                    if selected_count == 0:
                        st.warning("저장할 표를 선택하세요")
                    else:
                        # 먼저 모든 선택된 표에 설명이 있는지 체크
                        missing_desc = []
                        empty_data = []
                        for idx in sorted(st.session_state['selected_tables']):
                            table = st.session_state['tables'][idx]
                            desc = st.session_state.get(f'table_desc_{idx}', '').strip()
                            edited_df = st.session_state.get(f'edited_df_{idx}')
                            
                            if not desc:
                                missing_desc.append(f"표{table['table_index']}")
                            
                            # 빈 데이터 체크
                            if edited_df is None or edited_df.empty or len(edited_df.columns) == 0:
                                empty_data.append(f"표{table['table_index']}")
                        
                        if missing_desc:
                            st.error(f"다음 표의 설명을 입력하세요: {', '.join(missing_desc)}")
                            st.stop()
                        
                        if empty_data:
                            st.error(f"다음 표는 데이터가 비어있어 저장할 수 없습니다: {', '.join(empty_data)}")
                            st.warning("빈 표는 선택 해제하거나 삭제하세요")
                            st.stop()
                        
                        # 모든 표에 설명이 있고 데이터가 있으면 저장 진행
                        success_count = 0
                        for idx in sorted(st.session_state['selected_tables']):
                            table = st.session_state['tables'][idx]
                            desc = st.session_state.get(f'table_desc_{idx}', '').strip()
                            edited_df = st.session_state.get(f'edited_df_{idx}')
                            
                            if edited_df is not None and not edited_df.empty:
                                save_r = requests.post(
                                    f"{API_BASE_URL}/api/admin/save-table-to-csv",
                                    params={
                                        "knowledge_name": current_knowledge,
                                        "pdf_filename": st.session_state['pdf_name'],
                                        "page": table['page'],
                                        "table_index": table['table_index'],
                                        "description": desc
                                    },
                                    json={
                                        "data": edited_df.values.tolist(),
                                        "columns": edited_df.columns.tolist()
                                    }
                                )
                                if save_r.status_code == 200:
                                    success_count += 1
                        
                        if success_count > 0:
                            st.success(f"{success_count}개 CSV 저장 완료")
                            
                            for idx in sorted(st.session_state['selected_tables'], reverse=True):
                                st.session_state['tables'].pop(idx)
                            
                            st.session_state['selected_tables'] = set()
                            
                            if not st.session_state['tables']:
                                del st.session_state['tables']
                                del st.session_state['pdf_name']
                            
                            st.rerun()
            
            st.markdown("---")
            
            # 페이지네이션 UI
            st.info(f"총 {total_tables}개 표 중 {start_idx + 1}-{end_idx}번째 표시 중 | 선택된 표: {len(st.session_state['selected_tables'])}개")
            
            col_prev, col_page_info, col_next = st.columns([1, 2, 1])
            
            with col_prev:
                if st.button("이전 페이지", disabled=(st.session_state['current_page'] == 0), use_container_width=True):
                    st.session_state['current_page'] -= 1
                    st.rerun()
            
            with col_page_info:
                st.markdown(f"<div style='text-align: center; padding: 8px;'>페이지 {st.session_state['current_page'] + 1} / {total_pages}</div>", unsafe_allow_html=True)
            
            with col_next:
                if st.button("다음 페이지", disabled=(st.session_state['current_page'] >= total_pages - 1), use_container_width=True):
                    st.session_state['current_page'] += 1
                    st.rerun()
            
            st.markdown("---")
            
            # 현재 페이지의 표만 표시
            for i in range(start_idx, end_idx):
                table = st.session_state['tables'][i]
                col_check, col_content = st.columns([0.05, 0.95])
                
                with col_check:
                    checked = st.checkbox(
                        "",
                        key=f"check_{i}",
                        value=(i in st.session_state['selected_tables'])
                    )
                    if checked:
                        st.session_state['selected_tables'].add(i)
                    elif i in st.session_state['selected_tables']:
                        st.session_state['selected_tables'].discard(i)
                
                with col_content:
                    col_left, col_right = st.columns([1, 1])
                    
                    with col_left:
                        st.subheader("원본 이미지")
                        try:
                            img_r = requests.get(
                                f"{API_BASE_URL}/api/admin/get-pdf-page-image/"
                                f"{current_knowledge}/{st.session_state['pdf_name']}/{table['page']}"
                            )
                            if img_r.status_code == 200:
                                st.markdown(
                                    f'<img src="data:image/png;base64,{img_r.json()["image_base64"]}" '
                                    f'style="width:100%; border:1px solid #ddd;">',
                                    unsafe_allow_html=True
                                )
                        except:
                            st.error("이미지 로드 실패")
                    
                    with col_right:
                        st.subheader("CSV 편집")
                        if table['data'] and table['columns']:
                            df = pd.DataFrame(table['data'], columns=table['columns'])
                            edited = st.data_editor(
                                df,
                                num_rows="dynamic",
                                key=f"edit_{i}",
                                height=300
                            )
                            st.session_state[f'edited_df_{i}'] = edited
                        else:
                            st.error("데이터 없음 - 이 표는 저장할 수 없습니다")
                            st.caption("표 추출에 실패했습니다. 이 표를 삭제하거나 선택 해제하세요.")
                    
                    desc = st.text_input(
                        "표 설명:",
                        key=f"desc_{i}",
                        value=f"표설명{i+1}",
                        placeholder="예: 지역화폐 스테이블코인 비교"
                    )
                    st.session_state[f'table_desc_{i}'] = desc
                
                st.markdown("---")
            
            # 하단 페이지네이션 (동일)
            col_prev2, col_page_info2, col_next2 = st.columns([1, 2, 1])
            
            with col_prev2:
                if st.button("이전", key="prev_bottom", disabled=(st.session_state['current_page'] == 0), use_container_width=True):
                    st.session_state['current_page'] -= 1
                    st.rerun()
            
            with col_page_info2:
                st.markdown(f"<div style='text-align: center; padding: 8px;'>페이지 {st.session_state['current_page'] + 1} / {total_pages}</div>", unsafe_allow_html=True)
            
            with col_next2:
                if st.button("다음", key="next_bottom", disabled=(st.session_state['current_page'] >= total_pages - 1), use_container_width=True):
                    st.session_state['current_page'] += 1
                    st.rerun()
            
            st.markdown("---")
            
            # 하단 버튼
            col_btn1, col_btn2 = st.columns(2)
            
            with col_btn1:
                if st.button("선택 삭제", key="delete_bottom", use_container_width=True):
                    if selected_count == 0:
                        st.warning("삭제할 표를 선택하세요")
                    else:
                        for idx in sorted(st.session_state['selected_tables'], reverse=True):
                            st.session_state['tables'].pop(idx)
                        st.session_state['selected_tables'] = set()
                        st.success(f"{selected_count}개 표 삭제")
                        st.rerun()
            
            with col_btn2:
                if st.button("선택 CSV 저장 및 완료", key="save_bottom", type="primary", use_container_width=True):
                    if selected_count == 0:
                        st.warning("저장할 표를 선택하세요")
                    else:
                        # 먼저 모든 선택된 표에 설명이 있는지 체크
                        missing_desc = []
                        empty_data = []
                        for idx in sorted(st.session_state['selected_tables']):
                            table = st.session_state['tables'][idx]
                            desc = st.session_state.get(f'table_desc_{idx}', '').strip()
                            edited_df = st.session_state.get(f'edited_df_{idx}')
                            
                            if not desc:
                                missing_desc.append(f"표{table['table_index']}")
                            
                            # 빈 데이터 체크
                            if edited_df is None or edited_df.empty or len(edited_df.columns) == 0:
                                empty_data.append(f"표{table['table_index']}")
                        
                        if missing_desc:
                            st.error(f"다음 표의 설명을 입력하세요: {', '.join(missing_desc)}")
                            st.stop()
                        
                        if empty_data:
                            st.error(f"다음 표는 데이터가 비어있어 저장할 수 없습니다: {', '.join(empty_data)}")
                            st.warning("빈 표는 선택 해제하거나 삭제하세요")
                            st.stop()
                        
                        # 모든 표에 설명이 있고 데이터가 있으면 저장 진행
                        success_count = 0
                        for idx in sorted(st.session_state['selected_tables']):
                            table = st.session_state['tables'][idx]
                            desc = st.session_state.get(f'table_desc_{idx}', '').strip()
                            edited_df = st.session_state.get(f'edited_df_{idx}')
                            
                            if edited_df is not None and not edited_df.empty:
                                save_r = requests.post(
                                    f"{API_BASE_URL}/api/admin/save-table-to-csv",
                                    params={
                                        "knowledge_name": current_knowledge,
                                        "pdf_filename": st.session_state['pdf_name'],
                                        "page": table['page'],
                                        "table_index": table['table_index'],
                                        "description": desc
                                    },
                                    json={
                                        "data": edited_df.values.tolist(),
                                        "columns": edited_df.columns.tolist()
                                    }
                                )
                                if save_r.status_code == 200:
                                    success_count += 1
                        
                        if success_count > 0:
                            st.success(f"{success_count}개 CSV 저장 완료")
                            
                            for idx in sorted(st.session_state['selected_tables'], reverse=True):
                                st.session_state['tables'].pop(idx)
                            
                            st.session_state['selected_tables'] = set()
                            
                            if not st.session_state['tables']:
                                del st.session_state['tables']
                                del st.session_state['pdf_name']
                            
                            st.rerun()
            
            # 경고 문구
            st.markdown(
                '<p style="color: red; font-weight: bold;">CSV 편집시 항상 삭제할 표를 먼저 삭제한 후 진행하세요</p>',
                unsafe_allow_html=True
            )
    
    st.markdown("---")
    
    # ========================================
    # 4. 등록된 PDF 및 CSV 목록
    # ========================================
    st.header("4. 등록된 PDF 및 CSV 목록")
    
    try:
        files_response = requests.get(
            f"{API_BASE_URL}/api/admin/list-files/{current_knowledge}"
        )
        
        if files_response.status_code == 200:
            files_data = files_response.json()
            pdfs = files_data['pdfs']
            csvs = files_data['csvs']
            
            if pdfs or csvs:
                st.markdown("**PDF 파일:**")
                for pdf in pdfs:
                    st.markdown(f"  - {pdf['filename']}")
                
                st.markdown("")
                st.markdown("**CSV 파일:**")
                for csv in csvs:
                    st.markdown(f"  - {csv['filename']}")
                
                st.markdown(f"**총 {len(pdfs)}개 PDF, {len(csvs)}개 CSV**")
                
                st.markdown("---")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("PDF 추가 등록", use_container_width=True):
                        st.info("위의 '2. PDF 등록'으로 이동하여 추가 PDF를 업로드하세요")
                
                with col2:
                    if st.button("PDF 등록 완료", use_container_width=True):
                        st.success("PDF 등록 완료")
                
                with col3:
                    if st.button("전체 임베딩 시작", type="primary", use_container_width=True):
                        st.session_state['confirm_embedding'] = True
                        st.rerun()
                
                if st.session_state.get('confirm_embedding'):
                    st.warning("해당 지식의 PDF 등록이 완료되셨나요?")
                    st.caption("임베딩은 Phase 3에서 구현됩니다")
                    
                    col_confirm1, col_confirm2 = st.columns(2)
                    with col_confirm1:
                        if st.button("확인", use_container_width=True):
                            st.session_state['confirm_embedding'] = False
                            
                            with st.spinner("임베딩 진행 중... (수 분 소요될 수 있습니다)"):
                                try:
                                    response = requests.post(
                                        f"{API_BASE_URL}/api/admin/start-embedding",
                                        params={
                                            "knowledge_name": current_knowledge,
                                            "force_recreate": False
                                        }
                                    )
                                    
                                    if response.status_code == 200:
                                        result = response.json()
                                        st.success(f"✅ 임베딩 완료!")
                                        st.write(f"- 총 문서: {result['total_documents']}개")
                                        st.write(f"- PDF: {result['pdf_count']}개")
                                        st.write(f"- CSV: {result['csv_count']}개")
                                        st.write(f"- 청크: {result['total_chunks']}개")
                                    else:
                                        st.error(f"임베딩 실패: {response.text}")
                                except Exception as e:
                                    st.error(f"임베딩 중 오류: {str(e)}")
                        if st.button("취소", use_container_width=True):
                            st.session_state['confirm_embedding'] = False
                            st.rerun()
            else:
                st.info("등록된 파일이 없습니다. 위에서 PDF를 업로드하세요.")
    except:
        st.error("파일 목록 조회 실패")

# ========================================
# 등록된 지식 관리
# ========================================
# ========================================
# 등록된 지식 관리
# ========================================
elif menu == "등록된 지식 관리":
    st.title("등록된 지식 관리")
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/admin/list-knowledge")
        if response.status_code == 200:
            knowledge_list = response.json()['knowledge_list']
            
            if knowledge_list:
                for knowledge in knowledge_list:
                    with st.expander(f"📁 {knowledge['name']}", expanded=False):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"**PDF:** {knowledge['pdf_count']}개")
                            st.write(f"**CSV:** {knowledge['csv_count']}개")
                            if knowledge.get('description'):
                                st.caption(f"설명: {knowledge['description']}")
                        
                        with col2:
                            # 임베딩 상태 확인
                            chroma_path = f"document_sets/{knowledge['name']}/chroma_db"
                            if os.path.exists(chroma_path):
                                st.success("임베딩 완료")
                            else:
                                st.warning("임베딩 필요")
                        
                        st.markdown("---")
                        
                        # 파일 목록 보기
                        if st.button(f"📄 파일 목록 보기", key=f"view_{knowledge['name']}"):
                            files_response = requests.get(
                                f"{API_BASE_URL}/api/admin/list-files/{knowledge['name']}"
                            )
                            
                            if files_response.status_code == 200:
                                files_data = files_response.json()
                                
                                st.write("**PDF 파일:**")
                                for pdf in files_data['pdfs']:
                                    st.write(f"  - {pdf['filename']}")
                                
                                st.write("**CSV 파일:**")
                                for csv in files_data['csvs']:
                                    st.write(f"  - {csv['filename']}")
                        
                        # 버튼들
                        col_btn1, col_btn2, col_btn3 = st.columns(3)
                        
                        with col_btn1:
                            if st.button(f"PDF 추가", key=f"add_{knowledge['name']}", use_container_width=True):
                                st.session_state['current_knowledge'] = knowledge['name']
                                st.info("왼쪽 메뉴에서 '신규 지식 등록'을 선택하세요")
                        
                        with col_btn2:
                            if st.button(f"임베딩 시작", key=f"embed_{knowledge['name']}", use_container_width=True, type="primary"):
                                with st.spinner("임베딩 진행 중..."):
                                    try:
                                        embed_response = requests.post(
                                            f"{API_BASE_URL}/api/admin/start-embedding",
                                            params={
                                                "knowledge_name": knowledge['name'],
                                                "force_recreate": False
                                            }
                                        )
                                        
                                        if embed_response.status_code == 200:
                                            result = embed_response.json()
                                            st.success("임베딩 완료")
                                            st.write(f"총 문서: {result['total_documents']}개")
                                            st.write(f"청크: {result['total_chunks']}개")
                                        else:
                                            st.error(f"임베딩 실패: {embed_response.text}")
                                    except Exception as e:
                                        st.error(f"오류: {str(e)}")
                        
                        with col_btn3:
                            if st.button(f"지식 삭제", key=f"del_{knowledge['name']}", use_container_width=True):
                                st.warning("지식 삭제 기능은 Phase 2에서 구현 예정")
            else:
                st.info("등록된 지식이 없습니다.")
    except:
        st.error("지식 목록 조회 실패")