"""
LLMOps — observabilidad de llamadas a LLMs (Gemini, Groq).

Cada llamada relevante (WriterAgent/Gemini, OrchestratorAgent/Groq,
validación Pydantic de las cards) se registra en la tabla `llm_calls` de
PostgreSQL — la misma instancia compartida de AI Center (event_log,
agent_actions, system_logs viven ahí).

Best-effort por diseño: si Postgres no está accesible (ej. GitHub Actions
sin red hacia el mini PC, o Postgres caído) el logging se descarta con un
warning y el pipeline de producción sigue funcionando con normalidad.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

_PG_HOST = os.getenv("LLMOPS_PG_HOST", os.getenv("POSTGRES_HOST", "localhost"))
_PG_PORT = int(os.getenv("LLMOPS_PG_PORT", os.getenv("POSTGRES_PORT", "5432")))
_PG_DB = os.getenv("LLMOPS_PG_DB", os.getenv("POSTGRES_DB", "aicenter"))
_PG_USER = os.getenv("LLMOPS_PG_USER", os.getenv("POSTGRES_USER", "aicenter"))
_PG_PASSWORD = os.getenv("LLMOPS_PG_PASSWORD", os.getenv("POSTGRES_PASSWORD", "aicenter_secret"))
_ENABLED = os.getenv("LLMOPS_ENABLED", "true").lower() not in {"0", "false", "no"}

PROJECT_NAME = "misterfantasy_analytics"


def log_llm_call(
    component: str,
    provider: str,
    model: str,
    success: bool,
    latency_ms: int | None = None,
    attempt: int = 1,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    estimated_cost_usd: float | None = None,
    validation_errors: list | None = None,
    error: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Inserta un registro de una llamada LLM. Nunca lanza — un fallo aquí
    (sin red, Postgres caído) no debe tirar el pipeline de producción."""
    if not _ENABLED:
        return
    try:
        import psycopg2  # import perezoso: solo hace falta si LLMOps está activo

        conn = psycopg2.connect(
            host=_PG_HOST, port=_PG_PORT, dbname=_PG_DB,
            user=_PG_USER, password=_PG_PASSWORD, connect_timeout=3,
        )
        try:
            with conn, conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO llm_calls (
                        project, component, provider, model, attempt, success,
                        latency_ms, prompt_tokens, completion_tokens, total_tokens,
                        estimated_cost_usd, validation_errors, error, metadata
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        PROJECT_NAME, component, provider, model, attempt, success,
                        latency_ms, prompt_tokens, completion_tokens, total_tokens,
                        estimated_cost_usd,
                        json.dumps(validation_errors, ensure_ascii=False) if validation_errors else None,
                        error,
                        json.dumps(metadata, ensure_ascii=False) if metadata else None,
                    ),
                )
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"[llm_logger] No se pudo registrar la llamada LLM (component={component}): {e}")
