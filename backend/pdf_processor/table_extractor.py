"""
PDF 표 자동 추출 도구
pdfplumber를 사용하여 PDF에서 표를 추출하고 Excel로 변환
"""
import os
from typing import List, Dict, Optional
import pdfplumber
import pandas as pd
from pathlib import Path


class TableExtractor:
    """PDF에서 표를 추출하는 클래스"""
    
    def __init__(self, output_dir: str = "./uploads/excel"):
        """
        Args:
            output_dir: 추출된 Excel 파일을 저장할 디렉토리
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def extract_tables_from_pdf(self, pdf_path: str) -> List[Dict]:
        """
        PDF 파일에서 모든 표를 추출
        
        Args:
            pdf_path: PDF 파일 경로
            
        Returns:
            추출된 표 정보 리스트
        """
        tables_info = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    # 페이지에서 표 추출 (기본 설정 사용)
                    tables = page.extract_tables()
                    
                    if tables:
                        for table_idx, table in enumerate(tables, start=1):
                            # 빈 표 건너뛰기
                            if not table or len(table) < 2:
                                continue
                            
                            # DataFrame으로 변환
                            df = self._convert_to_dataframe(table)
                            
                            if df is not None and not df.empty:
                                # 미리보기 생성 (처음 5행)
                                preview = df.head(5).to_string()
                                
                                tables_info.append({
                                    'page': page_num,
                                    'table_index': table_idx,
                                    'data': df,
                                    'preview': preview,
                                    'shape': df.shape  # (행, 열)
                                })
        
        except Exception as e:
            print(f"PDF 표 추출 중 오류: {str(e)}")
            raise
        
        return tables_info
    
    def _convert_to_dataframe(self, table: List[List]) -> Optional[pd.DataFrame]:
        """
        추출된 표를 pandas DataFrame으로 변환
        """
        try:
            if not table or len(table) < 2:
                return None
            
            # 첫 행을 헤더로 사용
            headers = table[0]
            data_rows = table[1:]
            
            # None 값 처리 - 빈 값도 의미있는 헤더로 유지
            headers = [str(h).strip() if h and str(h).strip() else f"컬럼{i+1}" for i, h in enumerate(headers)]
            
            # DataFrame 생성
            df = pd.DataFrame(data_rows, columns=headers)
            
            # 병합된 셀 처리: 빈 셀을 위의 값으로 채우기
            for col in df.columns:
                # 빈 문자열, None, 공백만 있는 값을 NaN으로 변환
                df[col] = df[col].replace(['', None, ' ', '  '], pd.NA)
            
            # 첫 번째 컬럼만 forward fill (병합된 셀 처리)
            if len(df.columns) > 0:
                first_col = df.columns[0]
                df[first_col] = df[first_col].ffill()
            
            # 빈 행 제거
            df = df.dropna(how='all')
            
            # 공백 제거 및 None을 빈 문자열로
            df = df.map(lambda x: str(x).strip() if pd.notna(x) and x is not pd.NA else '')
            
            return df
        
        except Exception as e:
            print(f"DataFrame 변환 중 오류: {str(e)}")
            return None
    
    def save_table_to_excel(
        self, 
        df: pd.DataFrame, 
        pdf_filename: str, 
        page: int, 
        table_index: int,
        custom_name: Optional[str] = None
    ) -> str:
        """
        표를 Excel 파일로 저장
        """
        # 파일명 생성
        base_name = Path(pdf_filename).stem
        
        if custom_name:
            filename = f"{base_name}_표{table_index}_{custom_name}.xlsx"
        else:
            filename = f"{base_name}_표{table_index}_페이지{page}.xlsx"
        
        filepath = self.output_dir / filename
        
        # Excel로 저장
        df.to_excel(filepath, index=False, engine='openpyxl')
        
        return str(filepath)
    
    def extract_and_save_all(
        self, 
        pdf_path: str,
        auto_save: bool = False
    ) -> List[Dict]:
        """
        PDF에서 표를 추출하고 선택적으로 자동 저장
        """
        pdf_filename = Path(pdf_path).name
        tables_info = self.extract_tables_from_pdf(pdf_path)
        
        if auto_save:
            for table_info in tables_info:
                filepath = self.save_table_to_excel(
                    df=table_info['data'],
                    pdf_filename=pdf_filename,
                    page=table_info['page'],
                    table_index=table_info['table_index']
                )
                table_info['saved_path'] = filepath
        
        return tables_info