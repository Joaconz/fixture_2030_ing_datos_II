"""
Fixture 2030 — Carga masiva integrada (Hito 11 del PDF del TPO)
ARCHIVO: scripts/comun.py
PROPÓSITO: piezas compartidas por el orquestador, la validación y el análisis de
           distribución (solo biblioteca estándar de Python, corre en la notebook):
  1. cómo se llama a `docker compose` de cada módulo con su override (compose/*.yml);
  2. la definición de las 5 bases: arranque, preparación y CARGA con el cargador
     que ya tiene cada módulo (no se reescribe ninguno);
  3. clientes mínimos (mongosh, HTTP de Neo4j, cassandra-driver del cargador,
     redis-cli, HTTP de InfluxDB) para validar y medir la distribución;
  4. muestreo de CPU y RAM de los contenedores con `docker stats`.

AISLAMIENTO: todo lo que se levanta se llama f30cm-* (proyectos de compose,
contenedores, volúmenes, redes) y publica puertos propios en 127.0.0.1. Las
instancias compartidas fixture2030-* no se tocan. Los datos de los volúmenes
respaldados por carpeta van a ~/docker/data/f30cm/<base>.
"""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UTC = timezone.utc
for _flujo in (sys.stdout, sys.stderr):   # consola de Windows (cp1252): que no rompa con ✔ ✖ ▶
    if hasattr(_flujo, "reconfigure"):
        _flujo.reconfigure(encoding="utf-8", errors="replace")
MODULO = Path(__file__).resolve().parents[1]          # fixture2030-carga-masiva/
RAIZ = MODULO.parent                                  # raíz del repositorio
EVIDENCIA = MODULO / "evidencia"
SECRETOS = MODULO / ".secrets"
DATOS_HOST = Path.home() / "docker" / "data" / "f30cm"
PREFIJO = "f30cm"
ABORTO: str | None = None   # lo fija el vigía del Muestreador; corta la corrida

NEO4J_HTTP = "http://127.0.0.1:37474"
NEO4J_AUTH = ("neo4j", "fixture2030")                 # credencial de desarrollo del módulo (.env.example)
INFLUX_PUERTO = 18182
REDIS_PUERTO = 16380

# Volúmenes que pide el PDF (y que ya cargan los cargadores de cada módulo)
ESPERADO = {
    "mongodb": {"equipos": 64, "jugadores": 1_664},
    "neo4j": {"partidos": 127, "eventos": 1_572},
    "cassandra": {"comentarios": 1_050_000},           # generador.py: 300.000 + 300.000 + 450.000
    "redis": {"usuarios": 100_000},
    "influxdb": {"puntos": 10_094_400},
}


def ahora() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def sello() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def commit() -> str:
    def git(*a):
        return subprocess.run(["git", *a], cwd=RAIZ, capture_output=True, text=True).stdout.strip()
    corto = git("rev-parse", "--short", "HEAD") or "sin-git"
    sucio = git("status", "--porcelain", "--", ".")
    return corto + (" + cambios sin commitear" if sucio else "")


# ---------------------------------------------------------------------------
# Ejecución de comandos
# ---------------------------------------------------------------------------
class Registro:
    """Salida de consola + archivo de log de la corrida (thread-safe)."""

    def __init__(self, archivo: Path | None = None):
        self.archivo = archivo
        self._lock = threading.Lock()

    def __call__(self, texto: str, consola: bool = True) -> None:
        linea = f"[{datetime.now(UTC):%H:%M:%S}] {texto}"
        with self._lock:
            if consola:
                print(linea, flush=True)
            if self.archivo:
                with open(self.archivo, "a", encoding="utf-8") as f:
                    f.write(linea + "\n")


log = Registro()


class ErrorPaso(Exception):
    pass


