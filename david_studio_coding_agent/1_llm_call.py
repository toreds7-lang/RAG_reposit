from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()

def llm_call(prompt: str, model: str = "gpt-5") -> str:
    messages = [{"role": "user", "content": prompt}]
    chat_completion = client.chat.completions.create(
        model=model,
        messages=messages,
    )
    return chat_completion.choices[0].message.content

if __name__ == "__main__":
    prompt = "한국의 수도는 어디일까?"
    response = llm_call(prompt)
    print("LLM 답변:", response)