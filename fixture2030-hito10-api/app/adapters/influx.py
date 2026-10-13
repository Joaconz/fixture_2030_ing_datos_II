"""Adaptador InfluxDB 3 Core (Hito 8) — HTTP `/api/v3/query_sql` con httpx.

Consultas (CU12) sobre la tabla `estadisticas_equipo` de la base `fixture2030_vivo`
(tags partido_id, equipo_id, condicion, fase, sede_id; precisión de segundos).

SQL PARAMETRIZADO (RNF3 / §5.8): el texto SQL es fijo y los valores que llegan
del cliente viajan aparte, en el objeto `params` del cuerpo JSON:

    {"db": "...", "q": "... WHERE partido_id = $partido AND time >= $desde ...",
     "format": "json", "params": {"partido": "PAR-A-1", "desde": "2030-06-09T13:00:00Z", ...}}

InfluxDB 3 admite parámetros (`$nombre`) en los predicados del WHERE; los
timestamps se pasan como texto RFC 3339 (`time >= $desde`). Dos piezas NO son
parámetros, porque la documentación de InfluxDB 3 sólo garantiza el WHERE:
  - `LIMIT n`: el entero se interpola, pero sólo después de validarlo como `int`
    entre 1 y 2001 (el servicio pide `limit + 1`, y la ruta ya acota `limit` a 1..2000);
  - el intervalo de `date_bin(...)`: sale de un diccionario cerrado (`_INTERVALOS`)
    indexado por la agregación ya validada por el contrato; nunca es texto del cliente.

Respuestas de InfluxDB:
  - 200 con `[]` (o cuerpo vacío) = la tabla existe pero no hay filas en la ventana
    → lista vacía (el servicio responde 200 con `puntos: []`);
  - 401/403 (token inválido o revocado) → 503: una credencial rechazada es una
    falla de la dependencia, no del cliente; el mensaje público es el genérico;
  - cualquier otro estado (404 base inexistente, 400/500 "table not found", 5xx)
    → 503. Nunca se devuelve una lista vacía para ocultar una falla.
El token sale de `settings.influx_token_value()` (variable de entorno o archivo
local fuera del repo) y viaja sólo en la cabecera `Authorization`: nunca se loguea.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.adapters.base import ejecutar
from app.config.settings import Settings
from app.core.errors import DependencyUnavailableError
from app.schemas.estadisticas import Agregacion, PuntoEstadistica

log = logging.getLogger("fixture2030.adaptador")
UTC = timezone.utc

ERRORES_DISPONIBILIDAD: tuple[type[BaseException], ...] = (
    httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout, httpx.WriteTimeout,
    httpx.PoolTimeout, httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError,
)

LIMITE_MAXIMO = 2001  # 2000 del contrato + 1 para calcular `truncado`

# Diccionario CERRADO: la agregación ya fue validada como Literal por el contrato.
_INTERVALOS: dict[str, str] = {"1m": "INTERVAL '1 minute'", "5m": "INTERVAL '5 minutes'"}

_SQL_RAW = """SELECT time, equipo_id, condicion, posesion_pct, pases_acum, tiros_acum,
       goles_acum, minuto_juego
FROM estadisticas_equipo
WHERE partido_id = $partido AND time >= $desde AND time < $hasta{filtro_equipo}
ORDER BY time, equipo_id
LIMIT {limite}"""

_SQL_AGREGADO = """SELECT date_bin({intervalo}, time) AS tramo, equipo_id, condicion,
       last_value(posesion_pct ORDER BY time) AS posesion_pct,
       max(pases_acum)   AS pases_acum,
       max(tiros_acum)   AS tiros_acum,
       max(goles_acum)   AS goles_acum,
       max(minuto_juego) AS minuto_juego
