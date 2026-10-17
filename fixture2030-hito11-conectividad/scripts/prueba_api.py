"""Capa "API" — cadena completa cliente HTTP → API → adaptador → producto (RF15, RF18, RF19, §5.5).

Ejecuta las rutas de LECTURA principales de la API del Hito 10 (las escrituras
no se usan para probar conectividad: RNF6). Por cada request registra método y
path, parámetros, dependencia esperada, status, tiempo, X-Request-Id, resumen
del cuerpo (conteos, nunca datos personales), las líneas de log de ese request
id (si se pasa API_LOG) y la clasificación observada:

    exito · vacio_valido · inexistente · ruta_inexistente · validacion ·
    dependencia_no_disponible (503) · dependencia_timeout (504) ·
    error_interno (500) · api_no_alcanzable

    python3 scripts/prueba_api.py [--api-url URL] [--log ARCHIVO] [--producto X ...] [--etiqueta TEXTO]

Biblioteca estándar únicamente. Qué NO demuestra: rendimiento ni concurrencia.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from registro import Registro, cargar_config, redactar, ruta_publica, sello  # noqa: E402

CFG = cargar_config()
PA, PSE, PX = CFG["NEO4J_PARTIDO_DEMO"], CFG["NEO4J_PARTIDO_SIN_EVENTOS"], CFG["NEO4J_PARTIDO_INEXISTENTE"]
VENTANA = f"desde={CFG['INFLUX_DESDE']}&hasta={CFG['INFLUX_HASTA']}"

# (producto, path, dependencia esperada, clasificaciones aceptadas, qué se verifica)
CASOS: list[tuple[str, str, str, set[str], str]] = [
    ("api", "/health", "ninguna (liveness)", {"exito"}, "el proceso de la API responde sin tocar fuentes"),
    ("api", "/health/ready", "mongodb, neo4j (esenciales)", {"exito"}, "readiness: las esenciales están UP"),
    ("api", "/health/dependencias", "las cinco (chequeo profundo, con caché)", {"exito"}, "estado por dependencia"),
    ("mongodb", f"/equipos/{CFG['MONGO_EQUIPO_DEMO']}", "mongodb", {"exito"}, "CU1 ficha de equipo"),
    ("mongodb", f"/equipos/{CFG['MONGO_EQUIPO_DEMO']}/jugadores?limit=5", "mongodb", {"exito"}, "CU2 plantel paginado"),
    ("mongodb", "/equipos/XXX", "mongodb", {"inexistente"}, "equipo inexistente → 404, no 503"),
    ("mongodb", "/equipos/arg", "ninguna (se valida antes)", {"validacion"}, "entrada inválida → 400 sin tocar la fuente"),
    ("neo4j", f"/partidos/{PA}", "neo4j (+ caché redis)", {"exito"}, "CU4 detalle de partido (X-Cache)"),
    ("neo4j", f"/partidos/{PA}/eventos?limit=5", "neo4j", {"exito"}, "CU5 timeline"),
    ("neo4j", f"/partidos/{PSE}/eventos", "neo4j", {"vacio_valido"}, "partido sin eventos → 200 items: []"),
    ("neo4j", f"/partidos/{PX}/eventos", "neo4j", {"inexistente"}, "partido inexistente → 404 MATCH_NOT_FOUND"),
    ("cassandra", f"/partidos/{CFG['CASSANDRA_PARTIDO_DEMO']}/comentarios?limit=5", "cassandra", {"exito"}, "CU7 comentarios por partición"),
    ("cassandra", f"/partidos/{PX}/comentarios?limit=5", "cassandra", {"inexistente"}, "sin config de partición → 404"),
    ("redis", f"/sesiones/{CFG['REDIS_SESION_DEMO']}", "redis", {"exito", "inexistente"},
     "CU10 sesión de demo: 200 si está cargada, 404 si venció (TTL 30 min del Hito 7)"),
    ("redis", "/sesiones/diag-no-existe-h11", "redis", {"inexistente"}, "sesión inexistente → 404, no 503"),
    ("influxdb", f"/partidos/{CFG['INFLUX_PARTIDO_DEMO']}/estadisticas?{VENTANA}&agregacion=1m", "influxdb", {"exito"},
     "CU12 ventana agregada por minuto"),
    ("influxdb", f"/partidos/{CFG['INFLUX_PARTIDO_DEMO']}/estadisticas?desde=2031-01-01T00:00:00Z&hasta=2031-01-01T00:30:00Z",
     "influxdb", {"vacio_valido"}, "ventana sin puntos → 200 puntos: []"),
    ("influxdb", f"/partidos/{CFG['INFLUX_PARTIDO_DEMO']}/estadisticas?desde={CFG['INFLUX_HASTA']}&hasta={CFG['INFLUX_DESDE']}",
     "ninguna (se valida antes)", {"validacion"}, "ventana invertida → 400 INVALID_TIME_WINDOW"),
    ("iris", f"/partidos/{PA}/detalle", "iris (no integrado)", {"ruta_inexistente"},
     "la ruta de IRIS de la Clase 12 no existe en esta API: IRIS fuera de la arquitectura"),
]

CLASIF_INTERP = {
    "exito": "la cadena cliente–API–adaptador–producto funciona para este caso de uso",
    "vacio_valido": "la fuente respondió y no hay datos: ausencia válida (200), no timeout",
    "inexistente": "la fuente respondió: el recurso no existe (404), la dependencia está disponible",
    "ruta_inexistente": "la API no expone esa ruta (404 ROUTE_NOT_FOUND)",
    "validacion": "la API rechazó la entrada (400) antes de consultar la fuente",
    "dependencia_no_disponible": "la API está arriba pero no pudo usar la fuente (503): ver motivo en el log",
    "dependencia_timeout": "la fuente no respondió dentro de DEP_TIMEOUT_S (504)",
    "salud_degradada": "el chequeo de salud informa al menos una fuente que no está UP (503 con el detalle por fuente)",
    "error_interno": "error no clasificado (500): ver el log con el requestId",
    "api_no_alcanzable": "no hubo respuesta HTTP: la API no está escuchando en esa URL",
    "otro": "status inesperado",
}


def clasificar(status: int, cuerpo: Any) -> str:
    code = cuerpo.get("code") if isinstance(cuerpo, dict) else None
    if status == 0:
        return "api_no_alcanzable"
    if status == 504 or code == "DEPENDENCY_TIMEOUT":
        return "dependencia_timeout"
    if status == 503 and code == "DEPENDENCY_UNAVAILABLE":
        return "dependencia_no_disponible"
    if status == 503 and isinstance(cuerpo, dict) and ("dependencias" in cuerpo or "esenciales" in cuerpo):
        return "salud_degradada"
    if status == 404:
        return "ruta_inexistente" if code == "ROUTE_NOT_FOUND" else "inexistente"
    if status == 400:
        return "validacion"
    if status == 500:
        return "error_interno"
    if 200 <= status < 300:
        if isinstance(cuerpo, dict):
            for clave in ("items", "puntos"):
                if clave in cuerpo and cuerpo[clave] == []:
                    return "vacio_valido"
        return "exito"
    return "otro"


def resumen(cuerpo: Any) -> str:
    """Conteos y campos de estado; nunca valores personales."""
    if not isinstance(cuerpo, dict):
        return "-"
    if "code" in cuerpo and "message" in cuerpo:
        dep = next((d["problema"] for d in cuerpo.get("details") or [] if d.get("campo") == "dependencia"), None)
        return f"code={cuerpo['code']}" + (f" · dependencia={dep}" if dep else "")
    if "dependencias" in cuerpo:
        return f"estado={cuerpo['estado']} · " + ", ".join(f"{d['nombre']}={d['estado']}" for d in cuerpo["dependencias"]) \
            + f" · desdeCache={cuerpo.get('desdeCache')}"
    if "esenciales" in cuerpo:
        return f"estado={cuerpo['estado']} · noDisponibles={cuerpo.get('noDisponibles')}"
    partes = []
    for clave in ("estado", "codigo", "partidoId", "cantidad", "truncado"):
        if clave in cuerpo:
            partes.append(f"{clave}={cuerpo[clave]}")
    for clave in ("items", "puntos"):
        if isinstance(cuerpo.get(clave), list):
            partes.append(f"{clave}={len(cuerpo[clave])}")
    return " · ".join(partes) or f"campos: {', '.join(list(cuerpo)[:6])}"


def lineas_de_log(log: Path | None, rid: str) -> list[dict[str, Any]]:
    if log is None or not log.exists():
        return []
    salida = []
    for linea in log.read_text(encoding="utf-8", errors="replace").splitlines():
        if f'"request_id": "{rid}"' not in linea:
            continue
        try:
            d = json.loads(linea)
        except ValueError:
            continue
        salida.append({k: d[k] for k in ("ts", "nivel", "mensaje", "dependencia", "operacion", "resultado", "motivo",
                                         "status", "duracion_ms", "tipo") if k in d})
    return salida


def resumen_log(lineas: list[dict[str, Any]]) -> str:
    deps = [f"{d['dependencia']}.{d.get('operacion')}={d.get('resultado')}"
            + (f"/{d['motivo']}" if d.get("motivo") else "") + f" {d.get('duracion_ms')}ms"
            for d in lineas if d.get("mensaje") == "dependencia"]
    req = next((f"request {d.get('status')} {d.get('duracion_ms')}ms" for d in lineas if d.get("mensaje") == "request"), None)
    return "; ".join(([req] if req else []) + deps) or "-"


def pedir(base: str, path: str, rid: str, timeout: float) -> tuple[int, Any, dict[str, str], float, str]:
    req = urllib.request.Request(base.rstrip("/") + path, headers={"X-Request-Id": rid, "Accept": "application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status, texto, cab = r.status, r.read().decode(), dict(r.headers)
    except urllib.error.HTTPError as e:
        status, texto, cab = e.code, e.read().decode(errors="replace"), dict(e.headers)
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        motivo = getattr(e, "reason", e)
        return 0, None, {}, (time.perf_counter() - t0) * 1000, f"{type(motivo).__name__}: {motivo}"
    ms = (time.perf_counter() - t0) * 1000
    try:
        cuerpo = json.loads(texto) if texto else None
    except ValueError:
        cuerpo = None
    return status, cuerpo, cab, ms, ""


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--api-url", default=CFG["API_URL"])
    p.add_argument("--log", type=Path, help="archivo de log JSON de la API (iniciar_api.sh … | tee archivo)")
    p.add_argument("--producto", action="append")
    p.add_argument("--etiqueta", default="", help="texto que se agrega al nombre de la prueba (p. ej. 'fase 2: redis caído')")
    p.add_argument("--archivo", default="resultados_api")
    p.add_argument("--sin-no-alcanzable", action="store_true")
    a = p.parse_args()
    R = Registro(a.archivo, "Capa API — rutas del Hito 10 (cadena completa)")
    timeout = float(CFG.get("API_TIMEOUT", "8"))
    prefijo = f"h11-{sello()}"
    casos = [c for c in CASOS if not a.producto or c[0] in a.producto or c[0] == "api"]
    pendientes_log: list[tuple[str, dict[str, Any]]] = []
    for i, (producto, path, dep, aceptadas, que) in enumerate(casos, 1):
        rid = f"{prefijo}-{i:02d}"
        status, cuerpo, cab, ms, err = pedir(a.api_url, path, rid, timeout)
        clase = clasificar(status, cuerpo)
        extra = next((f" · X-Cache={v}" for k, v in cab.items() if k.lower() == "x-cache"), "")
        fila = R.agregar(producto=producto, capa="api",
                         prueba=f"GET {path}" + (f" [{a.etiqueta}]" if a.etiqueta else ""),
                         objetivo=f"{a.api_url} · dependencia: {dep}",
                         resultado="OK" if clase in aceptadas else ("FAIL" if clase in ("api_no_alcanzable", "error_interno",
                                                                                          "dependencia_no_disponible",
                                                                                          "dependencia_timeout") else "WARN"),
                         latencia_ms=ms,
                         detalle=f"HTTP {status or '—'} · {clase} · {resumen(cuerpo) if not err else err}{extra} · requestId={rid}",
                         interpretacion=f"{que}. Observado: {CLASIF_INTERP.get(clase, '')}",
                         no_demuestra="rendimiento o concurrencia (Hito 12)",
                         metodo="GET", path=path, status=status, clasificacion=clase, request_id=rid,
                         esperado=sorted(aceptadas))
        pendientes_log.append((rid, fila))
    if not a.sin_no_alcanzable:
        from urllib.parse import urlparse
        u = urlparse(a.api_url)
        mala = f"{u.scheme}://{u.hostname}:{(u.port or 80) + 1}"
        status, cuerpo, _, ms, err = pedir(mala, "/health", f"{prefijo}-na", 3)
        clase = clasificar(status, cuerpo)
        R.agregar(producto="api", capa="api", prueba="control: API no alcanzable (puerto sin listener)",
                  objetivo=f"{mala}/health", resultado="OK" if clase == "api_no_alcanzable" else "WARN", latencia_ms=ms,
                  detalle=f"{clase} · {err or status}", interpretacion=CLASIF_INTERP[clase],
                  no_demuestra="nada sobre las fuentes: no se llegó a la API")
    if a.log:
        time.sleep(0.3)   # el log de acceso se escribe al terminar la respuesta
        R.nota("## Líneas de log asociadas (filtradas por X-Request-Id, campos sin datos sensibles)\n\n"
               "| requestId | Log de acceso y de adaptadores |\n|---|---|\n" +
               "\n".join(f"| `{rid}` | {resumen_log(lineas_de_log(a.log, rid))} |" for rid, _ in pendientes_log))
        with (R.dir / f"{a.archivo}_logs.jsonl").open("a", encoding="utf-8") as f:
            for rid, _ in pendientes_log:
                for linea in lineas_de_log(a.log, rid):
                    f.write(redactar(json.dumps({"request_id": rid, **linea}, ensure_ascii=False)) + "\n")
    print(f"Evidencia: {ruta_publica(R.md)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
