"""Puertos: lo que cada servicio espera de un adaptador (RF9 / RNF5).

Los servicios dependen de estos Protocols, no de los drivers. Los adaptadores
reales (`app/adapters/*.py`) y los falsos de las pruebas unitarias
(`tests/unit/fakes.py`) implementan los mismos métodos.

Convenciones para todos los adaptadores:
  - Toda operación de red pasa por `app.adapters.base.ejecutar` (timeout + 503 + log).
  - "No existe" se devuelve como `None` (o lista vacía cuando el contenedor sí
    existe); el servicio decide el 404. Nunca se devuelve vacío para ocultar
    una falla de conexión.
  - `connect()` NO debe fallar si la fuente está caída al arrancar la API: la
    API arranca igual y esa fuente responde 503 hasta que vuelva.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.schemas.comentarios import Comentario
from app.schemas.equipos import Equipo, Jugador, PartidoDeEquipo
from app.schemas.estadisticas import Agregacion, PuntoEstadistica
from app.schemas.eventos import Evento, EventoNuevo
from app.schemas.partidos import PartidoDetalle


class Ciclo(Protocol):
    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def ping(self) -> None:
        """Sin excepción = UP. Lanza DependencyUnavailableError si no responde."""


# --------------------------------------------------------------------------- Mongo
class MongoPort(Ciclo, Protocol):
    async def get_equipo(self, codigo: str) -> Equipo | None: ...

    async def list_jugadores(self, codigo: str, posicion: str | None,
                             despues_de_dorsal: int | None, limite: int) -> list[Jugador]:
        """Jugadores del equipo ordenados por dorsal ascendente, dorsal > despues_de_dorsal.
        Usa el índice {equipoId, posicion}. Devuelve como máximo `limite` filas."""


# --------------------------------------------------------------------------- Neo4j
class Neo4jPort(Ciclo, Protocol):
    async def get_partido(self, partido_id: str) -> PartidoDetalle | None: ...

    async def list_partidos_de_equipo(self, codigo: str, limite: int) -> list[PartidoDeEquipo] | None:
        """None si el :Equipo no existe en el grafo; lista (posiblemente vacía) si existe."""

    async def list_eventos(self, partido_id: str, tipo: str | None,
                           despues_de_secuencia: int | None, limite: int) -> list[Evento] | None:
        """None si el :Partido no existe; [] si existe y no tiene eventos (o ninguno del tipo)."""

    async def registrar_evento(self, partido_id: str, evento_id: str, nuevo: EventoNuevo,
                               huella: str) -> tuple[Evento, bool]:
        """En UNA transacción de escritura: valida partido existente (NotFoundError),
        no FINALIZADO / sin FIN_PARTIDO previo / INICIO y FIN únicos (ConflictError),
        tipo presente en el catálogo :TipoEvento; asigna secuencia = max+1 y hace MERGE
        por evento_id. Si el evento ya existía devuelve (evento, False); si existía con
        otra `huella` del cuerpo lanza ConflictError IDEMPOTENCY_KEY_REUSED."""

    async def cerrar_partido(self, partido_id: str) -> PartidoDetalle:
        """Cierre CP en una transacción de escritura: sólo desde PROGRAMADO, exige
        FIN_PARTIDO, marcador derivado de los eventos GOL. NotFoundError / ConflictError."""


# --------------------------------------------------------------------------- Cassandra
@dataclass(frozen=True)
class ConfigParticion:
    """Fila de config_particion_partido (Q0)."""
    partido_id: str
    buckets: int
    ventana_minutos: int
    inicio: datetime


@dataclass(frozen=True)
class PosicionLectura:
    """Dónde continuar dentro de una partición (ventana, bucket): estrictamente
    después de (creado_en, comentario_id) en el orden de clustering."""
    creado_en: datetime
    comentario_id: str


class CassandraPort(Ciclo, Protocol):
    async def get_config(self, partido_id: str) -> ConfigParticion | None: ...

    async def leer_particion(self, partido_id: str, ventana: datetime, bucket: int,
                             despues_de: PosicionLectura | None, limite: int) -> list[Comentario]:
        """Una partición (partido_id, ventana, bucket), creado_en DESC, como máximo `limite`."""

    async def get_comentario(self, partido_id: str, ventana: datetime, bucket: int,
                             creado_en: datetime, comentario_id: str) -> Comentario | None:
        """Lectura por clave primaria completa (para detectar reintentos)."""

    async def insertar_comentario(self, c: Comentario, ventana: datetime, bucket: int) -> None:
        """LOGGED BATCH: comentarios_por_partido + comentarios_por_usuario (upsert)."""


# --------------------------------------------------------------------------- Redis
@dataclass(frozen=True)
class SesionCruda:
    campos: dict[str, str]   # hash f30:ses:{id} tal cual (el servicio filtra)
    ttl_s: int


class RedisPort(Ciclo, Protocol):
    async def get_sesion(self, sesion_id: str) -> SesionCruda | None:
        """HGETALL + TTL, sin renovar. None si la clave no existe."""

    async def cerrar_sesion(self, sesion_id: str) -> bool:
        """MULTI/EXEC: SREM del índice del usuario + DEL. False si no existía."""

    async def cache_get_partido(self, partido_id: str) -> str | None: ...
    async def cache_set_partido(self, partido_id: str, valor_json: str, ttl_s: int) -> None: ...
    async def cache_del_partido(self, partido_id: str) -> None: ...


# --------------------------------------------------------------------------- InfluxDB
class InfluxPort(Ciclo, Protocol):
    async def consultar_estadisticas(self, partido_id: str, desde: datetime, hasta: datetime,
                                     agregacion: Agregacion, equipo: str | None,
                                     limite: int) -> list[PuntoEstadistica]:
        """SQL parametrizado sobre estadisticas_equipo; devuelve hasta `limite` filas."""
