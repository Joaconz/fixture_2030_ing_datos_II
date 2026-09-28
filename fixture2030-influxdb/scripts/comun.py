"""
Fixture 2030 — Hito 8 · Series temporales (InfluxDB 2)
ARCHIVO: scripts/comun.py
PROPÓSITO: piezas compartidas por todos los scripts (solo biblioteca estándar):
  1. conexión HTTP a InfluxDB 2 (escritura line protocol, consultas Flux, API de buckets);
  2. lectura de la autorización local (secrets/admin-token.json, fuera del repositorio);
  3. calendario CANÓNICO de los 112 partidos, idéntico al del Hito 5 (Neo4j);
  4. guardado de evidencia con fecha, versión y recursos del ambiente (RNF10).

VERSIÓN: `influxdb:latest` = InfluxDB v2.9.1 (observado el 28/09/2026). Lenguaje de consulta:
Flux. Organización de los datos: organización > bucket > measurement > series.

COHERENCIA CON EL HITO 5 (Neo4j)
--------------------------------
Los partidos, sus fechas, sedes, equipos y los goles de la fase de grupos se
calculan con las MISMAS fórmulas de fixture2030-neo4j/queries/carga.cypher
(pasos 2, 4, 6, 7, 12 y 13). Por eso `partido_id`, `equipo_id` y `sede_id` de
este módulo son los mismos identificadores del grafo (y los `partido_id` son
los mismos del Hito 6 y del Hito 7).
"""
from __future__ import annotations

import csv
import io
import json
import os
import platform
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc

# ---------------------------------------------------------------------------
# Conexión
# ---------------------------------------------------------------------------
INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
TOKEN_FILE = Path(os.getenv("TOKEN_FILE", "secrets/admin-token.json"))

DB_VIVO = "fixture2030_vivo"               # bucket: detalle por segundo, retención 45 d
DB_HISTORICO = "fixture2030_historico"     # bucket: resúmenes, sin vencimiento
DB_PRUEBA_RETENCION = "fixture2030_prueba_retencion"  # bucket: retención 1 h (demostración)

PRECISION = "s"  # precisión declarada de TODOS los timestamps del módulo: segundos (RNF6)


def _credenciales() -> dict:
    if not TOKEN_FILE.exists():
        raise SystemExit(f"No existe {TOKEN_FILE}. Corré primero: sh scripts/inicializacion.sh")
    return json.loads(TOKEN_FILE.read_text(encoding="utf-8"))


def token() -> str:
    """Token de laboratorio. Nunca se imprime ni se guarda en evidencia (RNF7)."""
    return _credenciales()["token"]


def org() -> str:
    return _credenciales().get("org", "fixture2030")


