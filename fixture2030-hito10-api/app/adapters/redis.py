"""Adaptador Redis (Hito 7) — redis.asyncio, comandos nativos y MULTI/EXEC (sin Lua).

Implementa `RedisPort` (app/services/ports.py) sobre el modelo del Hito 7
(fixture2030-redis/docs/modelo_clave_valor.md):
  - sesión  `f30:ses:{id}` HASH (TTL deslizante de 1800 s, tope absoluto 12 h);
  - índice  `f30:usr:{usuario_id}:sesiones` SET;
  - caché   `f30:cache:partido:{id}` STRING JSON con `SET … EX`.

Como quedó el Hito 7 tras el PR #11: sólo comandos nativos y `MULTI/EXEC`.
Nada de EVAL / EVALSHA / FCALL.

El cliente se crea en `connect()` pero `redis.asyncio` no abre ningún socket
hasta el primer comando: la API arranca aunque Redis esté caído, y esa primera
operación falla con 503 (timeouts de conexión y de socket = `dep_timeout_s`).
"""
from __future__ import annotations

from redis.asyncio import Redis
from redis.exceptions import (BusyLoadingError, ConnectionError, NoPermissionError, RedisError, TimeoutError,
                              WatchError)

from app.adapters.base import ejecutar
from app.config.settings import Settings
from app.core.errors import DependencyUnavailableError
from app.services.ports import SesionCruda

# NoPermissionError (ACL NOPERM): identidad válida sin permiso → 503 con motivo autorizacion (Hito 11).
ERRORES_DISPONIBILIDAD: tuple[type[BaseException], ...] = (ConnectionError, TimeoutError, BusyLoadingError,
                                                         NoPermissionError)
# La caché es una optimización: CUALQUIER error de Redis en sus comandos (también un
# WRONGTYPE si otra herramienta dejó otro tipo en la clave) se trata como "caché no
# disponible" y el detalle se sirve desde Neo4j (BYPASS), nunca como 500.
ERRORES_CACHE: tuple[type[BaseException], ...] = (RedisError,)
INTENTOS_CIERRE = 2   # el primero + un reintento si WATCH abortó el EXEC


def clave_sesion(sesion_id: str) -> str:
    return f"f30:ses:{sesion_id}"


def clave_indice_usuario(usuario_id: str) -> str:
    return f"f30:usr:{usuario_id}:sesiones"


def clave_cache_partido(partido_id: str) -> str:
    return f"f30:cache:partido:{partido_id}"


def a_sesion_cruda(campos: dict[str, str], ttl: int) -> SesionCruda | None:
    """HGETALL vacío o TTL -2 (la clave venció entre los dos comandos) = no existe."""
    if not campos or ttl == -2:
        return None
    return SesionCruda(campos=dict(campos), ttl_s=int(ttl))


class RedisAdapter:
    nombre = "redis"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._timeout = settings.dep_timeout_s
        self._r: Redis | None = None

    # ------------------------------------------------------------------ ciclo de vida
    def _crear_cliente(self) -> Redis:
        return Redis.from_url(self.settings.redis_url.get_secret_value(),
                              socket_connect_timeout=self._timeout, socket_timeout=self._timeout,
                              decode_responses=True)

    async def connect(self) -> None:
        self._r = self._crear_cliente()

    async def close(self) -> None:
        if self._r is not None:
            await self._r.aclose()
            self._r = None

    @property
    def r(self) -> Redis:
        if self._r is None:     # por si se usa sin lifespan (no debería pasar)
            self._r = self._crear_cliente()
        return self._r

    async def _ejecutar(self, operacion: str, awaitable,  # type: ignore[no-untyped-def]
                        errores: tuple[type[BaseException], ...] = ERRORES_DISPONIBILIDAD):
        return await ejecutar(self.nombre, operacion, awaitable, timeout_s=self._timeout,
                              errores_de_disponibilidad=errores)

    async def ping(self) -> None:
        await self._ejecutar("ping", self.r.ping())

    # ------------------------------------------------------------------ sesiones
    async def get_sesion(self, sesion_id: str) -> SesionCruda | None:
        """HGETALL + TTL en un pipeline sin MULTI (`transaction=False`): un solo
        viaje de red. No hace falta atomicidad: son dos lecturas y, si la clave
        vence entre ambas, TTL devuelve -2 y se trata como inexistente. No se
        renueva el TTL (ni EXPIRE ni HSET)."""
        async def _leer() -> SesionCruda | None:
            async with self.r.pipeline(transaction=False) as pipe:
                pipe.hgetall(clave_sesion(sesion_id))
                pipe.ttl(clave_sesion(sesion_id))
                campos, ttl = await pipe.execute()
            return a_sesion_cruda(campos, ttl)
        return await self._ejecutar("get_sesion", _leer())

    async def cerrar_sesion(self, sesion_id: str) -> bool:
        """Logout del Hito 7 (§1.7): `MULTI` → `SREM` del índice + `DEL` → `EXEC`.

        Para hacer el SREM hace falta el `usuario_id`, que se lee antes con HGET.
        `WATCH f30:ses:{id}` protege ese intervalo: si la sesión cambia entre el
        HGET y el EXEC (renovación, bloqueo, recreación), el EXEC se aborta
        (`WatchError`) y se repite una vez la lectura con el valor nuevo. Si
        vuelve a abortar, se responde 503 (reintentar): nunca se borra a ciegas.
        """
        clave = clave_sesion(sesion_id)

        async def _cerrar() -> bool:
            async with self.r.pipeline(transaction=True) as pipe:
                for _ in range(INTENTOS_CIERRE):
                    try:
                        await pipe.watch(clave)
                        usuario_id = await pipe.hget(clave, "usuario_id")
                        existe = await pipe.exists(clave)
                        if not existe:
                            await pipe.unwatch()
                            return False
                        pipe.multi()
                        if usuario_id:
                            pipe.srem(clave_indice_usuario(usuario_id), sesion_id)
                        pipe.delete(clave)
                        resultados = await pipe.execute()
                        return bool(resultados[-1])
                    except WatchError:
                        await pipe.reset()
                        continue
            raise DependencyUnavailableError(self.nombre)
        return await self._ejecutar("cerrar_sesion", _cerrar())

    # ------------------------------------------------------------------ caché de partido
    async def cache_get_partido(self, partido_id: str) -> str | None:
        return await self._ejecutar("cache_get_partido", self.r.get(clave_cache_partido(partido_id)),
                                    ERRORES_CACHE)

    async def cache_set_partido(self, partido_id: str, valor_json: str, ttl_s: int) -> None:
        await self._ejecutar("cache_set_partido",
                             self.r.set(clave_cache_partido(partido_id), valor_json, ex=ttl_s),
                             ERRORES_CACHE)

    async def cache_del_partido(self, partido_id: str) -> None:
        await self._ejecutar("cache_del_partido", self.r.delete(clave_cache_partido(partido_id)),
                             ERRORES_CACHE)
