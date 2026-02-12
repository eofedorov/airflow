# LLM-Gate (P1)

AI-шлюз для классификации входящих инженерных задач и извлечения структурированных данных. Возвращает строго валидный JSON по контракту, с repair при невалидном ответе LLM.

## Стек

- Python 3.10+
- FastAPI, Pydantic, Jinja2, OpenAI API

## Установка

```bash
cd p1-prompt-contracts
pip install -e ".[dev]"
cp .env.example .env
```

## Запуск

```bash
uvicorn app.main:app --reload
```

API: http://127.0.0.1:8000  
Документация: http://127.0.0.1:8000/docs

## Эндпоинты

- `GET /prompts` — список доступных промптов и версий
- `POST /run/{prompt_name}` — выполнить промпт (body: `version`, `task`, `input`, `constraints`)

Пример:

```bash
curl -X POST http://127.0.0.1:8000/run/classify \
  -H "Content-Type: application/json" \
  -d '{"version": "v1", "task": "Classify", "input": "После релиза 2.1.3 на странице оплаты 500 ошибка."}'
```

## Тесты

```bash
pytest
```

Тесты включают:
- **test_contracts.py** — валидация схем (валидные проходят, лишние поля/неверные типы — падают)
- **test_render.py** — рендер шаблонов (подстановка task, input, output_contract)
- **test_runner_mock.py** — runner с mock LLM: happy path, repair path, оба невалидны
- **test_acceptance.py** — 10 кейсов (баг, фича, вопрос, UX, дубликат, техдолг): все возвращают валидный JSON, минимум 8 из 10 с ожидаемой меткой при mock
