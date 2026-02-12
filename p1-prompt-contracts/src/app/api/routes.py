"""Эндпоинты API."""
from fastapi import APIRouter
from pydantic import BaseModel

from app.prompts.registry import list_prompts as registry_list_prompts
from app.services.runner import run as runner_run

router = APIRouter()


class RunRequestBody(BaseModel):
    version: str = "v1"
    task: str = ""
    input: str | dict = ""
    constraints: dict = {}


@router.get("/prompts")
def list_prompts():
    """Список доступных промптов и версий из registry."""
    return {"prompts": registry_list_prompts()}


@router.post("/run/{prompt_name}")
def run_prompt(prompt_name: str, body: RunRequestBody):
    """
    Выполнить промпт. Возвращает валидный JSON по контракту или {"error", "diagnostics"}.
    """
    result = runner_run(
        prompt_name=prompt_name,
        version=body.version,
        task=body.task,
        input_data=body.input,
        constraints=body.constraints,
    )
    if result["ok"]:
        return result["data"]
    return {"error": result["error"], "diagnostics": result["diagnostics"]}
