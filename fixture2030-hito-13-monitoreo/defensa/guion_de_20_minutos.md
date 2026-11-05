# Guion de la defensa — 20 minutos (RF13, RNF12)

Equipo: Pazos · Núñez · Frisoli. **Quién presenta cada bloque lo decide el equipo** (A, B y C abajo); todos tienen que poder responder sobre cualquier módulo (restricción "Defensa" de la consigna). Respuestas preparadas: [`../docs/defensa_final.md`](../docs/defensa_final.md).

Regla del guion: cada vez que se muestra algo, se dice **qué decisión de base demuestra**. Si no demuestra una decisión, no se muestra.

| Min | Bloque | Quién | Qué se dice | Qué se muestra |
|---|---|---|---|---|
| 0:00–2:00 | **Inicio** | A | El problema: Mundial 2030 en seis países, 2–3 millones de usuarios simultáneos, picos de >100.000 req/s en un gol. Nueve necesidades de datos con accesos opuestos. Decisión general: un modelo por acceso dominante, integrados por una API | Una diapositiva o el diagrama del Hito 3 |
| 2:00–5:00 | **Arquitectura** | A | Recorrido de las cinco bases: qué guarda cada una y qué acceso la justifica. IRIS: por qué salió (duplicación de partidos, calendario inconsistente) | Tabla de [`decisiones_de_arquitectura.md`](../docs/decisiones_de_arquitectura.md) §1 |
| 5:00–10:00 | **Decisiones** | B | Tres decisiones con detalle, no las cinco: (1) partición de comentarios `(partido, ventana, bucket)` contra el hotspot del minuto 90, N=3/R=1/W=1; (2) Partidos en el grafo: cierre CP con marcador derivado de los goles, ingesta de eventos AP; (3) sesiones en Redis sin réplica entre regiones, a propósito. Qué se resigna en cada una | `esquema.cql` (clave primaria); `PATCH /partidos/{id}/estado` en Swagger |
| 10:00–14:00 | **Operación** | B | Un flujo completo: pedir los comentarios del partido caliente y un equipo; explicar qué base atiende cada request y por qué responden distinto | Swagger o Postman: `GET /partidos/PAR-D16-01/comentarios`, `GET /equipos/ARG`, `GET /health/dependencias` |
| 14:00–18:00 | **Evidencia** | C | (1) Dashboard: estado de las cinco bases. (2) La carga observada: Cassandra en 1 ms, la API en 42–91 ms al 97 % de CPU → el cuello es la API, no la base. (3) Prueba de falla de Redis: 503 solo en sesiones, MongoDB sigue; alerta a los 72 s. Qué haríamos ante cada señal | Grafana en vivo o capturas de `evidencia/` ([demo.md](demo.md)) |
| 18:00–20:00 | **Cierre** | C | Por qué es adecuada (frase central de `defensa_final.md`), trade-offs aceptados (consistencia eventual, desnormalización, cinco productos), qué no medimos y qué mejoraríamos: varios procesos de la API con la caché activa, después nodos de Cassandra | [`decisiones_de_arquitectura.md`](../docs/decisiones_de_arquitectura.md) §3 |

## Antes de entrar

- Hacer la preparación y el chequeo de [`demo.md`](demo.md) §1 **media hora antes**.
- Ensayar con cronómetro: si a los 10:00 no se terminó "Decisiones", recortar "Operación" a un solo request.
- Cada integrante repasa las respuestas de [`defensa_final.md`](../docs/defensa_final.md), incluidas las de módulos que no hizo.
