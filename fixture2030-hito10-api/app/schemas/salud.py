"""Contrato de liveness, readiness y chequeo por dependencia (Hito 10 CU13 + Hito 11 §5.6).

Estados por dependencia (significado definido, Hito 11 RNF9):
  - UP: el chequeo configurado (ping + contexto) terminó bien en esta verificación;
  - DOWN: se intentó y falló (`detalle` dice por qué: timeout, no responde,
    credencial rechazada, sin permiso, contexto inexistente, respuesta inválida);
  - NOT_CONFIGURED: el módulo no está preparado en este entorno (falta su
    configuración, o el producto está fuera de la arquitectura vigente: IRIS);
  - UNKNOWN: no se pudo evaluar (el chequeo terminó con un error no clasificado).
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from app.schemas.common import ApiModel

NombreDependencia = Literal["mongodb", "neo4j", "cassandra", "redis", "influxdb", "iris"]
EstadoDep = Literal["UP", "DOWN", "NOT_CONFIGURED", "UNKNOWN"]


class EstadoDependencia(ApiModel):
    nombre: NombreDependencia
    estado: EstadoDep
    latenciaMs: float | None = None
    detalle: str | None = None
    enArquitectura: bool = True


class SaludDependencias(ApiModel):
    estado: Literal["OK", "DEGRADADO"]
    dependencias: list[EstadoDependencia]
    verificadoEn: datetime | None = None
    desdeCache: bool = False


class Readiness(ApiModel):
    estado: Literal["LISTA", "LISTA_DEGRADADA", "NO_LISTA"]
    esenciales: list[str]
    noDisponibles: list[str]
    verificadoEn: datetime | None = None
    desdeCache: bool = False


class Vivo(ApiModel):
    estado: Literal["OK"] = "OK"