def _peticion(metodo: str, ruta: str, cuerpo: bytes | None = None,
              cabeceras: dict | None = None, timeout: int = 300, auth: bool = True) -> tuple[int, bytes]:
    req = urllib.request.Request(INFLUX_URL + ruta, data=cuerpo, method=metodo)
    if auth:
        req.add_header("Authorization", f"Token {token()}")
    for k, v in (cabeceras or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def escribir_lp(bucket: str, lineas: bytes, gzip_body: bool = False) -> tuple[int, bytes]:
    """POST /api/v2/write con precisión en segundos. Si una línea es inválida, InfluxDB
    rechaza el lote entero (HTTP 400): no hay escrituras parciales silenciosas."""
    cab = {"Content-Type": "text/plain; charset=utf-8"}
    cuerpo = lineas
    if gzip_body:
        import gzip
        cuerpo = gzip.compress(lineas, compresslevel=1)
        cab["Content-Encoding"] = "gzip"
    q = urllib.parse.urlencode({"org": org(), "bucket": bucket, "precision": PRECISION})
    return _peticion("POST", f"/api/v2/write?{q}", cuerpo, cab)


def _convertir(v: str):
    if v == "":
        return None
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if re.fullmatch(r"-?\d+\.\d*(e[-+]?\d+)?|-?\d+e[-+]?\d+", v, re.IGNORECASE):
        return float(v)
    return v


def consultar(flux: str, tipos: bool = False):
    """POST /api/v2/query con Flux -> lista de filas (dict). Con tipos=True devuelve además
    {columna: tipo} leído de la anotación #datatype del CSV (long, double, string, dateTime)."""
    dialecto = {"header": True, "delimiter": ",", "annotations": ["datatype"] if tipos else []}
    cuerpo = json.dumps({"query": flux, "type": "flux", "dialect": dialecto}).encode("utf-8")
    q = urllib.parse.urlencode({"org": org()})
    estado, resp = _peticion("POST", f"/api/v2/query?{q}", cuerpo,
                             {"Content-Type": "application/json", "Accept": "application/csv"})
    if estado != 200:
        raise RuntimeError(f"HTTP {estado}: {resp.decode('utf-8', 'replace')[:600]}")
    texto = resp.decode("utf-8").replace("\r\n", "\n")
    filas, tipos_col = [], {}
    for bloque in texto.split("\n\n"):
        lineas = [ln for ln in bloque.split("\n") if ln.strip()]
        if not lineas:
            continue
        dt = None
        for ln in lineas:
            if ln.startswith("#datatype"):
                dt = next(csv.reader([ln]))
        lineas = [ln for ln in lineas if not ln.startswith("#")]   # #datatype, #group, #default
        if not lineas:
            continue
        lector = csv.reader(io.StringIO("\n".join(lineas)))
        encabezado = next(lector, None)
        if not encabezado:
            continue
        if "error" in encabezado and "reference" in encabezado:
            fila = next(lector, [])
            raise RuntimeError(f"Error de Flux: {dict(zip(encabezado, fila)).get('error')}")
        if dt:
            tipos_col.update({c: t for c, t in zip(encabezado, dt) if c not in ("", "result", "table")})
        for fila in lector:
            d = {c: _convertir(v) for c, v in zip(encabezado, fila) if c not in ("", "result", "table")}
            filas.append(d)
    return (filas, tipos_col) if tipos else filas


def buckets() -> list[dict]:
    q = urllib.parse.urlencode({"org": org(), "limit": 100})
    estado, resp = _peticion("GET", f"/api/v2/buckets?{q}")
    if estado != 200:
        raise RuntimeError(f"HTTP {estado}: {resp[:300]!r}")
    return json.loads(resp)["buckets"]


def metricas() -> str:
    """Endpoint /metrics (formato Prometheus) del servidor: tamaño de shards, archivos TSM, etc."""
    estado, resp = _peticion("GET", "/metrics", auth=False)
    return resp.decode("utf-8", "replace") if estado == 200 else ""


def version_servidor() -> str:
    estado, resp = _peticion("GET", "/health", auth=False)
    if estado == 200:
        d = json.loads(resp)
        return f"InfluxDB {d.get('version', '?')} (commit {d.get('commit', '?')})"
    return f"desconocida (HTTP {estado})"


def rfc3339(dt: datetime) -> str:
    """Literal de tiempo para Flux: 2030-06-29T16:00:00Z (sin comillas)."""
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Calendario canónico (Hito 5)
# ---------------------------------------------------------------------------
# Orden = rankingFifa (1..64). Idéntico a carga.cypher, PASO 4. No reordenar.
EQUIPOS = ['ARG', 'URU', 'BRA', 'COL', 'ECU', 'PAR', 'CHI', 'PER', 'BOL', 'VEN', 'ESP', 'FRA',
           'ENG', 'GER', 'POR', 'ITA', 'NED', 'BEL', 'CRO', 'DEN', 'SUI', 'POL', 'SRB', 'AUT',
           'UKR', 'SCO', 'NOR', 'SWE', 'TUR', 'CZE', 'HUN', 'GRE', 'ROU', 'WAL', 'MAR', 'SEN',
           'EGY', 'NGA', 'ALG', 'TUN', 'CMR', 'GHA', 'CIV', 'MLI', 'RSA', 'COD', 'JPN', 'KOR',
           'IRN', 'AUS', 'KSA', 'QAT', 'IRQ', 'UZB', 'UAE', 'MEX', 'USA', 'CAN', 'CRC', 'JAM',
           'PAN', 'HON', 'NZL', 'FIJ']
GRUPOS = "ABCDEFGHIJKLMNOP"
SEDES = ['URU-CEN', 'ARG-MON', 'PAR-DCH', 'ESP-BER', 'ESP-CAM', 'ESP-MET', 'ESP-CAR', 'ESP-SMA',
         'ESP-MES', 'ESP-RIA', 'POR-LUZ', 'POR-ALV', 'POR-DRA', 'MAR-HAS', 'MAR-MOU', 'MAR-MAR']
CRUCES = [(0, 1), (2, 3), (0, 2), (1, 3), (0, 3), (1, 2)]

# Reloj de pared de un partido (segundos desde el inicio programado)
FIN_PRIMER_TIEMPO = 47 * 60          # 0'–47' (incluye descuento)
INICIO_SEGUNDO_TIEMPO = 62 * 60      # 15 min de entretiempo SIN feed de estadísticas
FIN_SEGUNDO_TIEMPO = 110 * 60        # 48 min de segundo tiempo
AUDIENCIA_DESDE = -15 * 60           # la audiencia se mide desde 15' antes del inicio
AUDIENCIA_HASTA = 130 * 60           # hasta 20' después del final


def segundo_de_minuto(minuto: int) -> int:
    """Minuto de juego (como en los eventos del Hito 5) → segundo de reloj de pared."""
    if minuto < 45:
        return minuto * 60 + 30
    return INICIO_SEGUNDO_TIEMPO + (minuto - 45) * 60 + 30


def minuto_de_segundo(s: int) -> int:
    """Segundo de reloj de pared → minuto de juego (inverso aproximado)."""
    if s < INICIO_SEGUNDO_TIEMPO:
        return s // 60
    return 45 + (s - INICIO_SEGUNDO_TIEMPO) // 60


@dataclass
class Partido:
    partido_id: str
    fase: str
    grupo: str | None
    local: str
    visitante: str
    sede_id: str
    inicio: datetime
    orden_global: int
    goles: list = field(default_factory=list)   # [(segundo_pared, 'LOCAL'|'VISITANTE')]
    audiencia: str = "NORMAL"                   # NORMAL | ALTA | MAXIMA
    pico_usuarios: int = 0

    @property
    def inicio_epoch(self) -> int:
        return int(self.inicio.timestamp())


def ranking(eq: str) -> int:
    return EQUIPOS.index(eq) + 1


def _goles_grupos(orden_global: int) -> list:
    """Plantilla de eventos del Hito 5 (PASO 7): gol LOCAL al 13'; si orden%3==1 gol
    VISITANTE al 75'; si orden%3==2 gol LOCAL al 82'."""
    goles = [(segundo_de_minuto(13), "LOCAL")]
    if orden_global % 3 == 1:
        goles.append((segundo_de_minuto(75), "VISITANTE"))
    elif orden_global % 3 == 2:
        goles.append((segundo_de_minuto(82), "LOCAL"))
    return goles


def _goles_d16(partido_id: str) -> list:
    """El Hito 5 deja los dieciseisavos PROGRAMADOS (sin eventos). El Hito 6 ya los trató
    como jugados (comentarios). Acá se simulan con una regla determinista propia."""
    import random
    rng = random.Random(f"goles-{partido_id}")
    goles = []
    for _ in range(rng.randint(1, 4)):
        minuto = rng.choice([m for m in range(2, 92) if m != 45])
        goles.append((segundo_de_minuto(minuto), rng.choice(["LOCAL", "VISITANTE"])))
    return sorted(goles)


def calendario() -> list[Partido]:
    """Los 112 partidos del Hito 5 (96 de grupos + 16 de dieciseisavos)."""
    partidos: list[Partido] = []
    base_grupos = datetime(2030, 6, 9, 13, 0, tzinfo=UTC)
    tablas: dict[int, list] = {}
    for orden in range(1, 17):
        g = GRUPOS[orden - 1]
        eqs = sorted([e for e in EQUIPOS if (ranking(e) - 1) % 16 == orden - 1], key=ranking)
        puntos = {e: [0, 0, 0] for e in eqs}  # pts, dif, gf
        for k, (a, b) in enumerate(CRUCES):
            jornada = k // 2 + 1
            og = (orden - 1) * 6 + k
            inicio = base_grupos + timedelta(days=(jornada - 1) * 5 + (orden - 1) % 4,
                                             hours=((orden - 1) // 4) * 3)
            p = Partido(f"PAR-{g}-{k + 1}", "GRUPOS", g, eqs[a], eqs[b], SEDES[og % 16], inicio, og,
                        goles=_goles_grupos(og))
            gl = sum(1 for _, c in p.goles if c == "LOCAL")
            gv = sum(1 for _, c in p.goles if c == "VISITANTE")
            for eq, gf, gc in ((p.local, gl, gv), (p.visitante, gv, gl)):
                puntos[eq][0] += 3 if gf > gc else 1 if gf == gc else 0
                puntos[eq][1] += gf - gc
                puntos[eq][2] += gf
            partidos.append(p)
        # Desempate del Hito 5 (PASO 13): pts DESC, dif DESC, gf DESC, equipoId ASC
        tablas[orden] = sorted(eqs, key=lambda e: (-puntos[e][0], -puntos[e][1], -puntos[e][2], e))

    base_d16 = datetime(2030, 6, 29, 16, 0, tzinfo=UTC)
    for i in range(16):
        pid = f"PAR-D16-{i + 1:02d}"
        loc = tablas[i + 1][0]                 # 1° del grupo N
        vis = tablas[((i + 1) % 16) + 1][1]    # 2° del grupo N+1, en anillo
        inicio = base_d16 + timedelta(days=i // 4, hours=(i % 4) * 3)
        partidos.append(Partido(pid, "DIECISEISAVOS", None, loc, vis, SEDES[i], inicio, 96 + i,
                                goles=_goles_d16(pid)))

    # Audiencia esperada (misma clasificación que el Hito 6: PAR-D16-01 = MAXIMA)
    for p in partidos:
        suma_rank = ranking(p.local) + ranking(p.visitante)            # 3 (más atractivo) .. 127
        atractivo = 0.35 + 0.65 * (127 - suma_rank) / 124
        if p.partido_id == "PAR-D16-01":
            p.audiencia, p.pico_usuarios = "MAXIMA", 2_500_000
        elif p.fase == "DIECISEISAVOS":
            p.audiencia, p.pico_usuarios = "ALTA", int(1_200_000 + 600_000 * atractivo)
        else:
            p.audiencia, p.pico_usuarios = "NORMAL", int(1_500_000 * atractivo)
    return sorted(partidos, key=lambda p: (p.inicio, p.partido_id))


# ---------------------------------------------------------------------------
# Evidencia (RNF10)
# ---------------------------------------------------------------------------
EVIDENCIA_DIR = Path(os.getenv("EVIDENCIA_DIR", "evidencia"))


def ambiente() -> dict:
    mem = None
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            mem = round(int(f.readline().split()[1]) / 1024 / 1024, 1)
    except OSError:
        pass
    return {"cpus_visibles": os.cpu_count(), "memoria_gb_visible": mem,
            "python": platform.python_version(), "plataforma": platform.platform()}


def guardar_evidencia(nombre: str, markdown: str, datos: dict | None = None) -> Path:
    EVIDENCIA_DIR.mkdir(parents=True, exist_ok=True)
    sello = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    ruta = EVIDENCIA_DIR / f"{nombre}_{sello}.md"
    ruta.write_text(markdown, encoding="utf-8")
    if datos is not None:
        (EVIDENCIA_DIR / f"{nombre}_{sello}.json").write_text(
            json.dumps(datos, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return ruta


def encabezado(titulo: str) -> list[str]:
    return [f"# {titulo}", "",
            f"- Fecha de ejecución (UTC): {datetime.now(UTC).isoformat(timespec='seconds')}",
            f"- Servidor: {version_servidor()}",
            f"- Ambiente del cliente: {ambiente()}", ""]


def tabla_md(filas: list[dict], columnas: list[str] | None = None, max_filas: int = 40) -> str:
    if not filas:
        return "_(sin filas)_"
    cols = columnas or list(filas[0].keys())
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for f in filas[:max_filas]:
        out.append("| " + " | ".join("" if f.get(c) is None else str(f.get(c)) for c in cols) + " |")
    if len(filas) > max_filas:
        out.append(f"\n_… {len(filas) - max_filas} filas más_")
    return "\n".join(out)


def cronometro():
    t0 = time.perf_counter()
    return lambda: time.perf_counter() - t0
