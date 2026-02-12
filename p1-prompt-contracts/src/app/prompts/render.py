"""Рендеринг шаблона и сбор контекста для LLM."""
import json
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.prompts.registry import PromptSpec, TEMPLATES_DIR


def get_schema_description(schema_class: type) -> str:
    """
    Краткое описание формата ответа в виде примера данных (не полная JSON Schema),
    чтобы модель возвращала данные, а не схему со служебными полями.
    """
    s = schema_class.model_json_schema()
    props = s.get("properties") or {}
    required = set(s.get("required") or [])
    parts = []
    for name in required or props.keys():
        if name not in props:
            continue
        p = props[name]
        ptype = p.get("type", "string")
        if ptype == "array":
            items = p.get("items", {})
            ref = items.get("$ref", "")
            if "Entity" in str(ref):
                parts.append(f'"{name}": [{{"type": "<string>", "value": "<string>"}}, ...]')
            else:
                parts.append(f'"{name}": [...]')
        elif ptype == "number" or (ptype == "integer" and "confidence" in name):
            parts.append(f'"{name}": <float 0-1>')
        elif "enum" in p or "const" in p:
            enum_vals = p.get("enum", [p.get("const")] if "const" in p else [])
            parts.append(f'"{name}": "{enum_vals[0]}" (one of: {", ".join(str(x) for x in enum_vals)})')
        else:
            max_len = p.get("maxLength", "")
            suffix = f", max {max_len} chars" if max_len else ""
            parts.append(f'"{name}": "<string>{suffix}"')
    return "Только этот JSON, без других полей:\n{" + ", ".join(parts) + "}"


class RenderContext:
    """Контекст для рендера: задача, вход, ограничения, описание схемы вывода."""
    def __init__(
        self,
        task: str,
        input_data: str | dict | Any,
        constraints: dict[str, Any] | None = None,
        output_contract: str | None = None,
    ):
        self.task = task
        self.input = input_data if isinstance(input_data, str) else json.dumps(input_data, ensure_ascii=False)
        self.constraints = constraints or {}
        self.output_contract = output_contract or ""


def render(spec: PromptSpec, context: RenderContext) -> tuple[str, str]:
    """
    Собрать сообщения для LLM: (system_message, user_message).
    Шаблон рендерится с контекстом; output_contract подставляется в шаблон.
    """
    if not context.output_contract and spec.output_schema:
        context.output_contract = get_schema_description(spec.output_schema)

    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(default=False),
    )
    template = env.get_template(spec.template_path.name)
    user_message = template.render(
        task=context.task,
        input=context.input,
        output_contract=context.output_contract,
        constraints=context.constraints,
    ).strip()

    system_message = spec.system_rules
    return system_message, user_message
