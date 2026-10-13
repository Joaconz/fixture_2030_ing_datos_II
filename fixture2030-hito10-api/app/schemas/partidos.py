"""Contrato de partidos (Neo4j, fuente vigente de N2 desde la reentrega del Hito 3)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import ApiModel

EstadoPartido = Literal["PROGRAMADO", "FINALIZADO"]


class Sede(ApiModel):
    sedeId: str = Field(examples=["URU-CEN"])
    nombre: str
    ciudad: str
    pais: str
    region: str = Field(examples=["AMERICAS"])


class EquipoEnPartido(ApiModel):
    equipoCodigo: str = Field(examples=["ARG"])
    nombre: str


class Marcador(ApiModel):
    golesLocal: int = Field(ge=0)
    golesVisitante: int = Field(ge=0)


class PartidoDetalle(ApiModel):
    partidoId: str = Field(examples=["PAR-A-1"])
    fase: str = Field(examples=["GRUPOS"])
    grupo: str | None = None
    jornada: int | None = None
    fechaHora: datetime
    estado: EstadoPartido
    sede: Sede | None = None
    local: EquipoEnPartido
    visitante: EquipoEnPartido
    marcador: Marcador | None = Field(default=None, description="null mientras el partido no está FINALIZADO")
    cantidadEventos: int = Field(ge=0)


class CambioEstado(ApiModel):
    """Única transición expuesta: PROGRAMADO → FINALIZADO (cierre CP del Hito 3)."""
    estado: Literal["FINALIZADO"]
