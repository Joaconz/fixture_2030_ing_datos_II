"""Fallas controladas y recuperación (RF17, RF20, RF21, §5.7) — sin borrar datos ni volúmenes.

Escenarios:
  detener FUENTE   `docker stop` del contenedor → la API (ya corriendo) responde
                   503 rápido; `docker start` → la API se recupera SIN reiniciarse.
                   Se comparan conteos de datos y la fecha de creación del
                   volumen nombrado antes y después (persistencia conservada).
  pausar FUENTE    `docker pause` → el puerto sigue abierto pero nadie contesta:
                   la API corta en DEP_TIMEOUT_S y responde 504 DEPENDENCY_TIMEOUT.
  config           levanta una SEGUNDA instancia temporal de la API (puerto 8011)
                   con UNA variable mal puesta por vez: credencial inválida,
                   database/keyspace inexistente, puerto o host incorrecto y
                   timeout demasiado bajo. La instancia normal no se toca.

    ../fixture2030-hito10-api/.venv/bin/python scripts/prueba_falla_controlada.py detener redis
    ../fixture2030-hito10-api/.venv/bin/python scripts/prueba_falla_controlada.py pausar influxdb
    ../fixture2030-hito10-api/.venv/bin/python scripts/prueba_falla_controlada.py config [--caso NOMBRE ...]

SEGURIDAD DE DATOS: sólo `docker stop/start` y `pause/unpause`; nunca `down -v`,
`rm` ni `volume rm`. Un `finally` vuelve a arrancar / despausar el contenedor
aunque el script se interrumpa. La instancia temporal se termina al final de cada caso.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prueba_api import clasificar, lineas_de_log, pedir, resumen  # noqa: E402
from registro import Registro, cargar_config, redactar, ruta_publica, sello  # noqa: E402

CFG = cargar_config()
API = os.environ.get("API_URL", CFG["API_URL"])
API_DIR = Path(CFG["API_DIR"])
PY_API = API_DIR / ".venv" / "bin" / "python"
PA = CFG["NEO4J_PARTIDO_DEMO"]

RUTA = {
    "mongodb": f"/equipos/{CFG['MONGO_EQUIPO_DEMO']}",
    "neo4j": f"/partidos/{PA}/eventos?limit=5",
    "cassandra": f"/partidos/{CFG['CASSANDRA_PARTIDO_DEMO']}/comentarios?limit=5",
    "redis": f"/sesiones/{CFG['REDIS_SESION_DEMO']}",
    "influxdb": f"/partidos/{CFG['INFLUX_PARTIDO_DEMO']}/estadisticas?desde={CFG['INFLUX_DESDE']}&hasta={CFG['INFLUX_HASTA']}",
}
CONTENEDOR = {"mongodb": CFG["MONGO_CONTAINER"], "neo4j": CFG["NEO4J_CONTAINER"],
              "cassandra": CFG["CASSANDRA_CONTAINER"], "redis": CFG["REDIS_CONTAINER"], "influxdb": CFG["INFLUX_CONTAINER"]}
VOLUMEN = {"mongodb": "fixture2030_mongo_data", "neo4j": "fixture2030_neo4j_data", "cassandra": "fixture2030_cassandra_data",
           "redis": "fixture2030_redis_data", "influxdb": "fixture2030_influxdb_data"}
PUERTO = {"mongodb": int(CFG["MONGO_PORT"]), "neo4j": int(CFG["NEO4J_BOLT_PORT"]), "cassandra": int(CFG["CASSANDRA_PORT"]),
          "redis": int(CFG["REDIS_PORT"]), "influxdb": 8181}


def sh(*cmd: str, timeout: float = 60, entrada: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(cmd), capture_output=True, text=True, timeout=timeout, input=entrada)


def conteo_datos(fuente: str) -> str:
    """Conteo de control de sólo lectura, desde el contenedor (para comparar antes/después)."""
    c = CONTENEDOR[fuente]
    try:
        if fuente == "redis":
            # Las sesiones vencen solas (TTL de 30 min del Hito 7): DBSIZE baja aunque no se pierda
            # nada. Se comparan las claves PERSISTENTES (sin TTL) y se informan las volátiles aparte.
            ks = sh("docker", "exec", c, "redis-cli", "INFO", "keyspace").stdout
            linea = next((ln for ln in ks.splitlines() if ln.startswith("db0:")), "db0:keys=0,expires=0")
            campos = dict(kv.split("=") for kv in linea.split(":", 1)[1].split(","))
            persistentes = int(campos["keys"]) - int(campos["expires"])
            return f"persistentes={persistentes} (con TTL: {campos['expires']}, vencen solas)"
        if fuente == "mongodb":
            return "jugadores=" + sh("docker", "exec", c, "mongosh", CFG["MONGO_DB"], "--quiet", "--eval",
                                     "db.jugadores.estimatedDocumentCount()").stdout.strip().splitlines()[-1]
        if fuente == "cassandra":
            out = sh("docker", "exec", c, "cqlsh", "-e",
                     f"SELECT count(*) FROM {CFG['CASSANDRA_KEYSPACE']}.config_particion_partido;", timeout=90).stdout
            return "config_particion_partido=" + next((ln.strip() for ln in out.splitlines() if ln.strip().isdigit()), "?")
        if fuente == "neo4j":
            env = dict(os.environ, NEO4J_USERNAME=CFG["NEO4J_USER"], NEO4J_PASSWORD=_neo4j_pwd())
            out = subprocess.run(["docker", "exec", "-e", "NEO4J_USERNAME", "-e", "NEO4J_PASSWORD", c, "cypher-shell",
                                  "--format", "plain", "MATCH (p:Partido) RETURN count(p)"],
                                 capture_output=True, text=True, timeout=60, env=env).stdout
            return "partidos=" + (out.strip().splitlines() or ["?"])[-1]
        if fuente == "influxdb":
            env = dict(os.environ, INFLUXDB3_AUTH_TOKEN=_influx_token())
            out = subprocess.run(["docker", "exec", "-e", "INFLUXDB3_AUTH_TOKEN", c, "influxdb3", "query", "--database",
                                  CFG["INFLUX_DB"], "--format", "csv",
                                  f"SELECT count(*) AS n FROM {CFG['INFLUX_TABLA']} WHERE partido_id = '{PA}'"],
                                 capture_output=True, text=True, timeout=60, env=env).stdout
            return f"puntos {PA}=" + (out.strip().splitlines() or ["?"])[-1]
    except (subprocess.SubprocessError, IndexError) as exc:
        return f"no medido ({type(exc).__name__})"
    return "-"


def _neo4j_pwd() -> str:
    from registro import neo4j_password
    return neo4j_password(CFG)[0] or ""


def _influx_token() -> str:
    from registro import influx_token
    return influx_token(CFG)[0] or ""


def volumen_creado(fuente: str) -> str:
    r = sh("docker", "volume", "inspect", VOLUMEN[fuente], "--format", "{{.Name}} creado {{.CreatedAt}}")
    return r.stdout.strip() or "volumen no encontrado"


def estado_contenedor(c: str) -> str:
    return sh("docker", "inspect", "-f", "{{.State.Status}}{{if .State.Health}}/{{.State.Health.Status}}{{end}}", c).stdout.strip()


def esperar_healthy(c: str, limite: float = 180) -> float:
    t0 = time.time()
    while time.time() - t0 < limite:
        est = estado_contenedor(c)
        if est.endswith("/healthy") or est == "running":
            return time.time() - t0
        time.sleep(2)
    return -1


def tcp(host: str, puerto: int) -> str:
    try:
        with socket.create_connection((host, puerto), timeout=float(CFG["CONNECT_TIMEOUT"])):
            return "conecta"
    except ConnectionRefusedError:
        return "connection refused"
    except socket.timeout:
        return "timeout"
    except OSError as exc:
        return type(exc).__name__


class Escenario:
    """Una tabla Markdown por escenario con los apartados de §5.7, más el JSONL común."""

    def __init__(self, titulo: str, log: Path | None) -> None:
        self.R = Registro("resultados_falla_controlada", "Fallas controladas y recuperación (§5.7)")
        self.log = log
        self.titulo = titulo
        self.filas: list[str] = []
        self.rid_base = f"h11-falla-{sello()}"
        self.n = 0

    def pedir(self, fase: str, producto: str, path: str, base: str = API, esperado: set[str] | None = None,
              log: Path | None = None) -> dict[str, Any]:
        self.n += 1
        rid = f"{self.rid_base}-{self.n:02d}"
        status, cuerpo, cab, ms, err = pedir(base, path, rid, float(CFG["API_TIMEOUT"]))
        clase = clasificar(status, cuerpo)
        time.sleep(0.2)
        lineas = lineas_de_log(log or self.log, rid)
        motivo = next((d.get("motivo") for d in lineas if d.get("motivo")), "-")
        aviso = next((d.get("mensaje") for d in lineas if d.get("nivel") == "WARNING"), "")
        res = {"fase": fase, "path": path, "status": status, "clase": clase, "ms": round(ms, 1), "rid": rid,
               "resumen": resumen(cuerpo) if not err else err, "motivo": motivo, "aviso": aviso,
               "retry_after": next((v for k, v in cab.items() if k.lower() == "retry-after"), "-")}
        self.filas.append(f"| {fase} | `GET {path}` | {status or '—'} | {clase} | {res['ms']} | `{rid}` | "
                          f"{res['resumen']} | {motivo} | {aviso or '-'} |")
        self.R.agregar(producto=producto, capa="api", prueba=f"[{self.titulo}] {fase}: GET {path}", objetivo=base,
                       resultado="OK" if (esperado is None or clase in esperado) else "FAIL", latencia_ms=ms,
                       detalle=f"HTTP {status or '—'} · {clase} · {res['resumen']} · motivo log={motivo} · requestId={rid}",
                       interpretacion=f"esperado: {', '.join(sorted(esperado)) if esperado else 'registrar'}",
                       no_demuestra="rendimiento bajo falla parcial con carga (Hito 12)",
                       escenario=self.titulo, fase=fase, status=status, clasificacion=clase, motivo=motivo, request_id=rid)
        return res

    def escribir(self, secciones: list[tuple[str, str]]) -> None:
        texto = [f"\n## Escenario: {self.titulo}\n"]
        for nombre, contenido in secciones:
            texto.append(f"**{nombre}:** {contenido}\n")
        texto.append("| Fase | Request | HTTP | Clasificación | ms | X-Request-Id | Respuesta (resumen) | Motivo en log | Aviso del adaptador |")
        texto.append("|---|---|---:|---|---:|---|---|---|---|")
        texto += self.filas
        # Relato por escenario en un archivo aparte: resultados_falla_controlada.md queda
        # como una sola tabla (una fila por prueba) y no se mezcla con estas secciones.
        relato = self.R.dir / "fallas_controladas.md"
        if not relato.exists():
            relato.write_text("# Fallas controladas y recuperación — relato por escenario (§5.7)\n\n"
                              "Tabla completa de pruebas: [`resultados_falla_controlada.md`](resultados_falla_controlada.md).\n",
                              encoding="utf-8")
        with relato.open("a", encoding="utf-8") as f:
            f.write(redactar("\n".join(texto)) + "\n")


# =========================================================================== detener / pausar
def detener_o_pausar(fuente: str, modo: str, log: Path | None) -> int:
    c, ruta = CONTENEDOR[fuente], RUTA[fuente]
    titulo = f"{'dependencia detenida (docker stop)' if modo == 'detener' else 'dependencia colgada (docker pause)'} — {fuente}"
    e = Escenario(titulo, log)
    if estado_contenedor(c).split("/")[0] != "running":
        print(f"El contenedor {c} no está corriendo: no se puede provocar la falla.", file=sys.stderr)
        return 1
    antes_datos, antes_vol = conteo_datos(fuente), volumen_creado(fuente)
    inicial = estado_contenedor(c)
    a1 = e.pedir("1. fuente arriba", fuente, ruta)
    e.pedir("1. fuente arriba", "api", "/health/ready")
    accion = ["docker", "stop", c] if modo == "detener" else ["docker", "pause", c]
    deshacer = ["docker", "start", c] if modo == "detener" else ["docker", "unpause", c]
    t_falla = time.time()
    sh(*accion, timeout=90)
    try:
        time.sleep(1)
        esperado = {"dependencia_no_disponible"} if modo == "detener" else {"dependencia_timeout"}
        if fuente == "redis" and modo == "detener":
            esperado = {"dependencia_no_disponible"}
        e.pedir("2. falla", fuente, ruta, esperado=esperado)
        e.pedir("2. falla (repite)", fuente, ruta, esperado=esperado)
        if fuente == "redis":
            e.pedir("2. falla", "neo4j", f"/partidos/{PA}", esperado={"exito"})   # caché = optimización
        time.sleep(float(cargar_api_setting("HEALTH_CACHE_S", "5")) + 0.5)   # que el chequeo no venga de caché
        e.pedir("2. falla", "api", "/health/dependencias", esperado={"salud_degradada"})
        ready = e.pedir("2. falla", "api", "/health/ready",
                        esperado={"salud_degradada"} if fuente in ("mongodb", "neo4j") else {"exito"})
        e.pedir("2. falla (otra fuente sigue)", "mongodb" if fuente != "mongodb" else "neo4j",
                RUTA["mongodb"] if fuente != "mongodb" else RUTA["neo4j"], esperado={"exito"})
        tcp_falla = tcp("127.0.0.1", PUERTO[fuente])
    finally:
        sh(*deshacer, timeout=120)
    t_vuelta = esperar_healthy(c)
    t0 = time.time()
    recuperada = None
    while time.time() - t0 < 90:
        st, cuerpo, _, _, _ = pedir(API, ruta, f"{e.rid_base}-espera", 10)
        if clasificar(st, cuerpo) not in ("dependencia_no_disponible", "dependencia_timeout", "api_no_alcanzable"):
            recuperada = time.time() - t0
            break
        time.sleep(2)
    e.pedir("3. recuperada (sin reiniciar la API)", fuente, ruta, esperado={a1["clase"]})
    time.sleep(float(cargar_api_setting("HEALTH_CACHE_S", "5")) + 0.5)
    e.pedir("3. recuperada", "api", "/health/dependencias", esperado={"exito"})
    despues_datos, despues_vol = conteo_datos(fuente), volumen_creado(fuente)
    conservado = antes_vol == despues_vol and antes_datos.split(" (")[0] == despues_datos.split(" (")[0]
    e.R.agregar(producto=fuente, capa="operacion", prueba=f"[{titulo}] datos y volumen conservados",
                objetivo=VOLUMEN[fuente], resultado="OK" if conservado else "WARN",
                detalle=f"antes: {antes_datos} · después: {despues_datos} · {despues_vol}",
                interpretacion="la falla se provocó sin tocar la persistencia (RNF6, Restricción 'Destrucción')")
    e.escribir([
        ("Condición inicial", f"contenedor `{c}` en estado `{inicial}`; API en {API} corriendo; {antes_datos}; {antes_vol}."),
        ("Cambio aplicado", f"`{' '.join(accion)}` (reversible). Nada se borra."),
        ("Prueba ejecutada", f"`GET {ruta}` antes, durante y después; `/health/dependencias`, `/health/ready`, "
                             f"una ruta de otra fuente y TCP a 127.0.0.1:{PUERTO[fuente]} durante la falla."),
        ("Respuesta de la API", f"ver tabla; `/health/ready` durante la falla: HTTP {ready['status']} ({ready['resumen']})."),
        ("Transporte durante la falla", f"TCP 127.0.0.1:{PUERTO[fuente]} → {tcp_falla} "
                                        f"({'stop: no hay listener' if modo == 'detener' else 'pause: el puerto lo sigue sosteniendo Docker, pero el proceso no contesta'})."),
        ("Recuperación", f"`{' '.join(deshacer)}`; contenedor listo en {t_vuelta:.0f} s; la API volvió a responder "
                         f"{'en ' + format(recuperada, '.1f') + ' s más' if recuperada is not None else 'NO (revisar)'} sin reiniciarse."),
        ("Datos y volúmenes conservados", f"antes `{antes_datos}` · después `{despues_datos}` · `{despues_vol}` "
                                          f"→ {'iguales' if conservado else 'DISTINTOS (revisar)'}."),
        ("Duración total", f"{time.time() - t_falla:.0f} s."),
    ])
    print(f"Evidencia: {ruta_publica(e.R.md)}")
    return 0


def cargar_api_setting(clave: str, defecto: str) -> str:
    from registro import _leer_env  # noqa: PLC2701
    return os.environ.get(clave) or _leer_env(API_DIR / ".env").get(clave) or defecto


# =========================================================================== configuración incorrecta
CASOS_CONFIG: dict[str, tuple[str, dict[str, str], str, str, set[str], str]] = {
    # nombre: (fuente, override, ruta, qué se rompe, clasificaciones esperadas, detalle esperado en /health)
    "neo4j-credencial": ("neo4j", {"NEO4J_PASSWORD": "contrasena-invalida-de-diagnostico"}, RUTA["neo4j"],
                         "credencial inválida (Neo4j)", {"dependencia_no_disponible"}, "credencial rechazada"),
    "neo4j-database": ("neo4j", {"NEO4J_DATABASE": "fixture2030inexistente"}, RUTA["neo4j"],
                       "database inexistente (Neo4j)", {"dependencia_no_disponible"}, "contexto inexistente"),
    "cassandra-keyspace": ("cassandra", {"CASSANDRA_KEYSPACE": "fixture2030_inexistente"}, RUTA["cassandra"],
                           "keyspace inexistente (Cassandra)", {"dependencia_no_disponible"}, "contexto inexistente"),
    "mongo-database": ("mongodb", {"MONGO_DB": "fixture2030_inexistente"}, RUTA["mongodb"],
                       "database inexistente (MongoDB)", {"inexistente"}, "contexto inexistente"),
    "influx-database": ("influxdb", {"INFLUX_DB": "fixture2030_inexistente"}, RUTA["influxdb"],
                        "database inexistente (InfluxDB)", {"dependencia_no_disponible"}, "contexto inexistente"),
    "influx-token": ("influxdb", {"INFLUX_TOKEN": "apiv3_token-invalido-de-diagnostico"}, RUTA["influxdb"],
                     "token inválido (InfluxDB)", {"dependencia_no_disponible"}, "credencial rechazada"),
    "influx-sin-token": ("influxdb", {"INFLUX_TOKEN": "", "INFLUX_TOKEN_FILE": "/nonexistent/admin-token.json"}, RUTA["influxdb"],
                         "token no configurado (InfluxDB)", {"dependencia_no_disponible"}, "sin configurar"),
    "redis-puerto": ("redis", {"REDIS_URL": "redis://127.0.0.1:6390/0"}, RUTA["redis"],
                     "puerto incorrecto (Redis 6390)", {"dependencia_no_disponible"}, "no responde"),
    # pymongo reintenta la selección de servidor: la PRIMERA request tras arrancar suma el
    # descubrimiento inicial de la topología y puede cortar por el timeout de la API (504);
    # las siguientes reciben antes el error del driver (503, motivo conexion). Se aceptan ambas.
    "mongo-host": ("mongodb", {"MONGO_URI": "mongodb://mongo-inexistente.invalid:27017"}, RUTA["mongodb"],
                   "host no resuelto (MongoDB)", {"dependencia_no_disponible", "dependencia_timeout"}, "no responde"),
    "timeout-bajo": ("neo4j", {"DEP_TIMEOUT_S": "0.001"}, RUTA["neo4j"],
                     "timeout demasiado bajo (DEP_TIMEOUT_S=0.001)", {"dependencia_timeout"}, "timeout"),
}


def configuracion(casos: list[str]) -> int:
    puerto = int(os.environ.get("API_PORT_PRUEBA", "8011"))
    base = f"http://127.0.0.1:{puerto}"
    crudo = Path(__file__).resolve().parents[1] / "docs" / "evidencia" / "crudo"
    crudo.mkdir(parents=True, exist_ok=True)
    if not PY_API.exists():
        print(f"Falta {PY_API}: correr primero bash ../fixture2030-hito10-api/scripts/iniciar_api.sh", file=sys.stderr)
        return 1
    for nombre in casos:
        fuente, override, ruta, que, esperado, det_salud = CASOS_CONFIG[nombre]
        log = crudo / f"api_config_{nombre}.log"
        env = dict(os.environ, **override, API_PORT=str(puerto), HEALTH_CACHE_S="0", LOG_LEVEL="INFO")
        if "DEP_TIMEOUT_S" not in override:
            env.pop("DEP_TIMEOUT_S", None)
        with log.open("w", encoding="utf-8") as salida:
            proc = subprocess.Popen([str(PY_API), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(puerto)],
                                    cwd=API_DIR, env=env, stdout=salida, stderr=subprocess.STDOUT)
        try:
            for _ in range(40):
                if tcp("127.0.0.1", puerto) == "conecta":
                    break
                time.sleep(0.25)
            e = Escenario(f"configuración incorrecta — {que}", log)
            r0 = e.pedir("con la variable mal puesta", fuente, ruta, base=base, esperado=esperado)
            r = e.pedir("con la variable mal puesta (repite)", fuente, ruta, base=base, esperado=esperado)
            s = e.pedir("con la variable mal puesta", "api", "/health/dependencias", base=base, esperado={"salud_degradada"})
            st, cuerpo, _, _, _ = pedir(base, "/health/dependencias", f"{e.rid_base}-det", 15)
            dep = next((d for d in (cuerpo or {}).get("dependencias", []) if d["nombre"] == fuente), {})
            e.R.agregar(producto=fuente, capa="api", prueba=f"[{e.titulo}] /health/dependencias detalle de {fuente}",
                        objetivo=base, resultado="OK" if dep.get("detalle") == det_salud else "FAIL",
                        detalle=f"{fuente}: estado={dep.get('estado')} · detalle={dep.get('detalle')} (esperado: {det_salud})",
                        interpretacion="el chequeo por dependencia nombra la capa que falló, sin exponer el valor")
            # con DEP_TIMEOUT_S global demasiado bajo TODAS las fuentes cortan; en el resto, las demás siguen
            otra_esperada = {"dependencia_timeout"} if "DEP_TIMEOUT_S" in override else {"exito"}
            ok_inst = e.pedir("otra fuente en la misma instancia", "mongodb" if fuente != "mongodb" else "cassandra",
                              RUTA["mongodb"] if fuente != "mongodb" else RUTA["cassandra"], base=base, esperado=otra_esperada)
            variables = ", ".join(f"`{k}`" for k in override)
            e.escribir([
                ("Condición inicial", f"instancia temporal de la API en {base} con la configuración normal salvo {variables}."),
                ("Cambio aplicado", f"{variables} = valor de diagnóstico ({que}); el valor no se muestra si es credencial. "
                                    "La instancia principal y las bases no se tocan."),
                ("Respuesta de la API", f"`GET {ruta}` → HTTP {r0['status']} {r0['clase']} en {r0['ms']} ms "
                                        f"(repetida: HTTP {r['status']} {r['clase']} en {r['ms']} ms); "
                                        f"`/health/dependencias` → HTTP {s['status']}, {fuente}: {dep.get('estado')} «{dep.get('detalle')}»; "
                                        f"otra fuente → {ok_inst['clase']}."),
                ("Mensaje de log", f"motivo `{r['motivo']}`; aviso del adaptador: «{r['aviso'] or '-'}»."),
                ("Recuperación", "se termina la instancia temporal (la configuración correcta nunca cambió)."),
                ("Datos y volúmenes conservados", "no aplica: sólo se leyó."),
            ])
        finally:
            proc.terminate()
            try:
                proc.wait(10)
            except subprocess.TimeoutExpired:
                proc.kill()
            log.write_text(redactar(log.read_text(encoding="utf-8", errors="replace")), encoding="utf-8")
        if nombre == "neo4j-credencial":
            time.sleep(6)   # Neo4j bloquea el usuario unos segundos tras intentos fallidos (auth_lock_time)
    print(f"Evidencia: {ruta_publica(e.R.md)}")
    return 0


def main() -> int:
    if not shutil.which("docker"):
        print("docker no está disponible: SKIP de las fallas controladas", file=sys.stderr)
        return 0
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="modo", required=True)
    for m in ("detener", "pausar"):
        s = sub.add_parser(m)
        s.add_argument("fuente", choices=list(RUTA))
        s.add_argument("--log", type=Path, help="log JSON de la API principal (para extraer el motivo)")
    c = sub.add_parser("config")
    c.add_argument("--caso", action="append", choices=list(CASOS_CONFIG))
    a = p.parse_args()
    if a.modo == "config":
        return configuracion(a.caso or list(CASOS_CONFIG))
    return detener_o_pausar(a.fuente, a.modo, a.log)


if __name__ == "__main__":
    sys.exit(main())
