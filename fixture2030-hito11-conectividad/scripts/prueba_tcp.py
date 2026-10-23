"""Capas 1 y 2 — resolución del host y transporte TCP (RF4, RF5, §5.3).

Por cada dependencia, desde el MISMO origen que la API (la notebook):
  1. resolución: `getaddrinfo(host)` → dirección o "host no resuelto";
  2. TCP: `connect()` con CONNECT_TIMEOUT → conexión exitosa, connection refused
     o timeout (son fallas distintas y se registran distinto).

No se usa HTTP para puertos binarios (Bolt, CQL, RESP, Mongo wire, Superserver):
abrir el socket sólo prueba que hay un listener (RNF4).

    python3 scripts/prueba_tcp.py [--producto X ...] [--escenarios]

--escenarios agrega las fallas de §5.3 provocadas a propósito, sin tocar las
bases: puerto incorrecto, host no resuelto, timeout hacia una IP sin ruta, el
significado de `localhost` dentro de un contenedor (vía `docker exec` en un
contenedor ya existente) y el bind a 127.0.0.1 de Redis/InfluxDB.
"""
from __future__ import annotations

import argparse
import errno
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from registro import Registro, cargar_config, ruta_publica  # noqa: E402

CFG = cargar_config()
R = Registro("resultados_tcp", "Capas 1-2 — resolución y TCP")
T = float(CFG.get("CONNECT_TIMEOUT", "2"))


def destinos() -> list[tuple[str, str, str, int, str]]:
    """(producto, etiqueta, host, puerto, protocolo)"""
    influx = urlparse(CFG["INFLUX_URL"])
    portal = urlparse(CFG["IRIS_PORTAL_URL"])
    return [
        ("mongodb", "MongoDB wire", CFG["MONGO_HOST"], int(CFG["MONGO_PORT"]), "MongoDB wire protocol"),
        ("neo4j", "Bolt (API)", CFG["NEO4J_HOST"], int(CFG["NEO4J_BOLT_PORT"]), "Bolt"),
        ("neo4j", "HTTP Browser", CFG["NEO4J_HOST"], int(CFG["NEO4J_HTTP_PORT"]), "HTTP"),
        ("cassandra", "CQL", CFG["CASSANDRA_HOST"], int(CFG["CASSANDRA_PORT"]), "CQL native protocol"),
        ("redis", "RESP", CFG["REDIS_HOST"], int(CFG["REDIS_PORT"]), "RESP"),
        ("influxdb", "HTTP API", influx.hostname or "", influx.port or 8181, "HTTP"),
        ("iris", "Superserver", CFG["IRIS_HOST"], int(CFG["IRIS_PORT"]), "IRIS Superserver (SQL/objetos)"),
        ("iris", "Management Portal", portal.hostname or "", portal.port or 52773, "HTTP"),
    ]


def resolver(host: str) -> tuple[str | None, float, str]:
    t0 = time.perf_counter()
    try:
        info = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        return info[0][4][0], (time.perf_counter() - t0) * 1000, ""
    except socket.gaierror as exc:
        return None, (time.perf_counter() - t0) * 1000, f"host no resuelto ({exc.strerror})"


def conectar(host: str, puerto: int, timeout: float = T) -> tuple[str, float, str]:
    """→ (clase, ms, detalle). clase ∈ ok | refused | timeout | unreachable | unresolved | error"""
    t0 = time.perf_counter()
    try:
        with socket.create_connection((host, puerto), timeout=timeout):
            return "ok", (time.perf_counter() - t0) * 1000, "conexión TCP establecida"
    except ConnectionRefusedError:
        return "refused", (time.perf_counter() - t0) * 1000, "connection refused (el host respondió RST: no hay listener)"
    except socket.timeout:
        return "timeout", (time.perf_counter() - t0) * 1000, f"timeout: sin respuesta en {timeout:g} s"
    except socket.gaierror as exc:
        return "unresolved", (time.perf_counter() - t0) * 1000, f"host no resuelto ({exc.strerror})"
    except OSError as exc:
        ms = (time.perf_counter() - t0) * 1000
        if exc.errno in (errno.EHOSTUNREACH, errno.ENETUNREACH):
            return "unreachable", ms, f"sin ruta al host ({exc.strerror})"
        return "error", ms, f"{type(exc).__name__}: {exc.strerror or exc}"


