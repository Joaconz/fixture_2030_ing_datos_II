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
            raise DependencyUnavailableError("redis", timeout=True)

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
