"""Adaptadores falsos en memoria para MongoPort y Neo4jPort (y la caché de RedisPort).

Reproducen el comportamiento observable de los adaptadores reales que los
servicios necesitan: "no existe" como None, orden por dorsal/secuencia, filtro
por `despues_de_*`, límite, y las reglas de conflicto de registrar/cerrar con
el mismo orden de evaluación que `app/adapters/neo4j.py`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from app.core.errors import ConflictError, DependencyUnavailableError, NotFoundError
from app.schemas.equipos import Colores, Equipo, Jugador, PartidoDeEquipo
from app.schemas.eventos import Evento, EventoNuevo
from app.schemas.partidos import EquipoEnPartido, Marcador, PartidoDetalle, Sede

POSICIONES = ["Arquero"] + ["Defensor"] * 5 + ["Mediocampista"] * 8 + ["Delantero"] * 9


def plantel(codigo: str, n: int = 23) -> list[Jugador]:
    return [Jugador(dni=str(30000000 + d), nombre=f"Nombre{d}", apellido=f"Apellido{d}",
                    fechaNacimiento=date(2000, 1, d % 28 + 1), posicion=POSICIONES[(d - 1) % 23],
                    dorsal=d, equipoCodigo=codigo) for d in range(1, n + 1)]


class FakeMongo:
    nombre = "mongodb"

    def __init__(self) -> None:
        self.equipos = {
            "ARG": Equipo(codigo="ARG", nombre="Argentina", confederacion="CONMEBOL", rankingFifa=1,
                          grupo="A", entrenador="Lionel Scaloni", sede="Montevideo",
                          colores=Colores(principal="Celeste", alternativo="Azul"),
                          cantidadJugadores=23),
            "FIJ": Equipo(codigo="FIJ", nombre="Fiyi", confederacion="OFC", rankingFifa=155, grupo="P"),
        }
        self.jugadores = {"ARG": plantel("ARG"), "FIJ": []}
        self.llamadas: list[tuple] = []

    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def ping(self) -> None: ...

    async def get_equipo(self, codigo: str) -> Equipo | None:
        self.llamadas.append(("get_equipo", codigo))
        return self.equipos.get(codigo)

    async def list_jugadores(self, codigo, posicion, despues_de_dorsal, limite):
        self.llamadas.append(("list_jugadores", codigo, posicion, despues_de_dorsal, limite))
        filas = [j for j in self.jugadores.get(codigo, [])
                 if (posicion is None or j.posicion == posicion)
                 and (despues_de_dorsal is None or j.dorsal > despues_de_dorsal)]
        return sorted(filas, key=lambda j: j.dorsal)[:limite]


# --------------------------------------------------------------------------- Neo4j
@dataclass
class _Partido:
    partido_id: str
    local: str
    visitante: str
    estado: str = "PROGRAMADO"
    fecha: datetime = datetime(2030, 7, 20, 16, 0, tzinfo=timezone.utc)
    goles: tuple[int, int] | None = None
    eventos: list[tuple[Evento, str | None]] = field(default_factory=list)   # (evento, huella)


CATALOGO = {"INICIO_PARTIDO", "FIN_PARTIDO", "PASE", "CORNER", "ATAJADA", "ASISTENCIA", "GOL",
            "PENAL", "FALTA", "TARJETA_AMARILLA", "TARJETA_ROJA", "SUSTITUCION"}


class FakeNeo4j:
    """Grafo mínimo: PAR-A-1 FINALIZADO con 13 eventos, PAR-D16-01 PROGRAMADO sin
    eventos, PAR-DEMO-API PROGRAMADO con 3 eventos de carga (como el script de demo)."""
    nombre = "neo4j"

    def __init__(self) -> None:
        self.catalogo = set(CATALOGO)
        self.equipos = {"ARG": "Argentina", "BRA": "Brasil", "MEX": "México", "NZL": "Nueva Zelanda"}
        self.partidos: dict[str, _Partido] = {}
        a1 = self._nuevo("PAR-A-1", "ARG", "MEX", estado="FINALIZADO")
        for i, tipo in enumerate(["INICIO_PARTIDO"] + ["PASE"] * 4 + ["GOL"] * 2 + ["FALTA"] * 5
                                 + ["FIN_PARTIDO"], start=1):
            self._agregar(a1, f"PAR-A-1-EV-{i:02d}", tipo, min(i * 7, 90), "LOCAL", 9, None)
        a1.goles = (2, 0)
        self._nuevo("PAR-D16-01", "BRA", "ARG")
        demo = self._nuevo("PAR-DEMO-API", "ARG", "BRA")
        self._agregar(demo, "PAR-DEMO-API-EV-01", "INICIO_PARTIDO", 0, None, None, None)
        self._agregar(demo, "PAR-DEMO-API-EV-02", "PASE", 10, "LOCAL", 5, None)
        self._agregar(demo, "PAR-DEMO-API-EV-03", "GOL", 11, "LOCAL", 9, None)
        self.llamadas: list[tuple] = []

    # ---------------------------------------------------------------- utilidades
    def _nuevo(self, pid: str, local: str, visitante: str, estado: str = "PROGRAMADO") -> _Partido:
        p = _Partido(pid, local, visitante, estado,
                     fecha=datetime(2030, 6, 9, 13, tzinfo=timezone.utc) + timedelta(days=len(self.partidos)))
        self.partidos[pid] = p
        return p

    @staticmethod
    def _agregar(p: _Partido, eid: str, tipo: str, minuto: int, cond, dorsal, huella,
                 origen: str = "CARGA") -> Evento:
        ev = Evento(eventoId=eid, partidoId=p.partido_id, secuencia=len(p.eventos) + 1, tipo=tipo,
                    minuto=minuto, condicionEquipo=cond, dorsalProtagonista=dorsal,
                    timestamp=p.fecha + timedelta(minutes=minuto), origen=origen)
        p.eventos.append((ev, huella))
        return ev

    def _detalle(self, p: _Partido) -> PartidoDetalle:
        gl = sum(1 for e, _ in p.eventos if e.tipo == "GOL" and e.condicionEquipo == "LOCAL")
        gv = sum(1 for e, _ in p.eventos if e.tipo == "GOL" and e.condicionEquipo == "VISITANTE")
        return PartidoDetalle(
            partidoId=p.partido_id, fase="DEMO", fechaHora=p.fecha, estado=p.estado,
            sede=Sede(sedeId="URU-CEN", nombre="Estadio Centenario", ciudad="Montevideo",
                      pais="Uruguay", region="AMERICAS"),
            local=EquipoEnPartido(equipoCodigo=p.local, nombre=self.equipos[p.local]),
            visitante=EquipoEnPartido(equipoCodigo=p.visitante, nombre=self.equipos[p.visitante]),
            marcador=Marcador(golesLocal=gl, golesVisitante=gv) if p.estado == "FINALIZADO" else None,
            cantidadEventos=len(p.eventos))

    # ---------------------------------------------------------------- puerto
    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def ping(self) -> None: ...

    async def get_partido(self, partido_id):
        p = self.partidos.get(partido_id)
        return self._detalle(p) if p else None

    async def list_partidos_de_equipo(self, codigo, limite):
        self.llamadas.append(("list_partidos_de_equipo", codigo, limite))
        if codigo not in self.equipos:
            return None
        filas = []
        for p in sorted(self.partidos.values(), key=lambda x: x.fecha):
            if codigo not in (p.local, p.visitante):
                continue
            local = codigo == p.local
            fin = p.estado == "FINALIZADO"
            filas.append(PartidoDeEquipo(
                partidoId=p.partido_id, fase="GRUPOS", fechaHora=p.fecha, estado=p.estado,
                condicion="LOCAL" if local else "VISITANTE",
                rivalCodigo=p.visitante if local else p.local,
                golesLocal=p.goles[0] if fin and p.goles else None,
                golesVisitante=p.goles[1] if fin and p.goles else None))
        return filas[:limite]

    async def list_eventos(self, partido_id, tipo, despues_de_secuencia, limite):
        self.llamadas.append(("list_eventos", partido_id, tipo, despues_de_secuencia, limite))
        p = self.partidos.get(partido_id)
        if p is None:
            return None
        filas = [e for e, _ in p.eventos
                 if (tipo is None or e.tipo == tipo)
                 and (despues_de_secuencia is None or e.secuencia > despues_de_secuencia)]
        return filas[:limite]

    async def registrar_evento(self, partido_id: str, evento_id: str, nuevo: EventoNuevo,
                               huella: str) -> tuple[Evento, bool]:
        self.llamadas.append(("registrar_evento", partido_id, evento_id))
        p = self.partidos.get(partido_id)
        if p is None:
            raise NotFoundError("no existe", code="MATCH_NOT_FOUND")
        for e, h in p.eventos:
            if e.eventoId == evento_id:
                if h != huella:
                    raise ConflictError("reusada", code="IDEMPOTENCY_KEY_REUSED")
                return e, False
        if p.estado == "FINALIZADO":
            raise ConflictError("finalizado", code="MATCH_FINALIZED")
        tipos = [e.tipo for e, _ in p.eventos]
        if "FIN_PARTIDO" in tipos:
            raise ConflictError("después de fin", code="EVENT_AFTER_FIN")
        if nuevo.tipo in ("INICIO_PARTIDO", "FIN_PARTIDO") and nuevo.tipo in tipos:
            raise ConflictError("duplicado", code="DUPLICATE_UNIQUE_EVENT")
        if nuevo.tipo not in self.catalogo:
            raise ConflictError("fuera de catálogo", code="EVENT_TYPE_NOT_IN_CATALOG")
        ev = self._agregar(p, evento_id, nuevo.tipo, nuevo.minuto, nuevo.condicionEquipo,
                           nuevo.dorsalProtagonista, huella, origen="API")
        return ev, True

    async def cerrar_partido(self, partido_id: str) -> PartidoDetalle:
        self.llamadas.append(("cerrar_partido", partido_id))
        p = self.partidos.get(partido_id)
        if p is None:
            raise NotFoundError("no existe", code="MATCH_NOT_FOUND")
        if p.estado != "PROGRAMADO":
            raise ConflictError("transición", code="INVALID_TRANSITION")
        if not any(e.tipo == "FIN_PARTIDO" for e, _ in p.eventos):
            raise ConflictError("sin fin", code="MISSING_FIN_PARTIDO")
        p.estado = "FINALIZADO"
        return self._detalle(p)


class FakeRedisCache:
    """Sólo la parte de caché de RedisPort que usa EventosService."""
    nombre = "redis"

    def __init__(self, caida: bool = False) -> None:
        self.caida = caida
        self.borradas: list[str] = []

    async def cache_del_partido(self, partido_id: str) -> None:
        if self.caida:
            raise DependencyUnavailableError("redis", timeout=True)
        self.borradas.append(partido_id)
