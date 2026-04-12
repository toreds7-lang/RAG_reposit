---
marp: true
theme: default
paginate: true
---

# 02. Neo4j 지식 그래프 구축

### CSV → Neo4j Knowledge Graph + 벡터 임베딩

- 입력: `01_pdf_extraction`에서 생성한 CSV 파일 7종
- 목표: Neo4j에 **노드 + 관계** 로드 → **벡터 인덱스** 생성
- 도구: **Neo4j Python Driver** + **OpenAI Embeddings API**
- 핵심 패턴: `UNWIND` + `MERGE` (배치 처리, 중복 방지)

---

# 그래프 스키마

```
[ Paper ] ←─PART_OF─ [ Section ] ─IS_NEXT_TO─▶ [ Section ]
                          │
                  IS_BELONGING_TO / CONTAINS
                          │
                      [ Section ]
                          │
          ┌───────────────┼─────────────────┐
       REFERENCES     INTRODUCES        REFERENCES
          ▼               ▼                 ▼
       [ Table ]     [ Equation ]       [ Figure ]
```

| 노드 | 주요 속성 |
|------|----------|
| `Paper` | paper_id, title, authors, year |
| `Section` | id, number, title, level, content, **embedding** |
| `Table` | id, number, caption, content, **embedding** |
| `Figure` | id, number, caption, description, **embedding** |
| `Equation` | id, number, formula, description, **embedding** |

---

# 제약조건 및 인덱스 — Cypher

```cypher
-- 유니크 제약조건: 노드 ID 중복 방지
CREATE CONSTRAINT section_id IF NOT EXISTS
  FOR (s:Section) REQUIRE s.id IS UNIQUE

CREATE CONSTRAINT table_id IF NOT EXISTS
  FOR (t:Table) REQUIRE t.id IS UNIQUE

-- 검색 성능용 인덱스
CREATE INDEX section_number IF NOT EXISTS
  FOR (s:Section) ON (s.number)

CREATE INDEX section_level IF NOT EXISTS
  FOR (s:Section) ON (s.level)
```

- `IF NOT EXISTS` → 멱등성 보장 (재실행 안전)
- 유니크 제약 → `MERGE` 시 중복 노드 방지의 기반

---

# UNWIND + MERGE 패턴 — 배치 노드 생성

```python
def _run_batched(self, cypher, rows, chunk_size=500):
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        session.run(cypher, {"rows": chunk})
```

```cypher
-- Section 노드 생성 Cypher
UNWIND $rows AS row
MERGE (s:Section {id: row.id})
ON CREATE SET
    s.number  = row.number,
    s.title   = row.title,
    s.level   = toInteger(row.level),
    s.content = row.content,
    s.page    = toInteger(row.page)
```

- **UNWIND**: Python 리스트 → Neo4j 행 단위 반복
- **MERGE**: 존재하면 매칭, 없으면 생성 (중복 방지)
- **ON CREATE SET**: 최초 생성 시에만 속성 설정
- **chunk_size=500**: 메모리 효율적 배치 처리

---

# 관계 생성 — Cypher

### 계층 관계 (IS_BELONGING_TO + CONTAINS)
```cypher
UNWIND $rows AS row
MATCH (child:Section  {id: row.from_id})
MATCH (parent:Section {id: row.to_id})
MERGE (child)-[:IS_BELONGING_TO]->(parent)
MERGE (parent)-[:CONTAINS]->(child)
```

### 순서 관계 (IS_NEXT_TO)
```cypher
UNWIND $rows AS row
MATCH (a:Section {id: row.from_id})
MATCH (b:Section {id: row.to_id})
MERGE (a)-[:IS_NEXT_TO]->(b)
```

### 참조 관계 (동적 레이블 처리)
```python
# 관계 유형 + 노드 레이블 조합별 분리 실행
for rel_type, group in df.groupby("relationship"):
    for from_label, to_label in group.groupby([...]).groups.keys():
        cypher = f"""
        MATCH (a:{from_label} {{id: row.from_id}})
        MATCH (b:{to_label}   {{id: row.to_id}})
        MERGE (a)-[r:{rel_type}]->(b)
        """
```

---

# OpenAI 임베딩 + 벡터 인덱스

### 임베딩 생성
```python
def embed_text(text):
    text = text.strip().replace("\n", " ")[:8000]
    response = openai_client.embeddings.create(
        input=[text], model="text-embedding-ada-002"
    )
    return response.data[0].embedding  # 1536차원 벡터

# Neo4j 노드에 임베딩 저장
MATCH (n:Section {id: $node_id})
SET n.embedding = $embedding
```

### 벡터 인덱스 생성
```cypher
CREATE VECTOR INDEX section_embedding IF NOT EXISTS
FOR (n:Section) ON (n.embedding)
OPTIONS {indexConfig: {
    `vector.dimensions`: 1536,
    `vector.similarity_function`: 'cosine'
}}
```

- 각 노드의 텍스트(content/description/formula) → 1536차원 벡터
- **cosine similarity** 기반 의미 검색 지원
- Section, Table, Figure, Equation 각각 별도 벡터 인덱스

---

# 검증 쿼리

### 노드/관계 수 확인
```cypher
MATCH (n)
RETURN labels(n)[0] AS label, count(n) AS count

MATCH ()-[r]->()
RETURN type(r) AS relationship, count(r) AS count
```

### 계층 구조 확인
```cypher
MATCH (child:Section)-[:IS_BELONGING_TO]->(parent:Section)
RETURN parent.number, child.number, child.title
ORDER BY parent.number, child.number
```

### 임베딩 확인
```cypher
MATCH (n) WHERE n.embedding IS NOT NULL
RETURN labels(n)[0] AS label,
       count(n) AS nodes_with_embedding,
       size(n.embedding) AS embedding_dim
```

- 전체 파이프라인 실행 후 반드시 데이터 정합성 검증
- Neo4j Browser에서 시각적 확인 가능: `MATCH (n)-[r]->(m) RETURN n,r,m LIMIT 50`
