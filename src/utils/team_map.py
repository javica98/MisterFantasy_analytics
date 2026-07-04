"""
Mapas de IDs de equipo y posición usados en Mister Fantasy.
Centralizados aquí para evitar duplicación entre módulos.
"""

TEAM_MAP: dict[int, str] = {
    15: "Real Madrid",
    3: "FC Barcelona",
    2: "Atlético de Madrid",
    17: "Sevilla FC",
    4: "Real Betis Balompié",
    16: "Real Sociedad",
    20: "Villarreal CF",
    1: "Athletic Club",
    19: "Valencia CF",
    50: "CA Osasuna",
    5: "RC Celta de Vigo",
    14: "Rayo Vallecano",
    48: "Deportivo Alavés",
    8: "RCD Espanyol",
    23: "Elche CF",
    9: "Getafe CF",
    222: "Girona FC",
    12: "Levante UD",
    408: "RCD Mallorca",
    1370: "Real Oviedo",
}

TEAM_POSICION: dict[int, str] = {
    1: "Portero",
    2: "Defensa",
    3: "Mediocentro",
    4: "Delantero",
}


def map_team(team_id) -> str | int | float:
    """
    Resuelve un ID de equipo a su nombre legible.

    Los CSVs de Mister Fantasy almacenan el ``equipoLiga`` como float
    (ej. ``15.0``), por lo que la función acepta int, float y None.

    Args:
        team_id: ID del equipo. Puede ser int, float, None o NaN.

    Returns:
        Nombre del equipo si está en ``TEAM_MAP``; ``"Sin equipo"`` si el ID
        es ``None``, ``NaN`` o ``0``; el ID original si no se reconoce.

    Examples:
        >>> map_team(15)
        'Real Madrid'
        >>> map_team(15.0)
        'Real Madrid'
        >>> map_team(None)
        'Sin equipo'
        >>> map_team(0)
        'Sin equipo'
        >>> map_team(9999)
        9999
    """
    import math
    if team_id is None:
        return "Sin equipo"
    try:
        if math.isnan(float(team_id)):
            return "Sin equipo"
        if float(team_id) == 0:
            return "Sin equipo"
    except (TypeError, ValueError):
        pass
    return TEAM_MAP.get(team_id, team_id)


def map_position(position_id) -> str | int | None:
    """Resuelve un ID de posición a nombre. Devuelve el original si no está en el mapa."""
    return TEAM_POSICION.get(position_id, position_id)