INTERPRETACION = {
    "ok": "hay un listener aceptando en ese host:puerto desde este origen",
    "refused": "el host existe y respondió, pero nada escucha en ese puerto (proceso caído, puerto no publicado o puerto equivocado)",
    "timeout": "no hubo respuesta: red, firewall, ruta inexistente o proceso colgado",
    "unreachable": "el sistema operativo no tiene ruta a esa red",
    "unresolved": "el nombre no se convierte en dirección desde este entorno",
    "error": "falla de red no clasificada",
}
NO_DEMUESTRA_TCP = "protocolo, autenticación, contexto ni consulta (solo hay un socket)"


def probar_destinos(productos: list[str]) -> None:
    for producto, etiqueta, host, puerto, protocolo in destinos():
        if producto not in productos:
            continue
        objetivo = f"{host}:{puerto} ({protocolo})"
        ip, ms_dns, err = resolver(host)
        R.agregar(producto=producto, capa="resolucion", prueba=f"getaddrinfo {host}", objetivo=host,
                  resultado="OK" if ip else "FAIL", latencia_ms=ms_dns,
                  detalle=f"→ {ip}" if ip else err,
                  interpretacion="el nombre resuelve desde el mismo origen que la API" if ip else INTERPRETACION["unresolved"],
                  no_demuestra="que haya un proceso escuchando")
        if not ip:
            continue
        clase, ms, detalle = conectar(host, puerto)
        if producto == "iris":
            resultado = "N/C"
            detalle += " — coherente con IRIS fuera de la arquitectura (NOT_CONFIGURED)" if clase != "ok" else \
                " — hay listener aunque IRIS está fuera de la arquitectura"
        else:
            resultado = "OK" if clase == "ok" else "FAIL"
        R.agregar(producto=producto, capa="tcp", prueba=f"TCP {etiqueta}", objetivo=objetivo, resultado=resultado,
                  latencia_ms=ms, detalle=detalle, interpretacion=INTERPRETACION[clase],
                  no_demuestra=NO_DEMUESTRA_TCP, clase_tcp=clase)


