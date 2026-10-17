"""Adaptador Neo4j (Hito 5) — driver oficial async (`neo4j` 6.x).

Modelo (fixture2030-neo4j/queries/estructura.cypher + carga.cypher):
  (:Equipo)-[:PARTICIPA_EN {condicion}]->(:Partido)-[:SE_JUEGA_EN]->(:Sede)
  (:Evento)-[:OCURRE_EN]->(:Partido), (:Evento)-[:ES_DE_TIPO]->(:TipoEvento)
  (:Evento)-[:PROTAGONIZADO_POR]->(:Jugador)-[:JUEGA_EN {dorsal}]->(:Equipo)
  (:Evento)-[:SIGUIENTE_EVENTO]->(:Evento)   orden total dentro del partido

Reglas del adaptador:
  - Todo Cypher es una constante con parámetros `$x`: ningún valor que venga del
    cliente se concatena en el texto de la consulta (RNF3 / inyección).
  - Lecturas en `session.execute_read`, escrituras en `session.execute_write`
    (transacción de escritura explícita; si la función lanza, el driver hace
    rollback y no confirma nada).
  - El driver se crea en `connect()` sin abrir conexiones (es perezoso): con
    Neo4j caído la API arranca igual y estas rutas responden 503.
  - Los timeouts del driver (conexión, adquisición del pool, reintentos de
    transacción) se acotan con `DEP_TIMEOUT_S`, el mismo que usa `ejecutar`.
  - `AuthError` también es "no disponible" (503): una credencial mal configurada
    es un problema de operación, y el mensaje público no la expone.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any, TypeVar

from neo4j import AsyncGraphDatabase, AsyncManagedTransaction
from neo4j.exceptions import (AuthError, ClientError, DatabaseUnavailable, Forbidden, ServiceUnavailable,
                              SessionExpired)

from app.adapters.base import ejecutar
from app.config.settings import Settings
from app.core.errors import ConflictError, DependencyUnavailableError, NotFoundError
from app.schemas.equipos import PartidoDeEquipo
from app.schemas.eventos import Evento, EventoNuevo, Protagonista
from app.schemas.partidos import EquipoEnPartido, Marcador, PartidoDetalle, Sede

T = TypeVar("T")

ERRORES_DISPONIBILIDAD: tuple[type[BaseException], ...] = (
    ServiceUnavailable, SessionExpired, AuthError, Forbidden, DatabaseUnavailable)

TIPOS_UNICOS = ("INICIO_PARTIDO", "FIN_PARTIDO")

# =========================================================================== Cypher
# Proyección común del detalle de partido (get_partido y cerrar_partido). El
# marcador se DERIVA de los eventos GOL por lado, igual que el paso 12 de
# carga.cypher: nunca puede contradecir al timeline.
CYPHER_DETALLE = """
MATCH (p:Partido {partidoId: $partidoId})
OPTIONAL MATCH (l:Equipo)-[:PARTICIPA_EN {condicion: 'LOCAL'}]->(p)
OPTIONAL MATCH (v:Equipo)-[:PARTICIPA_EN {condicion: 'VISITANTE'}]->(p)
OPTIONAL MATCH (p)-[:SE_JUEGA_EN]->(s:Sede)
WITH p, head(collect(DISTINCT l)) AS l, head(collect(DISTINCT v)) AS v,
     head(collect(DISTINCT s)) AS s
RETURN p {.partidoId, .fase, .grupo, .jornada, .fechaHora, .estado} AS partido,
       l {.equipoId, .nombre} AS local,
       v {.equipoId, .nombre} AS visitante,
       s {.sedeId, .nombre, .ciudad, .pais, .region} AS sede,
       COUNT { (:Evento)-[:OCURRE_EN]->(p) } AS cantidadEventos,
       COUNT { (g:Evento)-[:OCURRE_EN]->(p)
               WHERE g.tipo = 'GOL' AND g.condicionEquipo = 'LOCAL' } AS golesLocal,
       COUNT { (g:Evento)-[:OCURRE_EN]->(p)
               WHERE g.tipo = 'GOL' AND g.condicionEquipo = 'VISITANTE' } AS golesVisitante
