# Correlación request-id ↔ logs (RF18 / RNF10)

Obtenido con `curl -H 'X-Request-Id: evid-correlacion-N' http://localhost:8000/partidos/PAR-D16-01` (dos veces) y filtrando el stdout de uvicorn por ese id. La primera request consulta Redis (MISS), Neo4j y guarda en caché; la segunda sólo Redis (HIT). Ninguna línea contiene cuerpos, credenciales ni URIs.

```json
{"ts": "2026-10-13T19:39:22.411+00:00", "nivel": "WARNING", "logger": "fixture2030.adaptador", "request_id": "caida-redis-2-caida", "mensaje": "dependencia no disponible", "evento": "dependencia", "dependencia": "redis", "operacion": "get_sesion", "resultado": "no_disponible", "tipo": "ConnectionError"}
{"ts": "2026-10-13T19:39:22.411+00:00", "nivel": "INFO", "logger": "fixture2030.adaptador", "request_id": "caida-redis-2-caida", "mensaje": "dependencia", "evento": "dependencia", "duracion_ms": 0.9, "dependencia": "redis", "operacion": "get_sesion", "resultado": "no_disponible"}
{"ts": "2026-10-13T19:39:22.411+00:00", "nivel": "INFO", "logger": "fixture2030.acceso", "request_id": "caida-redis-2-caida", "mensaje": "request", "evento": "request", "metodo": "GET", "ruta": "/sesiones/{sesion_id}", "path": "/sesiones/demo-ses-0000001-1", "status": 503, "duracion_ms": 2.1}
{"ts": "2026-10-13T19:42:27.635+00:00", "nivel": "INFO", "logger": "fixture2030.adaptador", "request_id": "evid-correlacion-1", "mensaje": "dependencia", "evento": "dependencia", "duracion_ms": 3.6, "dependencia": "redis", "operacion": "cache_get_partido", "resultado": "ok"}
{"ts": "2026-10-13T19:42:27.651+00:00", "nivel": "INFO", "logger": "fixture2030.adaptador", "request_id": "evid-correlacion-1", "mensaje": "dependencia", "evento": "dependencia", "duracion_ms": 15.5, "dependencia": "neo4j", "operacion": "get_partido", "resultado": "ok"}
{"ts": "2026-10-13T19:42:27.652+00:00", "nivel": "INFO", "logger": "fixture2030.adaptador", "request_id": "evid-correlacion-1", "mensaje": "dependencia", "evento": "dependencia", "duracion_ms": 1.0, "dependencia": "redis", "operacion": "cache_set_partido", "resultado": "ok"}
{"ts": "2026-10-13T19:42:27.652+00:00", "nivel": "INFO", "logger": "fixture2030.acceso", "request_id": "evid-correlacion-1", "mensaje": "request", "evento": "request", "metodo": "GET", "ruta": "/partidos/{partido_id}", "path": "/partidos/PAR-D16-01", "status": 200, "duracion_ms": 22.3}
{"ts": "2026-10-13T19:42:27.663+00:00", "nivel": "INFO", "logger": "fixture2030.adaptador", "request_id": "evid-correlacion-2", "mensaje": "dependencia", "evento": "dependencia", "duracion_ms": 0.9, "dependencia": "redis", "operacion": "cache_get_partido", "resultado": "ok"}
{"ts": "2026-10-13T19:42:27.664+00:00", "nivel": "INFO", "logger": "fixture2030.acceso", "request_id": "evid-correlacion-2", "mensaje": "request", "evento": "request", "metodo": "GET", "ruta": "/partidos/{partido_id}", "path": "/partidos/PAR-D16-01", "status": 200, "duracion_ms": 2.0}
```
