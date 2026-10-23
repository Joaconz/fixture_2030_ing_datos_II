"""Rutas de salud: liveness (sin dependencias), readiness y estado por dependencia."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.core.deps import salud_service
from app.schemas.common import R500
from app.schemas.salud import Readiness, SaludDependencias, Vivo
from app.services.salud import SaludService

router = APIRouter(prefix="/health", tags=["Salud"])


@router.get("", operation_id="health", summary="Liveness: el proceso de la API responde (no consulta fuentes)",
            response_model=Vivo)
async def vivo() -> Vivo:
    return Vivo()


@router.get("/ready", operation_id="healthReady",
            summary="Readiness: las fuentes esenciales (READY_ESENCIALES) están UP",
            response_model=Readiness,
            responses={503: {"model": Readiness, "description": "NO_LISTA: alguna fuente esencial no está UP (mismo cuerpo)"},
                       **R500})
async def ready(response: Response,
                svc: Annotated[SaludService, Depends(salud_service)]) -> Readiness:
    lista = await svc.readiness()
    if lista.estado == "NO_LISTA":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return lista


@router.get("/dependencias", operation_id="healthDependencias",
            summary="Chequeo por dependencia (ping + contexto, con timeout y caché de HEALTH_CACHE_S)",
            response_model=SaludDependencias,
            responses={503: {"model": SaludDependencias,
                             "description": "Al menos una fuente de la arquitectura no está UP (mismo cuerpo)"},
                       **R500})
async def dependencias(response: Response,
                       svc: Annotated[SaludService, Depends(salud_service)]) -> SaludDependencias:
    salud = await svc.chequear()
    if salud.estado != "OK":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return salud
