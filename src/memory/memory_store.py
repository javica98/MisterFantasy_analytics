"""JSONL-backed memory store prepared for a future embedding index."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


DEFAULT_MEMORY_PATH = Path("newspaper/memory/memories.jsonl")


def read_memories(path: str | Path = DEFAULT_MEMORY_PATH) -> list[dict]:
    memory_path = Path(path)
    if not memory_path.exists():
        return []

    memories = []
    with memory_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            memories.append(json.loads(line))
    return memories


def upsert_memories(memories: Iterable[dict], path: str | Path = DEFAULT_MEMORY_PATH) -> int:
    """Insert/update memories by deterministic id. Returns number of new or updated rows."""
    memory_path = Path(path)
    memory_path.parent.mkdir(parents=True, exist_ok=True)

    existing = {memory["id"]: memory for memory in read_memories(memory_path)}
    changed = 0

    for memory in memories:
        memory_id = memory["id"]
        if existing.get(memory_id) != memory:
            existing[memory_id] = memory
            changed += 1

    ordered = sorted(existing.values(), key=lambda item: (item.get("fecha", ""), item.get("id", "")))
    with memory_path.open("w", encoding="utf-8") as handle:
        for memory in ordered:
            handle.write(json.dumps(memory, ensure_ascii=False, sort_keys=True) + "\n")

    return changed


def delete_memories(ids: Iterable[str], path: str | Path = DEFAULT_MEMORY_PATH) -> int:
    """Remove memories by id. Returns how many were actually removed."""
    memory_path = Path(path)
    ids_to_remove = set(ids)

    memories = read_memories(memory_path)
    kept = [memory for memory in memories if memory.get("id") not in ids_to_remove]
    removed = len(memories) - len(kept)

    if removed:
        with memory_path.open("w", encoding="utf-8") as handle:
            for memory in kept:
                handle.write(json.dumps(memory, ensure_ascii=False, sort_keys=True) + "\n")

    return removed


def retrieve_by_keywords(
    query: str,
    *,
    path: str | Path = DEFAULT_MEMORY_PATH,
    top_k: int = 8,
    temporada: str | None = None,
) -> list[dict]:
    """Tiny lexical retriever until the embedding index is added.

    Si se pasa `temporada`, solo se consideran memorias de esa temporada —
    evita que recuerdos de una temporada anterior contaminen las respuestas
    de la actual (hallazgo IA-02).
    """
    query_terms = _terms(query)
    if not query_terms:
        return []

    scored = []
    for memory in read_memories(path):
        if temporada is not None and memory.get("temporada") != temporada:
            continue
        text_terms = _terms(memory.get("query_text", ""))
        overlap = len(query_terms & text_terms)
        if overlap == 0:
            continue
        score = overlap + int(memory.get("importance", 1)) * 0.25
        scored.append((score, memory))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [memory for _, memory in scored[:top_k]]


def format_memory_context(memories: Iterable[dict]) -> str:
    lines = []
    for memory in memories:
        manager = memory.get("manager")
        player = memory.get("player")
        subject = " / ".join(part for part in [manager, player] if part)
        prefix = f"- {memory.get('fecha')} [{memory.get('category')}]"
        if subject:
            prefix += f" {subject}:"
        else:
            prefix += ":"
        lines.append(f"{prefix} {memory.get('summary')}")
    return "\n".join(lines)


def retrieve_relevant_memories(
    query: str,
    *,
    path: str | Path = DEFAULT_MEMORY_PATH,
    top_k: int = 8,
    temporada: str | None = None,
) -> list[dict]:
    """Use embeddings when available; fall back to lexical search.

    `temporada` filtra los recuerdos devueltos a los de esa temporada
    (hallazgo IA-02) — pásala explícitamente (ej. desde
    src.utils.db.get_active_season()) para no mezclar recuerdos de
    temporadas distintas en el mismo periódico.
    """
    try:
        from src.memory.embedding_store import retrieve_by_embedding

        return retrieve_by_embedding(query, memory_path=path, top_k=top_k, temporada=temporada)
    except Exception:
        return retrieve_by_keywords(query, path=path, top_k=top_k, temporada=temporada)


def _terms(text: str) -> set[str]:
    return {term.lower() for term in text.replace("_", " ").split() if len(term) > 2}