"""

# Partidos de un equipo: el rival es el otro extremo PARTICIPA_EN del mismo partido.
CYPHER_PARTIDOS_DE_EQUIPO = """
MATCH (e:Equipo {equipoId: $codigo})
OPTIONAL MATCH (e)-[r:PARTICIPA_EN]->(p:Partido)<-[:PARTICIPA_EN]-(rival:Equipo)
WHERE rival <> e
WITH e, r, p, rival
ORDER BY p.fechaHora, p.partidoId
RETURN e.equipoId AS equipoId,
       collect(CASE WHEN p IS NULL THEN null ELSE {
         partidoId: p.partidoId, fase: p.fase, grupo: p.grupo, fechaHora: p.fechaHora,
         estado: p.estado, condicion: r.condicion, rivalCodigo: rival.equipoId,
         golesLocal: p.golesLocal, golesVisitante: p.golesVisitante
       } END)[..$limite] AS partidos
"""

CYPHER_EXISTE_PARTIDO = "MATCH (p:Partido {partidoId: $partidoId}) RETURN p.partidoId AS partidoId"

# Timeline: se apoya en el índice compuesto evento_particion_partido
# (partidoId, secuencia) — una sola partición lógica, ya ordenada (Hito 5).
CYPHER_EVENTOS = """
MATCH (ev:Evento)-[:OCURRE_EN]->(:Partido {partidoId: $partidoId})
WHERE ev.partidoId = $partidoId AND ev.secuencia > $despues
  AND ($tipo IS NULL OR ev.tipo = $tipo)
WITH ev ORDER BY ev.secuencia LIMIT $limite
OPTIONAL MATCH (ev)-[:PROTAGONIZADO_POR]->(j:Jugador)
WITH ev, head(collect(j {.dni, .nombre, .apellido})) AS prot
RETURN ev {.eventoId, .partidoId, .secuencia, .tipo, .minuto, .condicionEquipo,
           .dorsalProtagonista, .timestamp, .origen} AS ev, prot
ORDER BY ev.secuencia
"""

CYPHER_EVENTO_POR_ID = """
MATCH (ev:Evento {eventoId: $eventoId})
OPTIONAL MATCH (ev)-[:PROTAGONIZADO_POR]->(j:Jugador)
WITH ev, head(collect(j {.dni, .nombre, .apellido})) AS prot
RETURN ev {.eventoId, .partidoId, .secuencia, .tipo, .minuto, .condicionEquipo,
           .dorsalProtagonista, .timestamp, .origen, .huella} AS ev, prot
"""

# Lock de escritura sobre el nodo :Partido. Escribir (y borrar) una propiedad
# toma el lock exclusivo del nodo, que Neo4j mantiene hasta el commit/rollback
# aunque la propiedad no quede persistida. Toda escritura de la API sobre un
# partido (alta de evento, cierre) empieza por acá, así que dos escrituras
# concurrentes sobre el MISMO partido se serializan: la segunda espera, y al
# continuar ve la secuencia, el FIN_PARTIDO o el estado que confirmó la primera.
CYPHER_BLOQUEAR_PARTIDO = """
MATCH (p:Partido {partidoId: $partidoId})
SET p._lockApi = true
REMOVE p._lockApi
RETURN p.estado AS estado
"""

CYPHER_ESTADO_EVENTOS = """
MATCH (p:Partido {partidoId: $partidoId})
OPTIONAL MATCH (ev:Evento)-[:OCURRE_EN]->(p)
WITH p, max(ev.secuencia) AS maxSecuencia, max(ev.minuto) AS maxMinuto,
     sum(CASE WHEN ev.tipo = 'FIN_PARTIDO' THEN 1 ELSE 0 END) AS fines,
     sum(CASE WHEN ev.tipo = $tipo THEN 1 ELSE 0 END) AS mismoTipo
RETURN maxSecuencia, maxMinuto, fines, mismoTipo,
       EXISTS { (:TipoEvento {tipoEventoId: $tipo}) } AS enCatalogo
