"""Capa 0 — configuración (RF3, RNF2, RNF7).

Antes de abrir un socket: ¿están definidos y bien formados los valores que va a
usar cada prueba? ¿De dónde sale cada uno (ejemplo, archivo local, entorno)?
¿Los secretos existen sin mostrarlos y sus archivos están fuera de git? ¿La
configuración del hito coincide con la que usa la API del Hito 10?

    python3 scripts/prueba_config.py [--producto mongodb|neo4j|cassandra|redis|influxdb|iris|api]

Qué NO demuestra: que los valores sean los correctos para el servidor real
(eso lo dicen las capas siguientes).
"""
from __future__ import annotations

import argparse
import os
import stat
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from registro import (REPO_DIR, Registro, cargar_config, influx_token, neo4j_password,  # noqa: E402
                      origen_de, ruta_publica, valores_publicos)

R = Registro("resultados_config", "Capa 0 — configuración")
CFG = cargar_config()

VARIABLES = {
    "api": [("API_URL", "url")],
    "mongodb": [("MONGO_HOST", "host"), ("MONGO_PORT", "puerto"), ("MONGO_DB", "nombre")],
    "neo4j": [("NEO4J_HOST", "host"), ("NEO4J_BOLT_PORT", "puerto"), ("NEO4J_HTTP_PORT", "puerto"),
              ("NEO4J_DATABASE", "nombre"), ("NEO4J_USER", "nombre")],
    "cassandra": [("CASSANDRA_HOST", "host"), ("CASSANDRA_PORT", "puerto"), ("CASSANDRA_KEYSPACE", "nombre"),
                  ("CASSANDRA_DC", "nombre")],
    "redis": [("REDIS_HOST", "host"), ("REDIS_PORT", "puerto"), ("REDIS_DB", "entero")],
    "influxdb": [("INFLUX_URL", "url"), ("INFLUX_DB", "nombre")],
    "iris": [("IRIS_HOST", "host"), ("IRIS_PORT", "puerto"), ("IRIS_PORTAL_URL", "url")],
}


def valido(tipo: str, valor: str) -> str | None:
    """None si está bien; si no, el problema."""
    if valor == "":
        return "vacío"
    if valor != valor.strip():
        return "tiene espacios al borde"
    if tipo == "puerto":
        return None if valor.isdigit() and 1 <= int(valor) <= 65535 else "no es un puerto 1–65535"
    if tipo == "entero":
        return None if valor.isdigit() else "no es entero"
    if tipo == "url":
        u = urlparse(valor)
        if u.scheme not in ("http", "https") or not u.hostname:
            return "no es una URL http(s)"
        if u.username or u.password:
            return "la URL trae credenciales (RNF7)"
        return None
    if tipo == "host":
        return None if " " not in valor and "/" not in valor else "no es un host"
    return None if " " not in valor else "contiene espacios"


def chequear_variables(producto: str) -> None:
    for clave, tipo in VARIABLES[producto]:
        valor = CFG.get(clave, "")
        problema = valido(tipo, valor)
        R.agregar(producto=producto, capa="configuracion", prueba=f"{clave} ({tipo})",
                  objetivo=f"{clave}={valor or '∅'}", resultado="FAIL" if problema else "OK",
                  detalle=problema or f"origen: {origen_de(CFG, clave)}",
                  interpretacion="valor utilizable por las pruebas" if not problema else "corregir antes de probar red",
                  no_demuestra="que el servidor exista en ese host/puerto")


