"""CU1–CU3 (equipos, plantel, partidos del equipo) y mapeo del adaptador Mongo."""
from datetime import date, datetime

import pytest
from bson import ObjectId

from app.adapters.mongo import (MongoAdapter, equipo_desde_documento, filtro_plantel,
                                jugador_desde_documento)
from app.config.settings import Settings
from app.core.errors import DependencyUnavailableError
from app.services import cursor_entero
from tests.unit.conftest import FuenteCaida, FuenteNoTocar
from tests.unit.fakes_mongo_neo4j import FakeMongo, FakeNeo4j



# --------------------------------------------------------------------------- CU1
def test_ficha_de_equipo(make_client):
    r = make_client(mongodb=FakeMongo()).get("/equipos/ARG")
    assert r.status_code == 200
    body = r.json()
    assert body["codigo"] == "ARG" and body["rankingFifa"] == 1
    assert body["colores"] == {"principal": "Celeste", "alternativo": "Azul"}
    assert "_id" not in body


def test_equipo_inexistente_da_404(make_client):
    r = make_client(mongodb=FakeMongo()).get("/equipos/XXX")
    assert r.status_code == 404 and r.json()["code"] == "TEAM_NOT_FOUND"


@pytest.mark.parametrize("ruta", ["/equipos/arg", "/equipos/ARGE", "/equipos/AR1/jugadores",
                                  "/equipos/ARG/jugadores?limit=0", "/equipos/ARG/jugadores?limit=51",
                                  "/equipos/ARG/jugadores?posicion=Volante",
                                  "/equipos/ARG/jugadores?cursor=no%20valido",
                                  "/equipos/ARG/partidos?limit=21", "/equipos/12/partidos"])
def test_entrada_invalida_da_400_sin_tocar_fuentes(make_client, ruta):
    r = make_client(mongodb=FuenteNoTocar("mongodb"), neo4j=FuenteNoTocar("neo4j")).get(ruta)
    assert r.status_code == 400 and r.json()["code"] == "VALIDATION_ERROR"


def test_mongo_caido_da_503(make_client):
    r = make_client(mongodb=FuenteCaida("mongodb")).get("/equipos/ARG")
    assert r.status_code == 503 and r.json()["code"] == "DEPENDENCY_UNAVAILABLE"
    assert r.headers["Retry-After"] == "5"


def test_mongo_timeout_da_504_distinto_de_503(make_client):
    r = make_client(mongodb=FuenteCaida("mongodb", timeout=True)).get("/equipos/ARG")
    assert r.status_code == 504 and r.json()["code"] == "DEPENDENCY_TIMEOUT"
    assert r.headers["Retry-After"] == "5"


# --------------------------------------------------------------------------- CU2
def test_paginacion_completa_sin_repetidos(make_client):
    mongo = FakeMongo()
    c = make_client(mongodb=mongo)
    dorsales, cursor, paginas = [], None, 0
    while True:
        url = "/equipos/ARG/jugadores?limit=5" + (f"&cursor={cursor}" if cursor else "")
        body = c.get(url).json()
        dorsales += [j["dorsal"] for j in body["items"]]
        paginas += 1
        cursor = body["nextCursor"]
        if cursor is None:
            break
    assert dorsales == list(range(1, 24)) and paginas == 5
    # se pide limit+1 al adaptador para saber si hay otra página
    pedidos = [ll for ll in mongo.llamadas if ll[0] == "list_jugadores"]
    assert len(pedidos) == 5 and all(ll[4] == 6 for ll in pedidos)


def test_pagina_exacta_no_deja_cursor_colgado(make_client):
    body = make_client(mongodb=FakeMongo()).get("/equipos/ARG/jugadores?limit=23").json()
    assert len(body["items"]) == 23 and body["nextCursor"] is None


def test_filtro_por_posicion(make_client):
    body = make_client(mongodb=FakeMongo()).get("/equipos/ARG/jugadores?posicion=Defensor").json()
    assert [j["dorsal"] for j in body["items"]] == [2, 3, 4, 5, 6]
    assert all(j["posicion"] == "Defensor" and j["equipoCodigo"] == "ARG" for j in body["items"])


def test_plantel_de_equipo_inexistente_es_404_no_lista_vacia(make_client):
    mongo = FakeMongo()
    r = make_client(mongodb=mongo).get("/equipos/XXX/jugadores")
    assert r.status_code == 404 and r.json()["code"] == "TEAM_NOT_FOUND"
    # la existencia del equipo se consulta sólo porque la página salió vacía
    assert mongo.llamadas == [("list_jugadores", "XXX", None, None, 21), ("get_equipo", "XXX")]


