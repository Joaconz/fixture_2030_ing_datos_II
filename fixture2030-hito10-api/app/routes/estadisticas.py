"""Rutas HTTP de estadísticas en vivo (InfluxDB 3)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime

from app.core.deps import estadisticas_service
from app.schemas.common import PATRON_EQUIPO, R500, R_DEPENDENCIA, PartidoId, r400
from app.schemas.estadisticas import Agregacion, EstadisticasPartido
from app.services.estadisticas import EstadisticasService

router = APIRouter(prefix="/partidos", tags=["Estadísticas · InfluxDB"])


@router.get("/{partido_id}/estadisticas", operation_id="getEstadisticasDePartido",
            summary="Estadísticas por equipo en una ventana temporal (máx. 3 h), crudas o agregadas",
            description="Ventana [desde, hasta) obligatoria, con zona horaria, `desde < hasta` y como máximo 3 horas. "
                        "Una ventana sin puntos responde 200 con `puntos: []`; InfluxDB caído responde 503, nunca una lista vacía.",
            response_model=EstadisticasPartido, responses={**r400("Parámetro inválido o ventana temporal inválida.", "INVALID_TIME_WINDOW", "TIME_WINDOW_TOO_LARGE"), **R_DEPENDENCIA, **R500})
async def consultar(partido_id: PartidoId,
                    svc: Annotated[EstadisticasService, Depends(estadisticas_service)],
                    desde: Annotated[AwareDatetime, Query(examples=["2030-06-09T13:00:00Z"])],
                    hasta: Annotated[AwareDatetime, Query(examples=["2030-06-09T13:30:00Z"])],
                    agregacion: Annotated[Agregacion, Query()] = "1m",
                    equipo: Annotated[str | None, Query(pattern=PATRON_EQUIPO)] = None,
                    limit: Annotated[int, Query(ge=1, le=2000)] = 500) -> EstadisticasPartido:
    return await svc.consultar(partido_id, desde, hasta, agregacion, equipo, limit)
