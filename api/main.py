from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CheckRequest(BaseModel):
    url: str

@app.get("/")
def health_check():
    return {"status": "awake"}

# [수정] 네이버 블로그 전용 추출 로직 강화
def extract_naver_content(soup):
    content = ""
    
    # 1. 스마트에디터 One (신버전) - 텍스트 모듈 직접 타겟팅 (가장 정확함)
    # se-module-text 또는 se-text-paragraph 클래스를 가진 요소들을 모두 찾음
    text_modules = soup.find_all(class_=['se-module-text', 'se-text-paragraph'])
    if text_modules:
        content = " ".join([t.get_text(separator=' ', strip=True) for t in text_modules])
        return content

    # 2. 스마트에디터 One (컨테이너 방식 - 백업)
    container = soup.find('div', {'class': 'se-main-container'})
    if container:
        return container.get_text(separator=' ', strip=True)

    # 3. 스마트에디터 2.0 (구버전)
    old_container = soup.find('div', id='postViewArea')
    if old_container:
        return old_container.get_text(separator=' ', strip=True)
        
    return ""

# 본문 추출 함수
def extract_main_content(soup, url):
    # 불필요한 태그 제거
    for tag in soup(['script', 'style', 'header', 'footer', 'nav', 'aside', 'form', 'noscript', 'iframe', 'button']):
        tag.decompose()
            
    content = None

    # [수정] 네이버 블로그 로직 분리
    if "blog.naver.com" in url:
        text = extract_naver_content(soup)
        if text: return text

    # 나머지 사이트 로직 (기존 유지)
    elif "tistory.com" in url:
        content = soup.find('div', {'class': 'tt_article_useless_p_margin'}) or soup.find('div', {'class': 'article'}) or soup.find('div', {'class': 'entry-content'}) or soup.find('div', {'class': 'area_view'})
    elif "velog.io" in url:
        content = soup.find('div', {'class': 'sc-bgqQoT'}) or soup.find('div', id='root')
    elif "medium.com" in url:
        content = soup.find('article') or soup.find('section')
    elif "brunch.co.kr" in url:
        content = soup.find('div', {'class': 'wrap_body'})

    # 공통 폴백 (Fallback)
    if not content:
        content = soup.find('article') or soup.find('main') or soup.find('div', {'role': 'main'}) or soup.find('div', id='content') or soup.find('div', {'class': 'content'}) or soup.find('div', {'class': 'post-body'}) or soup.find('div', {'class': 'markdown-body'})

    if not content:
        content = soup.find('body')

    if content:
        return content.get_text(separator=' ', strip=True)
    return ""


@app.post("/check-length")
def check_length(req: CheckRequest):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    url = req.url

    # [수정] 모바일 링크(m.blog.naver.com)가 들어오면 PC 링크로 변환
    if "m.blog.naver.com" in url:
        url = url.replace("m.blog.naver.com", "blog.naver.com")

    # 노션 예외 처리
    if "notion.site" in url or "notion.so" in url:
        return {
            "success": True,
            "length": 9999,
            "pass": True,
            "message": "노션 페이지는 글자 수 확인 없이 자동 인증됩니다! ✅"
        }

    try:
        response = requests.get(url, headers=headers, timeout=10) # 타임아웃 조금 늘림
        if response.status_code != 200:
            return {"success": False, "message": "블로그에 접속할 수 없습니다."}

        soup = BeautifulSoup(response.text, 'html.parser')

        # [네이버 블로그 iframe 처리]
        if "blog.naver.com" in url:
            iframe = soup.find('iframe', id='mainFrame')
            
            # iframe이 있으면 내부의 진짜 주소(src)를 가져옴
            if iframe:
                real_url = "https://blog.naver.com" + iframe['src']
                
                # iframe 내부 페이지 재요청
                response = requests.get(real_url, headers=headers, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
            
            # [추가] 혹시 iframe이 없고, 리다이렉트나 다른 파라미터 구조일 경우 대비
            # logNo 파라미터가 있는데 mainFrame을 못 찾은 경우 등은 
            # 현재 soup에서 바로 텍스트 추출 시도

        # 본문 추출
        text_content = extract_main_content(soup, url)
        
        # 공백 제거 후 글자 수 세기
        length = len(text_content.replace(" ", "").replace("\n", ""))
        
        MIN_LENGTH = 700 
        
        return {
            "success": True,
            "length": length,
            "pass": length >= MIN_LENGTH,
            "message": f"현재 글자 수: {length}자 (본문 추정)"
        }

    except Exception as e:
        print(f"Error checking url {url}: {e}")
        return {"success": False, "message": "시스템이 내용을 읽을 수 없는 구조입니다."}