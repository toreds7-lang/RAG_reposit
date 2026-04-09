# 파이썬으로 딥리서치 만들어보기


* 참고 자료 : https://github.com/dzhng/deep-research
기존 오픈소스 코드를 파이썬으로 변형하여 OpenAI의 Deep Research와 같은 심층적인 AI 에이전트 패턴을 파이썬으로 구현해보는 실습이다.

# 사전준비
## 사전 준비
1. [OpenAI 키 발급받기](https://github.com/dabidstudio/dabidstudio_guides/blob/main/get-openai-api-key.md)
2. [Firecrawl API키 발급받기](https://www.firecrawl.dev/)
3. [파이썬 가상환경 설정](https://github.com/dabidstudio/dabidstudio_guides/blob/main/python-set-venv.md)
4. 가상환경 활성화 한 후 패키지 설치
```bash
pip install openai python-dotenv firecrawl-py
```
5. .env 파일을 생성한 후 발급받은 API 키를 채워두기
```bash
OPENAI_API_KEY="OpenAI키"
FIRECRAWL_API_KEY="Firecrawl키"
```

# 코드 실행해보기
```
python main.py
```

- 리서치 하고싶은 주제를 입력하면 맞춤형 리서치를 위한 후속 질문이 나와서 답변을 해줍니다.
- 답변을 모두 완료하면 최종 보고서가 output 폴더에 저장됩니다.

# 유의사항
- Firecrawl의 경우 무료사용자(Free Tier)는 특정 키워드로 검색을 하는 경우 5회/min 제한이 있음
- 연구의 너비/깊이를 2/2로 해야 함 (이 이상으로 할 경우 1분 이상 기달려야 함)


