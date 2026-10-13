"""Tipos compartidos del contrato: error, identificadores y paginación."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import Header, Path, Query
from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Identificadores validados en el borde (RF10 / RNF3): si no cumplen el patrón,
# la request se rechaza con 400 antes de llegar a cualquier adaptador.
# ---------------------------------------------------------------------------
PATRON_EQUIPO = r"^[A-Z]{3}$"
PATRON_PARTIDO = r"^PAR-[A-Z0-9]{1,8}(-[A-Z0-9]{1,8}){0,2}$"
PATRON_SESION = r"^[A-Za-z0-9-]{3,64}$"
PATRON_IDEMPOTENCY = r"^[A-Za-z0-9_-]{8,64}$"
PATRON_CURSOR = r"^[A-Za-z0-9_-]{1,200}={0,2}$"

EquipoCodigo = Annotated[str, Path(pattern=PATRON_EQUIPO, description="Código FIFA de 3 letras.", examples=["ARG"])]
PartidoId = Annotated[str, Path(pattern=PATRON_PARTIDO, description="Identificador del partido (clave natural del Hito 5).", examples=["PAR-A-1"])]
SesionId = Annotated[str, Path(pattern=PATRON_SESION, examples=["demo-ses-0000001-1"])]
Cursor = Annotated[str | None, Query(pattern=PATRON_CURSOR, description="Cursor opaco devuelto como `nextCursor` por la página anterior.")]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", pattern=PATRON_IDEMPOTENCY,
                                       description="Clave elegida por el cliente; repetir la request con la misma clave no duplica la escritura (RNF14).")]


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class ErrorDetalle(ApiModel):
    campo: str
    problema: str


class ErrorResponse(ApiModel):
    """Formato único de error (RF12)."""
    code: str = Field(examples=["MATCH_NOT_FOUND"])
    message: str = Field(examples=["No existe el partido PAR-X-9."])
    requestId: str = Field(examples=["req-3f9c2a1b7d4e5f60"])
    details: list[ErrorDetalle] | None = None


def _err(descripcion: str, code: str) -> dict[str, Any]:
    return {"model": ErrorResponse, "description": descripcion,
            "content": {"application/json": {"example": {
                "code": code, "message": descripcion, "requestId": "req-3f9c2a1b7d4e5f60"}}}}


# Respuestas de error reutilizables en la declaración de cada ruta.
R400 = {400: _err("La request no cumple el contrato (parámetro, query o cuerpo inválido).", "VALIDATION_ERROR")}
R503 = {503: _err("La fuente de datos no respondió (caída o timeout).", "DEPENDENCY_UNAVAILABLE")}
R500 = {500: _err("Error interno; el detalle técnico queda sólo en los logs.", "INTERNAL_ERROR")}


def r404(code: str, descripcion: str) -> dict[int, dict[str, Any]]:
    return {404: _err(descripcion, code)}


def r409(descripcion: str, code: str = "CONFLICT") -> dict[int, dict[str, Any]]:
    return {409: _err(descripcion, code)}


def r403(code: str, descripcion: str) -> dict[int, dict[str, Any]]:
    return {403: _err(descripcion, code)}
