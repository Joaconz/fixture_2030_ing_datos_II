"""Contrato del chequeo de dependencias."""
from __future__ import annotations

from typing import Literal

from app.schemas.common import ApiModel

NombreDependencia = Literal["mongodb", "neo4j", "cassandra", "redis", "influxdb"]


class EstadoDependencia(ApiModel):
    nombre: NombreDependencia
    estado: Literal["UP", "DOWN"]
    latenciaMs: float | None = None
    detalle: str | None = None


class SaludDependencias(ApiModel):
    estado: Literal["OK", "DEGRADADO"]
    dependencias: list[EstadoDependencia]


class Vivo(ApiModel):
    estado: Literal["OK"] = "OK"
