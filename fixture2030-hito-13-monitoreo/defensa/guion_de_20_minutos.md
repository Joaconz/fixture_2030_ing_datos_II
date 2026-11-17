# Guion de la defensa — 20 minutos (RF13, RNF12)

Equipo: Pazos · Núñez · Frisoli. **Quién presenta cada bloque lo decide el equipo** (A, B y C abajo, completar antes del ensayo); todos tienen que poder responder sobre cualquier módulo (restricción "Defensa" de la consigna). Respuestas preparadas: [`../docs/defensa_final.md`](../docs/defensa_final.md). Repaso del sistema por dentro y preguntas probables: [`estudio_de_la_aplicacion.md`](estudio_de_la_aplicacion.md).

| Letra | Integrante |
|---|---|
| A | _a definir_ |
| B | _a definir_ |
| C | _a definir_ |

Regla del guion: cada vez que se muestra algo, se dice **qué decisión de base demuestra**. Si no demuestra una decisión, no se muestra.

| Min | Bloque | Quién | Qué se dice | Qué se muestra |
|---|---|---|---|---|
| 0:00–2:00 | **Inicio** | A | El problema: Mundial 2030 en seis países, 2–3 millones de usuarios simultáneos, picos de >100.000 req/s en un gol. Nueve necesidades de datos con accesos opuestos. Decisión general: un modelo por acceso dominante, integrados por una API | Una diapositiva o el diagrama del Hito 3 (o el dibujo de [`estudio_de_la_aplicacion.md`](estudio_de_la_aplicacion.md) §1) |
| 2:00–5:00 | **Arquitectura** | A | Recorrido de las cinco bases: qué guarda cada una y qué acceso la justifica. IRIS: por qué salió (duplicación de partidos, calendario inconsistente). N4 y N9: diseñadas, no implementadas | Tabla de [`decisiones_de_arquitectura.md`](../docs/decisiones_de_arquitectura.md) §1 |
| 5:00–10:00 | **Decisiones** | B | Tres decisiones con detalle, no las cinco: (1) partición de comentarios `(partido, ventana, bucket)` contra el hotspot del minuto 90, N=3/R=1/W=1 — **con la carga masiva:** `PAR-D16-01` tiene 32 veces el promedio de comentarios y su partición más grande queda en 16.161 filas; **con la replicación:** en el anillo de 3 nodos, W=ONE con un nodo caído se vio la consistencia eventual (0 filas → 1 tras el hinted handoff); (2) Partidos en el grafo: cierre CP con marcador derivado de los goles, ingesta de eventos AP; (3) sesiones en Redis sin réplica entre regiones, a propósito. Qué se resigna en cada una | `esquema.cql` (clave primaria); `PATCH /partidos/{id}/estado` en Swagger; [`fixture2030-carga-masiva/docs/distribucion_y_escalabilidad.md`](../../fixture2030-carga-masiva/docs/distribucion_y_escalabilidad.md) §Cassandra |
| 10:00–13:00 | **Operación** | B | Un flujo completo desde el front del hincha: ficha de un equipo y el partido caliente con eventos y comentarios; explicar qué base atiende cada panel y por qué responden distinto. Que cada panel falla por separado | Front (`npm run dev`, http://localhost:5173): `/equipos/ARG` y `/partidos/PAR-D16-01`. Plan B: Swagger con `GET /partidos/PAR-D16-01/comentarios`, `GET /equipos/ARG`, `GET /health/dependencias`, o las capturas de `fixture2030-hito10-api/docs/evidencia/front-stitch/` |
| 13:00–18:00 | **Evidencia** | C | (1) Dashboard *1. Resumen y SLAs*: estado de las cinco bases y SLAs de latencia y disponibilidad. (2) La carga observada: Cassandra en 1 ms, la API en 42–91 ms al 97 % de CPU → el cuello es la API, no la base. (3) Prueba de falla de Redis: 503 solo en sesiones, MongoDB sigue; alerta a los 72 s. (4) **Carga masiva** del volumen completo: 1,05 M comentarios, 10 M puntos, 100.000 usuarios; secuencial 324,5 s contra paralelo 382,6 s (sin memoria para paralelizar, el paralelo no gana); integridad 25/26, y el chequeo que falla es H1. Qué haríamos ante cada señal | Grafana en vivo o capturas de `evidencia/` ([demo.md](demo.md)); tabla de resultados de [`fixture2030-carga-masiva/README.md`](../../fixture2030-carga-masiva/README.md) |
| 18:00–20:00 | **Cierre** | C | Por qué es adecuada (frase central de `defensa_final.md`), trade-offs aceptados (consistencia eventual, desnormalización, cinco productos), qué no medimos (multirregión, escala real, el sistema integrado con réplicas) y qué mejoraríamos: varios procesos de la API con la caché activa, unificar el roster de equipos (H1), después nodos de Cassandra | [`decisiones_de_arquitectura.md`](../docs/decisiones_de_arquitectura.md) §3 |

## Antes de entrar

- Completar la tabla de integrantes (A, B, C) y que cada uno ensaye su bloque.
- Hacer la preparación y el chequeo de [`demo.md`](demo.md) §1 **media hora antes**. Si se usa el front, levantarlo también (`cd fixture2030-hito10-api/web && npm run dev`).
- Ensayar con cronómetro: si a los 10:00 no se terminó "Decisiones", recortar "Operación" a un solo panel.
- Cada integrante repasa [`estudio_de_la_aplicacion.md`](estudio_de_la_aplicacion.md) (§11 números, §13 autoevaluación, §14 preguntas probables) y las respuestas de [`defensa_final.md`](../docs/defensa_final.md), incluidas las de módulos que no hizo.
