"""CU5–CU7: timeline de eventos, alta validada por tipo (N8) y cierre CP del partido (N2).

Reglas por tipo de evento (N8)
==============================
Desde la reentrega del Hito 3 la API es el ÚNICO camino de escritura de eventos,
así que las reglas de cada tipo viven acá, en una tabla declarativa (`REGLAS`),
y se aplican ANTES de abrir cualquier transacción en Neo4j (400
EVENT_RULE_VIOLATION sin tocar la fuente, RNF3):

| Tipo              | condicionEquipo | dorsalProtagonista | Minuto        |
|-------------------|-----------------|--------------------|---------------|
| INICIO_PARTIDO    | prohibida       | prohibido          | sólo 0        |
| FIN_PARTIDO       | prohibida       | prohibido          | 0–130         |
| CORNER            | obligatoria     | opcional           | 0–130         |
| PASE, ATAJADA, ASISTENCIA, GOL, PENAL, FALTA, TARJETA_AMARILLA, TARJETA_ROJA, SUSTITUCION | obligatoria | obligatorio | 0–130 |

Criterio: INICIO/FIN son hitos administrativos del partido, no acciones de un
jugador; CORNER se le concede a un equipo y el ejecutor puede no registrarse;
el resto son acciones con un protagonista identificable por (condición, dorsal),
que es exactamente lo que el grafo usa para resolver `PROTAGONIZADO_POR`.

Las reglas que dependen del ESTADO del partido (no FINALIZADO, nada después de
FIN_PARTIDO, INICIO/FIN únicos, tipo presente en el catálogo :TipoEvento) no se
pueden decidir sin leer el grafo: las valida el adaptador dentro de la misma
transacción de escritura que crea el evento (409).

Idempotencia (CU6)
==================
`eventoId = {partidoId}-API-{sha256(Idempotency-Key)[:12]}` y
`huella = sha256(JSON canónico del cuerpo)`. Repetir la request con la misma
clave encuentra el mismo nodo → 200 + `Idempotent-Replayed: true`; misma clave
con otro cuerpo (otra huella) → 409 IDEMPOTENCY_KEY_REUSED.

Caché del detalle (CU4)
=======================
Tras una escritura confirmada (alta nueva o cierre) se borra
`f30:cache:partido:{id}` en Redis. Si Redis no responde, la request NO falla
(la escritura ya está confirmada en Neo4j, que es la fuente): se registra un
warning y la copia vieja vence sola por TTL (60 s, mismo criterio del Hito 7).
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Literal

from app.core.errors import NotFoundError, ValidationApiError
from app.schemas.eventos import Evento, EventoNuevo, PaginaEventos
from app.schemas.partidos import CambioEstado, PartidoDetalle
from app.services import cursor_entero
from app.services.ports import Neo4jPort, RedisPort

log = logging.getLogger("fixture2030.eventos")

TIPO_CURSOR = "evt"   # el cursor del timeline lleva la última secuencia devuelta

Exigencia = Literal["obligatorio", "opcional", "prohibido"]


@dataclass(frozen=True)
class Regla:
    condicion: Exigencia
    dorsal: Exigencia
    minuto_min: int = 0
    minuto_max: int = 130


_SIN_PROTAGONISTA = Regla(condicion="prohibido", dorsal="prohibido")
_CON_PROTAGONISTA = Regla(condicion="obligatorio", dorsal="obligatorio")

REGLAS: dict[str, Regla] = {
    "INICIO_PARTIDO": Regla(condicion="prohibido", dorsal="prohibido", minuto_max=0),
    "FIN_PARTIDO": _SIN_PROTAGONISTA,
    "CORNER": Regla(condicion="obligatorio", dorsal="opcional"),
    **{t: _CON_PROTAGONISTA for t in (
        "PASE", "ATAJADA", "ASISTENCIA", "GOL", "PENAL", "FALTA",
        "TARJETA_AMARILLA", "TARJETA_ROJA", "SUSTITUCION")},
}


def validar_reglas(nuevo: EventoNuevo) -> None:
    """Aplica `REGLAS[nuevo.tipo]`; junta TODAS las violaciones en `details`."""
    regla = REGLAS[nuevo.tipo]
    problemas: list[dict[str, str]] = []
    for campo, exigencia, valor in (("condicionEquipo", regla.condicion, nuevo.condicionEquipo),
                                    ("dorsalProtagonista", regla.dorsal, nuevo.dorsalProtagonista)):
        if exigencia == "obligatorio" and valor is None:
            problemas.append({"campo": campo, "problema": f"obligatorio para {nuevo.tipo}"})
        elif exigencia == "prohibido" and valor is not None:
            problemas.append({"campo": campo, "problema": f"no corresponde a {nuevo.tipo}"})
    if not regla.minuto_min <= nuevo.minuto <= regla.minuto_max:
        rango = (f"debe ser {regla.minuto_min}" if regla.minuto_min == regla.minuto_max
                 else f"debe estar entre {regla.minuto_min} y {regla.minuto_max}")
        problemas.append({"campo": "minuto", "problema": f"{rango} para {nuevo.tipo}"})
    if problemas:
        raise ValidationApiError(f"El evento no cumple las reglas del tipo {nuevo.tipo}.",
                                 code="EVENT_RULE_VIOLATION", details=problemas)


def derivar_evento_id(partido_id: str, idempotency_key: str) -> str:
    return f"{partido_id}-API-{hashlib.sha256(idempotency_key.encode()).hexdigest()[:12]}"


def huella_del_cuerpo(nuevo: EventoNuevo) -> str:
    """sha256 del JSON canónico (claves ordenadas, sin espacios; null == ausente)."""
    canonico = json.dumps(nuevo.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonico.encode()).hexdigest()


class EventosService:
    def __init__(self, neo4j: Neo4jPort, redis: RedisPort) -> None:
        self.neo4j = neo4j
        self.redis = redis

    async def list_eventos(self, partido_id: str, tipo: str | None, limit: int,
                           cursor: str | None) -> PaginaEventos:
        """CU5: timeline en orden de `secuencia`, paginado por keyset sobre la secuencia.
        Partido inexistente → 404; partido sin eventos → 200 con items [] (§5.6)."""
        despues = cursor_entero.decodificar(TIPO_CURSOR, cursor)
        filas = await self.neo4j.list_eventos(partido_id, tipo, despues, limit + 1)
        if filas is None:
            raise NotFoundError(f"No existe el partido {partido_id}.", code="MATCH_NOT_FOUND")
        items = filas[:limit]
        siguiente = (cursor_entero.codificar(TIPO_CURSOR, items[-1].secuencia)
                     if len(filas) > limit else None)
        return PaginaEventos(partidoId=partido_id, items=items, limit=limit, nextCursor=siguiente)

    async def registrar(self, partido_id: str, idempotency_key: str,
                        nuevo: EventoNuevo) -> tuple[Evento, bool]:
        """Devuelve (evento, creado). creado=False ⇒ reintento con la misma clave."""
        validar_reglas(nuevo)
        evento, creado = await self.neo4j.registrar_evento(
            partido_id, derivar_evento_id(partido_id, idempotency_key), nuevo,
            huella_del_cuerpo(nuevo))
        if creado:
            await self._invalidar_cache(partido_id)
        return evento, creado

    async def cerrar(self, partido_id: str, cambio: CambioEstado) -> PartidoDetalle:
        """CU7: el contrato sólo admite `estado: FINALIZADO`; las validaciones de la
        transición (PROGRAMADO, FIN_PARTIDO presente) y el marcador derivado de los
        GOL las hace el adaptador en una única transacción de escritura."""
        del cambio  # única transición posible, ya validada por el esquema
        detalle = await self.neo4j.cerrar_partido(partido_id)
        await self._invalidar_cache(partido_id)
        return detalle

    async def _invalidar_cache(self, partido_id: str) -> None:
        # La escritura ya está confirmada en Neo4j: una falla de la caché no puede
        # convertirla en error (el cliente reintentaría algo que ya ocurrió).
        try:
            await self.redis.cache_del_partido(partido_id)
        except Exception as exc:  # noqa: BLE001 — degradación documentada (vence por TTL)
            log.warning("no se pudo invalidar la caché del partido; vence por TTL", extra={
                "evento": "cache", "dependencia": "redis", "operacion": "cache_del_partido",
                "resultado": "no_invalidada", "tipo": type(exc).__name__})
