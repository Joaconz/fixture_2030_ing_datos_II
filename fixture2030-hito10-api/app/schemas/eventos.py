"""Contrato de eventos de partido (Neo4j, N3) y catálogo de tipos (Neo4j, N8)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import ApiModel

# Catálogo N8: los 12 :TipoEvento de fixture2030-neo4j/queries/carga.cypher (paso 3).
# Se valida en el borde; el motor sigue siendo la fuente (el adaptador verifica
# que el nodo exista antes de escribir).
TipoEvento = Literal[
    "INICIO_PARTIDO", "FIN_PARTIDO", "PASE", "CORNER", "ATAJADA", "ASISTENCIA",
    "GOL", "PENAL", "FALTA", "TARJETA_AMARILLA", "TARJETA_ROJA", "SUSTITUCION",
]
Condicion = Literal["LOCAL", "VISITANTE"]


class Protagonista(ApiModel):
    dni: str
    nombre: str
    apellido: str


class Evento(ApiModel):
    eventoId: str = Field(examples=["PAR-A-1-EV-05"])
    partidoId: str = Field(examples=["PAR-A-1"])
    secuencia: int = Field(ge=1, description="Reloj lógico dentro del partido (Hito 3)")
    tipo: TipoEvento
    minuto: int = Field(ge=0, le=130)
    condicionEquipo: Condicion | None = None
    dorsalProtagonista: int | None = Field(default=None, ge=1, le=99)
    protagonista: Protagonista | None = None
    timestamp: datetime | None = None
    origen: Literal["CARGA", "API"] = Field(default="CARGA", description="CARGA = carga del Hito 5; API = alta por este endpoint")


class PaginaEventos(ApiModel):
    partidoId: str
    items: list[Evento]
    limit: int
    nextCursor: str | None = None


class EventoNuevo(ApiModel):
    """Alta de un evento. Las reglas por tipo (qué campos exige cada uno) se
    validan en el servicio antes de escribir; ver docs/contratos_y_errores.md."""
    tipo: TipoEvento
    minuto: int = Field(ge=0, le=130, examples=[88])
    condicionEquipo: Condicion | None = Field(default=None, examples=["LOCAL"])
    dorsalProtagonista: int | None = Field(default=None, ge=1, le=99, examples=[9])
