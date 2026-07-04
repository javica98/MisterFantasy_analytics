from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Union

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

class FinalJSON(BaseModel):
    cards: List[Card] = Field(..., min_length=1)