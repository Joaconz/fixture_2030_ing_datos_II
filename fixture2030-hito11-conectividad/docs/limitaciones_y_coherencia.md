# Limitaciones y coherencia con el TPO

## 1. Limitaciones

| Limitación | Efecto en la evaluación | Cómo se informa |
|---|---|---|
| **IRIS fuera de la arquitectura** (reentrega del Hito 3, 13/10/2026) | la API no tiene adaptador de IRIS: la cadena API → IRIS no se puede evaluar | Evaluado igual con clientes nativos el 22/10/2026: TCP, portal, namespace y clase OK (corrida `20261022-203113`) |
| Autenticación y autorización de IRIS **no probadas** | el camino `IRIS_HABILITADO=1` usa la terminal del contenedor (`irisowner`, sin contraseña), que no prueba la credencial de un cliente externo | N/C en la matriz; se probaría con un cliente por el Superserver y un usuario de laboratorio |
| Laboratorio sin autenticación en MongoDB, Cassandra y Redis | las capas de autenticación y autorización no se pueden probar ahí | **N/C**, nunca OK. Se documenta qué error daría con autenticación y cómo lo clasificaría la API (motivos `autenticacion`/`autorizacion`) |
| Neo4j Community sin RBAC fino | la autorización se reduce a "la identidad puede leer su perfil y la database" | fila `SHOW CURRENT USER` |
| Token de InfluxDB de **administración** | la autorización probada es la de un admin. No se probó un token de sólo lectura | fila "permiso de consulta" |
| `cypher-shell`, `cqlsh` e `influxdb3` no están instalados en la notebook | esos CLI corren dentro de su contenedor: prueban protocolo, contexto y operación, **no** la ruta notebook → puerto | campo `origen: dentro del contenedor`. La ruta notebook → puerto la cubren `prueba_tcp.py` y `prueba_drivers.py` con los drivers de la API |
| La API **no** corre en un contenedor | la topología "API en Docker" se documenta con los escenarios desde un contenedor existente, no con la API real contenerizada | [`topologia_y_entornos.md`](topologia_y_entornos.md) §2 |
| API evaluada en `:8001` | en `:8000` corría la instancia del Hito 10 (otra rama), que no se tocó | `config/configuracion.env` local con `API_URL=http://localhost:8001`; la URL aparece en cada fila |
| Una sola notebook, un solo cliente secuencial | las latencias son de una prueba puntual (sub-milisegundo en TCP, milisegundos en la API) | **no son rendimiento**: el Hito 12 mide carga y concurrencia (RNF17) |
| Los `docker stop/pause` afectan a todo lo que use esos contenedores | durante ~20 s por escenario, la instancia del Hito 10 en `:8000` también vio la fuente caída | escenarios cortos, con `finally` que vuelve a arrancar el contenedor |
| Primera request a un Mongo con host que no resuelve | 504 en lugar de 503 (descubrimiento inicial de pymongo) | H11-4 en [`diagnostico_de_fallas.md`](diagnostico_de_fallas.md) |
| Redis no distingue clave vencida de clave inexistente | el diagnóstico infiere "vencida" por la carga de muestra y `expired_keys` | se escribe como inferencia, no como certeza |
| Cargas de muestra | la sesión de demo de Redis vence a los 30 min y el partido de demo de Neo4j se resetea con `sembrar_demo_neo4j.cypher`: antes de repetir la evaluación hay que recargar (preparación, no verificación) | README del Hito 10 |
| Capturas | la evidencia es texto (Markdown/JSONL) generado y redactado por los scripts. No hay capturas de pantalla | [`evidencia/capturas_redactadas/`](evidencia/capturas_redactadas/) tiene salidas de consola y de `/health` redactadas |

**Pruebas que no se hicieron:** escrituras (POST/PATCH/DELETE) como prueba de conectividad, porque modifican el dominio (RNF6; se probaron en el Hito 10); TLS (el laboratorio no lo usa); carga, concurrencia y throughput (Hito 12); caída de la red de Docker completa; caída simultánea de varias fuentes.

## 2. Coherencia con el TPO y con los hitos anteriores

| Decisión heredada | Fuente | Cómo la respeta este hito |
|---|---|---|
| N1 Equipos/Jugadores → MongoDB; N3 Eventos, N2 Partidos y N8 Tipos → Neo4j; N5 Comentarios → Cassandra; N6 Sesiones → Redis; N7 Estadísticas → InfluxDB | [`../../docs/ESTADO-CANONICO-NECESIDADES.md`](../../docs/ESTADO-CANONICO-NECESIDADES.md) (reentrega del Hito 3, 13/10/2026) | el mapa de dependencias evalúa exactamente esas cinco fuentes |
| IRIS fuera de la arquitectura; RF8 del Hito 10 no implementado con el ok del profesor (15/10/2026) | estado canónico, "Resueltos" | IRIS se declara `NO_CONFIGURADO`, sin inventar resultados (restricción "Productos") |
| Volúmenes nombrados (corrección del Hito 6, cumplir los RNF de infraestructura al pie de la letra) | `docker-compose.yml` de cada módulo | las fallas se provocan sólo con `stop/start` y `pause/unpause`. Se verificó la fecha de creación de cada volumen antes y después |
| Cargas deterministas e idempotentes (corrección del Hito 4) | `seed.js`, `carga_muestra.sh` | las pruebas sólo leen. Las cargas de muestra se pueden repetir para preparar el entorno sin duplicar nada |
| N/R/W explícito sólo para Cassandra (corrección del Hito 3) | Hito 3 | este hito no evalúa consistencia: es de conectividad. La API sigue leyendo Cassandra con `LOCAL_ONE` en un nodo único (Hito 10) y no se habla de N/R/W para los demás productos |
| Timeouts acotados, formato único de error, request-id (RNF8/RNF9/RNF10 del Hito 10) | API del Hito 10 | se mantienen. El Hito 11 separa el timeout (504) y agrega `motivo` al log |
| Preparación para el Hito 12 (carga masiva) | enunciado, §1 | antes de cargar volumen se sabe desde dónde se conecta la API, con qué host, puerto, driver y contexto, y cómo se comporta cada fuente al fallar. La matriz y los escenarios son la línea de base para comparar bajo carga |
