"""CU13 — salud de las cinco dependencias."""
from __future__ import annotations

import asyncio

from app.core.errors import DependencyUnavailableError

NOMBRES = ["mongodb", "neo4j", "cassandra", "redis", "influxdb"]


class PingOk:
    async def ping(self):
        await asyncio.sleep(0)


class PingCaido:
    def __init__(self, timeout=False):
        self.timeout = timeout

    async def ping(self):
        raise DependencyUnavailableError("redis", timeout=self.timeout)


class PingRaro:
    async def ping(self):
        raise RuntimeError("bolt://neo4j:secreto@10.0.0.5:7687 rechazó")


class PingNoImplementado:
    async def ping(self):
        raise NotImplementedError


def _todas_ok(**reemplazos):
    return {n: reemplazos.get(n, PingOk()) for n in NOMBRES}


def test_todas_up_200(make_client):
    r = make_client(**_todas_ok()).get("/health/dependencias")
    assert r.status_code == 200
    body = r.json()
    assert body["estado"] == "OK"
    assert [d["nombre"] for d in body["dependencias"]] == NOMBRES
    assert all(d["estado"] == "UP" and d["latenciaMs"] >= 0 for d in body["dependencias"])


def test_una_down_503_mismo_cuerpo(make_client):
    r = make_client(**_todas_ok(redis=PingCaido())).get("/health/dependencias")
    assert r.status_code == 503
    body = r.json()
    assert body["estado"] == "DEGRADADO" and "code" not in body
    por_nombre = {d["nombre"]: d for d in body["dependencias"]}
    assert por_nombre["redis"]["estado"] == "DOWN" and por_nombre["redis"]["detalle"] == "no responde"
    assert por_nombre["mongodb"]["estado"] == "UP"


def test_timeout_se_informa_como_timeout(make_client):
    body = make_client(**_todas_ok(influxdb=PingCaido(timeout=True))).get("/health/dependencias").json()
    assert {d["nombre"]: d for d in body["dependencias"]}["influxdb"]["detalle"] == "timeout"


def test_excepcion_inesperada_es_down_sin_filtrar_detalle(make_client):
    r = make_client(**_todas_ok(neo4j=PingRaro())).get("/health/dependencias")
    assert r.status_code == 503
    assert "secreto" not in r.text and "10.0.0.5" not in r.text and "bolt" not in r.text


def test_no_implementado_es_down(make_client):
    body = make_client(**_todas_ok(cassandra=PingNoImplementado())).get("/health/dependencias").json()
    d = {d["nombre"]: d for d in body["dependencias"]}["cassandra"]
    assert d["estado"] == "DOWN" and d["detalle"] == "no implementado"


def test_los_pings_corren_en_paralelo(make_client):
    import time

    class PingLento:
        async def ping(self):
            await asyncio.sleep(0.2)

    t0 = time.perf_counter()
    r = make_client(**{n: PingLento() for n in NOMBRES}).get("/health/dependencias")
    assert r.status_code == 200
    assert time.perf_counter() - t0 < 0.8
