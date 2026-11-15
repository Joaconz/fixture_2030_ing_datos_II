# Guion de la presentación final: diapositivas + demo en vivo (18 min)

Equipo: Pazos · Núñez · Frisoli. Duración objetivo **18 minutos**, con 2 de margen para llegar a 20. La demo de la UI va en el medio: primero se explica qué decidimos y después se ve funcionando, base por base.

- **Diapositivas:** deck "Fixture 2030 — Defensa final" (17 diapositivas + la de demo). Cada diapositiva tiene notas de orador.
- **Quién:** A = inicio y arquitectura · B = decisiones y **maneja la demo** · C = evidencia y cierre. Completar los nombres: A = `[__]`, B = `[__]`, C = `[__]`. Mientras B maneja el teclado, A narra qué base responde cada pantalla. Así hablan los tres durante la demo.
- **Regla:** cada pantalla de la demo se muestra para probar una decisión. Si no prueba nada, se saltea.
- Guion anterior del Hito 13 (sin UI, con Swagger): [`guion_de_20_minutos.md`](guion_de_20_minutos.md). Preparación y plan B: [`demo.md`](demo.md).

---

## Cronograma

| Min | Bloque | Quién | Diapositivas / pantalla |
|---|---|---|---|
| 0:00–1:30 | Inicio | A | 1 Portada · 2 El problema · 3 Un modelo por acceso dominante |
| 1:30–4:00 | Arquitectura | A | 4 Cinco bases detrás de una API · 5 Qué acceso justifica cada base · 6 IRIS |
| 4:00–7:00 | Decisiones | B | 7 Cassandra · 8 Neo4j · 9 Redis (un minuto cada una) |
| **7:00–13:00** | **Demo en vivo de la UI** | **B maneja, A narra** | Diapositiva 10 "Demo" → navegador (pasos D1–D7 de abajo) |
| 13:00–15:30 | Evidencia | C | Grafana en vivo (en lugar de la diapositiva 13) · 11 Volúmenes · 12 Replicación · 14 Cuello de botella · 15 Prueba de falla |
| 15:30–18:00 | Cierre | C | 16 Medido vs. proyección · 17 Lecciones · 18 Cierre y preguntas |
| 18:00–20:00 | Margen | — | Preguntas |

**Puntos de control:** si a las 7:00 no empezó la demo, recortar Decisiones a una frase por base. Si a las 12:00 la demo no llegó a D7, saltear la sesión opcional y mostrar `/salud` en 15 segundos. Si a las 16:00 no se llegó al cierre, ir directo a la 16 y la 18.

---

## Demo en vivo (7:00–13:00)

Ensayado de punta a punta el 14/11/2026 contra el stack local: los siete pasos funcionan con las acciones exactas de esta tabla.

Pestañas abiertas **antes de empezar**, en este orden:

1. Front: `http://localhost:5173`
2. Front, mesa de control: `http://localhost:5173/partidos/PAR-DEMO-API/mesa`
3. Front, salud: `http://localhost:5173/salud`
4. Grafana: `http://localhost:3000`, **ya logueado** (usuario y contraseña de desarrollo en [`../grafana/README.md`](../grafana/README.md)), dashboard *Fixture 2030 — 2. API integrada*, "Last 15 minutes"

Zoom del navegador al 125 % para que se lea desde el fondo.

