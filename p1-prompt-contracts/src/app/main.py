"""FastAPI entrypoint."""
from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(title="LLM-Gate", description="AI-шлюз для инженерных задач")
app.include_router(router, prefix="", tags=["run"])
