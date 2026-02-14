# LLM-Gate (P1)

AI-шлюз для классификации входящих инженерных задач и извлечения структурированных данных. Возвращает строго валидный JSON по контракту, с repair при невалидном ответе LLM.

## Стек

- Python 3.10+
- FastAPI, Pydantic, Jinja2, OpenAI API

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