| Paso | Tiempo | Qué hace B (pantalla) | Qué dice A | Base y decisión que prueba |
|---|---|---|---|---|
| **D1** Inicio y búsqueda | 0:30 | En `/`, mostrar "Partidos destacados". Escribir `a1` en el campo **Código FIFA del equipo** → Enter: aparece "El código tiene que ser de 3 letras". Borrar, escribir `ARG` → Enter | "El hincha busca a su selección por código FIFA. El código se valida antes de llamar a la API, con el mismo patrón que usa la API." | — (validación en el front y en la API) |
| **D2** Ficha del equipo | 1:00 | En la ficha de ARG: banda con ranking 1, grupo A, 26 jugadores y sede. En **Plantel** (26 jugadores), tocar el chip **Delanteros** → quedan 9 | "Todo esto es **un documento** de MongoDB, leído por su `_id`, que es el código FIFA. El plantel son los jugadores que referencian al equipo. Es lectura intensiva y escritura rara: el modelo documental." | **MongoDB**: un equipo completo en una lectura por clave |
| **D3** Partido y eventos | 1:00 | En la columna derecha (**Partidos en el Mundial 2030**), tocar ARG–BEL (29 de junio, dieciseisavos) → `PAR-D16-01`. Pestaña **Eventos y comentarios**: línea de tiempo del 0′ al 90′. Tocar el chip **Goles** → queda un solo evento: Fernández, 13′ | "El partido y sus eventos vienen del grafo. El marcador de arriba, 1–0, **no está guardado**: se calcula contando los eventos de gol, y acá se ve el único gol. Cada evento está encadenado al anterior." | **Neo4j**: recorrido de eventos y marcador derivado |
| **D4** Comentarios | 1:00 | Columna derecha, **Comentarios** (los últimos 15, todos del minuto 124). Abajo, en **Publicar un comentario**, alias y usuario ya vienen completos (`hincha42`, `USR-0000042`). Escribir "Golazo en vivo desde la defensa", minuto **90** → **Publicar** → "Comentario publicado." | "Es el partido de audiencia máxima: su ventana de 10 minutos está repartida en **4 buckets**. La lista lee primero la ventana más reciente, la del final del partido. Por eso el comentario del minuto 90 **no aparece arriba**: se guardó en la partición de su ventana (17:30), no en la del final. Esa es justamente la clave `(partido, ventana, bucket)`: nunca se escanea el partido entero. La escritura lleva una clave de idempotencia: si se reintenta, no se duplica." | **Cassandra**: partición `(partido, ventana, bucket)`, escritura W=1 |
| **D5** Estadísticas | 0:45 | En el mismo partido, pestaña **Estadísticas**. En **Comparativa**, Goles 1–0: el mismo marcador que sale de Neo4j. Al pie: "Ver los datos en tabla (**190 filas**)". Cambiar período a **2T** y detalle a **5 min** → "(**20 filas**)" | "Las estadísticas por segundo viven en una base de series de tiempo. Pasar de 1 a 5 minutos es una agregación por tiempo que hace la base, no la pantalla: de 190 filas a 20. Y los goles de la serie coinciden con el marcador del grafo." | **InfluxDB**: ventanas de tiempo y downsampling |
| **D6** Mesa de control: cierre CP | 1:15 | Pestaña 2 (`/partidos/PAR-DEMO-API/mesa`, ARG–BRA). (a) **Cerrar partido** → **Sí, cerrar partido** → **409 `MISSING_FIN_PARTIDO`**. (b) En **Registrar evento**: Tipo *Fin del partido*, Minuto 90, **Condición del equipo: Sin equipo**, **Dorsal: vacío** → **Registrar evento** → 201. (c) **Cerrar partido** → confirmar → **200 "Partido cerrado: ARG 1 – 0 BRA"** (tarda 2–3 s). (d) **Intentar cerrar otra vez** → confirmar → **409 `INVALID_TRANSITION`** | "Esta es la operación que no admite dos verdades: el cierre es CP. La transacción exige el evento de fin y calcula el marcador desde los goles: el 1–0 sale del gol que ya estaba cargado. Si se intenta de nuevo, se rechaza: no puede haber dos resultados oficiales." | **Neo4j**: cierre CP vs. ingesta AP (decisión 2) |
| **D7** Salud de las fuentes | 0:30 | Pestaña 3 (`/salud`): las cinco fuentes UP con su latencia, HTTP 200 | "La API ve cada base por separado y con su propio timeout. Si una cae, solo esa queda DOWN, el chequeo responde 503 y sus pantallas muestran 'no pudimos cargar'; el resto sigue funcionando, como en la prueba de falla." | Las cinco: aislamiento de fallas |

