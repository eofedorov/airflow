# Build from repo root: docker build -f apps/datastore/Dockerfile .
FROM python:slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY shared/common ./shared/common
COPY apps/datastore/src ./src
COPY apps/datastore/requirements.txt ./
COPY data/docs ./data/demo

RUN pip install --no-cache-dir -e ./shared/common \
    && pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/data/knowledge_base

ENV PYTHONPATH=/app/src
ENV DATA_PATH=/app/data
EXPOSE 8002
CMD ["uvicorn", "datastore.main:app", "--host", "0.0.0.0", "--port", "8002"]
