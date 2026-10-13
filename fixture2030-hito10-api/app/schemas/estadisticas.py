"""Contrato de estadísticas en vivo (InfluxDB 3 Core, N7, base fixture2030_vivo)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import ApiModel

Agregacion = Literal["raw", "1m", "5m"]


class PuntoEstadistica(ApiModel):
    time: datetime = Field(description="Instante del punto (raw) o inicio del tramo (1m/5m), UTC")
    equipoCodigo: str = Field(examples=["ARG"])
    condicion: Literal["LOCAL", "VISITANTE"] | None = None
    posesionPct: float | None = Field(default=None, description="raw: valor; 1m/5m: último valor del tramo")
    pasesAcum: int | None = Field(default=None, description="Contador acumulado; 1m/5m: máximo del tramo")
    tirosAcum: int | None = None
    golesAcum: int | None = None
    minutoJuego: int | None = None


class EstadisticasPartido(ApiModel):
    partidoId: str
    desde: datetime
    hasta: datetime
    agregacion: Agregacion
    puntos: list[PuntoEstadistica]
    cantidad: int
    truncado: bool = Field(description="true si se alcanzó el tope de puntos (`limit`) y hay más en la ventana")
