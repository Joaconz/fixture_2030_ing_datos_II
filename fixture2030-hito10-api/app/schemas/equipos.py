"""Contrato de equipos y jugadores (MongoDB, Hito 4) y partidos de un equipo (Neo4j)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import ApiModel

Posicion = Literal["Arquero", "Defensor", "Mediocampista", "Delantero"]
Confederacion = Literal["CONMEBOL", "UEFA", "CAF", "AFC", "CONCACAF", "OFC"]


class Colores(ApiModel):
    principal: str | None = None
    alternativo: str | None = None


class Equipo(ApiModel):
    """Proyección de `equipos` (Mongo): no se expone el documento completo."""
    codigo: str = Field(examples=["ARG"], description="= equipos._id (código FIFA)")
    nombre: str = Field(examples=["Argentina"])
    confederacion: Confederacion
    rankingFifa: int = Field(ge=1, examples=[1])
    grupo: str = Field(pattern=r"^[A-P]$", examples=["A"])
    entrenador: str | None = None
    sede: str | None = None
    colores: Colores | None = None
    cantidadJugadores: int | None = Field(default=None, ge=0)


class Jugador(ApiModel):
    dni: str = Field(examples=["30000010"], description="Clave natural del jugador en Mongo")
    nombre: str
    apellido: str
    fechaNacimiento: date
    posicion: Posicion
    dorsal: int = Field(ge=1, le=99)
    equipoCodigo: str = Field(examples=["ARG"])


class PaginaJugadores(ApiModel):
    equipoCodigo: str
    items: list[Jugador]
    limit: int
    nextCursor: str | None = Field(default=None, description="null cuando no hay más páginas")


class PartidoDeEquipo(ApiModel):
    """Un partido del equipo visto desde el grafo (recorrido PARTICIPA_EN)."""
    partidoId: str = Field(examples=["PAR-A-1"])
    fase: str = Field(examples=["GRUPOS"])
    grupo: str | None = None
    fechaHora: datetime
    estado: Literal["PROGRAMADO", "FINALIZADO"]
    condicion: Literal["LOCAL", "VISITANTE"]
    rivalCodigo: str = Field(examples=["MEX"])
    golesLocal: int | None = None
    golesVisitante: int | None = None


class PartidosDeEquipo(ApiModel):
    equipoCodigo: str
    items: list[PartidoDeEquipo]
    limit: int
