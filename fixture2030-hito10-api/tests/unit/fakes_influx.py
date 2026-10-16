"""Adaptador InfluxDB falso (implementa InfluxPort de app/services/ports.py)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.schemas.estadisticas import PuntoEstadistica

UTC = timezone.utc
INICIO_PAR_A_1 = datetime(2030, 6, 9, 13, 0, tzinfo=UTC)


def puntos_demo(cantidad: int, desde: datetime = INICIO_PAR_A_1) -> list[PuntoEstadistica]:
    """Puntos por segundo alternando ARG (LOCAL) / VEN (VISITANTE), deterministas."""
    out = []
    for i in range(cantidad):
        local = i % 2 == 0
        out.append(PuntoEstadistica(
            time=desde + timedelta(seconds=i // 2), equipoCodigo="ARG" if local else "VEN",
            condicion="LOCAL" if local else "VISITANTE", posesionPct=55.0 if local else 45.0,
            pasesAcum=i, tirosAcum=i // 10, golesAcum=0, minutoJuego=i // 120))
    return out


class InfluxFalso:
    nombre = "influxdb"

    def __init__(self, puntos: list[PuntoEstadistica] | None = None) -> None:
        self.puntos = puntos or []
        self.llamadas: list[dict] = []

    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def ping(self) -> None: ...

    async def consultar_estadisticas(self, partido_id, desde, hasta, agregacion, equipo, limite):
        self.llamadas.append({"partido_id": partido_id, "desde": desde, "hasta": hasta,
                              "agregacion": agregacion, "equipo": equipo, "limite": limite})
        filas = [p for p in self.puntos if desde <= p.time < hasta
                 and (equipo is None or p.equipoCodigo == equipo)]
        return filas[:limite]
