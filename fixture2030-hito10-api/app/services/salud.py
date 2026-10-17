"""CU13: estado de las dependencias (ping con timeout, en paralelo) y readiness.

Cada adaptador acota su ping con el timeout general (`app.adapters.base.ejecutar`).
El ping verifica, además de la respuesta del servidor, el contexto que usa la API
(Hito 11): colección `equipos` en Mongo, database en Neo4j, keyspace y sentencias
preparadas en Cassandra, token y database en InfluxDB. El `detalle` público es una
categoría (nunca hosts, URIs ni credenciales).

Costo y frecuencia (Hito 11 §5.6): el resultado se guarda `HEALTH_CACHE_S` segundos
en `CacheSalud`, compartido por /health/dependencias y /health/ready, y las
verificaciones concurrentes esperan la misma (single-flight): un balanceador o un
front que consulte cada segundo no genera una conexión por request en cada base.
Las requests normales de la API nunca disparan este chequeo.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from app.core.errors import DependencyUnavailableError
from app.schemas.salud import EstadoDependencia, Readiness, SaludDependencias
from app.services.ports import Ciclo

log = logging.getLogger("fixture2030.api")

DETALLE_POR_MOTIVO = {
    "timeout": "timeout",
    "conexion": "no responde",
    "autenticacion": "credencial rechazada",
    "autorizacion": "sin permiso",
    "contexto": "contexto inexistente",
    "rechazo": "respuesta inválida",
    "no_configurado": "sin configurar",
}

# Productos del TPO que no forman parte de la arquitectura vigente: se informan
# siempre como NOT_CONFIGURED, sin probarlos, y no degradan el estado global.
FUERA_DE_ARQUITECTURA = {"iris": "fuera de la arquitectura vigente (reentrega del Hito 3)"}


class CacheSalud:
    """Último resultado del chequeo profundo, con vencimiento y single-flight."""

    def __init__(self, ttl_s: float) -> None:
        self.ttl_s = ttl_s
        self._valor: SaludDependencias | None = None
        self._vence = 0.0
        self.lock = asyncio.Lock()

    def vigente(self) -> SaludDependencias | None:
        if self._valor is not None and time.monotonic() < self._vence:
            return self._valor
        return None

    def guardar(self, valor: SaludDependencias) -> None:
        self._valor, self._vence = valor, time.monotonic() + self.ttl_s


class SaludService:
    def __init__(self, adaptadores: dict[str, Ciclo], cache: CacheSalud | None = None,
                 esenciales: tuple[str, ...] = ("mongodb", "neo4j")) -> None:
        self.adaptadores = adaptadores
        self.cache = cache
        self.esenciales = esenciales

    async def _chequear_uno(self, nombre: str, adaptador: Ciclo) -> EstadoDependencia:
        inicio = time.perf_counter()
        estado, detalle = "UP", None
        try:
            await adaptador.ping()
        except NotImplementedError:
            estado, detalle = "DOWN", "no implementado"
        except DependencyUnavailableError as exc:
            estado = "NOT_CONFIGURED" if exc.motivo == "no_configurado" else "DOWN"
            detalle = DETALLE_POR_MOTIVO.get(exc.motivo, "no responde")
        except Exception as exc:  # noqa: BLE001 — se intentó, pero no se pudo clasificar
            log.warning("ping con error inesperado", extra={
                "evento": "dependencia", "dependencia": nombre, "operacion": "ping",
                "tipo": type(exc).__name__})
            estado, detalle = "UNKNOWN", "error no clasificado"
        latencia = round((time.perf_counter() - inicio) * 1000, 1)
        return EstadoDependencia(nombre=nombre, estado=estado, latenciaMs=latencia, detalle=detalle)

    async def _verificar(self) -> SaludDependencias:
        estados = list(await asyncio.gather(
            *(self._chequear_uno(n, a) for n, a in self.adaptadores.items())))
        estados += [EstadoDependencia(nombre=n, estado="NOT_CONFIGURED", detalle=d, enArquitectura=False)
                    for n, d in FUERA_DE_ARQUITECTURA.items()]
        en_arq = [e for e in estados if e.enArquitectura]
        estado = "OK" if all(e.estado == "UP" for e in en_arq) else "DEGRADADO"
        return SaludDependencias(estado=estado, dependencias=estados,
                                 verificadoEn=datetime.now(timezone.utc))

    async def chequear(self) -> SaludDependencias:
        if self.cache is None or self.cache.ttl_s <= 0:
            return await self._verificar()
        if (vigente := self.cache.vigente()) is not None:
            return vigente.model_copy(update={"desdeCache": True})
        async with self.cache.lock:   # single-flight: una sola verificación a la vez
            if (vigente := self.cache.vigente()) is not None:
                return vigente.model_copy(update={"desdeCache": True})
            resultado = await self._verificar()
            self.cache.guardar(resultado)
            return resultado

    async def readiness(self) -> Readiness:
        """LISTA: todas UP · LISTA_DEGRADADA: esenciales UP y alguna otra no ·
        NO_LISTA: alguna esencial no está UP (la API no puede atender su caso central)."""
        salud = await self.chequear()
        caidas = [d.nombre for d in salud.dependencias if d.enArquitectura and d.estado != "UP"]
        if any(n in caidas for n in self.esenciales):
            estado = "NO_LISTA"
        elif caidas:
            estado = "LISTA_DEGRADADA"
        else:
            estado = "LISTA"
        return Readiness(estado=estado, esenciales=list(self.esenciales), noDisponibles=caidas,
                         verificadoEn=salud.verificadoEn, desdeCache=salud.desdeCache)
