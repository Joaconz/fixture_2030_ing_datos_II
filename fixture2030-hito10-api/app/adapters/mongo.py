"""Adaptador MongoDB (Hito 4) — pymongo `AsyncMongoClient`.

Base `fixture2030`, colecciones `equipos` (clave natural `_id` = código FIFA) y
`jugadores` (`equipoId` referencia al equipo; índice
`idx_jugadores_equipoId_posicion` = `{equipoId: 1, posicion: 1}`).

Decisiones:
  - Conexión perezosa: crear el `AsyncMongoClient` no abre sockets; el primer
    comando hace la selección de servidor. Así `connect()` nunca bloquea ni falla
    con Mongo caído, y esa fuente responde 503 hasta que vuelva (ports.py).
  - Los tres timeouts del driver (selección de servidor, conexión, socket) se
    derivan de `DEP_TIMEOUT_S`, igual que el `asyncio.wait_for` de `ejecutar`:
    el driver se rinde antes o a la vez que la API, nunca después.
  - Sólo proyecciones explícitas: el documento completo nunca sale de acá y el
    `_id` (ObjectId) de los jugadores no se expone (su clave natural es el dni).
  - `hint` al índice `{equipoId, posicion}` en el listado del plantel: es el
    índice que el Hito 4 diseñó para este acceso; fijarlo hace que el plan sea
    el mismo con o sin `posicion` (con `posicion` es igualdad en las dos claves;
    sin ella, recorrido por el prefijo `equipoId`) y que el `explain()` de la
    evidencia sea reproducible. El orden por dorsal se resuelve en memoria sobre
    a lo sumo 23 documentos del equipo (sort acotado por `limit`).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pymongo import AsyncMongoClient
from pymongo.errors import AutoReconnect, ConnectionFailure, NetworkTimeout, ServerSelectionTimeoutError

from app.adapters.base import ejecutar
from app.config.settings import Settings
from app.schemas.equipos import Colores, Equipo, Jugador

ERRORES_DISPONIBILIDAD: tuple[type[BaseException], ...] = (
    ServerSelectionTimeoutError, ConnectionFailure, NetworkTimeout, AutoReconnect)

INDICE_PLANTEL = [("equipoId", 1), ("posicion", 1)]   # idx_jugadores_equipoId_posicion

PROYECCION_EQUIPO = {"_id": 1, "nombre": 1, "confederacion": 1, "rankingFifa": 1, "grupo": 1,
                     "entrenador": 1, "sede": 1, "colores": 1, "cantidadJugadores": 1}
PROYECCION_JUGADOR = {"_id": 0, "dni": 1, "nombre": 1, "apellido": 1, "fechaNacimiento": 1,
                      "posicion": 1, "dorsal": 1, "equipoId": 1}


# --------------------------------------------------------------------------- mapeo puro
def equipo_desde_documento(doc: dict[str, Any]) -> Equipo:
    """Documento de `equipos` → contrato público (`codigo` = `_id`)."""
    colores = doc.get("colores")
    return Equipo(
        codigo=doc["_id"],
        nombre=doc["nombre"],
        confederacion=doc["confederacion"],
        rankingFifa=int(doc["rankingFifa"]),
        grupo=doc["grupo"],
        entrenador=doc.get("entrenador"),
        sede=doc.get("sede"),
        colores=Colores(principal=colores.get("principal"), alternativo=colores.get("alternativo"))
        if isinstance(colores, dict) else None,
        cantidadJugadores=doc.get("cantidadJugadores"),
    )


def jugador_desde_documento(doc: dict[str, Any]) -> Jugador:
    """Documento de `jugadores` → contrato (`equipoCodigo` = `equipoId`, sin `_id`).
    `fechaNacimiento` es un BSON date (datetime en Python): se expone como fecha."""
    nacimiento = doc["fechaNacimiento"]
    if isinstance(nacimiento, datetime):
        nacimiento = nacimiento.date()
    return Jugador(
        dni=doc["dni"],
        nombre=doc["nombre"],
        apellido=doc["apellido"],
        fechaNacimiento=nacimiento,
        posicion=doc["posicion"],
        dorsal=int(doc["dorsal"]),
        equipoCodigo=doc["equipoId"],
    )


def filtro_plantel(codigo: str, posicion: str | None, despues_de_dorsal: int | None) -> dict[str, Any]:
    filtro: dict[str, Any] = {"equipoId": codigo}
    if posicion is not None:
        filtro["posicion"] = posicion
    if despues_de_dorsal is not None:
        filtro["dorsal"] = {"$gt": despues_de_dorsal}
    return filtro


# --------------------------------------------------------------------------- adaptador
class MongoAdapter:
    nombre = "mongodb"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: AsyncMongoClient | None = None

    # ---------------------------------------------------------------- ciclo de vida
    def _cliente(self) -> AsyncMongoClient:
        if self._client is None:
            ms = int(self.settings.dep_timeout_s * 1000)
            self._client = AsyncMongoClient(
                self.settings.mongo_uri.get_secret_value(),
                serverSelectionTimeoutMS=ms, connectTimeoutMS=ms, socketTimeoutMS=ms,
                appname="fixture2030-api",
            )
        return self._client

    async def connect(self) -> None:
        self._cliente()   # no abre conexiones: la primera operación selecciona servidor

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

    def _db(self):  # noqa: ANN202 — AsyncDatabase
        return self._cliente()[self.settings.mongo_db]

    async def _ejecutar(self, operacion: str, awaitable):  # noqa: ANN001, ANN202
        return await ejecutar(self.nombre, operacion, awaitable,
                              timeout_s=self.settings.dep_timeout_s,
                              errores_de_disponibilidad=ERRORES_DISPONIBILIDAD)

    async def ping(self) -> None:
        await self._ejecutar("ping", self._db().command("ping"))

    # ---------------------------------------------------------------- consultas
    async def get_equipo(self, codigo: str) -> Equipo | None:
        doc = await self._ejecutar(
            "get_equipo", self._db()["equipos"].find_one({"_id": codigo}, PROYECCION_EQUIPO))
        return equipo_desde_documento(doc) if doc else None

    async def list_jugadores(self, codigo: str, posicion: str | None,
                             despues_de_dorsal: int | None, limite: int) -> list[Jugador]:
        cursor = (self._db()["jugadores"]
                  .find(filtro_plantel(codigo, posicion, despues_de_dorsal), PROYECCION_JUGADOR)
                  .hint(INDICE_PLANTEL)
                  .sort("dorsal", 1)
                  .limit(limite))
        docs = await self._ejecutar("list_jugadores", cursor.to_list(length=limite))
        return [jugador_desde_documento(d) for d in docs]
