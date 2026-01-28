from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

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

# 본문 추출 함수 (기존과 동일)
def extract_main_content(soup, url):
    for tag in soup(['script', 'style', 'header', 'footer', 'nav', 'aside', 'form', 'noscript', 'iframe', 'button']):
        tag.decompose()
    for tag in soup.find_all(True, {'class': True}):
        classes = " ".join(tag.get('class'))
        if any(keyword in classes.lower() for keyword in ['comment', 'sidebar', 'related', 'menu', 'popup']):
            tag.decompose()
            
    content = None
    if "blog.naver.com" in url:
        content = soup.find('div', {'class': 'se-main-container'}) or soup.find('div', id='postViewArea')
    elif "tistory.com" in url:
        content = soup.find('div', {'class': 'tt_article_useless_p_margin'}) or soup.find('div', {'class': 'article'}) or soup.find('div', {'class': 'entry-content'}) or soup.find('div', {'class': 'area_view'})
    elif "velog.io" in url:
        content = soup.find('div', {'class': 'sc-bgqQoT'}) or soup.find('div', id='root')
    elif "medium.com" in url:
        content = soup.find('article') or soup.find('section')
    elif "brunch.co.kr" in url:
        content = soup.find('div', {'class': 'wrap_body'})

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

    # ---------------------------------------------------------
    # 🚨 [노션(Notion) 예외 처리]
    # Vercel에서는 노션 크롤링(Selenium)이 불가능하므로 자동 통과 처리
    # ---------------------------------------------------------
    if "notion.site" in url or "notion.so" in url:
        return {
            "success": True,
            "length": 9999, # 임의의 큰 숫자
            "pass": True,
            "message": "노션 페이지는 글자 수 확인 없이 자동 인증됩니다! ✅"
        }
    # ---------------------------------------------------------

    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200:
            return {"success": False, "message": "블로그에 접속할 수 없습니다."}

        soup = BeautifulSoup(response.text, 'html.parser')

        # [네이버 블로그 iframe 처리]
        if "blog.naver.com" in url:
            iframe = soup.find('iframe', id='mainFrame')
            if iframe:
                real_url = "https://blog.naver.com" + iframe['src']
                response = requests.get(real_url, headers=headers, timeout=5)
                soup = BeautifulSoup(response.text, 'html.parser')

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

# 실행: uvicorn main:app --reload