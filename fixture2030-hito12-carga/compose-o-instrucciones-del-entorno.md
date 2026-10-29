# Entorno de la prueba

| Componente | Dónde corre | Cómo se levanta | Por qué así |
|---|---|---|---|
| Cassandra 5 (Hito 6) | Contenedor `fixture2030-cassandra`, puerto 9042 | `fixture2030-cassandra/docker-compose.yml` (lo hace `preparar_datos.sh` si no está arriba) | Es la fuente del flujo; mismos datos y esquema del Hito 6 |
| API (Hito 10) | Notebook, 1 proceso `uvicorn` en el puerto 8000 | La levanta y la apaga `ejecutar_carga.sh` en cada corrida | Para controlar su configuración (caché de Q0 = 0 o 60) y que las dos corridas sean comparables |
| Generador (k6) | Contenedor `grafana/k6` efímero | `docker run` dentro de `ejecutar_carga.sh` | Percentiles, rampa y corte seguro sin instalar nada; llega a la API por `host.docker.internal:8000` |
| Muestreo de recursos | Notebook | `docker stats` (Cassandra) y `ps` (API) cada 2 s | Separar consumo del generador, la API y la base (RF6) |

Solo hace falta **Cassandra** levantada: el flujo no usa los otros módulos. Los avisos de la API sobre MongoDB o Neo4j caídos no afectan esta prueba.

**Límites de la notebook (RNF9):** k6 corre sin pausas entre requests (peor caso: cada usuario virtual manda la siguiente en cuanto recibe la anterior) con 20 usuarios virtuales. Generador, API y Cassandra comparten los mismos núcleos y memoria, así que los números son de **este** ambiente y no una garantía de producción.