def test_pagina_con_jugadores_no_consulta_el_equipo(make_client):
    mongo = FakeMongo()
    r = make_client(mongodb=mongo).get("/equipos/ARG/jugadores", params={"limit": 5})
    assert r.status_code == 200 and len(r.json()["items"]) == 5
    assert [c[0] for c in mongo.llamadas] == ["list_jugadores"]


def test_equipo_existente_sin_jugadores_da_200_vacio(make_client):
    body = make_client(mongodb=FakeMongo()).get("/equipos/FIJ/jugadores").json()
    assert body["items"] == [] and body["nextCursor"] is None


@pytest.mark.parametrize("cursor", [
    "AAAA",                                   # base64 válido, no es JSON
    cursor_entero.codificar("evt", 3),        # cursor de otro listado (eventos)
    cursor_entero.codificar("jug", -1),       # valor fuera de rango
    "eyJ0IjoianVnIiwidiI6InRyZXMifQ",         # {"t":"jug","v":"tres"}
])
def test_cursor_invalido_da_400_sin_tocar_mongo(make_client, cursor):
    r = make_client(mongodb=FuenteNoTocar("mongodb")).get(f"/equipos/ARG/jugadores?cursor={cursor}")
    assert r.status_code == 400 and r.json()["code"] == "INVALID_CURSOR"


def test_cursor_ida_y_vuelta():
    assert cursor_entero.decodificar("jug", cursor_entero.codificar("jug", 17)) == 17
    assert cursor_entero.decodificar("jug", None) is None


# --------------------------------------------------------------------------- CU3
def test_partidos_de_equipo(make_client):
    body = make_client(neo4j=FakeNeo4j()).get("/equipos/ARG/partidos").json()
    assert [p["partidoId"] for p in body["items"]] == ["PAR-A-1", "PAR-D16-01", "PAR-DEMO-API"]
    a1, d16 = body["items"][0], body["items"][1]
    assert a1["condicion"] == "LOCAL" and a1["rivalCodigo"] == "MEX" and a1["golesLocal"] == 2
    assert d16["condicion"] == "VISITANTE" and d16["rivalCodigo"] == "BRA" and d16["golesLocal"] is None


def test_partidos_respeta_limit(make_client):
    body = make_client(neo4j=FakeNeo4j()).get("/equipos/ARG/partidos?limit=1").json()
    assert len(body["items"]) == 1 and body["limit"] == 1


def test_partidos_de_equipo_sin_partidos_da_200_vacio(make_client):
    body = make_client(neo4j=FakeNeo4j()).get("/equipos/NZL/partidos").json()
    assert body["items"] == []


def test_partidos_de_equipo_inexistente_da_404(make_client):
    r = make_client(neo4j=FakeNeo4j()).get("/equipos/XXX/partidos")
    assert r.status_code == 404 and r.json()["code"] == "TEAM_NOT_FOUND"


def test_partidos_neo4j_caido_da_503(make_client):
    r = make_client(neo4j=FuenteCaida("neo4j")).get("/equipos/ARG/partidos")
    assert r.status_code == 503


# --------------------------------------------------------------------------- adaptador Mongo (sin Docker)
def test_mapeo_documento_equipo():
    eq = equipo_desde_documento({"_id": "ARG", "nombre": "Argentina", "confederacion": "CONMEBOL",
                                 "rankingFifa": 1, "grupo": "A", "colores": {"principal": "Celeste"},
                                 "cantidadJugadores": 23})
    assert eq.codigo == "ARG" and eq.colores.principal == "Celeste" and eq.colores.alternativo is None
    assert eq.entrenador is None


def test_mapeo_documento_jugador_sin_object_id():
    j = jugador_desde_documento({"_id": ObjectId(), "dni": "30000101", "nombre": "Lionel",
                                 "apellido": "Messi", "fechaNacimiento": datetime(1987, 6, 24),
                                 "posicion": "Delantero", "dorsal": 10, "equipoId": "ARG"})
    assert j.fechaNacimiento == date(1987, 6, 24) and j.equipoCodigo == "ARG"
    assert "_id" not in j.model_dump()


def test_filtro_plantel():
    assert filtro_plantel("ARG", None, None) == {"equipoId": "ARG"}
    assert filtro_plantel("ARG", "Arquero", 1) == {"equipoId": "ARG", "posicion": "Arquero",
                                                   "dorsal": {"$gt": 1}}


async def test_adaptador_mongo_arranca_sin_mongo_y_responde_503():
    a = MongoAdapter(Settings(mongo_uri="mongodb://127.0.0.1:1", dep_timeout_s=0.3))
    await a.connect()                      # no bloquea ni falla con la fuente caída
    with pytest.raises(DependencyUnavailableError):
        await a.get_equipo("ARG")
    await a.close()
