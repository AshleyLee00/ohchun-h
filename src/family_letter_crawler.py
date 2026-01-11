#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
학교 홈페이지 가정통신문 크롤러
HTML 페이지를 직접 크롤링하여 가정통신문을 수집하는 모듈입니다.
"""

import json
import logging
import os
import re
import requests
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup

# 로그 파일 경로 설정
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'family_letter_crawler.log')

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=log_file,
    filemode='w',
    encoding='utf-8'
)

def crawl_school_letters(url, site_name=None):
    """
    학교 홈페이지 가정통신문을 HTML 페이지에서 직접 크롤링합니다.
    
    Args:
        url (str): 가정통신문 목록 페이지 URL
        site_name (str, optional): 사이트 이름, 없으면 URL에서 추출
        
    Returns:
        dict: 크롤링된 가정통신문 정보
    """
    if not site_name:
        # URL에서 도메인 추출하여 사이트 이름으로 사용
        match = re.search(r'https?://(?:www\.)?([^/]+)', url)
        if match:
            site_name = match.group(1)
        else:
            site_name = "unknown_site"
    
    logging.info(f"{site_name} 가정통신문 HTML 크롤러 시작...")
    
    # 웹 페이지 요청
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = 'utf-8'  # 한글 인코딩 설정
    except requests.RequestException as e:
        logging.error(f"요청 중 오류 발생: {e}")
        return {
            "letters": [],
            "meta": {
                "total_count": 0,
                "last_updated": datetime.now().strftime("%Y-%m-%d"),
                "source": site_name,
                "url": url,
                "error": str(e)
            }
        }
    
    # HTML 파싱
    try:
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 가정통신문 테이블 찾기
        # 여러 방법으로 시도
        tbody = None
        
        # 방법 1: CSS 셀렉터로 직접 찾기
        tbody = soup.select_one('#subContent > div > div.BD_list > table > tbody')
        
        # 방법 2: 단계별로 찾기
        if not tbody:
            sub_content = soup.find(id='subContent')
            if sub_content:
                div = sub_content.find('div')
                if div:
                    bd_list = div.find('div', class_='BD_list')
                    if bd_list:
                        table = bd_list.find('table')
                        if table:
                            tbody = table.find('tbody')
        
        # 방법 3: class_='BD_list'로 찾기
        if not tbody:
            bd_list = soup.find('div', class_='BD_list')
            if bd_list:
                table = bd_list.find('table')
                if table:
                    tbody = table.find('tbody')
        
        # 방법 4: 모든 table에서 tbody 찾기
        if not tbody:
            tables = soup.find_all('table')
            for table in tables:
                tbody = table.find('tbody')
                if tbody:
                    # tbody에 tr이 있는지 확인
                    rows = tbody.find_all('tr')
                    if len(rows) > 0:
                        # 첫 번째 행에 td가 있는지 확인
                        first_row = rows[0]
                        if first_row.find_all('td'):
                            break
            else:
                tbody = None
        
        if not tbody:
            # 디버깅: HTML 일부 저장
            debug_html = soup.prettify()[:5000]  # 처음 5000자만
            logging.error(f"가정통신문 테이블을 찾을 수 없습니다. HTML 샘플: {debug_html}")
            return {
                "letters": [],
                "meta": {
                    "total_count": 0,
                    "last_updated": datetime.now().strftime("%Y-%m-%d"),
                    "source": site_name,
                    "url": url,
                    "error": "가정통신문 테이블을 찾을 수 없습니다."
                }
            }
        
        # 테이블의 모든 행(tr)을 찾습니다
        rows = tbody.find_all('tr')
        letters = []
        
        for row in rows:
            # 헤더 행은 건너뜁니다
            if row.find('th'):
                continue
                
            # td 요소들을 찾습니다
            cells = row.find_all('td')
            if len(cells) < 4:  # 최소 4개 컬럼 필요 (번호, 제목, 작성자, 등록일)
                continue
                
            try:
                # 번호 추출
                number_cell = cells[0]
                number = number_cell.get_text(strip=True)
                
                # 공지사항은 건너뜁니다
                if number == "공지" or number == "통합공지":
                    continue
                
                # 제목과 링크 추출 - td.ta_l 클래스를 가진 셀의 a 태그
                title_cell = row.find('td', class_='ta_l')
                if title_cell:
                    title_link = title_cell.find('a')
                    if title_link:
                        title = title_link.get_text(strip=True)
                        link = title_link.get('href', '')
                        
                        # JavaScript 링크 처리
                        if link.startswith('javascript:'):
                            onclick = title_link.get('onclick', '')
                            if onclick:
                                # onclick에서 파라미터 추출
                                match = re.search(r"['\"](\d+)['\"]", onclick)
                                if match:
                                    ntt_sn = match.group(1)
                                    # 상세보기 URL 생성
                                    link = f"/ocheonhs/na/ntt/selectNttView.do?mi=159125&bbsId=76556&nttSn={ntt_sn}"
                                else:
                                    link = ""
                        
                        if link and not link.startswith('http'):
                            link = urljoin(url, link)
                    else:
                        title = title_cell.get_text(strip=True)
                        link = ""
                else:
                    # fallback: 두 번째 셀에서 제목 찾기
                    title_cell = cells[1]
                    title_link = title_cell.find('a')
                    if title_link:
                        title = title_link.get_text(strip=True)
                        link = title_link.get('href', '')
                        if link and not link.startswith('http'):
                            link = urljoin(url, link)
                    else:
                        title = title_cell.get_text(strip=True)
                        link = ""
                
                # 날짜 추출 (일반적으로 4번째 셀, 인덱스 3)
                date_text = ""
                # 먼저 특정 인덱스에서 찾기 시도
                if len(cells) > 3:
                    date_cell = cells[3]
                    cell_text = date_cell.get_text(strip=True)
                    # YYYY.MM.DD 형식 찾기 (셀에 다른 텍스트가 있을 수 있음)
                    date_match = re.search(r'(\d{4}\.\d{2}\.\d{2})', cell_text)
                    if date_match:
                        date_text = date_match.group(1)
                
                # 인덱스에서 못 찾았으면 모든 셀에서 찾기
                if not date_text:
                    for idx, cell in enumerate(cells):
                        cell_text = cell.get_text(strip=True)
                        # YYYY.MM.DD 형식 찾기 (셀에 다른 텍스트가 있을 수 있음)
                        date_match = re.search(r'(\d{4}\.\d{2}\.\d{2})', cell_text)
                        if date_match:
                            date_text = date_match.group(1)
                            logging.debug(f"날짜를 인덱스 {idx}에서 찾았습니다: {date_text}")
                            break
                
                if not date_text:
                    logging.warning(f"날짜를 찾을 수 없습니다. 셀 내용: {[cell.get_text(strip=True) for cell in cells]}")
                
                # 첨부파일 여부 확인
                has_attachment = False
                for cell in cells:
                    if cell.find('img'):
                        has_attachment = True
                        break
                
                # 날짜 형식 정리 (YYYY.MM.DD 형식을 YYYY-MM-DD로 변환)
                try:
                    if re.match(r'\d{4}\.\d{2}\.\d{2}', date_text):
                        formatted_date = date_text.replace('.', '-')
                    else:
                        formatted_date = date_text
                except:
                    formatted_date = date_text
                
                letter_data = {
                    "number": number,
                    "title": title,
                    "author": "",
                    "date": formatted_date,
                    "views": "0",
                    "url": link,
                    "has_attachment": has_attachment
                }
                
                letters.append(letter_data)
                    
            except Exception as e:
                logging.error(f"행 파싱 중 오류 발생: {e}")
                continue
        
        logging.info(f"가정통신문 HTML 크롤링 완료: {len(letters)}개")
        
    except Exception as e:
        logging.error(f"HTML 파싱 오류: {e}")
        return {
            "letters": [],
            "meta": {
                "total_count": 0,
                "last_updated": datetime.now().strftime("%Y-%m-%d"),
                "source": site_name,
                "url": url,
                "error": f"HTML 파싱 오류: {str(e)}"
            }
        }
    
    # 메타 정보 추가
    result = {
        "letters": letters,
        "meta": {
            "total_count": len(letters),
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
            "source": site_name,
            "url": url
        }
    }
    
    logging.info(f"가정통신문 HTML 크롤링 완료: {len(letters)}개")
    return result

if __name__ == "__main__":
    # 오천고등학교 가정통신문 목록 페이지 URL
    test_url = "https://school.gyo6.net/ocheonhs/na/ntt/selectNttList.do?mi=159125&bbsId=76556"
    result = crawl_school_letters(test_url, "오천고등학교")
    
    # 모든 가정통신문 출력
    print("\n가정통신문 목록:")
    for i, letter in enumerate(result["letters"], 1):
        print(f"{letter.get('title')}\t{letter.get('date')}") 