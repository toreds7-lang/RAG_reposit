import json
import os
from typing import Optional
from openai import OpenAI
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage


def generate_quiz_from_code(code_cells: list, api_key: str = None) -> list:
    """Generate fill-in-the-blank quiz questions from code cells."""
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY")

    llm = ChatOpenAI(
        api_key=api_key,
        model="gpt-4o-mini",
        temperature=0.7,
    )

    quiz_questions = []

    for i, cell in enumerate(code_cells):
        if cell["type"] != "code" or not cell["source"].strip():
            continue

        code_snippet = cell["source"][:300]

        system_prompt = """You are an expert educator creating quiz questions from Python code.
Generate a single fill-in-the-blank question that tests understanding of the code.
The blank should be represented by _____.
Return a JSON object with 'question', 'blank_text', and 'answer' fields."""

        user_prompt = f"""Given this Python code:

```python
{code_snippet}
```

Create a fill-in-the-blank question that tests understanding of this code.
Example: "The method _____ is used to display the first rows of a DataFrame."
Answer: "head"

Return ONLY valid JSON with no markdown code blocks."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            response = llm.invoke(messages)
            response_text = response.content.strip()

            # Try to parse JSON
            import json
            question_data = json.loads(response_text)
            question_data["cell_index"] = i
            quiz_questions.append(question_data)
        except Exception as e:
            print(f"Warning: Could not generate quiz for cell {i}: {e}")

    return quiz_questions


def save_quiz(quiz_questions: list, output_path: str):
    """Save quiz questions to JSON file."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(quiz_questions, f, indent=2)
    print(f"Quiz saved to {output_path}")


def generate_quiz_from_graph(graph_path: str, cells: list, output_path: str, api_key: str = None):
    """Generate quiz from knowledge graph."""
    quiz = generate_quiz_from_code(cells, api_key)
    save_quiz(quiz, output_path)
    return quiz
