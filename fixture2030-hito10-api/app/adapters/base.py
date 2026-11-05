"""Pieza común a los cinco adaptadores: timeout, traducción de fallas y log.

Cada adaptador envuelve TODA operación de red con `ejecutar(...)`:
  - `asyncio.wait_for` con el timeout configurado (RNF8): una fuente lenta o
    caída nunca deja la request esperando indefinidamente (RNF9);
  - las excepciones de conexión/timeout propias del driver (que cada adaptador
    declara en `errores_de_disponibilidad`) se traducen a
    `DependencyUnavailableError` → HTTP 503 (504 si fue un timeout). Las
    `ApiError` de dominio pasan tal cual;
  - se registra una línea de log con dependencia, operación, resultado,
    motivo (Hito 11: timeout, conexion, autenticacion, autorizacion, contexto,
    no_configurado, rechazo) y duración, sin parámetros ni resultados (RNF10 / RNF7).
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable
from typing import TypeVar

from app.core.errors import ApiError, DependencyUnavailableError
from app.core.metricas import registrar_dependencia

T = TypeVar("T")
log = logging.getLogger("fixture2030.adaptador")


async def ejecutar(
    dependencia: str,
    operacion: str,
    awaitable: Awaitable[T],
    *,
    timeout_s: float,
    errores_de_disponibilidad: tuple[type[BaseException], ...] = (),
) -> T:
    inicio = time.perf_counter()
    resultado = "ok"
    motivo: str | None = None
    try:
        return await asyncio.wait_for(awaitable, timeout=timeout_s)
    except (asyncio.TimeoutError, TimeoutError) as exc:
        resultado, motivo = "timeout", "timeout"
        raise DependencyUnavailableError(dependencia, motivo="timeout") from exc
    except DependencyUnavailableError as exc:
        # el adaptador ya clasificó la falla (p. ej. token rechazado, database inexistente)
        resultado, motivo = ("timeout" if exc.timeout else "no_disponible"), exc.motivo
        raise
    except ApiError as exc:
        resultado = f"dominio:{exc.code}"
        raise
    except errores_de_disponibilidad as exc:
        motivo = motivo_de(exc)
        resultado = "timeout" if motivo == "timeout" else "no_disponible"
        log.warning("dependencia no disponible", extra={
            "evento": "dependencia", "dependencia": dependencia, "operacion": operacion,
            "resultado": resultado, "motivo": motivo, "tipo": type(exc).__name__})
        raise DependencyUnavailableError(dependencia, motivo=motivo) from exc
    finally:
        duracion_s = time.perf_counter() - inicio
        registrar_dependencia(dependencia, operacion, resultado, duracion_s)
        extra = {"evento": "dependencia", "dependencia": dependencia, "operacion": operacion,
                 "resultado": resultado,
                 "duracion_ms": round(duracion_s * 1000, 1)}
        if motivo:
            extra["motivo"] = motivo
        log.info("dependencia", extra=extra)


def motivo_de(exc: BaseException) -> str:
    """Clasifica una excepción de driver en un motivo de `MOTIVOS_DEPENDENCIA` (Hito 11).

    Se mira el tipo y el texto del error sólo para clasificar: el texto nunca
    se loguea ni se devuelve (puede traer hosts). "Connection refused" gana
    sobre "timeout" porque pymongo envuelve un rechazo en ServerSelectionTimeoutError
    (con el cliente async el texto es "[Errno 61] Connect call failed").
    """
    nombre = type(exc).__name__.lower()
    texto = str(exc).lower()
    if "auth" in nombre or "authenticat" in texto:
        return "autenticacion"
    if "unauthorized" in nombre or "forbidden" in nombre or "nopermission" in nombre:
        return "autorizacion"
    if ("does not exist" in texto or "not found" in texto or "databasenotfound" in texto
            or "unknown keyspace" in texto):
        return "contexto"       # keyspace/tabla/database inexistente
    if any(m in texto for m in ("refused", "connect call failed", "errno 61", "errno 111",
                                "nodename nor servname", "name or service not known")):
        return "conexion"       # rechazo del puerto (ECONNREFUSED 61 macOS / 111 Linux) o DNS
    if isinstance(exc, TimeoutError) or "timeout" in nombre or "timedout" in nombre:
        return "timeout"
    return "conexion"
