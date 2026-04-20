import os
from dotenv import load_dotenv
load_dotenv()
from firecrawl import FirecrawlApp
from openai import OpenAI
from utils import llm_call, JSON_llm, system_prompt
from pydantic import BaseModel
from typing import Optional

def test_llm_call_sync():
    """Test synchronous LLM call"""
    client = OpenAI()
    prompt = "안녕하세요!"
    model = "gpt-4o-mini"
    
    response = llm_call(prompt, model, client)
    print("\nLLM Call Test Results:")
    print(f"Prompt: {prompt}")
    print(f"Response: {response}")
    print(f"Response type: {type(response)}")
    print(f"Response length: {len(response)}")



class Evaluation(BaseModel):
    evaluation: str
    score: Optional[float]


def test_json_llm():
    """구조화된 LLM 응답을 받기"""
    client = OpenAI()    
    prompt = "다음 인사가 얼마나 친절한지 1줄로 평가해주고 점수도 0~10점 사이로 알려줘. 인사 : 안녕하십니까!!!"
    model = "gpt-4o-mini"
    
    response = JSON_llm(
        user_prompt=prompt,
        schema=Evaluation,
        client=client,
        system_prompt=system_prompt(),
        model=model
    )
    print("\nJSON LLM Test Results:")
    print(response.model_dump())  

def test_firecrawl_search():
    # FirecrawlApp 초기화 (API 키 필요)
    app = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY", ""))
    
    # 테스트할 검색어 설정
    query = "아침 운동의 신체적 이점"
    
    try:
        # 검색 실행
        # timeout: 검색 제한 시간 (밀리초)
        # limit: 최대 결과 수
        # scrapeOptions: 스크래핑 옵션 (마크다운 형식으로 결과 받기)
        response = app.search(
            query=query,
            timeout=15000,
            limit=1,
            scrape_options={"formats": ["markdown"]}
        )

        # 검색 결과 출력
        print(f"\n검색어 '{query}'에 대한 결과:\n")

        # 각 검색 결과 항목 출력
        for idx, result in enumerate(response.web or [], 1):
            # scrape_options 사용 시 Document 객체, 아닐 경우 SearchResultWeb 객체
            if hasattr(result, 'metadata') and result.metadata:
                title = result.metadata.title or '제목 없음'
                url = result.metadata.url or 'URL 없음'
                description = result.metadata.description or '설명 없음'
                markdown = result.markdown or ''
            else:
                title = getattr(result, 'title', None) or '제목 없음'
                url = getattr(result, 'url', None) or 'URL 없음'
                description = getattr(result, 'description', None) or '설명 없음'
                markdown = ''
            print(f"\n결과 {idx}:")
            print(f"제목: {title}")
            print(f"URL: {url}")
            print(f"본문: {markdown[:300]}...")
            print(f"설명: {description[:200]}...")
            
        return response
        
    except Exception as e:
        print(f"검색 중 오류 발생: {e}")
        return None

if __name__ == "__main__":
    # test_llm_call_sync()
    # test_json_llm()
    test_firecrawl_search()
    

