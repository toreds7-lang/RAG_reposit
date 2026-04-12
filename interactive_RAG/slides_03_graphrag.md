---
marp: true
theme: default
paginate: true
---

# 03. Neo4j GraphRAG

### 지식 그래프 기반 질의응답 시스템

- 입력: `02_graph_build`에서 구축한 Neo4j 지식 그래프
- 목표: **VectorRetriever** + **Text2CypherRetriever** 기반 RAG 구현
- 도구: **neo4j-graphrag** 패키지 + **OpenAI GPT-4o**
- 핵심: 질문 → 그래프 검색 → LLM 응답 생성

---

# GraphRAG 아키텍처

```
사용자 질문
     │
     ▼
┌─────────────────────────────────┐
│  Retriever (검색기)              │
│                                 │
│  ① VectorRetriever              │ ← 의미 유사도 기반 벡터 검색
│     질문 임베딩 → cosine 유사도   │
│                                 │
│  ② Text2CypherRetriever         │ ← 자연어 → Cypher 쿼리 변환
│     LLM이 Cypher 생성 → 실행     │
└─────────────────────────────────┘
     │ 검색된 컨텍스트
     ▼
┌─────────────────────────────────┐
│  LLM (GPT-4o)                   │
│  컨텍스트 + 질문 → 최종 응답      │
└─────────────────────────────────┘
```

- **VectorRetriever**: "Multi-Head Attention이란?" → 유사한 섹션 검색
- **Text2CypherRetriever**: "섹션 3의 하위 구조는?" → 그래프 순회

---

# VectorRetriever — 의미 기반 검색

### 개념
- 질문 텍스트 → **임베딩 벡터** 변환 (text-embedding-ada-002)
- Neo4j 벡터 인덱스에서 **cosine similarity** 상위 k개 노드 반환
- 비정형 질문, 개념 검색에 적합

### 초기화 코드
```python
from neo4j_graphrag.retrievers import VectorRetriever
from neo4j_graphrag.embeddings.openai import OpenAIEmbeddings

embedder = OpenAIEmbeddings(model="text-embedding-ada-002", api_key=API_KEY)

vector_retriever = VectorRetriever(
    driver=driver,
    index_name="section_embedding",      # 02에서 생성한 벡터 인덱스
    embedder=embedder,
    return_properties=["id", "number", "title", "content", "page", "level"],
)
```

---

# VectorRetriever — 검색 예제

```python
# 의미 검색: Multi-Head Attention 관련 섹션
query = "How does multi-head attention work?"
result = vector_retriever.search(query_text=query, top_k=3)

for item in result.items:
    print(item.content[:200])
    print(f"Score: {item.metadata.get('score'):.4f}")
```

```python
# 의미 검색: Positional Encoding
query = "What is positional encoding and why is it needed?"
result = vector_retriever.search(query_text=query, top_k=3)
```

- `top_k`: 반환할 최대 결과 수
- `score`: cosine similarity 점수 (1에 가까울수록 유사)
- 질문과 의미적으로 유사한 섹션을 자동 검색

---

# Text2CypherRetriever — 자연어 → Cypher

### 개념
- 자연어 질문 → LLM이 **Cypher 쿼리 자동 생성** → Neo4j 실행
- 그래프 구조(계층, 관계) 탐색에 적합
- **그래프 스키마**를 LLM에 제공하여 정확한 Cypher 생성 유도

### 그래프 스키마 정의 (핵심)
```python
NEO4J_SCHEMA = """
Node Labels and Properties:
- Section(id, number, title, level, content, page, embedding)
  * level: 1=top-level, 2=subsection, 3=sub-subsection
- Table(id, number, caption, content, page, embedding)
- Figure(id, number, caption, description, page, embedding)
- Equation(id, number, formula, description, page, embedding)

Relationship Types:
- (Section)-[:IS_BELONGING_TO]->(Section)  : 자식 → 부모
- (Section)-[:CONTAINS]->(Section)         : 부모 → 자식
- (Section)-[:REFERENCES]->(Table/Figure)
- (Section)-[:INTRODUCES]->(Equation)
"""
```

---

