# Repaso express — lo mínimo para defender

Para leer en 45 minutos. Lo de §1 a §4 es lo indispensable; §5 a §8 es lo que más se pregunta después. Si sobra tiempo, el detalle está en [`estudio_de_la_aplicacion.md`](estudio_de_la_aplicacion.md).

## 1. La idea en una frase

**Cada dato vive en la base que mejor resuelve cómo se lo usa, y una API los integra sin transacciones entre bases: si una base se cae, solo fallan sus rutas.**

Si te traban con una pregunta, volvé a esta frase.

## 2. Las cinco bases (lo que hay que saber de memoria)

| Base | Qué guarda | Por qué ahí | Consistencia |
|---|---|---|---|
| **MongoDB** (documental) | Equipos y jugadores | Se lee el equipo entero por su código FIFA y casi no cambia | CP al escribir, AP al leer |
| **Neo4j** (grafo) | Partidos, eventos, tipos de evento | Los eventos se recorren en orden y se relacionan | Eventos **AP**, cierre del partido **CP** |
| **Cassandra** (columnar) | Comentarios | Miles escriben a la vez en el minuto 90 | AP, **N=3 R=1 W=1** |
| **Redis** (clave-valor) | Sesiones y caché del partido | Se lee por clave y vence sola (TTL 30 min, tope 12 h) | AP, sin réplica entre regiones |
| **InfluxDB** (series de tiempo) | Estadísticas por segundo | Se consulta y agrega por tiempo | AP |

**IRIS (objetos) ya no está:** partidos y tipos estaban duplicados en IRIS y en Neo4j, y eso dio un calendario distinto entre bases. Lo sacamos en la reentrega del Hito 3 (aprobada el 13/10). Se resignó: las reglas por tipo de evento ahora las valida la API.

## 3. Tus tres decisiones (las presentás vos)

**Cassandra: la clave de los comentarios.**
- Clave `(partido, ventana de 10 min, bucket)`. Si fuera solo el partido, el minuto 90 caería entero en una partición, en un nodo: punto caliente.
- ARG–BEL: 300.000 comentarios, su partición más grande quedó en 16.161 filas (2,3 MB).
- 1.050.000 comentarios cargados, 17.774 escrituras/s en un nodo (pedían 10.000).
- Se resigna: búsquedas libres, una segunda tabla por usuario, consistencia eventual.

**Neo4j: dos consistencias en el mismo partido.**
- Cargar eventos es AP: no espera, y cada evento se encadena al anterior.
- Cerrar el partido es CP: una transacción que exige el evento de fin. No puede haber dos resultados.
- El marcador **no se guarda**: se cuentan los goles. Nunca contradice a los eventos.

**Redis: las sesiones no se replican, a propósito.**
- Si se cae una región, el usuario vuelve a entrar. Replicarla entre continentes suma latencia a todas las requests para cuidar un dato descartable.

## 4. Las preguntas más probables, con respuesta corta

**¿Por qué no una sola base?** Porque los accesos son opuestos: el cierre necesita consistencia fuerte, los comentarios escribir sin esperar, las sesiones vencerse, las estadísticas agregarse por tiempo. Con una sola, algún módulo resigna lo que más necesita. El costo: operar cinco productos.

**¿Qué pasa si se cae una base?** Solo fallan sus rutas (503) y el resto sigue. **Medido:** apagamos Redis, las sesiones dieron 503 y MongoDB siguió en 200. Detección a los 10 s, alerta a los 72 s.

**¿Dónde está el cuello de botella?** En la **API**, no en las bases: un proceso de Python al 97–100 % de CPU mientras Cassandra responde en 1 ms. Mejora: varios procesos de la API.

**¿Cómo saben si lo lento es la API o la base?** Comparando en Grafana la latencia de la API, la de la base vista desde la API y la de la base por dentro.

**¿Midieron replicación?** Sí, **aparte** del sistema: MongoDB con 3 nodos (failover en ~10 s, 0 escrituras perdidas) y Cassandra con 3 nodos (sigue con ONE y QUORUM, falla con ALL). La app de la demo corre con **un nodo por base**.

