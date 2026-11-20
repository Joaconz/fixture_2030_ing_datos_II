# Guion de la presentación final: diapositivas + demo en vivo (18 min)

Equipo: Pazos · Núñez · Frisoli. Duración objetivo **18 minutos**, con 2 de margen para llegar a 20. La demo de la UI va en el medio: primero se explica qué decidimos y después se ve funcionando, base por base.

- **Diapositivas:** deck "Fixture 2030 — Defensa final" (17 diapositivas + la de demo). Cada diapositiva tiene notas de orador.
- **Quién:** A = inicio y arquitectura · B = decisiones y **la demo completa** (maneja el teclado y la narra) · C = evidencia y cierre. A = **Valentina**, B = **Joaquín**, C = **Santiago**.
- **Regla:** cada pantalla de la demo se muestra para probar una decisión. Si no prueba nada, se saltea.
- Guion anterior del Hito 13 (sin UI, con Swagger): [`guion_de_20_minutos.md`](guion_de_20_minutos.md). Preparación y plan B: [`demo.md`](demo.md).

---

## Cronograma

| Min | Bloque | Quién | Diapositivas / pantalla |
|---|---|---|---|
| 0:00–1:30 | Inicio | A | 1 Portada · 2 El problema · 3 Un modelo por acceso dominante |
| 1:30–4:00 | Arquitectura | A | 4 Cinco bases detrás de una API · 5 Qué acceso justifica cada base · 6 IRIS |
| 4:00–7:00 | Decisiones | B | 7 Cassandra · 8 Neo4j · 9 Redis (un minuto cada una) |
| **7:00–13:00** | **Demo en vivo de la UI** | **B** (maneja y narra) | Diapositiva 10 "Demo" → navegador (pasos D1–D7 de abajo) |
| 13:00–15:30 | Evidencia | C | Grafana en vivo (en lugar de la diapositiva 13) · 11 Volúmenes · 12 Replicación · 14 Cuello de botella · 15 Prueba de falla |
| 15:30–18:00 | Cierre | C | 16 Medido vs. proyección · 17 Lecciones · 18 Cierre y preguntas |
| 18:00–20:00 | Margen | — | Preguntas |

**Puntos de control:** si a las 7:00 no empezó la demo, recortar Decisiones a una frase por base. Si a las 12:00 la demo no llegó a D7, saltear la sesión opcional y mostrar `/salud` en 15 segundos. Si a las 16:00 no se llegó al cierre, ir directo a la 16 y la 18.

---

## Demo en vivo (7:00–13:00) · Joaquín

Joaquín maneja y habla. Acá van los clics y una frase clave por paso; el texto completo para decir está en [`guion_hablado.md`](guion_hablado.md).

**Recorrido:** D1 Buscar ARG → D2 Ficha → D3 Partido → D4 Comentarios → D5 Estadísticas → D6 Cerrar partido → D7 Salud → Grafana (pasa a Santiago)

### Antes de empezar

- Pestaña 1: front, `http://localhost:5173`
- Pestaña 2: mesa de control, `http://localhost:5173/partidos/PAR-DEMO-API/mesa`
- Pestaña 3: salud, `http://localhost:5173/salud`
- Pestaña 4: Grafana, `http://localhost:3000`, **ya logueado**, dashboard *2. API integrada*, "Last 15 minutes" (usuario en [`../grafana/README.md`](../grafana/README.md))
- Zoom del navegador al **125 %**

---

### D1 · Buscar un equipo — 0:30

**Hacé**
1. En el inicio, señalá *Partidos destacados*.
2. Escribí `a1` en **Código FIFA del equipo** y Enter.
3. Borrá, escribí `ARG` y Enter.

**Vas a ver:** con `a1`, el aviso *"El código tiene que ser de 3 letras"*. Con `ARG`, la ficha.

**Decí:** "El código se valida en el front con el mismo patrón que la API: nada inválido llega a una base."

---

### D2 · Ficha del equipo — 1:00 · MongoDB

**Hacé**
1. Señalá la banda de arriba: ranking 1, grupo A, 26 jugadores, sede.
2. En **Plantel**, tocá el chip **Delanteros**.

**Vas a ver:** el plantel pasa de 26 a 9 jugadores.

**Decí:** "Todo esto es un solo documento de MongoDB, leído por su id, que es el código FIFA."

---

### D3 · Partido y eventos — 1:00 · Neo4j

**Hacé**
1. En la columna derecha, tocá **ARG–BEL** (29 de junio, dieciseisavos).
2. Pestaña **Eventos y comentarios**.
3. Tocá el chip **Goles**.

**Vas a ver:** la línea de tiempo del 0′ al 90′; con el filtro, un solo gol: Fernández, 13′. Arriba, 1–0.

**Decí:** "El 1–0 no está guardado: se calcula contando los eventos de gol."

---

### D4 · Comentarios — 1:00 · Cassandra

**Hacé**
1. Mostrá la lista de **Comentarios** (columna derecha).
2. Abajo, en **Publicar un comentario**, escribí *"Golazo en vivo desde la defensa"*, minuto **90**. Alias y usuario ya vienen completos.
3. **Publicar**.

**Vas a ver:** *"Comentario publicado."*, pero el comentario **no aparece arriba**. La lista muestra los 15 más recientes, del final del partido.

**Decí:** "No aparece arriba porque se guardó en la partición de su ventana de 10 minutos: es la clave (partido, ventana, bucket)."

