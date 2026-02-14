import os
import requests
from openai import OpenAI

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

if not GITHUB_TOKEN:
    raise ValueError("Set GITHUB_TOKEN environment variable")

BASE_URL = "https://models.github.ai/inference/v1"

headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Content-Type": "application/json",
}

# ---------- 1. Получаем список моделей ----------
print("Fetching available models...\n")

resp = requests.get("https://models.github.ai/catalog/models", headers=headers)
resp.raise_for_status()

models_data = resp.json()

print(models_data)

# ---------- 2. Тестовый запрос ----------
first_model = 'openai/gpt-4.1-nano'

print(f"\nTesting model: {first_model}\n")

client = OpenAI(
    base_url=BASE_URL,
    api_key=GITHUB_TOKEN,
)

completion = client.chat.completions.create(
    model=first_model,
    messages=[
        {"role": "user", "content": "Напиши короткое приветствие на русском языке."}
    ],
    max_tokens=50,
)

print("Model response:")
print(completion.choices[0].message.content)