FROM estadisticas_equipo
WHERE partido_id = $partido AND time >= $desde AND time < $hasta{filtro_equipo}
GROUP BY tramo, equipo_id, condicion
ORDER BY tramo, equipo_id
LIMIT {limite}"""

_FILTRO_EQUIPO = " AND equipo_id = $equipo"


def construir_consulta(partido_id: str, desde: datetime, hasta: datetime, agregacion: Agregacion,
                       equipo: str | None, limite: int) -> tuple[str, dict[str, Any]]:
    """Devuelve (sql, params). Pública para poder probarla sin red."""
    if not isinstance(limite, int) or isinstance(limite, bool) or not 1 <= limite <= LIMITE_MAXIMO:
        raise ValueError("limite fuera de rango")
    filtro = _FILTRO_EQUIPO if equipo is not None else ""
    if agregacion == "raw":
        sql = _SQL_RAW.format(filtro_equipo=filtro, limite=int(limite))
    else:
        sql = _SQL_AGREGADO.format(intervalo=_INTERVALOS[agregacion], filtro_equipo=filtro,
                                   limite=int(limite))
    params: dict[str, Any] = {"partido": partido_id, "desde": _rfc3339(desde), "hasta": _rfc3339(hasta)}
    if equipo is not None:
        params["equipo"] = equipo
    return sql, params


def _rfc3339(dt: datetime) -> str:
    dt = dt.astimezone(UTC)
    if dt.microsecond:
        return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _a_utc(valor: Any) -> datetime:
    """InfluxDB devuelve el tiempo como texto ISO en UTC sin la 'Z' (o con ella)."""
    texto = str(valor).strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(texto)
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _entero(valor: Any) -> int | None:
    return None if valor is None else int(valor)


def _decimal(valor: Any) -> float | None:
    return None if valor is None else float(valor)


def fila_a_punto(fila: dict[str, Any]) -> PuntoEstadistica:
    # Una columna NULL no aparece en la fila JSON de InfluxDB 3: por eso .get().
    return PuntoEstadistica(
        time=_a_utc(fila["tramo"] if "tramo" in fila else fila["time"]),
        equipoCodigo=str(fila["equipo_id"]),
        condicion=fila.get("condicion"),
        posesionPct=_decimal(fila.get("posesion_pct")),
        pasesAcum=_entero(fila.get("pases_acum")),
        tirosAcum=_entero(fila.get("tiros_acum")),
        golesAcum=_entero(fila.get("goles_acum")),
        minutoJuego=_entero(fila.get("minuto_juego")),
    )


class InfluxAdapter:
    nombre = "influxdb"

    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self._transport = transport  # sólo para pruebas (httpx.MockTransport)
        self._cliente: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------ ciclo
    async def connect(self) -> None:
        """Crea el cliente HTTP; no abre conexiones (la API arranca aunque Influx esté caído)."""
        if self._cliente is None:
            self._cliente = httpx.AsyncClient(base_url=self.settings.influx_url,
                                              timeout=httpx.Timeout(self.settings.dep_timeout_s),
                                              transport=self._transport)

    async def close(self) -> None:
        if self._cliente is not None:
            await self._cliente.aclose()
            self._cliente = None

    def _http(self) -> httpx.AsyncClient:
        if self._cliente is None:
            # connect() no se llamó (p. ej. un script): se crea igual, sin red.
            self._cliente = httpx.AsyncClient(base_url=self.settings.influx_url,
                                              timeout=httpx.Timeout(self.settings.dep_timeout_s),
                                              transport=self._transport)
        return self._cliente

    async def ping(self) -> None:
        """GET /health (no requiere token: el servidor corre con --disable-authz=health,ping)."""
        async def _ping() -> None:
            r = await self._http().get("/health")
            if r.status_code != 200:
                log.warning("influxdb /health respondió distinto de 200", extra={
                    "evento": "dependencia", "dependencia": self.nombre, "operacion": "ping",
                    "status": r.status_code})
                raise DependencyUnavailableError(self.nombre)

        await ejecutar(self.nombre, "ping", _ping(), timeout_s=self.settings.dep_timeout_s,
                       errores_de_disponibilidad=ERRORES_DISPONIBILIDAD)

    # -------------------------------------------------------------- consultas
    async def consultar_estadisticas(self, partido_id: str, desde: datetime, hasta: datetime,
                                     agregacion: Agregacion, equipo: str | None,
                                     limite: int) -> list[PuntoEstadistica]:
        sql, params = construir_consulta(partido_id, desde, hasta, agregacion, equipo, limite)
        filas = await ejecutar(self.nombre, f"query_sql:{agregacion}", self._query(sql, params),
                               timeout_s=self.settings.dep_timeout_s,
                               errores_de_disponibilidad=ERRORES_DISPONIBILIDAD)
        return [fila_a_punto(f) for f in filas]

    async def _query(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        token = self.settings.influx_token_value()
        if not token:
            log.error("token de InfluxDB no configurado: definir INFLUX_TOKEN o crear el archivo "
                      "de INFLUX_TOKEN_FILE (fixture2030-influxdb/scripts/autorizacion_local.sh)",
                      extra={"evento": "dependencia", "dependencia": self.nombre,
                             "operacion": "query_sql", "resultado": "sin_token"})
            raise DependencyUnavailableError(self.nombre)

        cuerpo = {"db": self.settings.influx_db, "q": sql, "format": "json", "params": params}
        r = await self._http().post("/api/v3/query_sql", json=cuerpo,
                                    headers={"Authorization": f"Bearer {token}"})
        if r.status_code == 200:
            texto = r.text.strip()
            if not texto:
                return []
            try:
                datos = json.loads(texto)
            except ValueError as exc:
                self._log_rechazo(r.status_code, "respuesta no es JSON")
                raise DependencyUnavailableError(self.nombre) from exc
            if not isinstance(datos, list):
                self._log_rechazo(r.status_code, "respuesta no es una lista de filas")
                raise DependencyUnavailableError(self.nombre)
            return datos
        if r.status_code in (401, 403):
            self._log_rechazo(r.status_code, "token rechazado por InfluxDB")
        else:
            self._log_rechazo(r.status_code, "InfluxDB rechazó la consulta")
        raise DependencyUnavailableError(self.nombre)

    def _log_rechazo(self, status: int, motivo: str) -> None:
        # Sin cuerpo de la respuesta, sin SQL, sin parámetros y sin token (RNF7 / RNF10).
        log.warning(motivo, extra={"evento": "dependencia", "dependencia": self.nombre,
                                   "operacion": "query_sql", "status": status})
