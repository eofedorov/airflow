# Build from repo root: docker build -f apps/mcp_server/Dockerfile .
# Two-stage: deps (cached) + app (only code). Rebuild deps only when shared/ or deps change.

# Stage deps: shared libs + heavy Python deps. No app code.
FROM python:slim AS deps
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install \
        --index-url https://download.pytorch.org/whl/cpu \
        --extra-index-url https://pypi.org/simple/ \
        torch sentence-transformers qdrant-client "psycopg[binary,pool]" mcp "uvicorn[standard]"

# Stage app: only app source (rebuilt when apps/mcp_server/src changes).
FROM deps AS app

COPY shared/common ./shared/common
COPY shared/db ./shared/db
COPY apps/mcp_server/src ./src

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -e ./shared/common -e ./shared/db

ENV PYTHONPATH=/app/src
EXPOSE 8001
CMD ["python", "-m", "mcp_server.main"]
