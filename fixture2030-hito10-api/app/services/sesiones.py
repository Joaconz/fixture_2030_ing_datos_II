"""CU10–CU11: validar e invalidar una sesión (Redis)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.core.errors import ForbiddenError, NotFoundError
from app.schemas.sesiones import Sesion
from app.services.ports import RedisPort, SesionCruda

log = logging.getLogger("fixture2030.servicio")

# Campos públicos que tiene que traer el hash para considerarlo una sesión.
# `solicitudes` (contador interno) no se expone (CU10).
CAMPOS_REQUERIDOS = ("usuario_id", "estado", "rol", "region", "dispositivo",
                     "creada_en", "ultima_actividad", "expira_absoluta")


def _no_encontrada(sesion_id: str) -> NotFoundError:
    return NotFoundError(f"No existe una sesión vigente con id '{sesion_id}'.", code="SESSION_NOT_FOUND")


def _epoch(valor: str) -> datetime:
    return datetime.fromtimestamp(int(valor), tz=timezone.utc)


def a_sesion(sesion_id: str, cruda: SesionCruda) -> Sesion:
    """Hash del Hito 7 → contrato. Lanza NotFoundError / ForbiddenError según CU10."""
    c = cruda.campos
    # Hash PARCIAL (sesiones.redis §3.4 bis): la renovación llegó después de que
    # la clave venciera y HSET creó un hash sólo con `ultima_actividad`. No es
    # una sesión: se responde igual que si no existiera. Mismo criterio si falta
    # cualquier otro campo público (dato incompleto, no un 500).
    if any(not c.get(k) for k in CAMPOS_REQUERIDOS):
        log.info("hash de sesión incompleto tratado como inexistente",
                 extra={"evento": "sesion_parcial"})
        raise _no_encontrada(sesion_id)
    if c["estado"] == "BLOQUEADA":
        raise ForbiddenError("La sesión existe pero está bloqueada.", code="SESSION_BLOCKED")
    if c["estado"] != "ACTIVA":
        raise _no_encontrada(sesion_id)
    try:
        return Sesion(
            sesionId=c.get("session_id") or sesion_id,
            usuarioId=c["usuario_id"],
            rol=c["rol"],
            region=c["region"],
            dispositivo=c["dispositivo"],
            estado="ACTIVA",
            creadaEn=_epoch(c["creada_en"]),
            ultimaActividad=_epoch(c["ultima_actividad"]),
            expiraAbsoluta=_epoch(c["expira_absoluta"]),
            ttlSegundos=cruda.ttl_s,
        )
    except ValueError as exc:   # epoch no numérico o rol fuera del dominio: dato corrupto
        log.warning("hash de sesión con valores inválidos", extra={"evento": "sesion_invalida"})
        raise _no_encontrada(sesion_id) from exc


class SesionesService:
    def __init__(self, redis: RedisPort) -> None:
        self.redis = redis

    async def obtener(self, sesion_id: str) -> Sesion:
        """CU10: HGETALL + TTL sin renovar. 404 inexistente/expirada/parcial, 403 bloqueada."""
        cruda = await self.redis.get_sesion(sesion_id)
        if cruda is None:
            raise _no_encontrada(sesion_id)
        return a_sesion(sesion_id, cruda)

    async def cerrar(self, sesion_id: str) -> None:
        """CU11: el efecto es idempotente; el reintento responde 404 (ya no existe)."""
        if not await self.redis.cerrar_sesion(sesion_id):
            raise _no_encontrada(sesion_id)
