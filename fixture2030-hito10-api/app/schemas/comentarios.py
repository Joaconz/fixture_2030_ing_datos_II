"""Contrato de comentarios (Cassandra, N6, keyspace fixture2030_comentarios)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, Field

from app.schemas.common import ApiModel

Hinchada = Literal["LOCAL", "VISITANTE", "NEUTRAL"]
Idioma = Literal["es", "pt", "en", "fr", "ar"]


class Comentario(ApiModel):
    comentarioId: str = Field(examples=["PAR-A-1-C000012"])
    partidoId: str
    usuarioId: str = Field(examples=["USR-0000042"])
    alias: str | None = None
    hinchada: Hinchada | None = None
    minutoPartido: int | None = None
    contenido: str
    idioma: Idioma | None = None
    creadoEn: datetime
    respondeA: str | None = None
    estadoModeracion: str = Field(examples=["PUBLICADO"])


class PaginaComentarios(ApiModel):
    partidoId: str
    items: list[Comentario]
    limit: int
    nextCursor: str | None = Field(default=None, description="Cursor opaco (ventana, bucket y último creado_en); null al agotar el partido")


class ComentarioNuevo(ApiModel):
    usuarioId: str = Field(pattern=r"^USR-[A-Z0-9]{3,12}$", examples=["USR-0000042"])
    alias: str = Field(min_length=1, max_length=40, examples=["hincha42"])
    contenido: str = Field(min_length=1, max_length=500, examples=["¡Qué golazo!"])
    creadoEn: AwareDatetime = Field(
        description="Instante del comentario en el reloj del torneo simulado (con zona horaria). "
                    "Debe caer dentro del tramo de comentarios del partido (−15′ a +125′ del inicio). "
                    "Es parte de la clave primaria: reenviar la misma request no duplica.",
        examples=["2030-06-09T13:47:00Z"])
    minutoPartido: int | None = Field(default=None, ge=0, le=130)
    hinchada: Hinchada | None = None
    idioma: Idioma = "es"
    respondeA: str | None = Field(default=None, max_length=80)
