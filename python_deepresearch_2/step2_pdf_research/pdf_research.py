"""
Recursive PDF research loop. Mirrors step2_research/research.py exactly but replaces
Firecrawl web search with hybrid retrieval over a pre-built PDF index.

Two behavioral additions vs. research.py:
  1. `seen_chunk_ids: set[int]` threads through recursion, preventing the same chunks
     from being re-processed by the LLM across sub-queries.
  2. Adaptive early-stop: when hybrid search returns zero new chunks (everything top-
     ranked has already been seen), the LLM-processing call is skipped for that branch.
     The `depth` parameter still acts as a hard ceiling.
"""

import logging
from typing import Dict, List, Optional, Set

from pydantic import BaseModel

from step2_pdf_research.pdf_ingestion import Chunk
from step2_pdf_research.pdf_search import HybridIndex, search_hybrid
from utils import JSON_llm, system_prompt

logger = logging.getLogger(__name__)


class PDFQuery(BaseModel):
    query: str
    research_goal: str


class PDFQueryResponse(BaseModel):
    queries: List[PDFQuery]


class PDFResultResponse(BaseModel):
    learnings: List[str]
    followUpQuestions: List[str]


class PDFResearchResult(BaseModel):
    learnings: List[str]
    source_pages: List[str]


def format_source_page(chunk: Chunk) -> str:
    return (
        f"PDF: {chunk.source_pdf} — Page {chunk.page_start}"
        f"{f'-{chunk.page_end}' if chunk.page_end != chunk.page_start else ''} "
        f"(Section: {chunk.section_hint})"
    )


def generate_pdf_queries(
    query: str,
    client,
    model: str,
    num_queries: int = 3,
    learnings: Optional[List[str]] = None,
) -> List[PDFQuery]:
    """PDF-internal search queries; emphasize exact technical terminology from the document."""
    logger.info(
        "generate_pdf_queries | model=%s | num_queries=%d | has_prior_learnings=%s",
        model, num_queries, bool(learnings),
    )
    prompt = (
        f"다음 사용자 입력을 기반으로 **이 PDF 문서 내부**를 검색하기 위한 쿼리를 생성하세요. "
        f"웹 검색이 아니라 PDF 내부 검색용이므로, 문서에서 실제 등장할 법한 정확한 기술 용어를 사용하세요. "
        f"JSON 객체를 반환하며, 'queries' 배열 필드에 {num_queries}개의 쿼리를 포함해야 합니다. "
        f"각 쿼리 객체에는 'query'(검색어)와 'research_goal'(이 쿼리로 알아내려는 목표) 필드가 포함되어야 "
        f"하며, 각 쿼리는 서로 다른 측면을 다루도록 고유해야 합니다: "
        f"<입력>{query}</입력>"
    )
    if learnings:
        prompt += (
            f"\n\n다음은 이전 연구에서 얻은 학습 내용입니다. 이를 활용하여 아직 다루지 않은 "
            f"구체적인 측면을 탐색하는 쿼리를 생성하세요: {' '.join(learnings)}"
        )

    response = JSON_llm(prompt, PDFQueryResponse, client, system_prompt=system_prompt(), model=model)
    try:
        result = PDFQueryResponse.model_validate(response)
        queries = result.queries if result.queries else []
        logger.info("generate_pdf_queries produced %d queries", len(queries))
        print(f"PDF 내부 검색 쿼리 {len(queries)}개 생성됨")
        return queries[:num_queries]
    except Exception as e:
        logger.error(
            "generate_pdf_queries FAILED | response_was_none=%s | error=%s",
            response is None, e, exc_info=True,
        )
        print(f"오류: generate_pdf_queries에서 JSON 응답 처리 실패: {e}")
        return []


def process_pdf_chunks(
    query: str,
    chunks: List[Chunk],
    client,
    model: str,
    num_learnings: int = 5,
    num_follow_up_questions: int = 3,
) -> Dict[str, List[str]]:
    """Extract learnings and follow-up questions from retrieved PDF chunks.

    Strictly grounded: the prompt forbids information not present in the provided chunks
    and requires each learning to end with an inline page citation "(p. N)".
    """
    logger.info(
        "process_pdf_chunks | query='%.80s' | num_chunks=%d | model=%s",
        query, len(chunks), model,
    )
    if not chunks:
        return {"learnings": [], "followUpQuestions": []}

    chunks_xml = "\n".join(
        f'<chunk id="{c.chunk_id}" page="{c.page_start}" section="{c.section_hint}">\n'
        f"{c.text}\n"
        f"</chunk>"
        for c in chunks
    )
    # Cap total chunk payload at 150k chars (matches reporting.py).
    chunks_xml = chunks_xml[:150000]

    prompt = (
        f"다음은 쿼리 <쿼리>{query}</쿼리>에 대해 PDF 문서에서 검색된 청크들입니다.\n\n"
        f"**중요 규칙:**\n"
        f"1. 반드시 제공된 청크 내용만 사용하세요. 청크에 없는 정보는 절대 포함하지 마세요.\n"
        f"2. 각 학습 내용(learning)의 끝에 `(p. N)` 형식으로 주 출처 페이지를 명시하세요.\n"
        f"3. 후속 질문(followUpQuestions)은 **청크에서 언급되지만 충분히 설명되지 않은 개념**을 "
        f"타겟팅하세요. 이는 재귀 검색이 그래프처럼 관련 개념으로 확장되도록 돕습니다.\n\n"
        f"JSON 객체를 반환하며, 'learnings'와 'followUpQuestions' 배열을 포함해야 합니다. "
        f"최대 {num_learnings}개의 학습 내용과 {num_follow_up_questions}개의 후속 질문을 생성하세요. "
        f"각 학습은 고유하고 간결하며 정보가 풍부해야 합니다.\n\n"
        f"<검색된 청크>\n{chunks_xml}\n</검색된 청크>"
    )
    response = JSON_llm(prompt, PDFResultResponse, client, system_prompt=system_prompt(), model=model)
    try:
        result = PDFResultResponse.model_validate(response)
        logger.info(
            "process_pdf_chunks | %d learnings | %d follow-ups extracted",
            len(result.learnings), len(result.followUpQuestions),
        )
        return {
            "learnings": result.learnings,
            "followUpQuestions": result.followUpQuestions[:num_follow_up_questions],
        }
    except Exception as e:
        logger.error(
            "process_pdf_chunks FAILED | query='%.80s' | error=%s",
            query, e, exc_info=True,
        )
        return {"learnings": [], "followUpQuestions": []}


