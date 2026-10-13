"""Contrato de sesiones (Redis, N5). Se exponen sólo los campos que necesita el consumidor."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import ApiModel


class Sesion(ApiModel):
    sesionId: str = Field(examples=["demo-ses-0000001-1"])
    usuarioId: str = Field(examples=["USR-0000001"])
    rol: Literal["HINCHA", "MODERADOR"]
    region: str = Field(examples=["AM"])
    dispositivo: str = Field(examples=["web"])
    estado: Literal["ACTIVA"] = Field(description="Una sesión BLOQUEADA responde 403, nunca 200")
    creadaEn: datetime
    ultimaActividad: datetime
    expiraAbsoluta: datetime
    ttlSegundos: int = Field(description="TTL restante en Redis; la consulta NO lo renueva")
