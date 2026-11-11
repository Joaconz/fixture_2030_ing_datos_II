"""
============================================================================
 Fixture 2030 — Hito 13 · exporter de Neo4j para Prometheus
 Neo4j Community no trae endpoint de Prometheus (es de Enterprise). Este
 exporter consulta Neo4j en cada scrape por la Query API HTTP
 (POST /db/<base>/query/v2) y devuelve las métricas en formato de texto de
 Prometheus en GET /metrics. Solo biblioteca estándar de Python: corre en la
 imagen python:3.12-slim sin instalar nada. Solo LEE: no escribe en el grafo.

 Variables de entorno:
   NEO4J_URL       http://host.docker.internal:7474
   NEO4J_USER      neo4j
   NEO4J_PASSWORD  fixture2030 (la de desarrollo de fixture2030-neo4j)
   NEO4J_DATABASE  neo4j
   PUERTO          9474
============================================================================
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

NEO4J_URL = os.environ.get("NEO4J_URL", "http://host.docker.internal:7474").rstrip("/")
USUARIO = os.environ.get("NEO4J_USER", "neo4j")
CLAVE = os.environ.get("NEO4J_PASSWORD", "fixture2030")
BASE = os.environ.get("NEO4J_DATABASE", "neo4j")
PUERTO = int(os.environ.get("PUERTO", "9474"))
TIMEOUT = 5
# Plazo total por scrape: Prometheus corta a los 10 s (scrape_timeout). Si Neo4j
# está lento, las consultas que no entran se saltean y el exporter responde igual.
PLAZO = 8

AUTH = "Basic " + base64.b64encode(f"{USUARIO}:{CLAVE}".encode()).decode()

# Consulta de referencia: la línea de tiempo de eventos de un partido, la
# lectura principal que hace la API (GET /partidos/{id}/eventos).
CONSULTA_REFERENCIA = (
    "MATCH (p:Partido) WITH p ORDER BY p.partidoId LIMIT 1 "
    "MATCH (ev:Evento)-[:OCURRE_EN]->(p) RETURN count(ev) AS eventos"
)
# Conteos por etiqueta y por tipo de relación (usan el count store: no recorren el grafo).
CONTEO_NODOS = (
    "CALL db.labels() YIELD label "
    "CALL (label) { MATCH (n:$(label)) RETURN count(n) AS c } RETURN label, c"
)
CONTEO_RELACIONES = (
    "CALL db.relationshipTypes() YIELD relationshipType AS t "
    "CALL (t) { MATCH ()-[r:$(t)]->() RETURN count(r) AS c } RETURN t, c"
)


def consultar(sentencia, limite, base=BASE):
    """Ejecuta una sentencia por la Query API sin pasarse de `limite` (perf_counter).
    Devuelve (filas, respuesta completa)."""
    restante = limite - time.perf_counter()
    if restante < 0.5:
        raise TimeoutError("sin tiempo dentro del plazo del scrape")
    pedido = urllib.request.Request(
        f"{NEO4J_URL}/db/{base}/query/v2",
        data=json.dumps({"statement": sentencia}).encode(),
        headers={"Authorization": AUTH, "Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(pedido, timeout=min(TIMEOUT, restante)) as r:
        cuerpo = json.load(r)
    if cuerpo.get("errors"):
        raise RuntimeError(cuerpo["errors"][0].get("message", "error de Neo4j"))
    return cuerpo["data"]["values"], cuerpo


def etiqueta(valor):
    return str(valor).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


class Metricas:
    def __init__(self):
        self.lineas = []

    def agregar(self, nombre, tipo, ayuda, muestras):
        """muestras: lista de (dict de etiquetas, valor)."""
        self.lineas.append(f"# HELP {nombre} {ayuda}")
        self.lineas.append(f"# TYPE {nombre} {tipo}")
        for etiquetas, valor in muestras:
            sufijo = ",".join(f'{k}="{etiqueta(v)}"' for k, v in etiquetas.items())
            self.lineas.append(f"{nombre}{{{sufijo}}} {valor}" if sufijo else f"{nombre} {valor}")

    def texto(self):
        return "\n".join(self.lineas) + "\n"


def error(bloque, exc):
    print(f"[neo4j-exporter] {bloque}: {exc}", file=sys.stderr, flush=True)


def recolectar():
    m = Metricas()
    inicio = time.perf_counter()
    limite = inicio + PLAZO

    # 1. Disponibilidad + latencia de la consulta de referencia. Si falla, la
    #    base no está usable (caída, credencial rechazada, base offline).
    try:
        t0 = time.perf_counter()
        _, cuerpo = consultar(CONSULTA_REFERENCIA, limite)
        ida_y_vuelta = time.perf_counter() - t0
        servidor = (cuerpo.get("resultConsumedAfter") or 0) / 1000
        arriba = 1
    except (urllib.error.URLError, OSError, RuntimeError, ValueError, KeyError) as exc:
        error("consulta de referencia", exc)
        arriba = 0
    m.agregar("neo4j_up", "gauge",
              "1 si el exporter pudo autenticarse y ejecutar la consulta de referencia en Neo4j.",
              [({}, arriba)])

    if arriba:
        m.agregar("neo4j_consulta_referencia_segundos", "gauge",
                  "Duración de la consulta de referencia (eventos de un partido): "
                  "servidor = tiempo del motor, ida_y_vuelta = vista por el exporter (incluye HTTP).",
                  [({"medida": "servidor"}, servidor), ({"medida": "ida_y_vuelta"}, round(ida_y_vuelta, 6))])

        bloques = [
            ("neo4j_nodos", "Cantidad de nodos por etiqueta.", CONTEO_NODOS, "etiqueta", BASE),
            ("neo4j_relaciones", "Cantidad de relaciones por tipo.", CONTEO_RELACIONES, "tipo", BASE),
        ]
        for nombre, ayuda, sentencia, clave, base in bloques:
            try:
                filas, _ = consultar(sentencia, limite, base)
                m.agregar(nombre, "gauge", ayuda, [({clave: f[0]}, f[1]) for f in filas])
            except (urllib.error.URLError, OSError, RuntimeError, ValueError, KeyError) as exc:
                error(nombre, exc)

        try:
            filas, _ = consultar("SHOW DATABASES YIELD name, currentStatus", limite, "system")
            m.agregar("neo4j_base_online", "gauge",
                      "1 si la base está online según SHOW DATABASES.",
                      [({"db": f[0]}, 1 if f[1] == "online" else 0) for f in filas])
        except (urllib.error.URLError, OSError, RuntimeError, ValueError, KeyError) as exc:
            error("neo4j_base_online", exc)

        try:
            # Incluye la transacción de esta misma consulta: se descuenta.
            filas, _ = consultar("SHOW TRANSACTIONS YIELD transactionId RETURN count(*) AS n", limite)
            m.agregar("neo4j_transacciones_abiertas", "gauge",
                      "Transacciones abiertas en este momento (SHOW TRANSACTIONS, sin contar la del exporter).",
                      [({}, max(filas[0][0] - 1, 0))])
        except (urllib.error.URLError, OSError, RuntimeError, ValueError, KeyError, IndexError) as exc:
            error("neo4j_transacciones_abiertas", exc)

        try:
            filas, _ = consultar(
                "CALL dbms.queryJmx('java.lang:type=Memory') YIELD attributes "
                "WITH attributes.HeapMemoryUsage.value.properties AS h RETURN h.used, h.max", limite)
            m.agregar("neo4j_heap_bytes", "gauge", "Memoria heap de la JVM de Neo4j (usada y máxima).",
                      [({"tipo": "usado"}, filas[0][0]), ({"tipo": "maximo"}, filas[0][1])])
        except (urllib.error.URLError, OSError, RuntimeError, ValueError, KeyError, IndexError) as exc:
            error("neo4j_heap_bytes", exc)

        try:
            filas, _ = consultar("CALL dbms.components() YIELD versions, edition RETURN versions[0], edition", limite, "system")
            m.agregar("neo4j_info", "gauge", "Versión y edición de Neo4j.",
                      [({"version": filas[0][0], "edicion": filas[0][1]}, 1)])
        except (urllib.error.URLError, OSError, RuntimeError, ValueError, KeyError, IndexError) as exc:
            error("neo4j_info", exc)

    m.agregar("neo4j_exporter_duracion_segundos", "gauge",
              "Lo que tardó el exporter en recolectar todas las métricas de este scrape.",
              [({}, round(time.perf_counter() - inicio, 6))])
    return m.texto()


class Manejador(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] != "/metrics":
            self.send_response(404)
            self.end_headers()
            return
        cuerpo = recolectar().encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, *args):
        pass  # sin una línea por scrape en los logs


if __name__ == "__main__":
    print(f"[neo4j-exporter] escuchando en :{PUERTO}/metrics, Neo4j en {NEO4J_URL} (base {BASE})", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PUERTO), Manejador).serve_forever()
