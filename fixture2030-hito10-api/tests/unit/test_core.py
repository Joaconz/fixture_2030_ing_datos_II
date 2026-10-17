"""Pruebas del núcleo: formato de error, 400 en lugar de 422, request-id, CORS/PNA."""
from tests.unit.conftest import FuenteNoTocar


def test_codigo_invalido_da_400_sin_tocar_la_fuente(make_client):
    c = make_client(mongodb=FuenteNoTocar("mongodb"))
    r = c.get("/equipos/argentina")
    assert r.status_code == 400
    body = r.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["requestId"] == r.headers["X-Request-Id"]
    assert body["details"][0]["campo"] == "path.codigo"


def test_request_id_del_cliente_se_respeta(make_client):
    r = make_client().get("/health", headers={"X-Request-Id": "postman-123"})
    assert r.status_code == 200
    assert r.headers["X-Request-Id"] == "postman-123"


def test_request_id_inseguro_se_reemplaza(make_client):
    r = make_client().get("/health", headers={"X-Request-Id": "a b\"<script>"})
    assert r.headers["X-Request-Id"].startswith("req-")


def test_dependencia_caida_da_503_con_formato_unico(make_client):
    from app.core import deps
    from app.core.errors import DependencyUnavailableError

    class SesionesCaidas:
        async def obtener(self, *_):
            raise DependencyUnavailableError("redis")

    c = make_client()
    c.app.dependency_overrides[deps.sesiones_service] = lambda: SesionesCaidas()
    r = c.get("/sesiones/demo-ses-0000001-1")
    assert r.status_code == 503
    body = r.json()
    assert body["code"] == "DEPENDENCY_UNAVAILABLE"
    assert set(body) <= {"code", "message", "requestId", "details"}
    assert "redis" in body["message"] and "6379" not in body["message"]
    assert r.headers.get("Retry-After") == "5"


def test_ruta_inexistente_usa_formato_unico(make_client):
    r = make_client().get("/no-existe")
    assert r.status_code == 404 and r.json()["code"] == "ROUTE_NOT_FOUND"


def test_preflight_cors_con_private_network(make_client):
    r = make_client().options("/equipos/ARG", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Private-Network": "true"})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert r.headers["access-control-allow-private-network"] == "true"


def test_origen_no_permitido_no_recibe_cors(make_client):
    r = make_client().get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_error_inesperado_da_500_seguro_con_request_id(make_client):
    class Rota:
        async def obtener(self, *_):
            raise RuntimeError("password=secreto mongodb://u:p@host")

    from app.core import deps
    c = make_client()
    c.app.dependency_overrides[deps.sesiones_service] = lambda: Rota()
    r = c.get("/sesiones/demo-ses-0000001-1")
    assert r.status_code == 500
    body = r.json()
    assert body["code"] == "INTERNAL_ERROR" and "secreto" not in r.text
    assert body["requestId"] == r.headers["X-Request-Id"] != "-"


# --------------------------------------------------------------------------- Hito 11: clasificación de fallas
def test_motivo_de_distingue_rechazo_timeout_credencial_y_contexto():
    import httpx
    from cassandra import InvalidRequest
    from neo4j.exceptions import AuthError
    from pymongo.errors import ServerSelectionTimeoutError
    from redis.exceptions import AuthenticationError, NoPermissionError
    from redis.exceptions import TimeoutError as RedisTimeout

    from app.adapters.base import motivo_de

    assert motivo_de(ServerSelectionTimeoutError("localhost:27017: [Errno 61] Connection refused")) == "conexion"
    assert motivo_de(ServerSelectionTimeoutError(
        "localhost:27017: [Errno 61] Connect call failed ('127.0.0.1', 27017), Timeout: 1.6s")) == "conexion"
    assert motivo_de(ServerSelectionTimeoutError("localhost:27017: timed out")) == "timeout"
    assert motivo_de(httpx.ReadTimeout("x")) == "timeout"
    assert motivo_de(RedisTimeout("Timeout reading from socket")) == "timeout"
    assert motivo_de(AuthError("The client is unauthorized due to authentication failure.")) == "autenticacion"
    assert motivo_de(AuthenticationError("invalid password")) == "autenticacion"
    assert motivo_de(NoPermissionError("NOPERM")) == "autorizacion"
    assert motivo_de(InvalidRequest("Keyspace 'fixture2030_x' does not exist")) == "contexto"
    assert motivo_de(httpx.ConnectError("[Errno 61] Connection refused")) == "conexion"


async def test_ejecutar_traduce_timeout_a_504_y_rechazo_a_503():
    import asyncio

    import pytest
    from redis.exceptions import ConnectionError as RedisConnectionError

    from app.adapters.base import ejecutar
    from app.core.errors import DependencyUnavailableError

    with pytest.raises(DependencyUnavailableError) as e:
        await ejecutar("redis", "op", asyncio.sleep(1), timeout_s=0.01)
    assert (e.value.status_code, e.value.code, e.value.motivo) == (504, "DEPENDENCY_TIMEOUT", "timeout")

    async def _rechazo():
        raise RedisConnectionError("Error 61 connecting to 127.0.0.1:6390. Connection refused.")
    with pytest.raises(DependencyUnavailableError) as e:
        await ejecutar("redis", "op", _rechazo(), timeout_s=1,
                       errores_de_disponibilidad=(RedisConnectionError,))
    assert (e.value.status_code, e.value.code, e.value.motivo) == (503, "DEPENDENCY_UNAVAILABLE", "conexion")
