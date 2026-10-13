"""Rutas HTTP de sesiones (Redis)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.core.deps import sesiones_service
from app.schemas.common import R400, R500, R503, SesionId, r403, r404
from app.schemas.sesiones import Sesion
from app.services.sesiones import SesionesService

router = APIRouter(prefix="/sesiones", tags=["Sesiones · Redis"])
Svc = Annotated[SesionesService, Depends(sesiones_service)]
R404_SESION = r404("SESSION_NOT_FOUND", "No existe una sesión vigente con ese id (inexistente o expirada).")


@router.get("/{sesion_id}", operation_id="getSesion",
            summary="Valida una sesión: HGETALL + TTL, sin renovarla",
            response_model=Sesion,
            responses={**R400, **r403("SESSION_BLOCKED", "La sesión existe pero está BLOQUEADA."),
                       **R404_SESION, **R503, **R500})
async def obtener(sesion_id: SesionId, svc: Svc) -> Sesion:
    return await svc.obtener(sesion_id)


@router.delete("/{sesion_id}", operation_id="cerrarSesion", status_code=status.HTTP_204_NO_CONTENT,
               summary="Invalida una sesión (MULTI/EXEC: SREM del índice del usuario + DEL)",
               response_class=Response, responses={**R400, **R404_SESION, **R503, **R500})
async def cerrar(sesion_id: SesionId, svc: Svc) -> Response:
    await svc.cerrar(sesion_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