**¿Por qué no SQL?** El problema es escalar escritura en picos y responder rápido desde seis países con datos de forma muy distinta.

**¿Por qué no hicieron Usuarios ni Auditoría (N4, N9)?** Los hitos se organizaron por modelo y esos usan motores que ya teníamos (MongoDB y Cassandra). Es alcance pendiente, no un error de diseño.

**"El gol es del 9, pero en el plantel el 9 es arquero."** La ficha sale de MongoDB y el partido de Neo4j, y los planteles no están unificados (hallazgo H1). Por eso la API nunca cruza esas dos bases.

## 5. La API por dentro (se pregunta mucho)

- **Capas:** `routes/` (valida con Pydantic y elige el código HTTP) → `services/` (reglas de negocio) → `adapters/` (uno por base). Los servicios no conocen el driver: los tests unitarios usan adaptadores falsos y corren sin Docker.
- **Pieza común, `adapters/base.py::ejecutar`:** toda consulta a cualquier base pasa por ahí, con timeout propio por base.
  - Si la base no contesta a tiempo → **504** `DEPENDENCY_TIMEOUT`.
  - Si la base está caída → **503** `DEPENDENCY_UNAVAILABLE`, nunca un 200 vacío.
  - La API arranca aunque una base esté caída y la retoma sola cuando vuelve.
- **Errores:** siempre `{code, message, requestId}`. El `requestId` es el mismo del log: así se encuentra el error. Nunca se muestran hosts, consultas ni trazas.
- **Idempotencia:** los dos POST (evento y comentario) piden `Idempotency-Key`. El mismo pedido repetido no duplica: responde 200 "replay". Misma clave con otro cuerpo → 409. El front manda la misma clave en un doble clic.
- **Caché del partido (cache-aside):** `GET /partidos/{id}` busca en Redis (`HIT`); si no está, lee Neo4j y guarda 60 s (`MISS`). Si Redis está caído, responde igual desde Neo4j (`BYPASS`): la caché nunca da error. Cargar un evento o cerrar el partido borra la copia.
- **Concurrencia:** si dos personas cargan eventos del mismo partido a la vez, la transacción bloquea el partido y se ordenan; no hay secuencias repetidas.
- **Seguridad:** sin autenticación (es laboratorio, documentado). Consultas parametrizadas, validación antes de consultar, secretos fuera del repo.

## 6. Monitoreo (Hito 13)

- **Prometheus** lee 13 targets cada 15 s: la API, exporters de cada base (Cassandra por JMX, Neo4j con un exporter propio porque Community no expone métricas, InfluxDB con token), sondas de disponibilidad e infraestructura.
- **Grafana, 5 dashboards:** 1. Resumen y SLAs · 2. API integrada · 3. Comparación entre bases · 4. Bases por dentro · 5. Infraestructura.
- **Cómo se diagnostica una latencia alta:** 2 → 3 → 4. Si la base por dentro es rápida pero vista desde la API es lenta, el problema es la API.
- **8 alertas**, entre ellas `BaseNoResponde`, `ApiLatenciaAlta` (p95 > 150 ms sostenido) y `CassandraEscriturasEncoladas`.
- **Prueba de falla de Redis:** detectada a los 10 s, alerta a los 72 s, sesiones en 503 y MongoDB en 200 todo el tiempo; volvió sola 13 s después de prenderlo.

## 7. Pruebas de carga

**Carga masiva (Hito 11):** carga el volumen completo en las cinco bases y valida la integridad.
- Secuencial **324,5 s**, paralelo **382,6 s**: el paralelo fue **más lento** porque no había memoria para correr todo junto (la primera vez colgó Docker). Es un resultado documentado, no un error.
- Integridad **25 de 26 chequeos**: el que falla es H1 (12 de 64 equipos no coinciden entre MongoDB y Neo4j).

