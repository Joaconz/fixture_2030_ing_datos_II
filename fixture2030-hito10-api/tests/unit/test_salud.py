"""CU13 — salud de las cinco dependencias."""
from __future__ import annotations

import asyncio

import pytest

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
    assert [d["nombre"] for d in body["dependencias"]] == NOMBRES + ["iris"]
    en_arq = [d for d in body["dependencias"] if d["enArquitectura"]]
    assert all(d["estado"] == "UP" and d["latenciaMs"] >= 0 for d in en_arq)
    iris = body["dependencias"][-1]
    assert iris["estado"] == "NOT_CONFIGURED" and iris["enArquitectura"] is False


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


def test_excepcion_inesperada_no_filtra_detalle(make_client):
    r = make_client(**_todas_ok(neo4j=PingRaro())).get("/health/dependencias")
    assert r.status_code == 503
    assert "secreto" not in r.text and "10.0.0.5" not in r.text and "bolt" not in r.text


class PingMotivo:
    def __init__(self, motivo):
        self.motivo = motivo

    async def ping(self):
        raise DependencyUnavailableError("x", motivo=self.motivo)


@pytest.mark.parametrize("motivo,estado,detalle", [
    ("autenticacion", "DOWN", "credencial rechazada"),
    ("autorizacion", "DOWN", "sin permiso"),
    ("contexto", "DOWN", "contexto inexistente"),
    ("no_configurado", "NOT_CONFIGURED", "sin configurar"),
])
def test_motivo_se_traduce_a_estado_y_detalle(make_client, motivo, estado, detalle):
    r = make_client(**_todas_ok(mongodb=PingMotivo(motivo))).get("/health/dependencias")
    assert r.status_code == 503
    d = {d["nombre"]: d for d in r.json()["dependencias"]}["mongodb"]
    assert (d["estado"], d["detalle"]) == (estado, detalle)


def test_excepcion_no_clasificada_es_unknown(make_client):
    d = {d["nombre"]: d for d in make_client(**_todas_ok(neo4j=PingRaro())).get("/health/dependencias")
         .json()["dependencias"]}["neo4j"]
    assert d["estado"] == "UNKNOWN"


def test_resultado_se_reutiliza_dentro_del_ttl(make_client):
    class Contador:
        n = 0

        async def ping(self):
            Contador.n += 1

    c = make_client(**_todas_ok(redis=Contador()))
    primero = c.get("/health/dependencias").json()
    segundo = c.get("/health/dependencias").json()
    c.get("/health/ready")
    assert Contador.n == 1
    assert primero["desdeCache"] is False and segundo["desdeCache"] is True
    assert primero["verificadoEn"] == segundo["verificadoEn"]


def test_ready_lista_degradada_y_no_lista(make_client):
    r = make_client(**_todas_ok()).get("/health/ready")
    assert r.status_code == 200 and r.json()["estado"] == "LISTA"
    r = make_client(**_todas_ok(redis=PingCaido())).get("/health/ready")
    assert r.status_code == 200 and r.json()["estado"] == "LISTA_DEGRADADA"
    assert r.json()["noDisponibles"] == ["redis"]
    r = make_client(**_todas_ok(mongodb=PingCaido())).get("/health/ready")
    assert r.status_code == 503 and r.json()["estado"] == "NO_LISTA"
    assert r.json()["esenciales"] == ["mongodb", "neo4j"]


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
