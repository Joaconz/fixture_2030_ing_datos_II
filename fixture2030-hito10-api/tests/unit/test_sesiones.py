"""CU10–CU11 (Redis) con FakeRedis."""
from __future__ import annotations

import asyncio

from app.adapters import redis as ad
from tests.unit.conftest import FuenteCaida, FuenteNoTocar
from tests.unit.fakes_cassandra_redis import FakeRedis

SID = "demo-ses-0000001-1"


def test_sesion_ok_sin_solicitudes(make_client):
    fake = FakeRedis()
    fake.crear_sesion(SID, ttl=1234)
    r = make_client(redis=fake).get(f"/sesiones/{SID}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "solicitudes" not in body
    assert body["sesionId"] == SID and body["usuarioId"] == "USR-DEMO1"
    assert body["estado"] == "ACTIVA" and body["ttlSegundos"] == 1234
    assert body["creadaEn"].startswith("2030-06-29T16:00:00")
    assert fake.ttls[f"f30:ses:{SID}"] == 1234     # no renueva


def test_sesion_inexistente_404(make_client):
    r = make_client(redis=FakeRedis()).get("/sesiones/no-existe")
    assert r.status_code == 404 and r.json()["code"] == "SESSION_NOT_FOUND"


def test_hash_parcial_404(make_client):
    fake = FakeRedis()
    fake.hashes["f30:ses:demo-E"] = {"ultima_actividad": "1908979260"}   # sesiones.redis §3.4 bis
    fake.ttls["f30:ses:demo-E"] = -1
    r = make_client(redis=fake).get("/sesiones/demo-E")
    assert r.status_code == 404 and r.json()["code"] == "SESSION_NOT_FOUND"


def test_sesion_bloqueada_403(make_client):
    fake = FakeRedis()
    fake.crear_sesion(SID, estado="BLOQUEADA")
    r = make_client(redis=fake).get(f"/sesiones/{SID}")
    assert r.status_code == 403 and r.json()["code"] == "SESSION_BLOCKED"


def test_cerrar_204_y_repetir_404(make_client):
    fake = FakeRedis()
    fake.crear_sesion(SID)
    fake.crear_sesion("demo-ses-0000001-2")
    c = make_client(redis=fake)
    r = c.delete(f"/sesiones/{SID}")
    assert r.status_code == 204 and r.content == b""
    assert f"f30:ses:{SID}" not in fake.hashes
    assert fake.sets["f30:usr:USR-DEMO1:sesiones"] == {"demo-ses-0000001-2"}
    assert c.get(f"/sesiones/{SID}").status_code == 404
    r2 = c.delete(f"/sesiones/{SID}")
    assert r2.status_code == 404 and r2.json()["code"] == "SESSION_NOT_FOUND"


def test_redis_caido_503(make_client):
    c = make_client(redis=FuenteCaida("redis"))
    for r in (c.get(f"/sesiones/{SID}"), c.delete(f"/sesiones/{SID}")):
        assert r.status_code == 503 and r.json()["code"] == "DEPENDENCY_UNAVAILABLE"


def test_id_invalido_400_sin_tocar_redis(make_client):
    r = make_client(redis=FuenteNoTocar("redis")).get("/sesiones/a b")
    assert r.status_code == 400


# --------------------------------------------------------------------------- mapeos del adaptador
def test_claves_del_hito7():
    assert ad.clave_sesion("x") == "f30:ses:x"
    assert ad.clave_indice_usuario("USR-1") == "f30:usr:USR-1:sesiones"
    assert ad.clave_cache_partido("PAR-A-1") == "f30:cache:partido:PAR-A-1"


def test_a_sesion_cruda():
    assert ad.a_sesion_cruda({}, -2) is None
    assert ad.a_sesion_cruda({"usuario_id": "U"}, -2) is None    # venció entre HGETALL y TTL
    assert ad.a_sesion_cruda({"usuario_id": "U"}, 30).ttl_s == 30


def test_redis_caido_real_da_503():
    """El adaptador real contra un puerto cerrado: 503, nunca None ni excepción cruda."""
    from app.config.settings import Settings
    from app.core.errors import DependencyUnavailableError

    async def _probar():
        a = ad.RedisAdapter(Settings(redis_url="redis://127.0.0.1:1/0", dep_timeout_s=0.5))
        await a.connect()
        try:
            await a.get_sesion(SID)
        except DependencyUnavailableError as exc:
            return exc
        finally:
            await a.close()
    assert isinstance(asyncio.run(_probar()), DependencyUnavailableError)
