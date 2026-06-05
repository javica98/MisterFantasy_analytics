"""Local NumPy embedding index for newspaper memories."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

import numpy as np

from src.memory.memory_store import DEFAULT_MEMORY_PATH, read_memories


DEFAULT_EMBEDDINGS_PATH = Path("newspaper/memory/embeddings.npy")
DEFAULT_INDEX_PATH = Path("newspaper/memory/embedding_index.json")
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def rebuild_embedding_index(
    *,
    memory_path: str | Path = DEFAULT_MEMORY_PATH,
    embeddings_path: str | Path = DEFAULT_EMBEDDINGS_PATH,
    index_path: str | Path = DEFAULT_INDEX_PATH,
    model_name: str = DEFAULT_EMBEDDING_MODEL,
) -> dict:
    """
    Rebuild the vector index from memories.jsonl, reusing cached vectors for
    already-indexed memory ids. Only new/unknown ids are re-encoded.
    """
    memories = read_memories(memory_path)
    ids = [memory["id"] for memory in memories]
    texts = [memory.get("query_text") or memory.get("summary") or "" for memory in memories]

    embeddings_path = Path(embeddings_path)
    index_path = Path(index_path)
    embeddings_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing cached vectors keyed by memory id
    cached_by_id = _load_cached_embeddings_by_id(embeddings_path, index_path)

    # Find which memories need new encoding
    new_positions = [i for i, id_ in enumerate(ids) if id_ not in cached_by_id]
    if new_positions:
        new_texts = [texts[i] for i in new_positions]
        model = _load_sentence_transformer(model_name)
        new_vecs = _encode_texts(model, new_texts)
        for i, vec in zip(new_positions, new_vecs):
            cached_by_id[ids[i]] = vec

    if ids:
        embeddings = np.array([cached_by_id[id_] for id_ in ids], dtype=np.float32)
    else:
        embeddings = np.empty((0,), dtype=np.float32)

    np.save(embeddings_path, embeddings)

    index = {
        "model_name": model_name,
        "memory_path": str(Path(memory_path)),
        "embeddings_path": str(embeddings_path),
        "count": len(memories),
        "dimension": int(embeddings.shape[1]) if embeddings.ndim == 2 and embeddings.size else 0,
        "items": [
            {
                "row": row,
                "id": memory["id"],
                "fecha": memory.get("fecha"),
                "category": memory.get("category"),
                "manager": memory.get("manager"),
                "player": memory.get("player"),
                "importance": memory.get("importance", 1),
            }
            for row, memory in enumerate(memories)
        ],
    }

    with index_path.open("w", encoding="utf-8") as handle:
        json.dump(index, handle, ensure_ascii=False, indent=2)

    return index


def _load_cached_embeddings_by_id(
    embeddings_path: Path, index_path: Path
) -> dict[str, np.ndarray]:
    """Return {memory_id: vector} for all entries already in the index."""
    if not embeddings_path.exists() or not index_path.exists():
        return {}
    try:
        existing_vecs = np.load(embeddings_path)
        with index_path.open("r", encoding="utf-8") as handle:
            existing_index = json.load(handle)
        return {
            item["id"]: existing_vecs[item["row"]]
            for item in existing_index.get("items", [])
            if item["row"] < len(existing_vecs)
        }
    except Exception:
        return {}


def retrieve_by_embedding(
    query: str,
    *,
    memory_path: str | Path = DEFAULT_MEMORY_PATH,
    embeddings_path: str | Path = DEFAULT_EMBEDDINGS_PATH,
    index_path: str | Path = DEFAULT_INDEX_PATH,
    model_name: str | None = None,
    top_k: int = 8,
    min_score: float = 0.0,
) -> list[dict]:
    """Retrieve memories by semantic similarity against the local embedding index."""
    memories = read_memories(memory_path)
    if not memories:
        return []

    index = _read_index(index_path)
    model_name = model_name or index.get("model_name") or DEFAULT_EMBEDDING_MODEL

    embeddings = np.load(embeddings_path)
    if len(memories) != embeddings.shape[0]:
        raise ValueError(
            "El indice de embeddings no coincide con memories.jsonl. "
            "Ejecuta scripts/rebuild_memory_embeddings.py."
        )

    model = _load_sentence_transformer(model_name)
    query_embedding = _encode_texts(model, [query])[0]
    scores = embeddings @ query_embedding

    ranked_rows = np.argsort(scores)[::-1]
    results = []
    for row in ranked_rows:
        score = float(scores[row])
        if score < min_score:
            continue
        memory = dict(memories[int(row)])
        memory["embedding_score"] = round(score, 4)
        results.append(memory)
        if len(results) >= top_k:
            break

    return results


def build_memory_query(events_json: dict, limit_items: int = 30) -> str:
    """Build a semantic query from the current newspaper data."""
    parts: list[str] = []

    clasificacion = events_json.get("clasificacion", {})
    for table_name in ("general", "jornada"):
        table = clasificacion.get(table_name, {})
        ordered = sorted(table.items(), key=lambda item: item[1].get("posicion", 999))[:3]
        for manager, stats in ordered:
            parts.append(
                f"{table_name} manager {manager} posicion {stats.get('posicion')} puntos {stats.get('puntos')}"
            )

    for transfer in events_json.get("transfers", [])[:limit_items]:
        parts.append(
            " ".join(
                str(value)
                for value in [
                    "mercado",
                    transfer.get("subtype"),
                    transfer.get("compra_venta"),
                    transfer.get("equipo"),
                    transfer.get("jugador"),
                    transfer.get("equipo_jugador"),
                    abs(float(transfer.get("ganancias") or 0)),
                ]
                if value is not None
            )
        )

    gameweek = sorted(
        events_json.get("gameweek", []),
        key=lambda row: abs(row.get("puntos", 0)),
        reverse=True,
    )[:limit_items]
    for row in gameweek:
        parts.append(
            " ".join(
                str(value)
                for value in [
                    "jornada",
                    row.get("manager"),
                    row.get("jugador"),
                    row.get("equipo_jugador"),
                    row.get("puntos"),
                    row.get("goles"),
                    row.get("asistencias"),
                    "roja" if row.get("roja", 0) else None,
                    "gol propia" if row.get("gol_propia", 0) else None,
                    "penalti parado" if row.get("penalti_parado", 0) else None,
                    "penalti fallado" if row.get("penalti_fallado", 0) else None,
                ]
                if value is not None
            )
        )

    return "\n".join(parts)


def _encode_texts(model, texts: Iterable[str]) -> np.ndarray:
    embeddings = model.encode(
        list(texts),
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(embeddings, dtype=np.float32)


def _load_sentence_transformer(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "Falta instalar sentence-transformers. Ejecuta: pip install sentence-transformers"
        ) from exc

    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    try:
        return SentenceTransformer(model_name, local_files_only=True)
    except TypeError:
        return SentenceTransformer(model_name)


def _read_index(index_path: str | Path) -> dict:
    with Path(index_path).open("r", encoding="utf-8") as handle:
        return json.load(handle)
