from pydantic import BaseModel, Field, model_validator
from typing import List, Literal, Optional

TIPOS_CARD = Literal[
    "clasificacion",
    "rumor",
    "Fichaje destacado",
    "Venta récord",
    "MVP de la jornada",
    "Peor actuación de la jornada",
    "Expulsión",
    "Héroe bajo palos",
    "Gol en propia",
]

# Tipos centrados en un jugador concreto (ver generate_prompt.py::build_player_block)
TIPOS_CON_JUGADOR = {
    "Fichaje destacado",
    "Venta récord",
    "MVP de la jornada",
    "Peor actuación de la jornada",
    "Expulsión",
    "Héroe bajo palos",
    "Gol en propia",
}

# Tipos de operación de mercado: siempre llevan una cantidad de dinero asociada
TIPOS_CON_DINERO = {"Fichaje destacado", "Venta récord"}

# Tipos de rendimiento en la jornada: siempre llevan puntos asociados
TIPOS_CON_PUNTOS = {
    "MVP de la jornada",
    "Peor actuación de la jornada",
    "Expulsión",
    "Héroe bajo palos",
    "Gol en propia",
}


class Card(BaseModel):
    tipo: TIPOS_CARD
    jugador: Optional[str] = None
    manager: Optional[str] = None
    puntos: Optional[float] = None
    dinero: Optional[float] = None
    equipo: Optional[str] = None
    titulo: str
    subtitulo: str
    texto: List[str] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _validar_campos_requeridos_por_tipo(self) -> "Card":
        if self.tipo in TIPOS_CON_JUGADOR and not self.jugador:
            raise ValueError(f'la card de tipo "{self.tipo}" requiere "jugador"')
        if self.tipo in TIPOS_CON_DINERO and self.dinero is None:
            raise ValueError(f'la card de tipo "{self.tipo}" requiere "dinero"')
        if self.tipo in TIPOS_CON_PUNTOS and self.puntos is None:
            raise ValueError(f'la card de tipo "{self.tipo}" requiere "puntos"')
        return self


class FinalJSON(BaseModel):
    cards: List[Card] = Field(..., min_length=1)