def deep_pdf_research(
    query: str,
    breadth: int,
    depth: int,
    client,
    model: str,
    index: HybridIndex,
    learnings: Optional[List[str]] = None,
    source_pages: Optional[List[str]] = None,
    seen_chunk_ids: Optional[Set[int]] = None,
    top_k_per_query: int = 8,
) -> Dict[str, List[str]]:
    """Recursively explore the PDF.

    Mirrors deep_research() structure: breadth//2 on recursion, depth-1 decrement,
    next_query composed from research_goal + followUpQuestions.
    """
    learnings = learnings or []
    source_pages = source_pages or []
    seen_chunk_ids = seen_chunk_ids if seen_chunk_ids is not None else set()

    logger.info(
        "deep_pdf_research | depth=%d | breadth=%d | acc_learnings=%d | acc_pages=%d | seen=%d",
        depth, breadth, len(learnings), len(source_pages), len(seen_chunk_ids),
    )
    print(f" ---------- Deep PDF Research 시도 ------------------")
    print(f" <주제> \n {query} \n </주제>")

    pdf_queries = generate_pdf_queries(
        query=query, client=client, model=model, num_queries=breadth, learnings=learnings,
    )
    logger.info("deep_pdf_research | %d queries generated for depth=%d", len(pdf_queries), depth)
    print(f" ------------ 해당 <주제>에 대해 생성된 PDF 검색 쿼리 ({len(pdf_queries)}개) ------------")
    for q in pdf_queries:
        print(f"   - {q.query}  (목표: {q.research_goal})")

    for index_i, pdf_query in enumerate(pdf_queries, start=1):
        logger.info(
            "deep_pdf_research | processing query %d/%d: '%s'",
            index_i, len(pdf_queries), pdf_query.query,
        )
        retrieved = search_hybrid(
            query=pdf_query.query,
            index=index,
            client=client,
            top_k=top_k_per_query,
            exclude_chunk_ids=seen_chunk_ids,
        )

        if not retrieved:
            logger.info(
                "deep_pdf_research | EARLY STOP | query='%s' | all top chunks already seen",
                pdf_query.query,
            )
            print(f"  - 쿼리 '{pdf_query.query}': 새로운 청크 없음 (이미 모두 탐색됨), 건너뜀")
            continue

        new_chunk_ids = [c.chunk_id for c in retrieved]
        seen_chunk_ids.update(new_chunk_ids)
        new_sources = [format_source_page(c) for c in retrieved]

        chunk_result = process_pdf_chunks(
            query=pdf_query.query,
            chunks=retrieved,
            client=client,
            model=model,
            num_follow_up_questions=breadth,
        )
        print(f"  - {index_i}번째 쿼리 '{pdf_query.query}' 처리 완료")
        print(f"  - 새 청크: {new_chunk_ids}")
        print(f"  - 학습 {len(chunk_result['learnings'])}건 추출")

        all_learnings = learnings + chunk_result["learnings"]
        all_sources = source_pages + new_sources
        new_depth = depth - 1
        new_breadth = max(1, breadth // 2)

        if new_depth > 0:
            logger.info(
                "deep_pdf_research | recursing | new_depth=%d | new_breadth=%d",
                new_depth, new_breadth,
            )
            next_query = (
                f"이전 연구목표: {pdf_query.research_goal}\n"
                f"후속 연구방향: {' '.join(chunk_result['followUpQuestions'])}"
            )
            sub_result = deep_pdf_research(
                query=next_query,
                breadth=new_breadth,
                depth=new_depth,
                client=client,
                model=model,
                index=index,
                learnings=all_learnings,
                source_pages=all_sources,
                seen_chunk_ids=seen_chunk_ids,
                top_k_per_query=top_k_per_query,
            )
            learnings = sub_result["learnings"]
            source_pages = sub_result["source_pages"]
        else:
            learnings = all_learnings
            source_pages = all_sources

    logger.info(
        "deep_pdf_research | done depth=%d | total_learnings=%d | total_pages=%d",
        depth, len(set(learnings)), len(set(source_pages)),
    )
    return {
        "learnings": list(set(learnings)),
        "source_pages": list(set(source_pages)),
    }
