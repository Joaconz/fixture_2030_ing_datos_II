"""Rutas de salud: viva (sin dependencias) y estado de las cinco fuentes."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.core.deps import salud_service
from app.schemas.common import R500
from app.schemas.salud import SaludDependencias, Vivo
from app.services.salud import SaludService

router = APIRouter(prefix="/health", tags=["Salud"])


@router.get("", operation_id="health", summary="La API está viva (no consulta fuentes)", response_model=Vivo)
async def vivo() -> Vivo:
    return Vivo()


@router.get("/dependencias", operation_id="healthDependencias",
            summary="Ping con timeout a MongoDB, Neo4j, Cassandra, Redis e InfluxDB",
            response_model=SaludDependencias,
            responses={503: {"model": SaludDependencias, "description": "Al menos una fuente está DOWN (mismo cuerpo)"}, **R500})
async def dependencias(response: Response,
                       svc: Annotated[SaludService, Depends(salud_service)]) -> SaludDependencias:
    salud = await svc.chequear()
    if salud.estado != "OK":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return salud
