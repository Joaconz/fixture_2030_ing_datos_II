"""Piezas comunes del Hito 11: configuración, redacción de secretos y registro de evidencia.

Lo usan todos los scripts de prueba (biblioteca estándar únicamente: corre con
cualquier python3 >= 3.10 y también con el .venv de la API).

- `cargar_config()`: lee config/configuracion-ejemplo.env, después
  config/configuracion.env (local, ignorado por git) y por último el entorno.
  Nunca evalúa los archivos como código (sólo líneas CLAVE=valor).
- `secretos(cfg)`: contraseñas y tokens que se cargan para las pruebas. Sólo se
  usan para (a) conectarse y (b) borrarlos de toda salida.
- `redactar(texto)`: borra secretos, URIs con credenciales, tokens `apiv3_…`,
  cabeceras Authorization y la ruta del home (RNF7 / RNF8).
- `Registro`: agrega un resultado por prueba en JSONL + Markdown, con fecha,
  commit, entorno, origen, producto, capa, objetivo, resultado, latencia,
  interpretación y lo que la prueba NO demuestra (RNF17 / RNF18).

Uso por línea de comandos (desde los scripts bash):
    python3 registro.py agregar --archivo resultados_clientes --producto redis \
        --capa protocolo --prueba "redis-cli PING" --objetivo 127.0.0.1:6379 \
        --resultado OK --detalle PONG --interpretacion "…" --no-demuestra "…"
    python3 registro.py config CLAVE              # imprime un valor de configuración (no secretos)
    python3 registro.py redactar < archivo        # filtra stdin
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HITO_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = HITO_DIR.parent
EVIDENCIA_DIR = HITO_DIR / "docs" / "evidencia"

RESULTADOS = ("OK", "WARN", "FAIL", "SKIP", "N/C")
CAPAS = ("configuracion", "resolucion", "tcp", "protocolo", "autenticacion", "autorizacion",
         "contexto", "operacion", "api")
CLAVES_SECRETAS = ("NEO4J_PASSWORD", "MONGO_PASSWORD", "REDIS_PASSWORD", "INFLUX_TOKEN",
                   "CASSANDRA_PASSWORD", "IRIS_PASSWORD")
RUTAS = ("API_DIR", "NEO4J_ENV_FILE", "INFLUX_TOKEN_FILE")


# --------------------------------------------------------------------------- configuración
def _leer_env(archivo: Path) -> dict[str, str]:
    valores: dict[str, str] = {}
    if not archivo.is_file():
        return valores
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        clave = clave.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", clave):
            continue
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        valores[clave] = valor
    return valores


def cargar_config() -> dict[str, str]:
    cfg = _leer_env(HITO_DIR / "config" / "configuracion-ejemplo.env")
    origen = {k: "configuracion-ejemplo.env" for k in cfg}
    local = _leer_env(HITO_DIR / "config" / "configuracion.env")
    cfg.update(local)
    origen.update({k: "configuracion.env" for k in local})
    for k in list(cfg) + list(CLAVES_SECRETAS):
        if k in os.environ:
            cfg[k] = os.environ[k]
            origen[k] = "entorno"
    for k in RUTAS:   # relativas a la carpeta del hito, para poder correr desde cualquier lado
        if cfg.get(k) and not Path(cfg[k]).is_absolute():
            cfg[k] = str((HITO_DIR / cfg[k]).resolve())
    cfg["_ORIGEN"] = json.dumps(origen)
    return cfg


def origen_de(cfg: dict[str, str], clave: str) -> str:
    return json.loads(cfg.get("_ORIGEN", "{}")).get(clave, "no definido")


def neo4j_password(cfg: dict[str, str]) -> tuple[str | None, str]:
    """(contraseña, de dónde salió). Nunca se imprime el valor."""
    if cfg.get("NEO4J_PASSWORD"):
        return cfg["NEO4J_PASSWORD"], origen_de(cfg, "NEO4J_PASSWORD")
    archivo = Path(cfg.get("NEO4J_ENV_FILE", ""))
    valor = _leer_env(archivo).get("NEO4J_PASSWORD") if archivo.is_file() else None
    if valor:
        return valor, f"archivo {ruta_publica(archivo)}"
    return None, "no definida"


def influx_token(cfg: dict[str, str]) -> tuple[str | None, str]:
    if cfg.get("INFLUX_TOKEN"):
        return cfg["INFLUX_TOKEN"], origen_de(cfg, "INFLUX_TOKEN")
    archivo = Path(cfg.get("INFLUX_TOKEN_FILE", ""))
    try:
        return json.loads(archivo.read_text(encoding="utf-8"))["token"], f"archivo {ruta_publica(archivo)}"
    except (OSError, ValueError, KeyError):
        return None, "no definido"


def valores_publicos(cfg: dict[str, str]) -> set[str]:
    """Valores que ya son públicos: la configuración no secreta y los defaults
    documentados en los `.env.example` versionados (p. ej. la contraseña de
    desarrollo de Neo4j, que coincide con el nombre de la base de Mongo)."""
    publicos = {v for k, v in cfg.items() if k not in CLAVES_SECRETAS and not k.startswith("_")}
    for ejemplo in REPO_DIR.glob("fixture2030-*/.env.example"):
        publicos |= set(_leer_env(ejemplo).values())
    return publicos


def secretos(cfg: dict[str, str] | None = None) -> list[str]:
    """Valores a borrar de toda salida. Un secreto igual a un valor público no
    se borra (destruiría la evidencia sin proteger nada); prueba_config lo marca WARN."""
    cfg = cfg or cargar_config()
    valores = [cfg.get(k, "") for k in CLAVES_SECRETAS]
    valores += [neo4j_password(cfg)[0] or "", influx_token(cfg)[0] or ""]
    publicos = valores_publicos(cfg)
    return sorted({v for v in valores if v and len(v) >= 4 and v not in publicos}, key=len, reverse=True)


# --------------------------------------------------------------------------- redacción
_HOME = str(Path.home())
_PATRONES = [
    (re.compile(r"(?i)(authorization:\s*bearer\s+)\S+"), r"\1***REDACTADO***"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{8,}"), r"\1***REDACTADO***"),
    (re.compile(r"apiv3_[A-Za-z0-9_\-]+"), "apiv3_***REDACTADO***"),
    (re.compile(r"(?i)\b([a-z][a-z0-9+.\-]*://)([^/\s:@]+):([^/\s@]+)@"), r"\1***:***@"),
    (re.compile(r"(?i)\b(password|passwd|pwd|token|secret)(\s*[=:]\s*)([^\s,;\"']+)"), r"\1\2***REDACTADO***"),
]


def ruta_publica(ruta: Path | str) -> str:
    texto = str(ruta)
    try:
        return str(Path(texto).resolve().relative_to(REPO_DIR))
    except ValueError:
        return texto.replace(_HOME, "~")


def redactar(texto: str, extra: list[str] | None = None) -> str:
    for valor in (extra if extra is not None else _SECRETOS_CACHE()):
        texto = texto.replace(valor, "***REDACTADO***")
    for patron, reemplazo in _PATRONES:
        texto = patron.sub(reemplazo, texto)
    return texto.replace(str(REPO_DIR), "<repo>").replace(_HOME, "~")


_cache: list[str] | None = None


def _SECRETOS_CACHE() -> list[str]:  # noqa: N802
    global _cache
    if _cache is None:
        _cache = secretos()
    return _cache


# --------------------------------------------------------------------------- contexto (RNF18)
def commit_actual() -> str:
    try:
        sha = subprocess.run(["git", "-C", str(HITO_DIR), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        sucio = subprocess.run(["git", "-C", str(HITO_DIR), "status", "--porcelain", "--", "."],
                               capture_output=True, text=True, timeout=5).stdout.strip()
        return (sha or "sin-git") + ("+cambios-locales" if sucio else "")
    except (OSError, subprocess.SubprocessError):
        return "sin-git"


def origen_ejecucion() -> str:
    """Desde dónde corre la prueba (RNF3). Sin hostname ni usuario (RNF7)."""
    dentro = Path("/.dockerenv").exists()
    lugar = "contenedor" if dentro else "notebook (host)"
    return f"{lugar} · {platform.system()} {platform.machine()} · python {platform.python_version()}"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sello() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def directorio_corrida() -> Path:
    """Carpeta de la corrida actual. evaluar_conectividad.sh fija CORRIDA_DIR para
    que todos los módulos de una misma ejecución escriban juntos."""
    d = os.environ.get("CORRIDA_DIR")
    ruta = Path(d) if d else EVIDENCIA_DIR / "corridas" / f"{sello()}_suelta"
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


# --------------------------------------------------------------------------- registro
class Registro:
    def __init__(self, nombre: str, titulo: str | None = None) -> None:
        self.dir = directorio_corrida()
        self.jsonl = self.dir / f"{nombre}.jsonl"
        self.md = self.dir / f"{nombre}.md"
        self.cfg = cargar_config()
        if not self.md.exists():
            cab = [f"# {titulo or nombre}", "",
                   f"- Fecha (UTC) de inicio: {ahora()}",
                   f"- Commit: `{commit_actual()}`",
                   f"- Entorno: {self.cfg.get('ENTORNO', '-')}",
                   f"- Origen de la prueba: {origen_ejecucion()}",
                   f"- Timeouts: conexión {self.cfg.get('CONNECT_TIMEOUT')} s · operación "
                   f"{self.cfg.get('OPERACION_TIMEOUT')} s · API {self.cfg.get('API_TIMEOUT')} s",
                   "- Secretos: ninguno se imprime; toda salida pasa por `registro.redactar` (RNF7/RNF8).",
                   "", "| Fecha (UTC) | Producto | Capa | Prueba | Objetivo / contexto | Resultado | ms | Detalle | Interpretación | No demuestra |",
                   "|---|---|---|---|---|---|---:|---|---|---|"]
            self.md.write_text("\n".join(cab) + "\n", encoding="utf-8")

    def agregar(self, *, producto: str, capa: str, prueba: str, objetivo: str, resultado: str,
                detalle: str = "", interpretacion: str = "", no_demuestra: str = "",
                latencia_ms: float | None = None, **extra: object) -> dict[str, object]:
        if resultado not in RESULTADOS:
            raise ValueError(f"resultado inválido: {resultado}")
        if capa not in CAPAS:
            raise ValueError(f"capa inválida: {capa}")
        fila: dict[str, object] = {
            "ts": ahora(), "commit": commit_actual(), "entorno": self.cfg.get("ENTORNO", "-"),
            "origen": origen_ejecucion(), "producto": producto, "capa": capa, "prueba": prueba,
            "objetivo": objetivo, "resultado": resultado,
            "latencia_ms": None if latencia_ms is None else round(latencia_ms, 1),
            "detalle": detalle, "interpretacion": interpretacion, "no_demuestra": no_demuestra,
        }
        fila.update(extra)
        texto = redactar(json.dumps(fila, ensure_ascii=False, default=str))
        fila = json.loads(texto)
        with self.jsonl.open("a", encoding="utf-8") as f:
            f.write(texto + "\n")
        celdas = [fila["ts"], producto, capa, f"`{fila['prueba']}`", f"`{fila['objetivo']}`",
                  f"**{resultado}**", "" if fila["latencia_ms"] is None else str(fila["latencia_ms"]),
                  fila["detalle"], fila["interpretacion"], fila["no_demuestra"]]
        with self.md.open("a", encoding="utf-8") as f:
            f.write("| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in celdas) + " |\n")
        print(f"[{resultado:<4}] {producto:<9} {capa:<13} {fila['prueba'][:48]:<48} {fila['detalle'][:70]}")
        sys.stdout.flush()
        return fila

    def nota(self, texto: str) -> None:
        """Párrafo libre al final del Markdown (ya redactado)."""
        with self.md.open("a", encoding="utf-8") as f:
            f.write("\n" + redactar(texto) + "\n")


def leer_corrida(directorio: Path) -> list[dict[str, object]]:
    filas: list[dict[str, object]] = []
    for archivo in sorted(directorio.glob("*.jsonl")):
        if archivo.stem.endswith("_logs") or archivo.stem == "matriz":
            continue          # extractos de log: otro esquema
        for linea in archivo.read_text(encoding="utf-8").splitlines():
            if linea.strip():
                fila = json.loads(linea)
                fila["_archivo"] = archivo.stem
                filas.append(fila)
    return filas


# --------------------------------------------------------------------------- CLI
def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("agregar")
    a.add_argument("--archivo", required=True)
    a.add_argument("--titulo")
    for campo in ("producto", "capa", "prueba", "objetivo", "resultado"):
        a.add_argument(f"--{campo}", required=True)
    for campo in ("detalle", "interpretacion", "no-demuestra"):
        a.add_argument(f"--{campo}", default="")
    a.add_argument("--latencia-ms", type=float)
    c = sub.add_parser("config")
    c.add_argument("clave")
    sub.add_parser("redactar")
    args = p.parse_args()

    if args.cmd == "agregar":
        Registro(args.archivo, args.titulo).agregar(
            producto=args.producto, capa=args.capa, prueba=args.prueba, objetivo=args.objetivo,
            resultado=args.resultado, detalle=args.detalle, interpretacion=args.interpretacion,
            no_demuestra=args.no_demuestra, latencia_ms=args.latencia_ms)
    elif args.cmd == "config":
        if args.clave in CLAVES_SECRETAS:
            print("se niega a imprimir un secreto", file=sys.stderr)
            return 2
        print(cargar_config().get(args.clave, ""))
    elif args.cmd == "redactar":
        sys.stdout.write(redactar(sys.stdin.read()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
