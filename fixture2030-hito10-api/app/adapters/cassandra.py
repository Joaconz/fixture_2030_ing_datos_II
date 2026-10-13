"""Adaptador Cassandra (Hito 6) — cassandra-driver 3.30, prepared statements.

Implementa `CassandraPort` (app/services/ports.py) sobre el keyspace
`fixture2030_comentarios` tal como lo dejó el Hito 6 (scripts/esquema.cql).

Decisiones:
  - Reactor de E/S: el driver usa por defecto `LibevConnection` (verificado en el
    venv con Python 3.12, donde `asyncore` ya no existe). Ese reactor corre en un
    hilo propio del driver; para no bloquear el event loop de FastAPI:
      * las consultas usan `session.execute_async(...)` y el `ResponseFuture`
        del driver se puentea a un `asyncio.Future` con `call_soon_threadsafe`;
      * lo único bloqueante (abrir el clúster, preparar sentencias, cerrar) corre
        en el threadpool (`run_in_executor`).
    Se descartó `AsyncioConnection`: en 3.30 sigue marcado como experimental y
    crea su propio loop en otro hilo, con lo que no ganaba nada frente a libev.
  - Conexión PEREZOSA: `connect()` no abre nada (Cluster.connect bloquea y falla
    si Cassandra está caída). La primera operación conecta con `connect_timeout`
    acotado; si falla → 503 y se reintenta en la próxima request (RNF9).
  - Perfil de ejecución: `DCAwareRoundRobinPolicy(local_dc)`, `LOCAL_ONE`
    (Hito 3: N=3, R=1, W=1 → se lee y escribe en una réplica del DC local) y
    `request_timeout = dep_timeout_s`.
  - Prepared statements, preparados una vez tras conectar.
  - Columnas en None → `UNSET_VALUE` (la columna no se escribe): bindear None
    escribiría un null explícito = un tombstone de celda, igual que evita
    `carga_masiva.py` del Hito 6.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from cassandra import (ConsistencyLevel, DriverException, OperationTimedOut, ReadTimeout,
                       Unavailable, WriteTimeout)
from cassandra.cluster import (EXEC_PROFILE_DEFAULT, Cluster, ExecutionProfile, NoHostAvailable,
                               Session)
from cassandra.connection import ConnectionException
from cassandra.policies import DCAwareRoundRobinPolicy
from cassandra.query import UNSET_VALUE, BatchStatement, BatchType, dict_factory

from app.adapters.base import ejecutar
from app.config.settings import Settings
from app.schemas.comentarios import Comentario
from app.services.ports import ConfigParticion, PosicionLectura

UTC = timezone.utc
log = logging.getLogger("fixture2030.adaptador")

# Fallas que significan "Cassandra no está disponible" → 503.
ERRORES_DISPONIBILIDAD: tuple[type[BaseException], ...] = (
    NoHostAvailable, OperationTimedOut, ReadTimeout, WriteTimeout, Unavailable, ConnectionException,
)
# Al conectar, cualquier error del driver (p. ej. keyspace aún no creado al
# preparar) también es "la fuente no está lista": 503, no 500.
ERRORES_AL_CONECTAR: tuple[type[BaseException], ...] = ERRORES_DISPONIBILIDAD + (DriverException,)

COLUMNAS_PARTIDO = ("partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, "
                    "hinchada, minuto_partido, responde_a, contenido, idioma, estado_moderacion")


# --------------------------------------------------------------------------- mapeos puros
def a_utc_naive(instante: datetime) -> datetime:
    """El driver interpreta los datetime naive como UTC: se normaliza antes de bindear."""
    if instante.tzinfo is None:
        return instante
    return instante.astimezone(UTC).replace(tzinfo=None)


def desde_driver(instante: datetime) -> datetime:
    """El driver devuelve `timestamp` como datetime naive en UTC → tz-aware."""
    return instante.replace(tzinfo=UTC) if instante.tzinfo is None else instante.astimezone(UTC)


def u(valor: Any) -> Any:
    """None → UNSET_VALUE: no escribir la columna (sin tombstone)."""
    return UNSET_VALUE if valor is None else valor


def fila_a_comentario(fila: dict[str, Any]) -> Comentario:
    return Comentario(
        comentarioId=fila["comentario_id"],
        partidoId=fila["partido_id"],
        usuarioId=fila["usuario_id"],
        alias=fila.get("alias_usuario"),
        hinchada=fila.get("hinchada"),
        minutoPartido=fila.get("minuto_partido"),
        contenido=fila.get("contenido") or "",
        idioma=fila.get("idioma"),
        creadoEn=desde_driver(fila["creado_en"]),
        respondeA=fila.get("responde_a"),
        estadoModeracion=fila.get("estado_moderacion") or "DESCONOCIDO",
    )


def fila_a_config(fila: dict[str, Any]) -> ConfigParticion:
    return ConfigParticion(partido_id=fila["partido_id"], buckets=int(fila["buckets"]),
                           ventana_minutos=int(fila["ventana_minutos"]),
                           inicio=desde_driver(fila["inicio"]))


def valores_insert_partido(c: Comentario, ventana: datetime, bucket: int) -> tuple[Any, ...]:
    """Orden de SQL_INSERT_PARTIDO."""
    return (c.partidoId, a_utc_naive(ventana), bucket, a_utc_naive(c.creadoEn), c.comentarioId,
            c.usuarioId, u(c.alias), u(c.hinchada), u(c.minutoPartido), u(c.respondeA),
            c.contenido, u(c.idioma), c.estadoModeracion)


def valores_insert_usuario(c: Comentario, ventana: datetime, bucket: int) -> tuple[Any, ...]:
    """Orden de SQL_INSERT_USUARIO. mes = 'AAAA-MM' de creado_en en UTC."""
    creado = a_utc_naive(c.creadoEn)
    return (c.usuarioId, creado.strftime("%Y-%m"), creado, c.comentarioId, c.partidoId,
            a_utc_naive(ventana), bucket, u(c.minutoPartido), c.contenido, c.estadoModeracion)


# --------------------------------------------------------------------------- adaptador
class CassandraAdapter:
    nombre = "cassandra"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._timeout = settings.dep_timeout_s
        ks = settings.cassandra_keyspace
        self._sql = {
            "config": f"SELECT partido_id, buckets, ventana_minutos, inicio "
                      f"FROM {ks}.config_particion_partido WHERE partido_id = ?",
            "particion": f"SELECT {COLUMNAS_PARTIDO} FROM {ks}.comentarios_por_partido "
                         f"WHERE partido_id = ? AND ventana = ? AND bucket = ? LIMIT ?",
            # "Estrictamente después de (t, id)" en el orden (creado_en DESC, comentario_id ASC)
            # = (creado_en = t AND comentario_id > id) ∪ (creado_en < t). Una tupla
            # (creado_en, comentario_id) < (?, ?) compara ambas columnas en orden ascendente
            # y no sirve con clustering mixto: se usan dos rangos de la misma partición.
            "empate": f"SELECT {COLUMNAS_PARTIDO} FROM {ks}.comentarios_por_partido "
                      f"WHERE partido_id = ? AND ventana = ? AND bucket = ? "
                      f"AND creado_en = ? AND comentario_id > ? LIMIT ?",
            "anteriores": f"SELECT {COLUMNAS_PARTIDO} FROM {ks}.comentarios_por_partido "
                          f"WHERE partido_id = ? AND ventana = ? AND bucket = ? "
                          f"AND creado_en < ? LIMIT ?",
            "pk": f"SELECT {COLUMNAS_PARTIDO} FROM {ks}.comentarios_por_partido "
                  f"WHERE partido_id = ? AND ventana = ? AND bucket = ? "
                  f"AND creado_en = ? AND comentario_id = ?",
            "insert_partido": f"INSERT INTO {ks}.comentarios_por_partido "
                              f"(partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, "
                              f"alias_usuario, hinchada, minuto_partido, responde_a, contenido, idioma, "
                              f"editado, estado_moderacion) "
                              f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, false, ?)",
            "insert_usuario": f"INSERT INTO {ks}.comentarios_por_usuario "
                              f"(usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, "
                              f"minuto_partido, contenido, estado_moderacion) "
                              f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            "ping": "SELECT release_version FROM system.local",
        }
        self._cluster: Cluster | None = None
        self._session: Session | None = None
        self._prep: dict[str, Any] = {}
        self._lock: asyncio.Lock | None = None
        self._conexion_en_curso: asyncio.Future[None] | None = None

    # ------------------------------------------------------------------ ciclo de vida
    async def connect(self) -> None:
        """Perezosa a propósito: no toca la red (la API arranca aunque Cassandra esté caída)."""
        self._lock = asyncio.Lock()

    async def close(self) -> None:
        cluster, self._cluster, self._session, self._prep = self._cluster, None, None, {}
        if cluster is not None:
            await asyncio.get_running_loop().run_in_executor(None, cluster.shutdown)

    async def ping(self) -> None:
        await self._consultar("ping", "ping", ())

    # ------------------------------------------------------------------ conexión
    def _conectar_bloqueante(self) -> None:
        """Corre en el threadpool. Deja sesión y sentencias listas o lanza y no deja nada."""
        perfil = ExecutionProfile(
            load_balancing_policy=DCAwareRoundRobinPolicy(local_dc=self.settings.cassandra_dc),
            consistency_level=ConsistencyLevel.LOCAL_ONE,
            request_timeout=self._timeout,
            row_factory=dict_factory,
        )
        cluster = Cluster(self.settings.cassandra_host_list, port=self.settings.cassandra_port,
                          execution_profiles={EXEC_PROFILE_DEFAULT: perfil},
                          connect_timeout=self._timeout, control_connection_timeout=self._timeout)
        try:
            session = cluster.connect()
            prep = {k: session.prepare(v) for k, v in self._sql.items()}
        except BaseException:
            cluster.shutdown()
            raise
        self._cluster, self._prep, self._session = cluster, prep, session

    async def _sesion(self) -> Session:
        if self._session is not None:
            return self._session
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            if self._session is None:
                if self._conexion_en_curso is None or self._conexion_en_curso.done():
                    fut = asyncio.get_running_loop().run_in_executor(None, self._conectar_bloqueante)
                    # si nadie la espera (timeout), que la excepción no quede "sin recuperar"
                    fut.add_done_callback(lambda f: f.cancelled() or f.exception())
                    self._conexion_en_curso = fut
                # shield: el timeout de esta request no descarta una conexión que
                # termina un instante después; la próxima request la reutiliza.
                await ejecutar(self.nombre, "conectar", asyncio.shield(self._conexion_en_curso),
                               timeout_s=self._timeout * 2,
                               errores_de_disponibilidad=ERRORES_AL_CONECTAR)
        assert self._session is not None
        return self._session

    # ------------------------------------------------------------------ ejecución
    @staticmethod
    def _a_asyncio(response_future: Any) -> asyncio.Future[list[dict[str, Any]]]:
        """Puente ResponseFuture (hilo del driver) → asyncio.Future (event loop)."""
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[list[dict[str, Any]]] = loop.create_future()

        def _fijar(resultado: Any = None, error: BaseException | None = None) -> None:
            if fut.done():          # la request ya expiró (wait_for canceló)
                return
            if error is not None:
                fut.set_exception(error)
            else:
                fut.set_result(list(resultado or []))

        response_future.add_callbacks(
            callback=lambda filas: loop.call_soon_threadsafe(_fijar, filas, None),
            errback=lambda exc: loop.call_soon_threadsafe(_fijar, None, exc))
        return fut

    async def _ejecutar_sentencia(self, sentencia: Any, params: Any) -> list[dict[str, Any]]:
        sesion = await self._sesion()
        return await self._a_asyncio(sesion.execute_async(sentencia, params))

    async def _consultar(self, operacion: str, clave: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        async def _correr() -> list[dict[str, Any]]:
            await self._sesion()
            return await self._ejecutar_sentencia(self._prep[clave], params)
        return await ejecutar(self.nombre, operacion, _correr(), timeout_s=self._timeout * 3,
                              errores_de_disponibilidad=ERRORES_DISPONIBILIDAD)

    # ------------------------------------------------------------------ puerto
    async def get_config(self, partido_id: str) -> ConfigParticion | None:
        filas = await self._consultar("get_config", "config", (partido_id,))
        return fila_a_config(filas[0]) if filas else None

    async def leer_particion(self, partido_id: str, ventana: datetime, bucket: int,
                             despues_de: PosicionLectura | None, limite: int) -> list[Comentario]:
        v = a_utc_naive(ventana)
        if despues_de is None:
            filas = await self._consultar("leer_particion", "particion", (partido_id, v, bucket, limite))
            return [fila_a_comentario(f) for f in filas]
        t = a_utc_naive(despues_de.creado_en)

        async def _dos_rangos() -> list[dict[str, Any]]:
            await self._sesion()
            empate, anteriores = await asyncio.gather(
                self._ejecutar_sentencia(self._prep["empate"],
                                         (partido_id, v, bucket, t, despues_de.comentario_id, limite)),
                self._ejecutar_sentencia(self._prep["anteriores"], (partido_id, v, bucket, t, limite)))
            return (empate + anteriores)[:limite]   # empate va primero en el orden de clustering

        filas = await ejecutar(self.nombre, "leer_particion", _dos_rangos(), timeout_s=self._timeout * 3,
                               errores_de_disponibilidad=ERRORES_DISPONIBILIDAD)
        return [fila_a_comentario(f) for f in filas]

    async def get_comentario(self, partido_id: str, ventana: datetime, bucket: int,
                             creado_en: datetime, comentario_id: str) -> Comentario | None:
        filas = await self._consultar("get_comentario", "pk", (
            partido_id, a_utc_naive(ventana), bucket, a_utc_naive(creado_en), comentario_id))
        return fila_a_comentario(filas[0]) if filas else None

    async def insertar_comentario(self, c: Comentario, ventana: datetime, bucket: int) -> None:
        """W1 del Hito 6: LOGGED BATCH (las dos tablas quedan iguales o ninguna), upsert."""
        async def _batch() -> None:
            await self._sesion()
            lote = BatchStatement(batch_type=BatchType.LOGGED)
            lote.add(self._prep["insert_partido"], valores_insert_partido(c, ventana, bucket))
            lote.add(self._prep["insert_usuario"], valores_insert_usuario(c, ventana, bucket))
            await self._ejecutar_sentencia(lote, None)
        await ejecutar(self.nombre, "insertar_comentario", _batch(), timeout_s=self._timeout * 3,
                       errores_de_disponibilidad=ERRORES_DISPONIBILIDAD)

