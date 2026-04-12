---
marp: true
theme: default
paginate: true
---

# 01. PDF 구조 추출

### PDF → 구조화된 지식 그래프 데이터

- 대상 논문: **"Attention Is All You Need"** (Vaswani et al., 2017)
- 목표: PDF에서 **섹션, 표, 그림, 수식** 추출 → CSV/Excel 저장
- 도구: **PyMuPDF** (fitz) + **pandas**
- 최종 산출물: 노드 4종 CSV + 관계 3종 CSV + 통합 Excel

---

# 전체 파이프라인

```
PDF (1706.03762v7.pdf)
  │
  ├─ PyMuPDF 텍스트 추출
  │     └─ 페이지별 텍스트 + 전체 텍스트
  │
  ├─ 메타데이터 정의 (하드코딩)
  │     ├─ 섹션 계층 구조 (목차 기반)
  │     ├─ 표 캡션 + 내용
  │     ├─ 그림 캡션 + 설명
  │     └─ 수식 공식 + 설명
  │
  ├─ 정규식 기반 섹션 본문 추출
  │
  ├─ 관계 정의
  │     ├─ IS_BELONGING_TO (자식→부모)
  │     ├─ IS_NEXT_TO (인접 섹션)
  │     └─ REFERENCES / ILLUSTRATES / SUPPORTS / ...
  │
  └─ CSV / Excel 저장
```

---

# 노드(Node) 설계 — 4가지 유형

| 노드 | 속성 | 예시 |
|------|------|------|
| **Section** | id, number, title, level, content, page | `section_3_2_1`, "Scaled Dot-Product Attention" |
| **Table** | id, number, caption, content, page | `table_1`, 복잡도 비교표 |
| **Figure** | id, number, caption, description, page | `figure_1`, Transformer 아키텍처 다이어그램 |
| **Equation** | id, number, formula, description, page | `eq_1`, Attention(Q,K,V) 공식 |

- **level**: 1=최상위(Introduction), 2=하위(Attention), 3=소하위(Scaled Dot-Product)
- **content**: PyMuPDF로 추출한 섹션 본문 텍스트

---

# PyMuPDF 텍스트 추출 — 핵심 코드

```python
import fitz  # PyMuPDF

def extract_full_text_by_page(pdf_path):
    doc = fitz.open(str(pdf_path))
    pages = {}
    for i, page in enumerate(doc):
        pages[i + 1] = page.get_text("text")  # 1-indexed
    doc.close()
    return pages

def extract_all_text(pdf_path):
    doc = fitz.open(str(pdf_path))
    text_parts = [page.get_text("text") for page in doc]
    doc.close()
    return "\n".join(text_parts)
```

- `fitz.open()` → PDF 문서 객체
- `page.get_text("text")` → 페이지 내 텍스트 추출
- 전체 텍스트 → 섹션 헤딩 파싱에 활용

---

# 섹션 본문 추출 — 정규식 기반 파싱

```python
def extract_section_content(full_text, sections):
    # 섹션 헤딩 패턴: "3.2.1 Scaled Dot-Product Attention"
    for sec in sections:
        num = re.escape(sec["number"])
        title = re.escape(sec["title"])
        pattern = rf"(?m)^{num}\s+{title}"
        match = re.search(pattern, full_text)
        positions.append((match.start(), match.end(), sec))

    # 현재 헤딩 ~ 다음 헤딩 사이의 텍스트 = 섹션 content
    for i, (start, end, sec) in enumerate(sorted_positions):
        next_start = sorted_positions[i+1][0] if i+1 < len(...) else len(full_text)
        sec["content"] = full_text[end:next_start].strip()
```

- 논문 목차를 Python 리스트로 하드코딩 (SECTIONS_META)
- 정규식으로 헤딩 위치 탐색 → 인접 헤딩 사이 텍스트 슬라이싱

---

# 관계(Relationship) 설계 — 3가지 유형

```
Section ──IS_BELONGING_TO──▶ Section (자식→부모)
  3.2.1                        3.2

Section ──IS_NEXT_TO──▶ Section (같은 레벨, 순서)
  3.2.1                  3.2.2

Section ──REFERENCES──▶ Table / Figure / Equation
Figure  ──ILLUSTRATES──▶ Section
Table   ──SUPPORTS──▶ Section
Table   ──COMPARES──▶ Section
Section ──INTRODUCES──▶ Equation
```

- **IS_BELONGING_TO**: 섹션 번호에서 부모 자동 유도 (`3.2.1` → `3.2`)
- **IS_NEXT_TO**: 같은 부모 아래 인접 섹션 연결
- **REFERENCES 계열**: 메타데이터의 `related_section` 필드 기반

---

# 관계 생성 — 핵심 코드

### 부모-자식 관계 (IS_BELONGING_TO)
```python
def get_parent_number(number):
    parts = number.split(".")
    if len(parts) <= 1:
        return None  # 최상위 섹션은 부모 없음
    return ".".join(parts[:-1])  # "3.2.1" → "3.2"
```

### 인접 순서 관계 (IS_NEXT_TO)
```python
# 같은 부모의 자식들을 그룹화
parent_groups = defaultdict(list)
for sec in sections_data:
    parent = get_parent(sec["number"])
    parent_groups[parent].append(sec)

# 각 그룹 내에서 순서대로 연결
for parent, children in parent_groups.items():
    children_sorted = sorted(children, key=lambda x: ...)
    for i in range(len(children_sorted) - 1):
        # children_sorted[i] → children_sorted[i+1]
```

---

# DataFrame → CSV/Excel 저장

### 출력 파일 구조

| 파일 | 내용 |
|------|------|
| `nodes_sections.csv` | Section 노드 (id, number, title, level, content, page) |
| `nodes_tables.csv` | Table 노드 (id, number, caption, content, page) |
| `nodes_figures.csv` | Figure 노드 (id, number, caption, description, page) |
| `nodes_equations.csv` | Equation 노드 (id, number, formula, description, page) |
| `relationships_hierarchy.csv` | IS_BELONGING_TO (from_id, to_id) |
| `relationships_sequence.csv` | IS_NEXT_TO (from_id, to_id) |
| `relationships_references.csv` | REFERENCES 계열 (from_id, relationship, to_id) |
| `transformer_knowledge_graph.xlsx` | 전체 통합 (7개 시트 + Summary) |

- 모든 CSV: UTF-8 인코딩, pandas `to_csv()` 사용
- Excel: `openpyxl` 엔진, 시트별 분리 저장
