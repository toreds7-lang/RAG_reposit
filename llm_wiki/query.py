import os
import re
import glob
import tiktoken
from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage, HumanMessage

WIKI_DIR = "llm-wiki/wiki"
CONTEXT_TOKEN_BUDGET = 20_000
TOP_K_PAGES = 5

SYSTEM_PROMPT = """You are a wiki assistant for LangGraph learning notes.
Answer the user's query using ONLY the provided wiki pages.
- Cite which wiki pages your answer draws from (e.g. "source: langgraph-memory.md")
- If the answer is not in the wiki, say so explicitly
- Be concise and specific"""


def load_wiki():
    pages = {}
    for path in glob.glob(f"{WIKI_DIR}/*.md"):
        name = os.path.basename(path)
        with open(path, encoding="utf-8") as f:
            pages[name] = f.read()
    return pages


def load_api_key():
    with open("env.txt") as f:
        for line in f:
            if line.startswith("OPENAI_API_KEY="):
                os.environ["OPENAI_API_KEY"] = line.strip().split("=", 1)[1]


def score_pages(question: str, pages: dict) -> list:
    words = {w.lower() for w in re.findall(r'\w+', question) if len(w) >= 3}
    scored = []
    for name, content in pages.items():
        haystack = content.lower() + " " + name.lower()
        score = sum(1 for w in words if w in haystack)
        scored.append((name, content, score))
    return sorted(scored, key=lambda x: (x[2], len(x[1])), reverse=True)


def select_pages(scored: list, budget: int, top_k: int) -> list:
    enc = tiktoken.encoding_for_model("gpt-4o")
    if all(s == 0 for _, _, s in scored):
        scored = sorted(scored, key=lambda x: len(x[1]), reverse=True)
    selected = []
    used_tokens = 0
    for name, content, _score in scored:
        if len(selected) >= top_k:
            break
        page_tokens = len(enc.encode(f"=== {name} ===\n{content}"))
        if used_tokens + page_tokens <= budget:
            selected.append((name, content))
            used_tokens += page_tokens
    return selected


def query_wiki(question: str) -> str:
    pages = load_wiki()
    scored = score_pages(question, pages)
    selected = select_pages(scored, CONTEXT_TOKEN_BUDGET, TOP_K_PAGES)

    if not selected:
        return "No relevant wiki pages found for your question."

    context = "\n\n".join(f"=== {name} ===\n{content}" for name, content in selected)
    model = init_chat_model("gpt-4o", model_provider="openai")

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Wiki content:\n{context}\n\nQuestion: {question}")
    ]
    response = model.invoke(messages)
    return response.content


if __name__ == "__main__":
    load_api_key()
    print("Wiki Assistant - Type 'Quit' or 'quit' to exit")

    while True:
        question = input("\nQuestion: ").strip()

        if question.lower() == "quit":
            print("Goodbye!")
            break

        if not question:
            print("Please enter a question.")
            continue

        print("\nAnswer:")
        print(query_wiki(question))