"""

CYPHER_CREAR_EVENTO = """
MATCH (p:Partido {partidoId: $partidoId})
MATCH (t:TipoEvento {tipoEventoId: $tipo})
OPTIONAL MATCH (p)-[:SE_JUEGA_EN]->(s:Sede)
WITH p, t, head(collect(s)) AS s
CREATE (ev:Evento {
  eventoId: $eventoId, partidoId: $partidoId, secuencia: $secuencia, tipo: $tipo,
  minuto: $minuto, condicionEquipo: $condicion, dorsalProtagonista: $dorsal,
  timestamp: p.fechaHora + duration({minutes: $minuto}),
  regionOrigen: s.region, origen: 'API', huella: $huella, registradoEn: datetime()
})
CREATE (ev)-[:OCURRE_EN]->(p)
CREATE (ev)-[:ES_DE_TIPO]->(t)
WITH ev, p
OPTIONAL MATCH (prev:Evento {partidoId: $partidoId, secuencia: $secuenciaAnterior})
FOREACH (_ IN CASE WHEN prev IS NULL THEN [] ELSE [1] END |
  CREATE (prev)-[:SIGUIENTE_EVENTO]->(ev))
WITH ev, p
OPTIONAL MATCH (p)<-[:PARTICIPA_EN {condicion: $condicion}]-(:Equipo)<-[jn:JUEGA_EN]-(j:Jugador)
WHERE jn.dorsal = $dorsal
WITH ev, head(collect(j)) AS j
FOREACH (_ IN CASE WHEN j IS NULL THEN [] ELSE [1] END |
  CREATE (ev)-[:PROTAGONIZADO_POR]->(j))
RETURN ev {.eventoId, .partidoId, .secuencia, .tipo, .minuto, .condicionEquipo,
           .dorsalProtagonista, .timestamp, .origen} AS ev,
       j {.dni, .nombre, .apellido} AS prot
"""

CYPHER_HAY_FIN = """
RETURN EXISTS { (:Evento {tipo: 'FIN_PARTIDO'})-[:OCURRE_EN]->(:Partido {partidoId: $partidoId}) } AS hayFin
"""

CYPHER_CERRAR = """
MATCH (p:Partido {partidoId: $partidoId})
WITH p,
     COUNT { (g:Evento)-[:OCURRE_EN]->(p)
             WHERE g.tipo = 'GOL' AND g.condicionEquipo = 'LOCAL' } AS golesLocal,
     COUNT { (g:Evento)-[:OCURRE_EN]->(p)
             WHERE g.tipo = 'GOL' AND g.condicionEquipo = 'VISITANTE' } AS golesVisitante
SET p.estado = 'FINALIZADO', p.golesLocal = golesLocal, p.golesVisitante = golesVisitante,
    p.cerradoEn = datetime()
