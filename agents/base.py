import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

_root = Path(__file__).parent.parent
load_dotenv(_root / ".env")
load_dotenv(_root / ".env.example")  # fallback if .env not created yet

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1",
)

ORCHESTRATOR_MODEL = "deepseek-reasoner"
AGENT_MODEL = "deepseek-chat"
