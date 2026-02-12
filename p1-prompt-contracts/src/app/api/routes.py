"""Эндпоинты API."""
import logging

from fastapi import APIRouter
from pydantic import BaseModel

from app.prompts.registry import list_prompts as registry_list_prompts
from app.services.runner import run as runner_run

router = APIRouter()
logger = logging.getLogger(__name__)


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
    logger.info("[API] POST /run/%s version=%s task=%s", prompt_name, body.version, (body.task or "")[:50])
    result = runner_run(
        prompt_name=prompt_name,
        version=body.version,
        task=body.task,
        input_data=body.input,
        constraints=body.constraints,
    )
    if result["ok"]:
        logger.info("[API] /run/%s ok returning data", prompt_name)
        return result["data"]
    logger.warning("[API] /run/%s error=%s", prompt_name, result.get("error", ""))
    return {"error": result["error"], "diagnostics": result["diagnostics"]}
