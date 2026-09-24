# Evidencia — Hito 6 · Módulo de Comentarios (Cassandra)

Registro de lo que hay que dejar en esta carpeta para RF13 y RNF9. Cada archivo de texto se puede generar redirigiendo la salida del comando (`> docs/evidencia/<archivo>.txt`).

| # | Evidencia | Comando | Archivo |
|---|---|---|---|
| 1 | Nodo arriba y versión | `docker compose ps` · `docker compose exec cassandra nodetool status` · `docker compose exec cassandra cqlsh -e "SHOW VERSION"` | `01_ambiente.txt` o captura |
| 2 | Esquema creado | `docker compose exec cassandra cqlsh -f /scripts/esquema.cql` (termina con `DESCRIBE KEYSPACE`) | `02_esquema.txt` |
| 3 | Carga de muestra e idempotencia | correr `carga_muestra.cql` dos veces; los conteos finales deben coincidir | `03_carga_muestra_x2.txt` |
| 4 | CRUD | `docker compose exec cassandra cqlsh -f /scripts/crud.cql` | `04_crud.txt` |
| 5 | Consultas (incluye la traza de una sola partición) | `docker compose exec cassandra cqlsh -f /scripts/consultas.cql` | `05_consultas.txt` |
| 6 | Carga masiva y tasa de escritura | `docker compose --profile carga run --rm cargador` | `carga_masiva_<fecha>.md` / `.json` (los genera el script) |
| 7 | Tamaño de particiones | `nodetool flush` + `nodetool tablehistograms` + `nodetool tablestats` | `07_particiones.txt` |
| 8 | Consultas con volumen | repetir `consultas.cql` después de la carga masiva | `08_consultas_con_volumen.txt` |

Ejemplo (`-T` evita que la terminal agregue caracteres de control al archivo):

```bash
docker compose exec -T cassandra cqlsh -f /scripts/crud.cql > docs/evidencia/04_crud.txt
```

| Fecha | Versión de Cassandra | Equipo (CPU / RAM / disco) | Quién ejecutó |
|---|---|---|---|
| 2026-09-24 | 5.0.9 | MacBook Air · SSD · Docker Desktop con 8 CPUs y 3,8 GB visibles para los contenedores | Valentina Frisoli |
