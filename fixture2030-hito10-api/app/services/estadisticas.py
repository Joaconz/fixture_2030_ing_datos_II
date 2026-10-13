"""CU12: estadísticas de un partido en una ventana temporal (InfluxDB 3)."""
from __future__ import annotations

from datetime import datetime

from app.schemas.estadisticas import Agregacion, EstadisticasPartido
from app.services.ports import InfluxPort


class EstadisticasService:
    def __init__(self, influx: InfluxPort) -> None:
        self.influx = influx

    async def consultar(self, partido_id: str, desde: datetime, hasta: datetime,
                        agregacion: Agregacion, equipo: str | None, limit: int) -> EstadisticasPartido:
        raise NotImplementedError  # Ola 1 · agente C