**Cuidado en D6 (b):** si se deja la condición en *Local (ARG)* o el dorsal en 9, la API responde **400 `EVENT_RULE_VIOLATION`** ("condicionEquipo / dorsalProtagonista no corresponde a FIN_PARTIDO"). Si pasa, no es un problema: decir "la API valida las reglas de cada tipo de evento", corregir los dos campos y registrar de nuevo.

**Estadísticas y eventos coinciden en los 112 partidos.** Hasta el 15/11/2026, InfluxDB generaba al azar los goles de dieciseisavos, y ARG–BEL daba BEL 2–0 contra el 1–0 de Neo4j. Ahora el generador usa la misma plantilla de eventos de eliminatoria que `carga.cypher` (paso 15). Si la pestaña Estadísticas de ARG–BEL muestra Goles 0–2, el volumen de InfluxDB tiene la carga vieja: correr el paso 1 de la preparación.

**Opcional (si sobra un minuto):** `http://localhost:5173/sesiones/demo-ses-0000001-1` muestra la sesión de Redis con su **TTL restante**, el vencimiento absoluto (12 h) y el botón *Invalidar sesión*. Qué decir: "La sesión vence sola. Esta pantalla es de soporte y consultarla no renueva el TTL; lo renueva cada request del propio usuario, hasta el tope de 12 h."

**Transición a Evidencia (C):** pasar a la pestaña 4 (Grafana). "Las requests que acaban de ver ya están acá": en *2. API integrada*, *Requests por segundo* muestra los 200, el 201 del evento y los **409 del cierre**; *Latencia p95 por ruta*, cada pantalla; *Porcentaje de respuestas 5xx* en "No data" quiere decir que no hubo ningún error del servidor. En *3. Comparación entre bases*, la latencia de cada base vista desde la API. Después volver a las diapositivas 11, 12, 14 y 15.

---

## Preparación (30 minutos antes)

Desde la raíz del repo, con la notebook enchufada.

0. **Docker con memoria libre.** Docker Desktop tiene ~7,7 GB. En el ensayo, los contenedores de otros proyectos (Supabase) arrancaron solos y ocupaban 6 GB: así Cassandra no entra. Detenerlos antes (`docker stop <nombres>`, sin borrarlos). Si `docker ps` responde "500 Internal Server Error", la VM de Docker se colgó: `docker desktop restart` (tarda unos minutos en parar).
1. Bases, monitoreo y API: seguir [`demo.md`](demo.md) §1 (levanta las cinco bases, Prometheus/Grafana y la API en `:8000`). Dos cosas que aparecieron en el ensayo:
   - InfluxDB tiene `pull_policy: always`: sin buena red, `docker compose up -d` se queda descargando la imagen. Si el contenedor ya existe, alcanza con `docker start fixture2030-influxdb`.
   - La API lee el token de InfluxDB de `fixture2030-influxdb/secrets/admin-token.json`, que no se versiona. En un clon o worktree nuevo hay que copiarlo de donde se generó, o crearlo con `scripts/autorizacion_local.sh`. Sin token, D5 sale vacío.
   - **Mongo con 26 jugadores por equipo.** Si la ficha de ARG dice 23 jugadores, el volumen tiene la carga vieja. La semilla es idempotente (upsert por DNI), así que se puede correr sin miedo:
     ```bash
     (cd fixture2030-mongodb/load && npm ci && node seed.js)    # 64 equipos, 1.664 jugadores
     ```
   - **InfluxDB con los goles alineados a Neo4j.** Si ARG–BEL muestra Goles 0–2 en Estadísticas, regenerar y recargar las estadísticas (sobrescribe los mismos timestamps, no duplica). Los scripts usan solo la biblioteca estándar y corren con el Python local:
     ```bash
     cd fixture2030-influxdb
     python3 scripts/generacion_puntos.py --perfil completo
     python3 scripts/carga_lotes.py --perfil completo --tabla estadisticas_equipo   # 1.276.800 puntos, ~15 s
     ```
