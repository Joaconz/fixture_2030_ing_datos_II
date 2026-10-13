"""CU12: estadísticas de un partido en una ventana temporal (InfluxDB 3).

Reglas validadas ANTES de consultar InfluxDB (RNF3): ventana [desde, hasta) con
`desde < hasta` y de 3 horas como máximo (la zona horaria obligatoria la exige
la ruta con `AwareDatetime`). Se piden `limit + 1` filas para saber si hay más
puntos que el tope (`truncado`) sin una segunda consulta. Una ventana sin puntos
es 200 con `puntos: []`; InfluxDB caído o sin token propaga 503.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.core.errors import ValidationApiError
from app.schemas.estadisticas import Agregacion, EstadisticasPartido
from app.services.ports import InfluxPort

VENTANA_MAXIMA = timedelta(hours=3)


class EstadisticasService:
    def __init__(self, influx: InfluxPort) -> None:
        self.influx = influx

    async def consultar(self, partido_id: str, desde: datetime, hasta: datetime,
                        agregacion: Agregacion, equipo: str | None, limit: int) -> EstadisticasPartido:
        if desde.tzinfo is None or hasta.tzinfo is None:
            raise ValidationApiError("`desde` y `hasta` deben incluir zona horaria.",
                                     code="VALIDATION_ERROR",
                                     details=[{"campo": "desde/hasta", "problema": "sin zona horaria"}])
        if desde >= hasta:
            raise ValidationApiError("La ventana es inválida: `desde` debe ser anterior a `hasta`.",
                                     code="INVALID_TIME_WINDOW",
                                     details=[{"campo": "desde", "problema": "debe ser menor que hasta"}])
        if hasta - desde > VENTANA_MAXIMA:
            raise ValidationApiError("La ventana supera el máximo de 3 horas.",
                                     code="TIME_WINDOW_TOO_LARGE",
                                     details=[{"campo": "hasta", "problema": "hasta - desde > 3 h"}])

        filas = await self.influx.consultar_estadisticas(partido_id, desde, hasta, agregacion,
                                                         equipo, limit + 1)
        truncado = len(filas) > limit
        puntos = filas[:limit]
        return EstadisticasPartido(partidoId=partido_id, desde=desde, hasta=hasta,
                                   agregacion=agregacion, puntos=puntos, cantidad=len(puntos),
                                   truncado=truncado)