# Text2CypherRetriever — 초기화 + 커스텀 프롬프트

```python
from neo4j_graphrag.retrievers import Text2CypherRetriever

# Cypher 문법 가이드 포함 커스텀 프롬프트
T2C_CUSTOM_PROMPT = """Task: Generate Cypher for Neo4j from user input.
Schema: {schema}
Examples: {examples}

CRITICAL: 복수 관계 타입은 파이프 구분자 사용
  Correct:   [:REFERENCES|INTRODUCES|CONTAINS]
  WRONG:     [:REFERENCES|:INTRODUCES|:CONTAINS]

Input: {query_text}
Cypher query:
"""

T2C_EXAMPLES = [
    "MATCH (s:Section)-[:REFERENCES|INTRODUCES]-(n) RETURN s, n",
    "MATCH (s:Section)-[:IS_BELONGING_TO]->(parent:Section) ...",
]

t2c_retriever = Text2CypherRetriever(
    driver=driver, llm=llm,
    neo4j_schema=NEO4J_SCHEMA,
    examples=T2C_EXAMPLES,
    custom_prompt=T2C_CUSTOM_PROMPT,
)
```

- **examples**: few-shot 예제로 Cypher 품질 향상
- **custom_prompt**: Neo4j 5.x 문법 규칙 명시 → 오류 방지

---

# GraphRAG 파이프라인 — Retriever + LLM 통합

```python
from neo4j_graphrag.generation import GraphRAG
from neo4j_graphrag.llm import OpenAILLM

llm = OpenAILLM(model_name="gpt-4o", model_params={"temperature": 0},
                api_key=API_KEY)

# VectorRetriever 기반 GraphRAG
rag = GraphRAG(retriever=vector_retriever, llm=llm)

# Text2CypherRetriever 기반 GraphRAG
rag_t2c = GraphRAG(retriever=t2c_retriever, llm=llm)
```

### 질의응답 실행
```python
# 의미 검색 기반 Q&A
response = rag.search(
    query_text="Scaled Dot-Product Attention 수식을 설명해주세요",
    retriever_config={"top_k": 5},
)
print(response.answer)

# 구조 탐색 기반 Q&A
response = rag_t2c.search(
    query_text="섹션 3의 모든 하위 섹션을 보여주세요"
)
print(response.answer)
```

---

# GraphRAG 활용 예제

### 논문 요약
```python
summary_query = """
"Attention Is All You Need" 논문을 요약하세요:
1. 핵심 아이디어
2. Transformer 모델 구조
3. Self-Attention의 장점
4. 주요 실험 결과
"""
response = rag.search(query_text=summary_query, retriever_config={"top_k": 8})
```

### 심층 요약 — 그래프 직접 탐색 + LLM
```python
# Cypher로 섹션 + 수식 + 표 데이터 직접 수집
sections = session.run("MATCH (s:Section) WHERE s.level=1 RETURN ...").data()
equations = session.run("MATCH (e:Equation) RETURN ...").data()
tables = session.run("MATCH (t:Table) RETURN ...").data()

# 수집된 컨텍스트를 OpenAI API에 직접 전달
response = openai_client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": context + prompt}],
)
```

---

# VectorRetriever vs Text2CypherRetriever

| 구분 | VectorRetriever | Text2CypherRetriever |
|------|----------------|---------------------|
| **검색 방식** | 임베딩 cosine 유사도 | 자연어 → Cypher 변환 |
| **적합한 질문** | "Attention이란?" (개념 검색) | "섹션 3의 하위 구조는?" (구조 탐색) |
| **장점** | 의미적 유사도, 비정형 질문 처리 | 정확한 그래프 순회, 관계 추적 |
| **단점** | 구조적 관계 탐색 어려움 | LLM의 Cypher 생성 정확도 의존 |
| **필요 조건** | 벡터 인덱스 | 그래프 스키마 + 예제 쿼리 |

### 실전 전략
- **의미 검색** (개념, 설명 질문) → VectorRetriever
- **구조 탐색** (계층, 관계, 목록 질문) → Text2CypherRetriever
- **두 Retriever를 목적에 따라 선택적 활용**