---

### D5 · Estadísticas — 0:45 · InfluxDB

**Hacé**
1. Pestaña **Estadísticas**.
2. Señalá *Comparativa*: Goles 1–0.
3. Cambiá período a **2T** y detalle a **5 min**.

**Vas a ver:** al pie, *Ver los datos en tabla* pasa de **190 filas** a **20 filas**.

**Decí:** "Esa agregación por tiempo la hace InfluxDB, no la pantalla. Y los goles coinciden con el grafo."

---

### D6 · Cerrar un partido — 1:15 · Neo4j, CP

**Hacé**
1. Pasá a la **pestaña 2** (ARG–BRA).
2. **Cerrar partido** → **Sí, cerrar partido**.
3. En **Registrar evento**: tipo *Fin del partido*, minuto **90**, condición **Sin equipo**, dorsal **vacío** → **Registrar evento**.
4. **Cerrar partido** → confirmar. Tarda 2–3 segundos.
5. **Intentar cerrar otra vez** → confirmar.

**Vas a ver:**
- en el paso 2, **409 `MISSING_FIN_PARTIDO`**;
- en el paso 3, **201**;
- en el paso 4, **200 "Partido cerrado: ARG 1 – 0 BRA"**;
- en el paso 5, **409 `INVALID_TRANSITION`**.

**Decí:** "El cierre es CP: exige el evento de fin, calcula el marcador desde los goles y no acepta un segundo resultado."

> **Ojo en el paso 3:** si queda la condición en *Local (ARG)* o el dorsal en 9, sale **400 `EVENT_RULE_VIOLATION`**. No pasa nada: decí "la API valida las reglas de cada tipo de evento", corregí los dos campos y registrá de nuevo.

---

### D7 · Salud de las fuentes — 0:30

**Hacé**
1. Pasá a la **pestaña 3**.

**Vas a ver:** las cinco fuentes en UP, con su latencia.

**Decí:** "Cada base tiene su propio timeout: si una cae, solo esa queda en rojo y el resto sigue. Santiago les muestra eso con datos."

---

### Al terminar: pase a Santiago

Santiago toma la **pestaña 4** (Grafana): en *2. API integrada* se ven las requests de la demo (los 200, el 201 del evento y los 409 del cierre) y *Porcentaje de respuestas 5xx* en "No data", o sea sin errores. En *3. Comparación entre bases*, la latencia de cada base vista desde la API. Después vuelve a las diapositivas 11, 12, 14 y 15.

### Si sobra un minuto (opcional)

Abrir `http://localhost:5173/sesiones/demo-ses-0000001-1`: la sesión de Redis con su TTL restante y el tope de 12 h. **Decí:** "La sesión vence sola; consultarla desde acá no la renueva."

### Notas de la demo

- **Ensayos.** De punta a punta el 14/11/2026, y de nuevo el 18/11/2026 desde volúmenes vacíos con las cargas de muestra: D1 a D7 y el paso opcional dan lo que dicen las tarjetas. Grafana no se probó en el segundo ensayo.
- **Comentarios de D4.** Con la carga de muestra de Cassandra, los 15 más recientes van del 124′ al 91′; con la carga masiva, casi todos son del 124′.
- **Goles de D5.** Desde el 15/11/2026, InfluxDB usa la misma plantilla de goles que `carga.cypher` (paso 15). Si ARG–BEL muestra Goles 0–2, el volumen tiene la carga vieja: correr el paso 1 de la preparación.
- **Pregunta probable (H1).** "El gol es del 9, pero en el plantel el 9 es arquero." La ficha sale de MongoDB y el partido de Neo4j, y los planteles de las dos bases no están unificados; además, 6 DNI coinciden entre las dos bases para jugadores distintos (H1 en [`../../docs/ESTADO-CANONICO-NECESIDADES.md`](../../docs/ESTADO-CANONICO-NECESIDADES.md)). Respuesta: "Dentro de cada base el dorsal y el DNI son únicos. Entre MongoDB y Neo4j el roster no está unificado, es el hallazgo H1, y por eso la API nunca cruza esas dos bases."

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
| La mesa de `PAR-DEMO-API` no muestra los botones y dice "La mesa de control sólo está disponible mientras el partido está PROGRAMADO" | El partido quedó cerrado de un ensayo anterior: no se corrió el paso 2 de la preparación. Correrlo, esperar un minuto (caché del detalle en Redis) y recargar la pestaña. Si no hay tiempo, explicar el flujo con la diapositiva 8 |
| D6 (paso 3) responde 400 `EVENT_RULE_VIOLATION` | Falta poner *Sin equipo* y vaciar el dorsal (ver "Ojo en el paso 3" de D6) |
| Estadísticas vacías | Falta el token o la carga de muestra de InfluxDB ([`demo.md`](demo.md) §3). Mostrar la diapositiva de volúmenes |
| Nada anda | Diapositivas + capturas de [`../evidencia/dashboards/`](../evidencia/dashboards/) y del front en [`../../fixture2030-hito10-api/docs/evidencia/front-stitch/`](../../fixture2030-hito10-api/docs/evidencia/front-stitch/) (inicio, ficha ARG, eventos y comentarios, estadísticas, estados de error). Las decisiones se defienden igual |

## Después

`Ctrl+C` en el front y en la API; las bases con `docker compose stop` (nunca `down -v`). Para repetir la demo, volver a correr los pasos 2 y 3 de la preparación.