**Carga de la API (Hito 12):** el pico de comentarios tras un gol en ARG–BEL, 80 % lecturas y 20 % escrituras.
- **364 req/s, 0 errores**, sin comentarios duplicados.
- Optimización: caché de la configuración de partición → **−99,98 %** de esas lecturas. La latencia no mejoró de forma demostrable.
- El límite es la CPU de la API, no Cassandra (lo confirmó el Hito 13: Cassandra 1,1 ms por dentro, API 42–91 ms al 97 % de CPU).

**Replicación (aparte del sistema):**
- MongoDB, 3 nodos: si se mata el primario, elige otro en **9,99 s**, 0 de 226 escrituras perdidas. Para que sea CP de verdad hace falta `w: "majority"`.
- Cassandra, 3 nodos, RF=3: con un nodo caído, ONE y QUORUM siguen, ALL falla. Con W=ONE se vio la consistencia eventual: el nodo que volvió leyó 0 filas y recién 1 a los 13 s (hinted handoff).

## 8. Números de memoria

| Qué | Número |
|---|---|
| Equipos / jugadores (MongoDB) | 64 / 1.664 (26 por equipo) |
| Partidos / eventos / tipos (Neo4j) | 127 / 1.572 / 12 |
| Comentarios (Cassandra) | 1.050.000 |
| Usuarios con sesión (Redis) | 100.000 |
| Puntos de estadísticas (InfluxDB) | 10.094.400 |
| Partido caliente | ARG–BEL: 300.000 comentarios, 4 buckets, partición máxima 16.161 filas |
| Pedido del enunciado | 2–3 M usuarios, >100.000 req/s, <100 ms |
| Medido | ~400 req/s en una notebook |

## 9. Más preguntas posibles

**¿Por qué Partidos en Neo4j si el Hito 2 decía Objetos?** La matriz le daba a Objetos apenas 0,10 de ventaja: una decisión frágil. Al implementar, la duplicación dio un calendario inconsistente real, y el profesor aprobó moverlo.

**¿Por qué Neo4j Community y no Enterprise?** Es la edición libre. Costo: sin réplicas y sin métricas (escribimos un exporter). En producción iría Enterprise.

**¿Por qué no LWT (`IF NOT EXISTS`) para no duplicar comentarios?** Usa Paxos y contradice el W=1 elegido para aguantar el pico. La clave primaria sale de la clave de idempotencia, así que un reintento pisa la misma fila.

**¿Qué cambiarían primero para producción?** Varios procesos de la API (con la caché activa), unificar los equipos (H1), `w: "majority"` en MongoDB, más nodos de Cassandra y autenticación.

**¿Qué pasa si se cae Neo4j?** Fallan partidos y eventos (503) y el cierre espera: prefiere no cerrar a cerrar mal. Equipos, comentarios, sesiones y estadísticas siguen.

## 10. Lo que NO hay que decir

- Que soporta 100.000 req/s: medimos **~400 req/s** en una notebook.
- Que la app corre con réplicas: corre con un nodo por base.
- Que la caché del Hito 12 mejoró la latencia: bajó lecturas (−99,98 %), no latencia.

## 11. La demo en una línea por paso

1. **D1** Buscar `a1` (error) y `ARG` → validación en el front.
2. **D2** Ficha de ARG, chip Delanteros (26 → 9) → MongoDB, un documento.
3. **D3** ARG–BEL, Eventos, chip Goles → Neo4j, el 1–0 se calcula.
4. **D4** Publicar comentario minuto 90, no aparece arriba → Cassandra, va a su ventana.
5. **D5** Estadísticas, 2T y 5 min (190 → 20 filas) → InfluxDB agrega.
6. **D6** Mesa ARG–BRA: cerrar (409) → fin *Sin equipo*, dorsal vacío (201) → cerrar (200, 1–0) → otra vez (409) → cierre CP.
7. **D7** Salud: las cinco en UP → cada base con su timeout.

Después pasás a Santiago con Grafana. Entre ensayos, reiniciá D6 con el comando de [`como_correr_la_app.md`](como_correr_la_app.md) §3.