def ignorado_por_git(ruta: Path) -> bool | None:
    """True = ignorada; False = NO ignorada; None = no se puede verificar (la carpeta no es un
    repositorio git, p. ej. una copia bajada como ZIP, o git no está instalado)."""
    try:
        r = subprocess.run(["git", "-C", str(REPO_DIR), "check-ignore", "-q", str(ruta)],
                           capture_output=True, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if r.returncode == 0:
        return True
    if r.returncode == 1:
        return False
    return None  # 128: no es un repositorio git


def versionado(ruta: Path) -> bool:
    r = subprocess.run(["git", "-C", str(REPO_DIR), "ls-files", "--error-unmatch", str(ruta)],
                       capture_output=True, timeout=5)
    return r.returncode == 0


def chequear_secreto(producto: str, nombre: str, valor: str | None, origen: str, archivo: Path | None) -> None:
    R.agregar(producto=producto, capa="configuracion", prueba=f"{nombre} definido (sin mostrar el valor)",
              objetivo=origen, resultado="OK" if valor else "FAIL",
              detalle=f"definido ({len(valor)} caracteres)" if valor else "no definido",
              interpretacion="la prueba de identidad podrá ejecutarse" if valor else
              "sin secreto la capa de autenticación queda FAIL",
              no_demuestra="que el servidor lo acepte")
    if valor and valor in valores_publicos(CFG):
        R.agregar(producto=producto, capa="configuracion", prueba=f"{nombre} distinto de los valores públicos",
                  objetivo="comparado con .env.example y config no secreta", resultado="WARN",
                  detalle="es la credencial de desarrollo documentada en un .env.example versionado",
                  interpretacion="no es un secreto real: sirve en el laboratorio, no en un entorno compartido",
                  no_demuestra="nada sobre el servidor", observacion=True)
    if archivo is not None and archivo.exists():
        problemas = []
        if versionado(archivo):
            problemas.append("ESTÁ VERSIONADO")
        elif not ignorado_por_git(archivo):
            problemas.append("no está cubierto por .gitignore")
        modo = stat.S_IMODE(archivo.stat().st_mode)
        if modo & stat.S_IROTH:
            problemas.append(f"legible por otros usuarios ({oct(modo)})")
        R.agregar(producto=producto, capa="configuracion", prueba="archivo del secreto fuera de git",
                  objetivo=ruta_publica(archivo), resultado="FAIL" if "ESTÁ VERSIONADO" in problemas
                  else ("WARN" if problemas else "OK"),
                  detalle="; ".join(problemas) or f"ignorado por git, permisos {oct(modo)}",
                  interpretacion="el secreto no se publica en el repositorio (RNF7)",
                  no_demuestra="que el valor sea vigente", observacion="ESTÁ VERSIONADO" not in problemas)


def chequear_api_efectiva() -> None:
    """Compara la configuración del hito con la que carga la API (app/config/settings.py)."""
    api_dir = Path(CFG.get("API_DIR", ""))
    sys.path.insert(0, str(api_dir))
    try:
        from app.config.settings import Settings  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        R.agregar(producto="api", capa="configuracion", prueba="settings efectivos de la API",
                  objetivo=ruta_publica(api_dir), resultado="SKIP",
                  detalle=f"no se pudo importar app.config.settings ({type(exc).__name__}); correr con el .venv de la API",
                  interpretacion="SKIP = no probado, no 'mal configurado'")
        return
    cwd = os.getcwd()
    os.chdir(api_dir)          # la API resuelve su .env relativo a su carpeta
    try:
        s = Settings()
    finally:
        os.chdir(cwd)
    redis = urlparse(s.redis_url.get_secret_value())
    mongo = urlparse(s.mongo_uri.get_secret_value())
    neo = urlparse(s.neo4j_uri)
    pares = [
        ("mongodb", "host:puerto", f"{mongo.hostname}:{mongo.port or 27017}", f"{CFG['MONGO_HOST']}:{CFG['MONGO_PORT']}"),
        ("mongodb", "database", s.mongo_db, CFG["MONGO_DB"]),
        ("neo4j", "host:puerto Bolt", f"{neo.hostname}:{neo.port or 7687}", f"{CFG['NEO4J_HOST']}:{CFG['NEO4J_BOLT_PORT']}"),
        ("neo4j", "database", s.neo4j_database, CFG["NEO4J_DATABASE"]),
        ("cassandra", "host:puerto", f"{s.cassandra_hosts}:{s.cassandra_port}", f"{CFG['CASSANDRA_HOST']}:{CFG['CASSANDRA_PORT']}"),
        ("cassandra", "keyspace", s.cassandra_keyspace, CFG["CASSANDRA_KEYSPACE"]),
        ("redis", "host:puerto/db", f"{redis.hostname}:{redis.port or 6379}{redis.path or '/0'}",
         f"{CFG['REDIS_HOST']}:{CFG['REDIS_PORT']}/{CFG['REDIS_DB']}"),
        ("influxdb", "url", s.influx_url.rstrip("/"), CFG["INFLUX_URL"].rstrip("/")),
        ("influxdb", "database", s.influx_db, CFG["INFLUX_DB"]),
    ]
    norm = {"localhost": "127.0.0.1"}
    for producto, campo, api, hito in pares:
        a = api
        h = hito
        for k, v in norm.items():
            a, h = a.replace(k, v), h.replace(k, v)
        R.agregar(producto=producto, capa="configuracion", prueba=f"API vs hito: {campo}",
                  objetivo=f"API={api} · hito={hito}", resultado="OK" if a == h else "WARN",
                  detalle="coinciden" if a == h else "DIFIEREN: la prueba nativa no mide lo que usa la API",
                  interpretacion="la evaluación apunta al mismo destino que la API",
                  no_demuestra="que ese destino responda")
    R.agregar(producto="api", capa="configuracion", prueba="timeout de dependencias de la API (DEP_TIMEOUT_S)",
              objetivo=f"dep_timeout_s={s.dep_timeout_s}", resultado="OK" if 0 < s.dep_timeout_s <= 10 else "WARN",
              detalle=f"health_cache_s={s.health_cache_s} · ready_esenciales={s.ready_esenciales}",
              interpretacion="ninguna operación de la API espera indefinidamente (RNF5/RNF12)",
              no_demuestra="que el timeout sea el adecuado bajo carga (Hito 12)")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--producto", choices=list(VARIABLES), action="append")
    productos = p.parse_args().producto or list(VARIABLES)
    for prod in productos:
        chequear_variables(prod)
    if "neo4j" in productos:
        valor, origen = neo4j_password(CFG)
        archivo = None if origen_de(CFG, "NEO4J_PASSWORD") == "entorno" else Path(CFG.get("NEO4J_ENV_FILE", ""))
        chequear_secreto("neo4j", "NEO4J_PASSWORD", valor, origen, archivo)
    if "influxdb" in productos:
        valor, origen = influx_token(CFG)
        archivo = None if CFG.get("INFLUX_TOKEN") else Path(CFG.get("INFLUX_TOKEN_FILE", ""))
        chequear_secreto("influxdb", "token de InfluxDB", valor, origen, archivo)
    if "mongodb" in productos and not CFG.get("MONGO_USER"):
        R.agregar(producto="mongodb", capa="configuracion", prueba="credencial", objetivo="MONGO_USER vacío",
                  resultado="N/C", detalle="laboratorio sin autenticación (decisión del Hito 4)",
                  interpretacion="la capa de autenticación se informa como N/C, no como OK")
    for prod, nota in (("cassandra", "AllowAllAuthenticator (Hito 6)"), ("redis", "sin requirepass, sólo 127.0.0.1 (Hito 7)")):
        if prod in productos:
            R.agregar(producto=prod, capa="configuracion", prueba="credencial", objetivo="sin usuario",
                      resultado="N/C", detalle=f"laboratorio sin autenticación: {nota}",
                      interpretacion="la capa de autenticación se informa como N/C, no como OK")
    if "iris" in productos:
        R.agregar(producto="iris", capa="configuracion", prueba="producto fuera de la arquitectura", objetivo="IRIS",
                  resultado="N/C", detalle="fuera de la arquitectura vigente desde la reentrega del Hito 3",
                  interpretacion="se declara NOT_CONFIGURED: no se inventan resultados")
    if "api" in productos:
        chequear_api_efectiva()
    for ruta in ("config/configuracion.env",):
        archivo = Path(__file__).resolve().parents[1] / ruta
        ignorada = ignorado_por_git(archivo)
        R.agregar(producto="api", capa="configuracion", prueba="config local ignorada por git",
                  objetivo=ruta,
                  resultado="OK" if ignorada else "FAIL" if ignorada is False else "SKIP",
                  detalle=("cubierta por .gitignore" if ignorada else "NO está ignorada" if ignorada is False
                           else "no se pudo verificar: la carpeta no es un repositorio git (copia ZIP) o falta git"),
                  interpretacion="valores propios o secretos no se versionan" if ignorada is not None
                  else "SKIP = verificación no ejecutada; NO significa que el archivo esté versionado")
    print(f"Evidencia: {ruta_publica(R.md)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
