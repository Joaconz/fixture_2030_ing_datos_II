"""Rutas HTTP de comentarios (Cassandra)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.deps import comentarios_service
from app.schemas.comentarios import Comentario, ComentarioNuevo, PaginaComentarios
from app.schemas.common import R500, R_DEPENDENCIA, Cursor, IdempotencyKey, PartidoId, r400, r404
from app.services.comentarios import ComentariosService

router = APIRouter(prefix="/partidos", tags=["Comentarios · Cassandra"])
Svc = Annotated[ComentariosService, Depends(comentarios_service)]
R404_PARTIDO = r404("MATCH_NOT_FOUND", "El partido no tiene configuración de partición (Q0): no existe para el módulo de comentarios.")


@router.get("/{partido_id}/comentarios", operation_id="listComentarios",
            summary="Comentarios de un partido, del más reciente al más antiguo, paginados por partición",
            response_model=PaginaComentarios, responses={**r400("Parámetro inválido o cursor que no corresponde.", "INVALID_CURSOR"), **R404_PARTIDO, **R_DEPENDENCIA, **R500})
async def listar(partido_id: PartidoId, svc: Svc,
                 limit: Annotated[int, Query(ge=1, le=50)] = 20,
                 cursor: Cursor = None) -> PaginaComentarios:
    return await svc.listar(partido_id, limit, cursor)


@router.post("/{partido_id}/comentarios", operation_id="publicarComentario",
             summary="Publica un comentario (LOGGED BATCH en las dos tablas); idempotente por Idempotency-Key",
             response_model=Comentario, status_code=status.HTTP_201_CREATED,
             responses={200: {"model": Comentario, "description": "Reintento: el comentario ya existía",
                              "headers": {"Idempotent-Replayed": {"schema": {"type": "string", "enum": ["true"]}}}},
                        **r400("Cuerpo inválido o `creadoEn` fuera del tramo del partido.", "COMMENT_OUTSIDE_MATCH_WINDOW"),
                        **R404_PARTIDO, **R_DEPENDENCIA, **R500})
async def publicar(partido_id: PartidoId, body: ComentarioNuevo, response: Response,
                   idempotency_key: IdempotencyKey, svc: Svc) -> Comentario:
    comentario, creado = await svc.publicar(partido_id, idempotency_key, body)
    if not creado:
        response.status_code = status.HTTP_200_OK
        response.headers["Idempotent-Replayed"] = "true"
    return comentario
