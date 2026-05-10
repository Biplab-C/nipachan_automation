import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from providers.llm.base import LLMProvider

_root = Path(__file__).parent.parent.parent
load_dotenv(_root / ".env")
load_dotenv(_root / ".env.example")

_client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1",
)

MODEL = "deepseek-chat"


class DeepSeekProvider(LLMProvider):
    def complete(self, system: str, user: str) -> str:
        response = _client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
        )
        return response.choices[0].message.content.strip()
