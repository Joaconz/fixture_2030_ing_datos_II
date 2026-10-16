"""Adaptador InfluxDB con httpx.MockTransport: SQL parametrizado, auth y mapeo de errores."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import pytest

from app.adapters.influx import InfluxAdapter, construir_consulta
from app.config.settings import Settings
from app.core.errors import DependencyUnavailableError

UTC = timezone.utc
TOKEN = "apiv3_token-de-prueba-no-real"
DESDE = datetime(2030, 6, 9, 13, 0, tzinfo=UTC)
HASTA = datetime(2030, 6, 9, 13, 30, tzinfo=UTC)
PARTIDO_RARO = "PAR-A-1' OR '1'='1"   # nunca llega por la ruta (patrón), pero prueba el aislamiento


def _settings(token: str | None = TOKEN, tmp_path=None) -> Settings:
    kw = {"influx_url": "http://influx.test:8181", "influx_db": "fixture2030_vivo", "dep_timeout_s": 1.0}
    if token is not None:
        kw["influx_token"] = token
    if tmp_path is not None:
        kw["influx_token_file"] = tmp_path / "no-existe.json"
    return Settings(_env_file=None, **kw)


def _adaptador(handler, token: str | None = TOKEN, tmp_path=None) -> InfluxAdapter:
    return InfluxAdapter(_settings(token, tmp_path), transport=httpx.MockTransport(handler))


class Grabador:
    def __init__(self, respuesta: httpx.Response | None = None) -> None:
        self.requests: list[httpx.Request] = []
        self.respuesta = respuesta or httpx.Response(200, json=[])

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.respuesta

    @property
    def cuerpo(self) -> dict:
        return json.loads(self.requests[-1].content)


async def test_raw_va_parametrizado_con_auth():
    g = Grabador()
    a = _adaptador(g)
    await a.connect()
    await a.consultar_estadisticas(PARTIDO_RARO, DESDE, HASTA, "raw", "ARG", 11)
    req = g.requests[0]
    assert req.method == "POST" and req.url.path == "/api/v3/query_sql"
    assert req.headers["Authorization"] == f"Bearer {TOKEN}"
    c = g.cuerpo
    assert c["db"] == "fixture2030_vivo" and c["format"] == "json"
    assert c["params"] == {"partido": PARTIDO_RARO, "desde": "2030-06-09T13:00:00Z",
                           "hasta": "2030-06-09T13:30:00Z", "equipo": "ARG"}
    sql = c["q"]
    for valor in (PARTIDO_RARO, "PAR-A-1", "ARG", "2030-06-09"):
        assert valor not in sql
    assert "partido_id = $partido" in sql and "time >= $desde" in sql and "time < $hasta" in sql
    assert "equipo_id = $equipo" in sql and sql.rstrip().endswith("LIMIT 11")
    assert TOKEN not in req.content.decode()
    await a.close()


@pytest.mark.parametrize("agregacion,intervalo", [("1m", "INTERVAL '1 minute'"), ("5m", "INTERVAL '5 minutes'")])
def test_agregado_usa_date_bin_last_value_y_max(agregacion, intervalo):
    sql, params = construir_consulta("PAR-A-1", DESDE, HASTA, agregacion, None, 501)
    assert f"date_bin({intervalo}, time)" in sql
    assert "last_value(posesion_pct ORDER BY time)" in sql
    assert "max(pases_acum)" in sql and "max(goles_acum)" in sql and "sum(" not in sql
    assert "GROUP BY tramo, equipo_id, condicion" in sql
    assert "$equipo" not in sql and "equipo" not in params


@pytest.mark.parametrize("limite", [0, 2002, -1, True, "10; DROP"])
def test_limite_invalido_no_se_interpola(limite):
    with pytest.raises(ValueError):
        construir_consulta("PAR-A-1", DESDE, HASTA, "raw", None, limite)


async def test_mapeo_de_filas_y_tiempo_utc():
    filas = [
        {"time": "2030-06-09T13:00:05", "equipo_id": "ARG", "condicion": "LOCAL",
         "posesion_pct": 55.5, "pases_acum": 12, "tiros_acum": 1, "goles_acum": 0, "minuto_juego": 0},
        {"time": "2030-06-09T13:00:05", "equipo_id": "SRB", "condicion": "VISITANTE",
         "posesion_pct": 44.5, "pases_acum": 9, "tiros_acum": 0, "minuto_juego": 0},  # goles NULL: ausente
    ]
    a = _adaptador(Grabador(httpx.Response(200, json=filas)))
    puntos = await a.consultar_estadisticas("PAR-A-1", DESDE, HASTA, "raw", None, 10)
    assert puntos[0].time == datetime(2030, 6, 9, 13, 0, 5, tzinfo=UTC)
    assert puntos[0].time.tzinfo is not None
    assert puntos[0].equipoCodigo == "ARG" and puntos[0].posesionPct == 55.5 and puntos[0].pasesAcum == 12
    assert puntos[1].golesAcum is None and puntos[1].condicion == "VISITANTE"


async def test_mapeo_agregado_lee_tramo():
    filas = [{"tramo": "2030-06-09T13:05:00", "equipo_id": "ARG", "condicion": "LOCAL",
              "posesion_pct": 52.0, "pases_acum": 80, "tiros_acum": 2, "goles_acum": 1, "minuto_juego": 9}]
    a = _adaptador(Grabador(httpx.Response(200, json=filas)))
    p = (await a.consultar_estadisticas("PAR-A-1", DESDE, HASTA, "1m", None, 10))[0]
    assert p.time == datetime(2030, 6, 9, 13, 5, tzinfo=UTC) and p.minutoJuego == 9


@pytest.mark.parametrize("respuesta", [httpx.Response(200, json=[]), httpx.Response(200, content=b"")])
async def test_sin_filas_lista_vacia(respuesta):
    assert await _adaptador(Grabador(respuesta)).consultar_estadisticas(
        "PAR-A-1", DESDE, HASTA, "raw", None, 10) == []


@pytest.mark.parametrize("status", [400, 401, 403, 404, 500, 503])
async def test_estados_no_200_son_503(status, caplog):
    a = _adaptador(Grabador(httpx.Response(status, text="error: table 'x' not found")))
    with pytest.raises(DependencyUnavailableError) as exc:
        await a.consultar_estadisticas("PAR-A-1", DESDE, HASTA, "raw", None, 10)
    assert exc.value.dependency == "influxdb"
    assert TOKEN not in caplog.text


async def test_json_inesperado_es_503():
    a = _adaptador(Grabador(httpx.Response(200, json={"error": "x"})))
    with pytest.raises(DependencyUnavailableError):
        await a.consultar_estadisticas("PAR-A-1", DESDE, HASTA, "raw", None, 10)


@pytest.mark.parametrize("exc_cls", [httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout,
                                     httpx.RemoteProtocolError])
async def test_errores_de_red_son_503(exc_cls):
    def handler(request):
        raise exc_cls("falla simulada", request=request)
    with pytest.raises(DependencyUnavailableError):
        await _adaptador(handler).consultar_estadisticas("PAR-A-1", DESDE, HASTA, "raw", None, 10)


async def test_sin_token_503_sin_llamar_a_influx(tmp_path, caplog):
    g = Grabador()
    a = _adaptador(g, token=None, tmp_path=tmp_path)
    with pytest.raises(DependencyUnavailableError):
        await a.consultar_estadisticas("PAR-A-1", DESDE, HASTA, "raw", None, 10)
    assert g.requests == []
    assert "token de InfluxDB no configurado" in caplog.text


async def test_ping_health_sin_token():
    g = Grabador(httpx.Response(200, json={"status": "pass"}))
    a = _adaptador(g, token=None)
    await a.ping()
    assert g.requests[0].url.path == "/health" and "Authorization" not in g.requests[0].headers


async def test_ping_caido_es_503():
    def handler(request):
        raise httpx.ConnectError("rechazada", request=request)
    with pytest.raises(DependencyUnavailableError):
        await _adaptador(handler).ping()
    with pytest.raises(DependencyUnavailableError):
        await _adaptador(Grabador(httpx.Response(500))).ping()