def correr(cmd: list[str], cwd: Path | None = None, env: dict | None = None, etiqueta: str = "",
           entrada: str | None = None, timeout: int = 3600, chequear: bool = True) -> str:
    """Corre un comando, guarda TODA su salida en el log (con etiqueta) y la devuelve."""
    entorno = {**os.environ, **(env or {})}
    t0 = time.perf_counter()
    p = subprocess.run(cmd, cwd=cwd, env=entorno, input=entrada, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    salida = (p.stdout or "") + (("\n" + p.stderr) if p.stderr and p.stderr.strip() else "")
    if etiqueta:
        for linea in salida.rstrip().splitlines():
            log(f"  {etiqueta} | {linea}", consola=False)
    if chequear and p.returncode != 0:
        cola = "\n".join(salida.strip().splitlines()[-15:])
        raise ErrorPaso(f"{' '.join(cmd[:8])}… salió con {p.returncode} ({time.perf_counter() - t0:.1f} s):\n{cola}")
    return salida


def dexec(contenedor: str, *cmd: str, entrada: str | None = None, etiqueta: str = "", **kw) -> str:
    return correr(["docker", "exec", *(["-i"] if entrada is not None else []), contenedor, *cmd],
                  entrada=entrada, etiqueta=etiqueta, **kw)


# ---------------------------------------------------------------------------
# Las cinco bases
# ---------------------------------------------------------------------------
class Base:
    nombre = ""
    carpeta = ""            # carpeta del módulo en el repo
    servicio = ""           # servicio principal del compose del módulo
    contenedor = ""
    perfiles: list[str] = []
    datos_en_carpeta = False  # volumen nombrado respaldado por carpeta del host
    reserva_mib = 0   # suma de los mem_limit de sus contenedores (compose/<base>.yml)

    def __init__(self, opciones: dict | None = None):
        self.op = opciones or {}
        self.dir = RAIZ / self.carpeta
        self.proyecto = f"{PREFIJO}-{self.nombre}"
        self.override = f"../fixture2030-carga-masiva/compose/{self.nombre}.yml"
        self.datos = DATOS_HOST / self.nombre

    # -- compose -------------------------------------------------------------
    def env(self) -> dict:
        return {}

    def compose(self, *args: str, etiqueta: str | None = None, **kw) -> str:
        cmd = ["docker", "compose", "-p", self.proyecto, "-f", "docker-compose.yml", "-f", self.override]
        for p in self.perfiles:
            cmd += ["--profile", p]
        return correr(cmd + list(args), cwd=self.dir, env=self.env(),
                      etiqueta=self.nombre if etiqueta is None else etiqueta, **kw)

    # -- ciclo de vida -------------------------------------------------------
    def limpiar(self) -> None:
        """Deja la base en CERO: borra contenedores, volúmenes y carpeta de datos PROPIOS."""
        self.compose("down", "-v", "--remove-orphans", timeout=300)
        if self.datos.exists():
            shutil.rmtree(self.datos, ignore_errors=True)
        if self.datos_en_carpeta:
            self.datos.mkdir(parents=True, exist_ok=True)

    def apagar(self) -> None:
        self.compose("down", "-v", "--remove-orphans", timeout=300)
        shutil.rmtree(self.datos, ignore_errors=True)

    def arrancar(self) -> None:
        self.compose("up", "-d", "--wait", "--wait-timeout", "600", self.servicio, timeout=900)

    def preparar(self) -> None:
        """Esquema / estructura / dependencias del cargador. No se cuenta como carga."""

    def cargar(self) -> dict:
        """Corre el cargador del módulo. Devuelve {'volumen': n, 'unidad': str, ...}."""
        raise NotImplementedError


class MongoDB(Base):
    nombre, carpeta, servicio, contenedor = "mongodb", "fixture2030-mongodb", "mongodb", "f30cm-mongodb"
    perfiles = ["carga"]
    cargador = "f30cm-mongodb-cargador"
    reserva_mib = 1152   # 768m servidor + 384m cargador

    def preparar(self) -> None:
        # init/01-validators.js ya corrió al crear el contenedor (validadores + índices).
        self.compose("up", "-d", "cargador")
        dexec(self.cargador, "sh", "-c",
              "cp /src/package.json /src/package-lock.json /src/seed.js /app/ && "
              "npm ci --no-audit --no-fund --loglevel=error", etiqueta=self.nombre, timeout=900)

    def cargar(self) -> dict:
        dexec(self.cargador, "node", "seed.js", etiqueta=self.nombre)
        c = mongo_json(self.contenedor, "({e: db.equipos.countDocuments(), j: db.jugadores.countDocuments()})")
        return {"volumen": c["e"] + c["j"], "unidad": "documentos",
                "detalle": f"{c['e']} equipos + {c['j']} jugadores (load/seed.js, bulkWrite con upsert)"}


class Neo4j(Base):
    nombre, carpeta, servicio, contenedor = "neo4j", "fixture2030-neo4j", "neo4j", "f30cm-neo4j"
    reserva_mib = 2048   # 2g servidor

    def _cypher_archivo(self, archivo: str) -> None:
        dexec(self.contenedor, "cypher-shell", "-u", NEO4J_AUTH[0], "-p", NEO4J_AUTH[1], "-f", archivo,
              etiqueta=self.nombre, timeout=3600)

    def preparar(self) -> None:
        self._cypher_archivo("/queries/estructura.cypher")

    def cargar(self) -> dict:
        self._cypher_archivo("/queries/carga.cypher")
        r = cypher("MATCH (n) WITH count(n) AS nodos MATCH ()-[r]->() RETURN nodos, count(r) AS rels")[0]
        return {"volumen": r["nodos"] + r["rels"], "unidad": "nodos+relaciones",
                "detalle": f"{r['nodos']:,} nodos + {r['rels']:,} relaciones (queries/carga.cypher, MERGE)"}


class Cassandra(Base):
    nombre, carpeta, servicio, contenedor = "cassandra", "fixture2030-cassandra", "cassandra", "f30cm-cassandra"
    perfiles = ["carga"]
    datos_en_carpeta = True
    cargador = "f30cm-cassandra-cargador"
    reserva_mib = 2816   # 2g servidor + 768m cargador

    def env(self) -> dict:
        return {"CASSANDRA_DATA_DIR": self.datos.as_posix()}

    def preparar(self) -> None:
        dexec(self.contenedor, "cqlsh", "-f", "/scripts/esquema.cql", etiqueta=self.nombre, timeout=600)
        self.compose("up", "-d", "cargador")
        dexec(self.cargador, "pip", "install", "--quiet", "--no-cache-dir", "cassandra-driver",
              etiqueta=self.nombre, timeout=900)

    def cargar(self) -> dict:
        salida = f"/app/evidencia/{self.op.get('corrida', 'suelta')}"
        args = ["python", "scripts/carga_masiva.py", "--salida", salida]
        if self.op.get("cassandra_concurrencia"):
            args += ["--concurrencia", str(self.op["cassandra_concurrencia"])]
        dexec(self.cargador, *args, etiqueta=self.nombre, timeout=7200)
        carpeta = EVIDENCIA / "modulos" / "cassandra" / self.op.get("corrida", "suelta")
        informe = json.loads(sorted(carpeta.glob("carga_masiva_*.json"))[-1].read_text(encoding="utf-8"))
        r = informe["resultado"]
        return {"volumen": r["comentarios"], "unidad": "comentarios",
                "escrituras": r["escrituras_ok"], "errores": r["errores"],
                "tasa_propia": f"{r['escrituras_por_segundo']:,.0f} escrituras/s (medida por carga_masiva.py)",
                "parametros": informe["parametros"],
                "detalle": f"{r['comentarios']:,} comentarios = {r['escrituras_ok']:,} filas en 2 tablas "
                           f"(scripts/carga_masiva.py, concurrencia {informe['parametros']['concurrencia']})"}


class Redis(Base):
    nombre, carpeta, servicio, contenedor = "redis", "fixture2030-redis", "redis", "f30cm-redis"
    datos_en_carpeta = True
    reserva_mib = 512   # 512m servidor

    def env(self) -> dict:
        return {"REDIS_DATA_DIR": self.datos.as_posix(), "REDIS_PORT": str(REDIS_PUERTO)}

    def cargar(self) -> dict:
        # Igual que correr_volumen.sh del módulo: primero la muestra del hito (rankings y
        # votación, que son las claves que nombran partidos) y después los 100.000 usuarios.
        dexec(self.contenedor, "sh", "/scripts/carga_muestra.sh", etiqueta=self.nombre)
        sal = dexec(self.contenedor, "sh", "/scripts/carga_volumen.sh", "100000", etiqueta=self.nombre)
        m = re.search(r"conteo usuarios=(\d+) sesiones=(\d+) perfiles=(\d+)", sal)
        u = int(m.group(1)) if m else 0
        return {"volumen": u, "unidad": "usuarios",
                "comandos": u * 11,
                "detalle": f"carga_muestra.sh + carga_volumen.sh 100000: {m.group(0) if m else 'sin conteo'} "
                           "(11 comandos por usuario, redis-cli --pipe)"}


class InfluxDB(Base):
    nombre, carpeta, servicio, contenedor = "influxdb", "fixture2030-influxdb", "influxdb", "f30cm-influxdb"
    perfiles = ["herramientas"]
    datos_en_carpeta = True
    secretos = SECRETOS / "influxdb"
    reserva_mib = 2560   # 2g servidor + 512m herramientas

    def env(self) -> dict:
        return {"INFLUX_DATA_DIR": self.datos.as_posix(), "INFLUX_PORT": str(INFLUX_PUERTO)}

    def manifiesto(self) -> Path:
        return self.dir / "data" / "lp" / "completo" / "manifiesto.json"

    def generar_insumos(self) -> float | None:
        """generacion_puntos.py --perfil completo (determinista). Solo si faltan los archivos."""
        if self.manifiesto().exists():
            return None
        t0 = time.perf_counter()
        self.compose("run", "--rm", "--no-deps", "herramientas", "scripts/generacion_puntos.py",
                     "--perfil", "completo", timeout=7200)
        return time.perf_counter() - t0

    def limpiar(self) -> None:
        super().limpiar()
        shutil.rmtree(self.secretos, ignore_errors=True)   # el token muere con la instancia

    def apagar(self) -> None:
        super().apagar()
        shutil.rmtree(self.secretos, ignore_errors=True)

    def preparar(self) -> None:
        # scripts/inicializacion.sh del módulo, apuntado a ESTA instancia (variables opcionales
        # agregadas para esto): token de administración y las 3 bases con su retención.
        self.secretos.mkdir(parents=True, exist_ok=True)
        (EVIDENCIA / "modulos" / "influxdb").mkdir(parents=True, exist_ok=True)
        env = {**self.env(),
               "COMPOSE_PROJECT_NAME": self.proyecto,
               "COMPOSE_PATH_SEPARATOR": ";",
               "COMPOSE_FILE": f"docker-compose.yml;{self.override}",
               "SECRETS_DIR": "../fixture2030-carga-masiva/.secrets/influxdb",
               "EVIDENCIA_DIR": "../fixture2030-carga-masiva/evidencia/modulos/influxdb",
               "INFLUX_VOLUME": f"{PREFIJO}_influxdb_data"}
        correr(["sh", "scripts/inicializacion.sh"], cwd=self.dir, env=env, etiqueta=self.nombre, timeout=900)

    def cargar(self) -> dict:
        args = ["run", "--rm", "--no-deps", "--name", "f30cm-influxdb-cargador", "herramientas",
                "scripts/carga_lotes.py", "--perfil", "completo"]
        if self.op.get("influx_hilos"):
            args += ["--hilos", str(self.op["influx_hilos"])]
        if self.op.get("influx_lote"):
            args += ["--lote", str(self.op["influx_lote"])]
        sal = self.compose(*args, timeout=7200)
        m = re.search(r"Puntos confirmados por el servidor \| ([\d,]+)", sal)
        n = int(m.group(1).replace(",", "")) if m else 0
        t = re.search(r"\*\*Tasa de carga\*\* \| \*\*([\d,.]+) puntos/s", sal)
        return {"volumen": n, "unidad": "puntos",
                "tasa_propia": f"{t.group(1)} puntos/s (medida por carga_lotes.py)" if t else None,
                "detalle": f"{n:,} puntos en fixture2030_vivo (scripts/carga_lotes.py --perfil completo, "
                           f"lote {self.op.get('influx_lote') or 50000}, hilos {self.op.get('influx_hilos') or 8})"}


CLASES = {c.nombre: c for c in (MongoDB, Neo4j, Cassandra, Redis, InfluxDB)}
# Orden por defecto (secuencial y cola del modo paralelo). Cada base se verifica apenas
# termina su carga, así que las sesiones de Redis (TTL 1201-1800 s) se cuentan vivas.
ORDEN = ["mongodb", "neo4j", "cassandra", "influxdb", "redis"]


# ---------------------------------------------------------------------------
# Clientes mínimos para validar y medir
# ---------------------------------------------------------------------------
def mongo_json(contenedor: str, expresion_js: str):
    """Evalúa una expresión JS en mongosh (base fixture2030) y devuelve el resultado como JSON."""
    sal = dexec(contenedor, "mongosh", "--quiet", "fixture2030", "--eval",
                f"print(EJSON.stringify({expresion_js}, {{relaxed: true}}))", timeout=600)
    return json.loads(sal.strip().splitlines()[-1])


def cypher(consulta: str, **parametros) -> list[dict]:
    """Consulta por la API HTTP transaccional de Neo4j (puerto propio 37474)."""
    cuerpo = json.dumps({"statements": [{"statement": consulta, "parameters": parametros}]}).encode()
    req = urllib.request.Request(f"{NEO4J_HTTP}/db/neo4j/tx/commit", data=cuerpo, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Basic " + base64.b64encode(":".join(NEO4J_AUTH).encode()).decode())
    with urllib.request.urlopen(req, timeout=600) as r:
        resp = json.loads(r.read())
    if resp.get("errors"):
        raise ErrorPaso(f"Neo4j: {resp['errors']}")
    res = resp["results"][0]
    return [dict(zip(res["columns"], fila["row"])) for fila in res["data"]]


def cassandra_py(codigo: str, timeout: int = 1800):
    """Corre Python en el contenedor cargador de Cassandra (ya tiene cassandra-driver) y
    devuelve el JSON que el código imprime en su última línea."""
    pre = ("import json\nfrom cassandra.cluster import Cluster\n"
           "cl = Cluster(['cassandra']); s = cl.connect('fixture2030_comentarios')\n"
           "s.default_timeout = 120\n")
    sal = dexec(Cassandra.cargador, "python", "-", entrada=pre + codigo + "\ncl.shutdown()\n", timeout=timeout)
    return json.loads(sal.strip().splitlines()[-1])


def redis(*args: str, entrada: str | None = None) -> str:
    return dexec(Redis.contenedor, "redis-cli", *args, entrada=entrada, timeout=600)


def influx_sql(sql: str, base: str = "fixture2030_vivo") -> list[dict]:
    token = json.loads((InfluxDB.secretos / "admin-token.json").read_text(encoding="utf-8"))["token"]
    cuerpo = json.dumps({"db": base, "q": sql, "format": "json"}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{INFLUX_PUERTO}/api/v3/query_sql", data=cuerpo, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=900) as r:
        datos = r.read()
    return json.loads(datos) if datos.strip() else []


# ---------------------------------------------------------------------------
# Recursos: docker stats
# ---------------------------------------------------------------------------
_UNIDADES = {"b": 1, "kib": 1024, "mib": 1024 ** 2, "gib": 1024 ** 3, "kb": 1e3, "mb": 1e6, "gb": 1e9}


def a_bytes(texto: str) -> float:
    m = re.match(r"([\d.]+)\s*([a-zA-Z]+)", texto.strip())
    return float(m.group(1)) * _UNIDADES.get(m.group(2).lower(), 1) if m else 0.0


class Muestreador(threading.Thread):
    """Toma `docker stats --no-stream` en bucle (cada llamada tarda ~2 s) mientras dura la carga.
    Registra TODOS los contenedores: los f30cm-* son los de la prueba y el resto es la carga
    de fondo de la VM (otras instancias que no son de esta prueba).

    VIGÍA (después del cuelgue del 11/11): si la RAM de todos los contenedores llega a menos de
    `margen_vm_mib` del total de la VM, o la RAM disponible del host baja de `host_min_mib`,
    durante 3 muestras seguidas, o `docker stats` no contesta 2 veces seguidas (el motor se
    empieza a trabar), mata los contenedores f30cm-* y marca ABORTO: la corrida se corta y se
    informa, en vez de dejar que Docker Desktop se cuelgue."""

    def __init__(self, vm_mib: int | None = None, margen_vm_mib: int = 256, host_min_mib: int = 250):
        super().__init__(daemon=True)
        self.muestras: list[dict] = []
        self.host_libre: list[tuple] = []
        self.fase = "inicio"
        self.vm_mib, self.margen_vm_mib, self.host_min_mib = vm_mib, margen_vm_mib, host_min_mib
        self._alarmas = self._sin_respuesta = 0
        self._fin = threading.Event()

    def run(self) -> None:
        t0 = time.perf_counter()
        while not self._fin.is_set():
            try:
                sal = subprocess.run(["docker", "stats", "--no-stream", "--format",
                                      "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}"],
                                     capture_output=True, text=True, timeout=45).stdout
                self._sin_respuesta = 0
            except subprocess.TimeoutExpired:
                self._sin_respuesta += 1
                if self._sin_respuesta >= 2:
                    self.abortar("docker stats no respondió en 45 s, dos veces seguidas")
                continue
            t = round(time.perf_counter() - t0, 1)
            host = ram_libre_host_mib()
            self.host_libre.append((t, host))
            total = 0.0
            for linea in sal.strip().splitlines():
                nombre, cpu, mem = linea.split("|")
                b = a_bytes(mem.split("/")[0])
                total += b
                self.muestras.append({"t": t, "fase": self.fase, "contenedor": nombre,
                                      "cpu_pct": float(cpu.rstrip("%") or 0), "mem_bytes": b})
            total_mib = total / 2 ** 20
            motivo = None
            if self.vm_mib and total_mib > self.vm_mib - self.margen_vm_mib:
                motivo = f"contenedores {total_mib:,.0f} MiB de {self.vm_mib:,} MiB de la VM"
            elif host is not None and host < self.host_min_mib:
                motivo = f"RAM disponible del host {host} MiB (< {self.host_min_mib})"
            self._alarmas = self._alarmas + 1 if motivo else 0
            if motivo:
                log(f"⚠ vigía: {motivo} ({self._alarmas}/3)")
            if self._alarmas >= 3:
                self.abortar(motivo)

    def abortar(self, motivo: str) -> None:
        global ABORTO
        if ABORTO:
            return
        ABORTO = motivo
        log(f"✖ VIGÍA: corto la corrida — {motivo}. Mato los contenedores f30cm-*.")
        try:
            ids = subprocess.run(["docker", "ps", "-q", "--filter", f"name={PREFIJO}-"],
                                 capture_output=True, text=True, timeout=60).stdout.split()
            if ids:
                subprocess.run(["docker", "kill", *ids], capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            log("✖ VIGÍA: docker no respondió al kill")
        self._fin.set()

    def detener(self) -> None:
        self._fin.set()
        self.join(timeout=90)

    def resumen(self) -> dict:
        por: dict[str, dict] = {}
        instantes: dict[float, dict] = {}
        for m in self.muestras:
            c = por.setdefault(m["contenedor"], {"cpu": [], "mem": []})
            c["cpu"].append(m["cpu_pct"])
            c["mem"].append(m["mem_bytes"])
            i = instantes.setdefault(m["t"], {"prueba_mem": 0.0, "prueba_cpu": 0.0, "otros_mem": 0.0})
            if m["contenedor"].startswith(PREFIJO):
                i["prueba_mem"] += m["mem_bytes"]
                i["prueba_cpu"] += m["cpu_pct"]
            else:
                i["otros_mem"] += m["mem_bytes"]
        contenedores = {
            n: {"muestras": len(v["cpu"]), "cpu_prom_pct": round(sum(v["cpu"]) / len(v["cpu"]), 1),
                "cpu_max_pct": round(max(v["cpu"]), 1), "mem_max_mib": round(max(v["mem"]) / 2 ** 20)}
            for n, v in sorted(por.items()) if n.startswith(PREFIJO)}
        otros = {n: round(max(v["mem"]) / 2 ** 20) for n, v in por.items() if not n.startswith(PREFIJO)}
        pico = max(instantes.values(), key=lambda i: i["prueba_mem"] + i["otros_mem"], default={})
        return {
            "muestras": len(instantes),
            "contenedores_prueba": contenedores,
            "pico_mem_prueba_mib": round(max((i["prueba_mem"] for i in instantes.values()), default=0) / 2 ** 20),
            "pico_cpu_prueba_pct": round(max((i["prueba_cpu"] for i in instantes.values()), default=0), 1),
            "pico_mem_total_vm_mib": round((pico.get("prueba_mem", 0) + pico.get("otros_mem", 0)) / 2 ** 20),
            "mem_otros_contenedores_mib": round(sum(otros.values())),
            "otros_contenedores": len(otros),
            "ram_libre_host_min_mib": min((v for _, v in self.host_libre if v is not None), default=None),
        }

    def csv(self, ruta: Path) -> None:
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("t_s,fase,contenedor,cpu_pct,mem_mib\n")
            for m in self.muestras:
                if m["contenedor"].startswith(PREFIJO):
                    f.write(f"{m['t']},{m['fase']},{m['contenedor']},{m['cpu_pct']},{m['mem_bytes'] / 2 ** 20:.1f}\n")


def ram_libre_host_mib() -> int | None:
    """RAM física libre de la notebook. En Windows la VM de Docker (WSL2) vive dentro de esa
    RAM: si el host se queda sin memoria, Windows pagina la VM y el motor de Docker se cuelga
    aunque adentro de la VM "sobre" memoria (es lo que pasó el 11/11, ver evidencia/cuelgue_*)."""
    if os.name == "nt":
        import ctypes

        class Estado(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        e = Estado()
        e.dwLength = ctypes.sizeof(Estado)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(e))
        return int(e.ullAvailPhys / 2 ** 20)
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            return next(int(x.split()[1]) // 1024 for x in f if x.startswith("MemAvailable:"))
    except (OSError, StopIteration):
        return None


def memoria_contenedores_mib() -> dict:
    """RAM que ocupan ahora los contenedores, separando los de la prueba (f30cm-*) del resto."""
    sal = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.Name}}|{{.MemUsage}}"],
                         capture_output=True, text=True, timeout=120).stdout
    res = {"prueba": 0.0, "ajenos": 0.0, "ajenos_cantidad": 0}
    for linea in sal.strip().splitlines():
        nombre, mem = linea.split("|")
        clave = "prueba" if nombre.startswith(PREFIJO) else "ajenos"
        res[clave] += a_bytes(mem.split("/")[0]) / 2 ** 20
        res["ajenos_cantidad"] += clave == "ajenos"
    return {k: round(v) for k, v in res.items()}


def memoria_vm_bytes() -> int:
    return int(subprocess.run(["docker", "info", "--format", "{{.MemTotal}}"],
                              capture_output=True, text=True).stdout.strip() or 0)


def cpus_vm() -> int:
    return int(subprocess.run(["docker", "info", "--format", "{{.NCPU}}"],
                              capture_output=True, text=True).stdout.strip() or 0)
