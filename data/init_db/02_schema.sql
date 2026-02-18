-- Схема, расширения, таблицы, триггеры, гранты, начальные данные
-- Выполняется под postgres в БД llm_gate (POSTGRES_DB)

-- Схема и расширения
CREATE SCHEMA IF NOT EXISTS llm AUTHORIZATION llm_gate_admin;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Default privileges (для будущих объектов, создаваемых llm_gate_admin)
ALTER DEFAULT PRIVILEGES FOR ROLE llm_gate_admin IN SCHEMA llm
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO llm_gate_app;
ALTER DEFAULT PRIVILEGES FOR ROLE llm_gate_admin IN SCHEMA llm
  GRANT USAGE, SELECT ON SEQUENCES TO llm_gate_app;
ALTER DEFAULT PRIVILEGES FOR ROLE llm_gate_admin IN SCHEMA llm
  GRANT SELECT ON TABLES TO llm_gate_ro;
ALTER DEFAULT PRIVILEGES FOR ROLE llm_gate_admin IN SCHEMA llm
  GRANT USAGE, SELECT ON SEQUENCES TO llm_gate_ro;

GRANT USAGE ON SCHEMA llm TO llm_gate_app, llm_gate_ro;
GRANT CREATE ON SCHEMA llm TO llm_gate_owner;
GRANT ALL ON SCHEMA llm TO llm_gate_admin;
REVOKE ALL ON SCHEMA llm FROM PUBLIC;

-- Переключаемся на llm_gate_admin, чтобы default privileges сработали
SET ROLE llm_gate_admin;

-- ====================== Таблицы ======================

CREATE TABLE IF NOT EXISTS llm.kb_documents (
  doc_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source            TEXT NOT NULL DEFAULT 'local_fs',
  doc_key           TEXT NOT NULL,
  title             TEXT NOT NULL,
  doc_type          TEXT NOT NULL DEFAULT 'general',
  project           TEXT NOT NULL DEFAULT 'core',
  language          TEXT NOT NULL DEFAULT 'ru',
  version           TEXT NOT NULL DEFAULT 'v1',
  sha256            TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_active         BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT uq_kb_documents_doc_key UNIQUE (doc_key)
);
CREATE INDEX IF NOT EXISTS ix_kb_documents_type_project
  ON llm.kb_documents (doc_type, project);

