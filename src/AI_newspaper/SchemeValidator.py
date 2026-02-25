from pydantic import BaseModel, Field
from typing import List, Optional, Union

class Card(BaseModel):
    tipo: str
    jugador: Optional[str] = None
    manager: Optional[str] = None
    puntos: Optional[float] = None
    dinero: Optional[float] = None
    equipo: Optional[str] = None
    titulo: str
    subtitulo: str
    texto: List[str] = Field(..., min_items=1)

class FinalJSON(BaseModel):
    cards: List[Card] = Field(..., min_items=1)