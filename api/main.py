from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin # URL 합치기용 모듈

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

@app.post("/check-length")
def check_length(req: CheckRequest):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    url = req.url

    try:
        # 1. 일단 접속
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200:
            return {"success": False, "message": "블로그에 접속할 수 없습니다."}

        soup = BeautifulSoup(response.text, 'html.parser')

        # ---------------------------------------------------------
        # 🚨 [네이버 블로그 전용 처리 로직]
        # ---------------------------------------------------------
        if "blog.naver.com" in url:
            iframe = soup.find('iframe', id='mainFrame')
            
            if iframe:
                # iframe의 src(진짜 주소)를 가져옴
                # 예: /PostView.naver?blogId=...
                real_url = "https://blog.naver.com" + iframe['src']
                
                # 진짜 주소로 다시 요청!
                response = requests.get(real_url, headers=headers, timeout=5)
                soup = BeautifulSoup(response.text, 'html.parser')
        # ---------------------------------------------------------

        # HTML 태그 제거하고 순수 텍스트만 추출
        text_content = soup.get_text(separator=' ', strip=True)
        
        # 공백 제거 후 글자 수 세기
        length = len(text_content.replace(" ", ""))
        
        return {
            "success": True,
            "length": length,
            "pass": length >= 700,
            "message": f"현재 글자 수: {length}자"
        }

    except Exception as e:
        print(e) # 서버 콘솔에 에러 출력
        return {"success": False, "message": f"오류 발생: 시스템이 읽을 수 없는 구조입니다."}

# 실행: uvicorn main:app --reload