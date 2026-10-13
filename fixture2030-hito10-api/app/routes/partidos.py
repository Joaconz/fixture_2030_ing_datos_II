"""Rutas HTTP de partidos y eventos (Neo4j; detalle con caché Redis)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.deps import eventos_service, partidos_service
from app.schemas.common import R400, R500, R503, Cursor, IdempotencyKey, PartidoId, r404, r409
from app.schemas.eventos import Evento, EventoNuevo, PaginaEventos, TipoEvento
from app.schemas.partidos import CambioEstado, PartidoDetalle
from app.services.eventos import EventosService
from app.services.partidos import PartidosService

router = APIRouter(prefix="/partidos", tags=["Partidos · Neo4j"])
R404_PARTIDO = r404("MATCH_NOT_FOUND", "No existe el partido solicitado.")
CABECERA_CACHE = {"X-Cache": {"description": "HIT (Redis), MISS (Neo4j y se guarda) o BYPASS (Redis no disponible: se sirvió desde Neo4j)",
                              "schema": {"type": "string", "enum": ["HIT", "MISS", "BYPASS"]}}}
CABECERA_REPLAY = {"Idempotent-Replayed": {"description": "Presente con valor `true` cuando la respuesta corresponde a un reintento",
                                           "schema": {"type": "string", "enum": ["true"]}}}


@router.get("/{partido_id}", operation_id="getPartido",
            summary="Detalle de un partido: equipos, sede, estado y marcador (Neo4j + caché Redis)",
            response_model=PartidoDetalle,
            responses={200: {"headers": CABECERA_CACHE}, **R400, **R404_PARTIDO, **R503, **R500})
async def get_partido(partido_id: PartidoId, response: Response,
                      svc: Annotated[PartidosService, Depends(partidos_service)]) -> PartidoDetalle:
    detalle, estado_cache = await svc.get_detalle(partido_id)
    response.headers["X-Cache"] = estado_cache
    return detalle


@router.get("/{partido_id}/eventos", operation_id="listEventosDePartido",
            summary="Timeline de eventos de un partido, en orden de secuencia (Cypher parametrizado)",
            response_model=PaginaEventos, responses={**R400, **R404_PARTIDO, **R503, **R500})
async def list_eventos(partido_id: PartidoId,
                       svc: Annotated[EventosService, Depends(eventos_service)],
                       tipo: Annotated[TipoEvento | None, Query()] = None,
                       limit: Annotated[int, Query(ge=1, le=200)] = 50,
                       cursor: Cursor = None) -> PaginaEventos:
    return await svc.list_eventos(partido_id, tipo, limit, cursor)


@router.post("/{partido_id}/eventos", operation_id="registrarEvento",
             summary="Registra un evento validado contra las reglas de su tipo (N8); idempotente por Idempotency-Key",
             response_model=Evento, status_code=status.HTTP_201_CREATED,
             responses={200: {"model": Evento, "description": "Reintento: el evento ya existía con esa clave", "headers": CABECERA_REPLAY},
                        **R400, **R404_PARTIDO,
                        **r409("El estado del partido impide el evento (FINALIZADO, posterior a FIN_PARTIDO, INICIO/FIN repetido) o la clave ya se usó con otro cuerpo.", "MATCH_FINALIZED"),
                        **R503, **R500})
async def registrar_evento(partido_id: PartidoId, body: EventoNuevo, response: Response,
                           idempotency_key: IdempotencyKey,
                           svc: Annotated[EventosService, Depends(eventos_service)]) -> Evento:
    evento, creado = await svc.registrar(partido_id, idempotency_key, body)
    if not creado:
        response.status_code = status.HTTP_200_OK
        response.headers["Idempotent-Replayed"] = "true"
    return evento


@router.patch("/{partido_id}/estado", operation_id="cerrarPartido",
              summary="Cierre validado del partido (PROGRAMADO → FINALIZADO) en una transacción de escritura",
              response_model=PartidoDetalle,
              responses={**R400, **R404_PARTIDO,
                         **r409("Transición inválida: el partido ya está FINALIZADO o no tiene FIN_PARTIDO.", "INVALID_TRANSITION"),
                         **R503, **R500})
async def cerrar_partido(partido_id: PartidoId, body: CambioEstado,
                         svc: Annotated[EventosService, Depends(eventos_service)]) -> PartidoDetalle:
    return await svc.cerrar(partido_id, body)