# --------------------------------------------------------------------------- escenarios de §5.3
def escenarios() -> None:
    def esc(nombre: str, host: str, puerto: int, esperado: str, explicacion: str, timeout: float = T) -> None:
        clase, ms, detalle = conectar(host, puerto, timeout)
        R.agregar(producto="red", capa="tcp", prueba=f"escenario: {nombre}", objetivo=f"{host}:{puerto}",
                  resultado="OK" if clase == esperado else "WARN", latencia_ms=ms,
                  detalle=f"{detalle} (esperado: {esperado})", interpretacion=explicacion,
                  no_demuestra="nada sobre las bases: es un control del diagnóstico", clase_tcp=clase)

    esc("puerto incorrecto (Mongo en 27018)", CFG["MONGO_HOST"], 27018, "refused",
        "mismo host que responde en 27017: el proceso está activo pero la prueba apunta a otro listener")
    esc("host no resuelto", "mongodb-inexistente.invalid", 27017, "unresolved",
        "falla de nombre: no se llegó a intentar el socket")
    esc("timeout (IP sin respuesta, TEST-NET-1)", "192.0.2.1", 27017, "timeout",
        "nadie responde ni rechaza: así se ve un firewall o una ruta inexistente", timeout=T)

    # Bind a loopback: Redis e Influx publican sólo en 127.0.0.1 (Hitos 7 y 8).
    ip_lan = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.0.2.1", 9))   # no envía nada: sólo elige la interfaz de salida
        ip_lan = s.getsockname()[0]
        s.close()
    except OSError:
        pass
    if ip_lan and not ip_lan.startswith("127."):
        for prod, puerto in (("redis", int(CFG["REDIS_PORT"])), ("influxdb", urlparse(CFG["INFLUX_URL"]).port or 8181),
                             ("mongodb", int(CFG["MONGO_PORT"]))):
            clase, ms, detalle = conectar(ip_lan, puerto)
            esperado = "ok" if prod == "mongodb" else "refused"
            R.agregar(producto=prod, capa="tcp", prueba=f"escenario: mismo puerto por la IP de la LAN",
                      objetivo=f"<ip-lan>:{puerto}", resultado="OK" if clase == esperado else "WARN", latencia_ms=ms,
                      detalle=f"{detalle.replace(ip_lan, '<ip-lan>')} (esperado: {esperado})",
                      interpretacion=("publicado sólo en 127.0.0.1: desde otra máquina (o por la IP de la LAN) no hay listener"
                                      if prod != "mongodb" else
                                      "Mongo se publica en 0.0.0.0: también es alcanzable desde la LAN (sin auth: sólo laboratorio)"),
                      no_demuestra="nada sobre el protocolo", clase_tcp=clase)

    # localhost dentro de un contenedor (RNF3): se usa un contenedor que ya existe
    # (Cassandra trae bash, getent y timeout), sin descargar imágenes.
    cont = CFG.get("CASSANDRA_CONTAINER", "fixture2030-cassandra")
    if not shutil.which("docker"):
        R.agregar(producto="red", capa="tcp", prueba="escenario: localhost dentro de un contenedor", objetivo=cont,
                  resultado="SKIP", detalle="docker no está instalado", interpretacion="SKIP = no probado")
        return
    pruebas = [
        ("localhost:27017 visto desde el contenedor de Cassandra", "localhost", 27017, "refused",
         "dentro del contenedor, localhost es el propio contenedor: allí no hay MongoDB"),
        ("nombre de servicio en la misma red Compose", "cassandra", 9042, "ok",
         "en la red fixture2030-cassandra-net el servicio se alcanza por su nombre y puerto INTERNO"),
        ("nombre de un servicio de OTRA red Compose", CFG.get("MONGO_CONTAINER", "fixture2030_mongo"), 27017, "unresolved",
         "cada módulo tiene su propia red: el DNS de Docker no resuelve contenedores de otras redes"),
        ("host.docker.internal:27017 (puerto publicado en la notebook)", "host.docker.internal", 27017, "ok",
         "Docker Desktop expone la notebook como host.docker.internal: así llegaría una API contenerizada"),
    ]
    for nombre, host, puerto, esperado, explicacion in pruebas:
        script = (f'if ! getent hosts {host} >/dev/null; then echo unresolved; '
                  f'elif timeout {T:g} bash -c "</dev/tcp/{host}/{puerto}" 2>/tmp/e; then echo ok; '
                  f'elif grep -qi refused /tmp/e; then echo refused; else echo timeout; fi')
        t0 = time.perf_counter()
        try:
            r = subprocess.run(["docker", "exec", cont, "bash", "-c", script], capture_output=True, text=True,
                               timeout=T + 8)
            clase = (r.stdout.strip().splitlines() or ["error"])[-1]
            detalle = clase if r.returncode == 0 else f"docker exec falló: {r.stderr.strip()[:80]}"
        except subprocess.TimeoutExpired:
            clase, detalle = "error", "docker exec no terminó"
        R.agregar(producto="red", capa="tcp", prueba=f"escenario: {nombre}", objetivo=f"{cont} → {host}:{puerto}",
                  resultado="OK" if clase == esperado else "WARN", latencia_ms=(time.perf_counter() - t0) * 1000,
                  detalle=f"{detalle} (esperado: {esperado}) · origen: dentro del contenedor {cont}",
                  interpretacion=explicacion, no_demuestra="que la API funcione dentro de Docker (no se ejecuta así)",
                  clase_tcp=clase)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--producto", action="append",
                   choices=["mongodb", "neo4j", "cassandra", "redis", "influxdb", "iris"])
    p.add_argument("--escenarios", action="store_true")
    a = p.parse_args()
    probar_destinos(a.producto or ["mongodb", "neo4j", "cassandra", "redis", "influxdb", "iris"])
    if a.escenarios:
        escenarios()
    print(f"Evidencia: {ruta_publica(R.md)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
