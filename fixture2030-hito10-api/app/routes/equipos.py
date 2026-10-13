"""Rutas HTTP de equipos: sólo contrato y delegación al servicio (RNF1)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import equipos_service
from app.schemas.common import R400, R500, R503, Cursor, EquipoCodigo, r404
from app.schemas.equipos import Equipo, PaginaJugadores, PartidosDeEquipo, Posicion
from app.services.equipos import EquiposService

router = APIRouter(prefix="/equipos")
Svc = Annotated[EquiposService, Depends(equipos_service)]
R404_EQUIPO = r404("TEAM_NOT_FOUND", "No existe el equipo solicitado.")


@router.get("/{codigo}", tags=["Equipos · MongoDB"], operation_id="getEquipo",
            summary="Ficha de un equipo (MongoDB, búsqueda por _id con proyección)",
            response_model=Equipo, responses={**R400, **R404_EQUIPO, **R503, **R500})
async def get_equipo(codigo: EquipoCodigo, svc: Svc) -> Equipo:
    return await svc.get_equipo(codigo)


@router.get("/{codigo}/jugadores", tags=["Equipos · MongoDB"], operation_id="listJugadoresDeEquipo",
            summary="Plantel paginado de un equipo (MongoDB, índice {equipoId, posicion})",
            response_model=PaginaJugadores, responses={**R400, **R404_EQUIPO, **R503, **R500})
async def list_jugadores(codigo: EquipoCodigo, svc: Svc,
                         posicion: Annotated[Posicion | None, Query()] = None,
                         limit: Annotated[int, Query(ge=1, le=50)] = 20,
                         cursor: Cursor = None) -> PaginaJugadores:
    return await svc.list_jugadores(codigo, posicion, limit, cursor)


@router.get("/{codigo}/partidos", tags=["Partidos · Neo4j"], operation_id="listPartidosDeEquipo",
            summary="Partidos en los que participa un equipo (Neo4j, recorrido PARTICIPA_EN)",
            response_model=PartidosDeEquipo, responses={**R400, **R404_EQUIPO, **R503, **R500})
async def list_partidos(codigo: EquipoCodigo, svc: Svc,
                        limit: Annotated[int, Query(ge=1, le=20)] = 10) -> PartidosDeEquipo:
    return await svc.list_partidos(codigo, limit)