CREATE TABLE IF NOT EXISTS llm.kb_chunks (
  chunk_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  doc_id            UUID NOT NULL REFERENCES llm.kb_documents(doc_id) ON DELETE CASCADE,
  chunk_index       INT  NOT NULL,
  section           TEXT,
  text              TEXT NOT NULL,
  text_tokens_est   INT  NOT NULL DEFAULT 0,
  embedding_ref     TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_kb_chunks_doc_index UNIQUE (doc_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS ix_kb_chunks_doc_id ON llm.kb_chunks (doc_id);

CREATE TABLE IF NOT EXISTS llm.runs (
  run_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_type          TEXT NOT NULL,
  request_id        TEXT,
  user_query        TEXT,
  status            TEXT NOT NULL DEFAULT 'started',
  model             TEXT,
  temperature       NUMERIC(4,3),
  max_tokens        INT,
  tokens_in         INT NOT NULL DEFAULT 0,
  tokens_out        INT NOT NULL DEFAULT 0,
  cost_usd          NUMERIC(12,6) NOT NULL DEFAULT 0,
  error_code        TEXT,
  error_message     TEXT,
  started_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at       TIMESTAMPTZ,
  meta              JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_runs_started_at ON llm.runs (started_at DESC);
CREATE INDEX IF NOT EXISTS ix_runs_status ON llm.runs (status);

CREATE TABLE IF NOT EXISTS llm.run_retrievals (
  run_id            UUID NOT NULL REFERENCES llm.runs(run_id) ON DELETE CASCADE,
  chunk_id          UUID NOT NULL REFERENCES llm.kb_chunks(chunk_id) ON DELETE RESTRICT,
  rank              INT  NOT NULL,
  score             NUMERIC(12,6),
  used_in_context   BOOLEAN NOT NULL DEFAULT TRUE,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (run_id, chunk_id)
);
CREATE INDEX IF NOT EXISTS ix_run_retrievals_run_rank ON llm.run_retrievals (run_id, rank);

CREATE TABLE IF NOT EXISTS llm.tool_calls (
  tool_call_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id            UUID NOT NULL REFERENCES llm.runs(run_id) ON DELETE CASCADE,
  tool_name         TEXT NOT NULL,
  args              JSONB NOT NULL DEFAULT '{}'::jsonb,
  result_meta       JSONB NOT NULL DEFAULT '{}'::jsonb,
  status            TEXT NOT NULL DEFAULT 'ok',
  error_message     TEXT,
  duration_ms       INT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_tool_calls_run_id ON llm.tool_calls (run_id);
CREATE INDEX IF NOT EXISTS ix_tool_calls_tool_name ON llm.tool_calls (tool_name);

CREATE TABLE IF NOT EXISTS llm.sql_allowlist (
  allowlist_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  schema_name       TEXT NOT NULL DEFAULT 'llm',
  table_name        TEXT NOT NULL,
  is_enabled        BOOLEAN NOT NULL DEFAULT TRUE,
  comment           TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_sql_allowlist UNIQUE (schema_name, table_name)
);

-- ====================== Триггер ======================

CREATE OR REPLACE FUNCTION llm.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_kb_documents_updated_at ON llm.kb_documents;
CREATE TRIGGER trg_kb_documents_updated_at
BEFORE UPDATE ON llm.kb_documents
FOR EACH ROW EXECUTE FUNCTION llm.set_updated_at();

-- ====================== Возврат роли ======================
RESET ROLE;

-- Явные гранты на уже созданные таблицы
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA llm TO llm_gate_app;
GRANT SELECT ON ALL TABLES IN SCHEMA llm TO llm_gate_ro;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA llm TO llm_gate_app, llm_gate_ro;

-- ====================== Начальные данные ======================

-- Allowlist
INSERT INTO llm.sql_allowlist(schema_name, table_name, comment)
VALUES
  ('llm', 'kb_documents', 'Read-only: KB documents registry'),
  ('llm', 'kb_chunks', 'Read-only: KB chunks'),
  ('llm', 'runs', 'Read-only: runs telemetry'),
  ('llm', 'run_retrievals', 'Read-only: retrieval audit'),
  ('llm', 'tool_calls', 'Read-only: tool calls audit')
ON CONFLICT (schema_name, table_name) DO UPDATE
SET is_enabled = EXCLUDED.is_enabled, comment = EXCLUDED.comment;

-- Документы
INSERT INTO llm.kb_documents (doc_key, title, doc_type, project, language, version, sha256)
VALUES
  ('docs/runbook_payments.md', 'Runbook: Payments 500 errors', 'runbook', 'checkout', 'ru', 'v1', NULL),
  ('docs/adr_cache.md',        'ADR: Cache strategy for product cards', 'adr', 'catalog', 'ru', 'v1', NULL),
  ('docs/onboarding.md',       'Onboarding: LLM-Gate service', 'onboarding', 'core', 'ru', 'v1', NULL),
  ('docs/rfc_rag_quality.md',  'RFC: RAG quality and evaluation', 'rfc', 'core', 'ru', 'v1', NULL),
  ('docs/security_mcp.md',     'Security: MCP tool policies', 'policy', 'core', 'ru', 'v1', NULL)
ON CONFLICT (doc_key) DO UPDATE
SET title = EXCLUDED.title, doc_type = EXCLUDED.doc_type, project = EXCLUDED.project,
    language = EXCLUDED.language, version = EXCLUDED.version;

-- Чанки
WITH docs AS (SELECT doc_id, doc_key FROM llm.kb_documents)
INSERT INTO llm.kb_chunks (doc_id, chunk_index, section, text, text_tokens_est, embedding_ref)
SELECT d.doc_id, x.chunk_index, x.section, x.text, x.text_tokens_est, NULL
FROM docs d
JOIN LATERAL (VALUES
  (0, 'Symptoms',   'После релиза 2.1.3 на странице оплаты появляется HTTP 500. Часто сопровождается ростом ошибок stripe_charge_failed и таймаутами на платежном шлюзе.', 90),
  (1, 'Steps',      'Диагностика: 1) проверить графики 5xx по /api/checkout/pay 2) посмотреть последние деплои checkout-service 3) проверить статус Stripe и сетевые таймауты.', 110),
  (2, 'Mitigation', 'Митигация: откатить checkout-service на предыдущую версию, включить feature-flag fallback на альтернативный метод оплаты, увеличить таймауты только после проверки.', 120)
) AS x(chunk_index, section, text, text_tokens_est) ON d.doc_key = 'docs/runbook_payments.md'
ON CONFLICT (doc_id, chunk_index) DO UPDATE SET section = EXCLUDED.section, text = EXCLUDED.text, text_tokens_est = EXCLUDED.text_tokens_est;

WITH docs AS (SELECT doc_id, doc_key FROM llm.kb_documents)
INSERT INTO llm.kb_chunks (doc_id, chunk_index, section, text, text_tokens_est, embedding_ref)
SELECT d.doc_id, x.chunk_index, x.section, x.text, x.text_tokens_est, NULL
FROM docs d
JOIN LATERAL (VALUES
  (0, 'Decision',     'Принято: кешировать карточки товара в Redis на 10 минут, инвалидация по событию product.updated из Kafka.', 70),
  (1, 'Rationale',    'Причина: снизить нагрузку на Postgres и ускорить p95 для /api/products/{id}. Риск: устаревшие данные при сбоях инвалидации.', 95),
  (2, 'Consequences', 'Последствия: нужен outbox для событий, мониторинг lag по consumer, и fallback на чтение из БД при miss/ошибке Redis.', 95)
) AS x(chunk_index, section, text, text_tokens_est) ON d.doc_key = 'docs/adr_cache.md'
ON CONFLICT (doc_id, chunk_index) DO UPDATE SET section = EXCLUDED.section, text = EXCLUDED.text, text_tokens_est = EXCLUDED.text_tokens_est;

WITH docs AS (SELECT doc_id, doc_key FROM llm.kb_documents)
INSERT INTO llm.kb_chunks (doc_id, chunk_index, section, text, text_tokens_est, embedding_ref)
SELECT d.doc_id, x.chunk_index, x.section, x.text, x.text_tokens_est, NULL
FROM docs d
JOIN LATERAL (VALUES
  (0, 'Overview',  'LLM-Gate — сервис-оркестратор. Он принимает запросы, применяет контракты вывода (Pydantic), вызывает LLM и инструменты (через MCP) и пишет аудит в Postgres.', 120),
  (1, 'Local run', 'Локальный запуск: docker compose up (postgres, qdrant). Затем uvicorn app.main:app. Переменные: DATABASE_URL, QDRANT_URL, LLM_API_KEY.', 110)
) AS x(chunk_index, section, text, text_tokens_est) ON d.doc_key = 'docs/onboarding.md'
ON CONFLICT (doc_id, chunk_index) DO UPDATE SET section = EXCLUDED.section, text = EXCLUDED.text, text_tokens_est = EXCLUDED.text_tokens_est;

WITH docs AS (SELECT doc_id, doc_key FROM llm.kb_documents)
INSERT INTO llm.kb_chunks (doc_id, chunk_index, section, text, text_tokens_est, embedding_ref)
SELECT d.doc_id, x.chunk_index, x.section, x.text, x.text_tokens_est, NULL
FROM docs d
JOIN LATERAL (VALUES
  (0, 'Golden set',    'Качество RAG измеряем golden-набором: 20 вопросов, ожидаемые doc_id. Для ok-ответов должны быть источники (chunk_id) с цитатой.', 95),
  (1, 'Failure modes', 'Типовые сбои: нерелевантный retrieval (плохие чанки), слишком большой контекст, конфликт инструкций, отсутствие "insufficient_context".', 100)
) AS x(chunk_index, section, text, text_tokens_est) ON d.doc_key = 'docs/rfc_rag_quality.md'
ON CONFLICT (doc_id, chunk_index) DO UPDATE SET section = EXCLUDED.section, text = EXCLUDED.text, text_tokens_est = EXCLUDED.text_tokens_est;

WITH docs AS (SELECT doc_id, doc_key FROM llm.kb_documents)
INSERT INTO llm.kb_chunks (doc_id, chunk_index, section, text, text_tokens_est, embedding_ref)
SELECT d.doc_id, x.chunk_index, x.section, x.text, x.text_tokens_est, NULL
FROM docs d
JOIN LATERAL (VALUES
  (0, 'Policy', 'MCP tools по умолчанию read-only. Для sql_read разрешены только SELECT и allowlist таблиц. Запрещены ;, DDL/DML, системные схемы.', 110),
  (1, 'Limits', 'Лимиты: max_tool_calls_per_request=6, max_rows=200, max_payload=200KB. Все tool-calls логируются с args (с маскированием) и duration_ms.', 115)
) AS x(chunk_index, section, text, text_tokens_est) ON d.doc_key = 'docs/security_mcp.md'
ON CONFLICT (doc_id, chunk_index) DO UPDATE SET section = EXCLUDED.section, text = EXCLUDED.text, text_tokens_est = EXCLUDED.text_tokens_est;

-- Демо run
WITH new_run AS (
  INSERT INTO llm.runs (run_type, request_id, user_query, status, model, temperature, max_tokens, tokens_in, tokens_out, cost_usd, meta)
  VALUES ('rag_ask', 'demo-req-001', 'Почему на оплате может быть 500 и что делать?', 'ok', 'demo-model', 0.2, 800, 1200, 350, 0.012500, '{"k": 5, "strict_mode": true}'::jsonb)
  RETURNING run_id
),
picked_chunks AS (
  SELECT c.chunk_id, c.chunk_index
  FROM llm.kb_chunks c JOIN llm.kb_documents d ON d.doc_id = c.doc_id
  WHERE d.doc_key = 'docs/runbook_payments.md' AND c.chunk_index IN (0,1,2)
)
INSERT INTO llm.run_retrievals (run_id, chunk_id, rank, score, used_in_context)
SELECT r.run_id, pc.chunk_id, ROW_NUMBER() OVER (ORDER BY pc.chunk_index) - 1, (0.90 - (pc.chunk_index * 0.05))::numeric(12,6), TRUE
FROM new_run r CROSS JOIN picked_chunks pc;

WITH r AS (SELECT run_id FROM llm.runs WHERE request_id = 'demo-req-001' LIMIT 1)
INSERT INTO llm.tool_calls (run_id, tool_name, args, result_meta, status, duration_ms)
SELECT r.run_id, x.tool_name, x.args, x.result_meta, 'ok', x.duration_ms
FROM r CROSS JOIN (VALUES
  ('kb_search',    '{"query":"500 на оплате","k":5,"filters":{"project":"checkout"}}'::jsonb, '{"returned":3,"bytes_out":4200}'::jsonb, 38),
  ('kb_get_chunk', '{"chunk_id":"(example-1)"}'::jsonb, '{"bytes_out":1800}'::jsonb, 12),
  ('kb_get_chunk', '{"chunk_id":"(example-2)"}'::jsonb, '{"bytes_out":2100}'::jsonb, 14)
) AS x(tool_name, args, result_meta, duration_ms);