2. **Reiniciar el partido de demo.** Sin esto, D6 falla porque el partido quedó cerrado en el ensayo anterior:
   ```bash
   docker exec -i fixture2030-neo4j cypher-shell -u neo4j -p fixture2030 < fixture2030-hito10-api/scripts/sembrar_demo_neo4j.cypher
   ```
3. **Recargar las sesiones de Redis** (vencen a los 30 minutos; hacerlo lo más cerca posible de la presentación):
   ```bash
   docker exec fixture2030-redis sh /scripts/carga_muestra.sh
   ```
4. Front:
   ```bash
   cd fixture2030-hito10-api/web && npm ci && npm run dev
   ```
   Tiene que quedar en el puerto **5173**, que es el que la API acepta en CORS.
5. Chequeo rápido: `/salud` con las cinco en UP; ficha de ARG con **26** jugadores; `/partidos/PAR-D16-01` con eventos, comentarios y estadísticas con Goles **1–0**; la mesa de `PAR-DEMO-API` sin respuestas previas. Después de resembrar, esperar un minuto antes de abrir la mesa: el detalle del partido queda en caché de Redis hasta 60 s.
6. Loguearse en Grafana y dejar abiertas las cuatro pestañas de la demo.
7. Ocultar terminales y `.env` con credenciales antes de compartir pantalla.

**Datos que usa la demo** (los dejan las cargas de muestra): ARG en MongoDB; `PAR-D16-01` (ARG–BEL) tiene eventos en Neo4j, comentarios en Cassandra (4 buckets, audiencia máxima) y estadísticas en InfluxDB; `PAR-DEMO-API` (ARG–BRA) es el partido descartable para escribir. Cada ensayo agrega un comentario en la ventana de las 17:30 de `PAR-D16-01`: no molesta, porque no aparece en la primera página.

## Plan B de la demo

| Si falla… | Hacer |
|---|---|
| El front no levanta | Mismo flujo en Swagger (`http://localhost:8000/docs`): `GET /equipos/ARG`, `GET /partidos/PAR-D16-01`, comentarios, estadísticas y `PATCH /partidos/PAR-DEMO-API/estado` |
| Una pantalla dice "No pudimos cargar…" | Decirlo como evidencia: esa base no responde y el resto de la pantalla sigue. Botón **Reintentar**; si no, seguir con el paso siguiente |
| D6 (a) responde 409 `INVALID_TRANSITION` en lugar de `MISSING_FIN_PARTIDO` | El partido quedó cerrado: no se corrió el paso 2 de la preparación. Explicar el flujo con la diapositiva 8 |
| D6 (b) responde 400 `EVENT_RULE_VIOLATION` | Falta poner *Sin equipo* y vaciar el dorsal (ver "Cuidado en D6") |
| Estadísticas vacías | Falta el token o la carga de muestra de InfluxDB ([`demo.md`](demo.md) §3). Mostrar la diapositiva de volúmenes |
| Nada anda | Diapositivas + capturas de [`../evidencia/dashboards/`](../evidencia/dashboards/) y del front en [`../../fixture2030-hito10-api/docs/evidencia/front-stitch/`](../../fixture2030-hito10-api/docs/evidencia/front-stitch/) (inicio, ficha ARG, eventos y comentarios, estadísticas, estados de error). Las decisiones se defienden igual |

## Después

`Ctrl+C` en el front y en la API; las bases con `docker compose stop` (nunca `down -v`). Para repetir la demo, volver a correr los pasos 2 y 3 de la preparación.