"""


# =========================================================================== mapeo puro
def a_nativo(valor: Any) -> Any:
    """neo4j.time.DateTime/Date → datetime/date de Python (los demás valores, tal cual)."""
    return valor.to_native() if hasattr(valor, "to_native") else valor


def evento_desde_registro(ev: dict[str, Any], prot: dict[str, Any] | None) -> Evento:
    return Evento(
        eventoId=ev["eventoId"],
        partidoId=ev["partidoId"],
        secuencia=ev["secuencia"],
        tipo=ev["tipo"],
        minuto=ev["minuto"],
        condicionEquipo=ev.get("condicionEquipo"),
        dorsalProtagonista=ev.get("dorsalProtagonista"),
        protagonista=Protagonista(dni=prot["dni"], nombre=prot["nombre"], apellido=prot["apellido"])
        if prot else None,
        timestamp=a_nativo(ev.get("timestamp")),
        origen="API" if ev.get("origen") == "API" else "CARGA",
    )


def detalle_desde_registro(r: dict[str, Any]) -> PartidoDetalle:
    """Registro de CYPHER_DETALLE → PartidoDetalle. El marcador sólo se expone
    con el partido FINALIZADO (mientras tanto es `null`, contrato del CU4)."""
    p, s = r["partido"], r["sede"]
    if r["local"] is None or r["visitante"] is None:
        # Invariante de la carga: todo :Partido tiene un LOCAL y un VISITANTE.
        raise ValueError(f"partido {p['partidoId']} sin LOCAL/VISITANTE en el grafo")
    finalizado = p["estado"] == "FINALIZADO"
    return PartidoDetalle(
        partidoId=p["partidoId"],
        fase=p["fase"],
        grupo=p.get("grupo"),
        jornada=p.get("jornada"),
        fechaHora=a_nativo(p["fechaHora"]),
        estado=p["estado"],
        sede=Sede(sedeId=s["sedeId"], nombre=s["nombre"], ciudad=s["ciudad"], pais=s["pais"],
                  region=s["region"]) if s else None,
        local=EquipoEnPartido(equipoCodigo=r["local"]["equipoId"], nombre=r["local"]["nombre"]),
        visitante=EquipoEnPartido(equipoCodigo=r["visitante"]["equipoId"],
                                  nombre=r["visitante"]["nombre"]),
        marcador=Marcador(golesLocal=r["golesLocal"], golesVisitante=r["golesVisitante"])
        if finalizado else None,
        cantidadEventos=r["cantidadEventos"],
    )


def partido_de_equipo_desde_mapa(m: dict[str, Any]) -> PartidoDeEquipo:
    finalizado = m["estado"] == "FINALIZADO"
    return PartidoDeEquipo(
        partidoId=m["partidoId"],
        fase=m["fase"],
        grupo=m.get("grupo"),
        fechaHora=a_nativo(m["fechaHora"]),
        estado=m["estado"],
        condicion=m["condicion"],
        rivalCodigo=m["rivalCodigo"],
        golesLocal=m.get("golesLocal") if finalizado else None,
        golesVisitante=m.get("golesVisitante") if finalizado else None,
    )


def _partido_inexistente(partido_id: str) -> NotFoundError:
    return NotFoundError(f"No existe el partido {partido_id}.", code="MATCH_NOT_FOUND")


# =========================================================================== funciones de transacción
async def _tx_detalle(tx: AsyncManagedTransaction, partido_id: str) -> PartidoDetalle | None:
    r = await (await tx.run(CYPHER_DETALLE, partidoId=partido_id)).single()
    return detalle_desde_registro(r.data()) if r else None


async def _tx_partidos_de_equipo(tx: AsyncManagedTransaction, codigo: str,
                                 limite: int) -> list[PartidoDeEquipo] | None:
    r = await (await tx.run(CYPHER_PARTIDOS_DE_EQUIPO, codigo=codigo, limite=limite)).single()
    if r is None:
        return None
    return [partido_de_equipo_desde_mapa(m) for m in r["partidos"]]


async def _tx_eventos(tx: AsyncManagedTransaction, partido_id: str, tipo: str | None,
                      despues: int | None, limite: int) -> list[Evento] | None:
    if await (await tx.run(CYPHER_EXISTE_PARTIDO, partidoId=partido_id)).single() is None:
        return None
    res = await tx.run(CYPHER_EVENTOS, partidoId=partido_id, tipo=tipo,
                       despues=despues if despues is not None else 0, limite=limite)
    return [evento_desde_registro(r["ev"], r["prot"]) async for r in res]


async def _tx_registrar(tx: AsyncManagedTransaction, partido_id: str, evento_id: str,
                        nuevo: EventoNuevo, huella: str) -> tuple[Evento, bool]:
    # 1. Lock del partido (serializa altas/cierres concurrentes) + existencia.
    bloqueo = await (await tx.run(CYPHER_BLOQUEAR_PARTIDO, partidoId=partido_id)).single()
    if bloqueo is None:
        raise _partido_inexistente(partido_id)

    # 2. Idempotencia: ya existe el evento de esta clave → replay o clave reutilizada.
    #    Va ANTES de las reglas de estado: un reintento después del cierre sigue
    #    respondiendo 200 con el evento original.
    previo = await (await tx.run(CYPHER_EVENTO_POR_ID, eventoId=evento_id)).single()
    if previo is not None:
        if previo["ev"].get("huella") != huella:
            raise ConflictError("La Idempotency-Key ya se usó con otro cuerpo.",
                                code="IDEMPOTENCY_KEY_REUSED")
        return evento_desde_registro(previo["ev"], previo["prot"]), False

    # 3. Reglas que dependen del estado del partido (N2/N8).
    if bloqueo["estado"] == "FINALIZADO":
        raise ConflictError(f"El partido {partido_id} ya está FINALIZADO.", code="MATCH_FINALIZED")
    estado = await (await tx.run(CYPHER_ESTADO_EVENTOS, partidoId=partido_id,
                                 tipo=nuevo.tipo)).single()
    if estado["fines"] > 0:
        raise ConflictError("El partido ya tiene FIN_PARTIDO: no admite más eventos.",
                            code="EVENT_AFTER_FIN")
    if nuevo.tipo in TIPOS_UNICOS and estado["mismoTipo"] > 0:
        raise ConflictError(f"El partido ya tiene un evento {nuevo.tipo}.",
                            code="DUPLICATE_UNIQUE_EVENT")
    if estado["maxMinuto"] is not None and nuevo.minuto < estado["maxMinuto"]:
        # El reloj lógico es `secuencia`; el minuto de juego tampoco puede retroceder
        # (un FIN_PARTIDO al minuto 5 después de un GOL al 13 dejaría un timeline absurdo).
        raise ConflictError(f"El minuto {nuevo.minuto} es anterior al último evento registrado "
                            f"(minuto {estado['maxMinuto']}).", code="EVENT_OUT_OF_ORDER")
    if not estado["enCatalogo"]:
        raise ConflictError(f"El tipo {nuevo.tipo} no está en el catálogo :TipoEvento.",
                            code="EVENT_TYPE_NOT_IN_CATALOG")

    # 4. Alta: secuencia = max + 1 (protegida por el lock del paso 1).
    anterior = estado["maxSecuencia"]
    creado = await (await tx.run(
        CYPHER_CREAR_EVENTO, partidoId=partido_id, eventoId=evento_id, tipo=nuevo.tipo,
        minuto=nuevo.minuto, condicion=nuevo.condicionEquipo, dorsal=nuevo.dorsalProtagonista,
        huella=huella, secuencia=(anterior or 0) + 1, secuenciaAnterior=anterior,
    )).single()
    return evento_desde_registro(creado["ev"], creado["prot"]), True


async def _tx_cerrar(tx: AsyncManagedTransaction, partido_id: str) -> PartidoDetalle:
    bloqueo = await (await tx.run(CYPHER_BLOQUEAR_PARTIDO, partidoId=partido_id)).single()
    if bloqueo is None:
        raise _partido_inexistente(partido_id)
    if bloqueo["estado"] != "PROGRAMADO":
        raise ConflictError(f"Transición inválida: el partido está {bloqueo['estado']}.",
                            code="INVALID_TRANSITION")
    if not (await (await tx.run(CYPHER_HAY_FIN, partidoId=partido_id)).single())["hayFin"]:
        raise ConflictError("No se puede cerrar: el partido no tiene evento FIN_PARTIDO.",
                            code="MISSING_FIN_PARTIDO")
    await (await tx.run(CYPHER_CERRAR, partidoId=partido_id)).consume()
    detalle = await _tx_detalle(tx, partido_id)
    assert detalle is not None  # el nodo está bloqueado por esta misma transacción
    return detalle


# =========================================================================== adaptador
class Neo4jAdapter:
    nombre = "neo4j"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._driver = None

    # ---------------------------------------------------------------- ciclo de vida
    def _crear_driver(self):  # noqa: ANN202 — AsyncDriver
        t = self.settings.dep_timeout_s
        return AsyncGraphDatabase.driver(
            self.settings.neo4j_uri,
            auth=(self.settings.neo4j_user, self.settings.neo4j_password.get_secret_value()),
            connection_timeout=t, connection_acquisition_timeout=t, max_transaction_retry_time=t,
            user_agent="fixture2030-api",
            # "La propiedad X no existe" (p. ej. `huella`/`origen` antes del primer
            # alta por la API) es esperable y sólo ensuciaría el log.
            notifications_disabled_classifications=["UNRECOGNIZED"],
        )

    async def connect(self) -> None:
        if self._driver is None:
            self._driver = self._crear_driver()   # perezoso: no abre conexiones

    async def close(self) -> None:
        if self._driver is not None:
            await self._driver.close()
            self._driver = None

    async def _en_sesion(self, operacion: str, escritura: bool,
                         fn: Callable[..., Awaitable[T]], *args: Any) -> T:
        if self._driver is None:
            await self.connect()

        async def _correr() -> T:
            try:
                async with self._driver.session(database=self.settings.neo4j_database) as s:
                    if escritura:
                        return await s.execute_write(fn, *args)
                    return await s.execute_read(fn, *args)
            except (AuthError, Forbidden):
                raise   # los clasifica `ejecutar` (autenticacion / autorizacion)
            except ClientError as exc:
                # Hito 11 (RF17): database inexistente = contexto mal configurado → 503,
                # no 500. Cualquier otro ClientError (Cypher inválido) sigue siendo 500.
                if (exc.code or "").endswith("DatabaseNotFound"):
                    raise DependencyUnavailableError(self.nombre, motivo="contexto") from exc
                raise

        return await ejecutar(self.nombre, operacion, _correr(),
                              timeout_s=self.settings.dep_timeout_s,
                              errores_de_disponibilidad=ERRORES_DISPONIBILIDAD)

    async def ping(self) -> None:
        async def _uno(tx: AsyncManagedTransaction) -> None:
            if (await (await tx.run("RETURN 1 AS ok")).single()) is None:
                raise DependencyUnavailableError(self.nombre)
        await self._en_sesion("ping", False, _uno)

    # ---------------------------------------------------------------- lecturas
    async def get_partido(self, partido_id: str) -> PartidoDetalle | None:
        return await self._en_sesion("get_partido", False, _tx_detalle, partido_id)

    async def list_partidos_de_equipo(self, codigo: str, limite: int) -> list[PartidoDeEquipo] | None:
        return await self._en_sesion("list_partidos_de_equipo", False,
                                     _tx_partidos_de_equipo, codigo, limite)

    async def list_eventos(self, partido_id: str, tipo: str | None,
                           despues_de_secuencia: int | None, limite: int) -> list[Evento] | None:
        return await self._en_sesion("list_eventos", False, _tx_eventos,
                                     partido_id, tipo, despues_de_secuencia, limite)

    # ---------------------------------------------------------------- escrituras
    async def registrar_evento(self, partido_id: str, evento_id: str, nuevo: EventoNuevo,
                               huella: str) -> tuple[Evento, bool]:
        """Alta de evento en UNA transacción de escritura (ver `_tx_registrar`).

        Orden: lock del partido → 404 si no existe → replay/409 por idempotencia →
        409 MATCH_FINALIZED / EVENT_AFTER_FIN / DUPLICATE_UNIQUE_EVENT /
        EVENT_TYPE_NOT_IN_CATALOG → CREATE con `secuencia = coalesce(max, 0) + 1`,
        `origen: 'API'`, `huella`, OCURRE_EN, ES_DE_TIPO, SIGUIENTE_EVENTO desde el
        anterior y PROTAGONIZADO_POR si (condición, dorsal) resuelve un jugador.

        Concurrencia: la transacción empieza escribiendo-y-borrando una propiedad
        del :Partido (`CYPHER_BLOQUEAR_PARTIDO`), lo que toma su lock exclusivo
        hasta el commit. Dos altas simultáneas del mismo partido quedan en fila:
        la segunda lee el `max(secuencia)` ya confirmado por la primera, así que
        no hay dos eventos con la misma secuencia ni dos FIN_PARTIDO. Si además
        llegan dos requests con la misma clave, la segunda encuentra el nodo y
        responde replay; la restricción única de `eventoId` es la red de seguridad.
        """
        return await self._en_sesion("registrar_evento", True, _tx_registrar,
                                     partido_id, evento_id, nuevo, huella)

    async def cerrar_partido(self, partido_id: str) -> PartidoDetalle:
        """Cierre CP en UNA transacción de escritura, con el mismo lock del partido
        que el alta de eventos (un FIN_PARTIDO y un cierre concurrentes no se cruzan):
        404 / 409 INVALID_TRANSITION (no PROGRAMADO) / 409 MISSING_FIN_PARTIDO; luego
        cuenta GOL por condición y fija estado, golesLocal, golesVisitante y cerradoEn."""
        return await self._en_sesion("cerrar_partido", True, _tx_cerrar, partido_id)
