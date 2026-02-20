# Build from repo root: docker build -f apps/mcp_server/Dockerfile .
FROM python:slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY shared/common ./shared/common
COPY shared/db ./shared/db
COPY apps/mcp_server/src ./src

RUN pip install --no-cache-dir -e ./shared/common -e ./shared/db \
    && pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu \
        --extra-index-url https://pypi.org/simple/ \
        torch sentence-transformers qdrant-client "psycopg[binary,pool]" mcp "uvicorn[standard]"

ENV PYTHONPATH=/app/src
EXPOSE 8001
CMD ["python", "-m", "mcp_server.main"]
