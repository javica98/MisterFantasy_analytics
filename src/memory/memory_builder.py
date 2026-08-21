"""Build compact memories from newspaper source data and generated cards."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any


IMPORTANT_CARD_TYPES = {
    "clasificacion",
    "rumor",
    "Fichaje destacado",
    "Venta record",
    "Venta récord",
    "MVP de la jornada",
    "Peor actuacion de la jornada",
    "Peor actuación de la jornada",
    "Expulsion",
    "Expulsión",
    "Heroe bajo palos",
    "Héroe bajo palos",
    "Gol en propia",
}


def build_memories(
    events_json: dict[str, Any],
    cards_json: dict[str, Any] | None = None,
    temporada: str | None = None,
) -> list[dict[str, Any]]:
    """Create factual and narrative memory records for one newspaper run.

    `temporada` se guarda en cada memoria para poder filtrar la recuperación
    por temporada activa (ver retrieve_relevant_memories) y evitar que
    recuerdos de una temporada anterior contaminen el periódico de la
    siguiente (hallazgo IA-02). Si se omite, la memoria queda sin
    temporada — no colisiona con memorias etiquetadas, pero tampoco se
    recupera cuando se filtra por una temporada concreta.
    """
    cards_json = cards_json or {}
    fecha = _memory_date(events_json)

    memories: list[dict[str, Any]] = []
    memories.extend(_classification_memories(events_json, fecha, temporada))
    memories.extend(_transfer_memories(events_json, fecha, temporada))
    memories.extend(_gameweek_memories(events_json, fecha, temporada))
    memories.extend(_narrative_memories(cards_json, fecha, temporada))

    return [_with_id(memory) for memory in memories]


def _classification_memories(events_json: dict[str, Any], fecha: str, temporada: str | None = None) -> list[dict[str, Any]]:
    clasificacion = events_json.get("clasificacion", {})
    general = clasificacion.get("general", {})
    jornada = clasificacion.get("jornada", {})
    if not general and not jornada:
        return []

    ordered_general = sorted(general.items(), key=lambda item: item[1].get("posicion", 999))
    ordered_jornada = sorted(jornada.items(), key=lambda item: item[1].get("posicion", 999))

    lider = ordered_general[0] if ordered_general else None
    perseguidor = ordered_general[1] if len(ordered_general) > 1 else None
    colista = ordered_general[-1] if ordered_general else None
    mejor_jornada = ordered_jornada[0] if ordered_jornada else None
    peor_jornada = ordered_jornada[-1] if ordered_jornada else None

    facts: dict[str, Any] = {
        "lider": _manager_snapshot(lider),
        "perseguidor": _manager_snapshot(perseguidor),
        "colista": _manager_snapshot(colista),
        "mejor_jornada": _manager_snapshot(mejor_jornada),
        "peor_jornada": _manager_snapshot(peor_jornada),
    }

    distancia = None
    if lider and perseguidor:
        distancia = lider[1].get("puntos", 0) - perseguidor[1].get("puntos", 0)
        facts["distancia_lider_perseguidor"] = distancia

    summary_parts = []
    if lider:
        summary_parts.append(f"{lider[0]} lidera la general con {lider[1].get('puntos')} puntos")
    if perseguidor:
        summary_parts.append(f"{perseguidor[0]} persigue desde la posicion {perseguidor[1].get('posicion')}")
    if distancia is not None:
        summary_parts.append(f"la distancia entre ambos es de {distancia} puntos")
    if mejor_jornada:
        summary_parts.append(f"{mejor_jornada[0]} fue el mejor manager de la jornada")
    if colista:
        summary_parts.append(f"{colista[0]} cierra la clasificacion general")

    summary = ". ".join(summary_parts) + "."
    tags = _clean_list(
        [
            "clasificacion",
            "liderato",
            lider[0] if lider else None,
            perseguidor[0] if perseguidor else None,
            colista[0] if colista else None,
            mejor_jornada[0] if mejor_jornada else None,
        ]
    )

    return [
        _base_memory(
            fecha=fecha,
            layer="factual",
            category="clasificacion",
            summary=summary,
            facts=facts,
            tags=tags,
            importance=5,
            temporada=temporada,
        )
    ]


def _transfer_memories(events_json: dict[str, Any], fecha: str, temporada: str | None = None) -> list[dict[str, Any]]:
    memories = []
    for transfer in events_json.get("transfers", []):
        manager = transfer.get("equipo")
        jugador = transfer.get("jugador")
        accion = transfer.get("compra_venta")
        subtipo = transfer.get("subtype")
        dinero = abs(float(transfer.get("ganancias") or 0))
        equipo_jugador = transfer.get("equipo_jugador")

        if accion not in {"compra", "venta"}:
            continue

        if subtipo == "clausula" and accion == "compra":
            label = "clausulazo"
        elif accion == "compra":
            label = "fichaje"
        else:
            label = "venta"

        article = "un" if label in {"fichaje", "clausulazo"} else "una"
        summary = (
            f"{manager} hizo {article} {label} de {jugador} ({equipo_jugador}) "
            f"por {dinero:.2f} millones."
        )

        memories.append(
            _base_memory(
                fecha=transfer.get("fecha") or fecha,
                layer="factual",
                category=label,
                manager=manager,
                player=jugador,
                team=equipo_jugador,
                summary=summary,
                facts={
                    "accion": accion,
                    "subtipo": subtipo,
                    "dinero": dinero,
                    "clasificacion_manager_general": transfer.get("clasificacion_manager_general"),
                    "clasificacion_manager_jornada": transfer.get("clasificacion_manager_jornada"),
                },
                tags=_clean_list([label, subtipo, manager, jugador, equipo_jugador, "mercado"]),
                importance=_money_importance(dinero, subtipo),
                temporada=temporada,
            )
        )

    return memories


def _gameweek_memories(events_json: dict[str, Any], fecha: str, temporada: str | None = None) -> list[dict[str, Any]]:
    gameweek = events_json.get("gameweek", [])
    if not gameweek:
        return []

    selected = []
    selected.extend(sorted(gameweek, key=lambda row: row.get("puntos", 0), reverse=True)[:3])
    selected.append(min(gameweek, key=lambda row: row.get("puntos", 0)))

    for row in gameweek:
        if any(row.get(flag, 0) for flag in ("roja", "gol_propia", "penalti_parado", "penalti_fallado")):
            selected.append(row)

    memories = []
    seen = set()
    for row in selected:
        key = (row.get("fecha"), row.get("manager"), row.get("jugador"), row.get("puntos"))
        if key in seen:
            continue
        seen.add(key)

        category = _gameweek_category(row)
        manager = row.get("manager")
        jugador = row.get("jugador")
        puntos = row.get("puntos")
        equipo_jugador = row.get("equipo_jugador")
        summary = f"{jugador} hizo {puntos} puntos para {manager} en la jornada."

        memories.append(
            _base_memory(
                fecha=row.get("fecha") or fecha,
                jornada=row.get("jornada"),
                layer="factual",
                category=category,
                manager=manager,
                player=jugador,
                team=equipo_jugador,
                summary=summary,
                facts={
                    "puntos": puntos,
                    "posicion": row.get("posicion"),
                    "equipo_local": row.get("equipo_local"),
                    "equipo_visitante": row.get("equipo_visitante"),
                    "goles": row.get("goles"),
                    "asistencias": row.get("asistencias"),
                    "roja": row.get("roja"),
                    "gol_propia": row.get("gol_propia"),
                    "penalti_parado": row.get("penalti_parado"),
                    "penalti_fallado": row.get("penalti_fallado"),
                    "clasificacion_manager_general": row.get("clasificacion_manager_general"),
                    "clasificacion_manager_jornada": row.get("clasificacion_manager_jornada"),
                },
                tags=_clean_list([category, manager, jugador, equipo_jugador, "jornada"]),
                importance=4 if category in {"mvp", "peor_actuacion"} else 3,
                temporada=temporada,
            )
        )

    return memories


def _narrative_memories(cards_json: dict[str, Any], fecha: str, temporada: str | None = None) -> list[dict[str, Any]]:
    memories = []
    for card in cards_json.get("cards", []):
        tipo = card.get("tipo")
        if tipo not in IMPORTANT_CARD_TYPES:
            continue

        title = card.get("titulo")
        subtitle = card.get("subtitulo")
        text_items = [str(item) for item in card.get("texto", []) if item]
        text = " ".join(text_items)
        manager = card.get("manager")
        jugador = card.get("jugador")
        equipo = card.get("equipo")

        summary_bits = [bit for bit in [title, subtitle, text] if bit]
        summary = " | ".join(summary_bits)

        memories.append(
            _base_memory(
                fecha=fecha,
                layer="narrative",
                category=_slug(tipo),
                manager=manager,
                player=jugador,
                team=equipo,
                title=title,
                subtitle=subtitle,
                summary=summary,
                facts={
                    "tipo_card": tipo,
                    "puntos": card.get("puntos"),
                    "dinero": card.get("dinero"),
                },
                tags=_clean_list([tipo, manager, jugador, equipo, "periodico", "titular"]),
                importance=5 if tipo in {"clasificacion", "Fichaje destacado", "MVP de la jornada"} else 3,
                temporada=temporada,
            )
        )

    return memories


def _base_memory(
    *,
    fecha: str,
    layer: str,
    category: str,
    summary: str,
    facts: dict[str, Any],
    tags: list[str],
    importance: int,
    jornada: int | None = None,
    manager: str | None = None,
    player: str | None = None,
    team: str | None = None,
    title: str | None = None,
    subtitle: str | None = None,
    temporada: str | None = None,
) -> dict[str, Any]:
    memory = {
        "schema_version": 1,
        "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "fecha": fecha,
        "jornada": jornada,
        "temporada": temporada,
        "layer": layer,
        "category": category,
        "manager": manager,
        "player": player,
        "team": team,
        "title": title,
        "subtitle": subtitle,
        "summary": summary,
        "facts": facts,
        "tags": tags,
        "importance": importance,
    }
    memory["query_text"] = _query_text(memory)
    return memory


def _with_id(memory: dict[str, Any]) -> dict[str, Any]:
    # temporada incluida en el hash: la misma combinación fecha/jornada/
    # categoria/manager/jugador/titulo puede repetirse de una temporada a
    # otra y no deben colisionar en el mismo id al hacer upsert (IA-02).
    raw = "|".join(
        str(memory.get(key) or "")
        for key in ("temporada", "fecha", "jornada", "layer", "category", "manager", "player", "title")
    )
    memory["id"] = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return memory


def _query_text(memory: dict[str, Any]) -> str:
    parts = [
        memory.get("fecha"),
        memory.get("layer"),
        memory.get("category"),
        memory.get("manager"),
        memory.get("player"),
        memory.get("team"),
        memory.get("title"),
        memory.get("subtitle"),
        memory.get("summary"),
        " ".join(memory.get("tags", [])),
    ]
    return " ".join(str(part) for part in parts if part)


def _memory_date(events_json: dict[str, Any]) -> str:
    return events_json.get("fecha_fin") or events_json.get("fecha_inicio") or datetime.today().strftime("%Y-%m-%d")


def _manager_snapshot(item) -> dict[str, Any] | None:
    if not item:
        return None
    manager, stats = item
    return {
        "manager": manager,
        "puntos": stats.get("puntos"),
        "posicion": stats.get("posicion"),
    }


def _money_importance(dinero: float, subtipo: str | None) -> int:
    if subtipo == "clausula" or dinero >= 20:
        return 5
    if dinero >= 10:
        return 4
    return 3


def _gameweek_category(row: dict[str, Any]) -> str:
    if row.get("roja", 0):
        return "expulsion"
    if row.get("gol_propia", 0):
        return "gol_propia"
    if row.get("penalti_parado", 0):
        return "penalti_parado"
    if row.get("penalti_fallado", 0):
        return "penalti_fallado"
    if row.get("puntos", 0) < 0:
        return "peor_actuacion"
    return "mvp"


def _slug(value: str) -> str:
    value = value.lower().strip()
    value = (
        value.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ñ", "n")
    )
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def _clean_list(values: list[Any]) -> list[str]:
    cleaned = []
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned
