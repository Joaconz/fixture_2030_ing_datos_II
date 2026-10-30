# Ambiente — corrida linea_base

| Dato | Valor |
|---|---|
| Fecha (UTC) | 2026-10-30T16:47:30Z |
| Commit | ef271d9 |
| Corrida / usuarios de prueba | 301647 / USR-LT301647001 … USR-LT301647020 |
| Escenario | 20 VUs · rampa 30s · sostenimiento 120s · bajada 10s · 80 % GET / 20 % POST |
| API | FastAPI del Hito 10, 1 proceso uvicorn · COMENTARIOS_CONFIG_CACHE_S=0 · DEP_TIMEOUT_S por defecto |
| Cassandra | cqlsh 6.2.0 | Cassandra 5.0.9 | CQL spec 3.4.7 | Native protocol v5 |
| Generador | k6 v2.3.0 (commit/e088784614, go1.27.1, linux/arm64) (Docker) |
| Docker | CPUs 10 · memoria 8319504384 bytes · Docker Desktop |
| Sistema | Darwin arm64 |
