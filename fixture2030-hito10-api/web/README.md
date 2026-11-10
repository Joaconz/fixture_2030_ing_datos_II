# Fixture 2030 · front del hincha (Hito 10)

Front de consumo de la API REST integrada (`../app`, FastAPI) para el hincha del Mundial 2030: buscar un
equipo por código FIFA, ver su ficha, su plantel y sus partidos, y entrar al detalle de un partido con eventos,
comentarios, estadísticas y planteles. El diseño es el del proyecto de Google Stitch
**“Fixture 2030 - B Estadio de día”** (`8584982924763569966`), con el sistema de `stitch/DESIGN.md` y las
reglas de producto de `PRODUCT.md`. El hincha ve el dato del partido, no la base que lo guarda: las pantallas
no nombran MongoDB, Neo4j, Cassandra, Redis ni InfluxDB.

## Requisitos

- Node 20.19+ (probado con Node 24) y npm.
- La API corriendo en `http://localhost:8000` (ver el README de la API). El front compila y testea sin ella.

## Comandos

```bash
npm ci               # dependencias
npm run dev          # http://localhost:5173 (puerto fijo: es el que está en CORS_ORIGINS por defecto)
npm run build        # tsc -b (estricto) + vite build → dist/
npm run lint         # ESLint (typescript-eslint, react-hooks, react-refresh; no-explicit-any = error)
npm test             # Vitest: cliente, errores, Idempotency-Key, cursor, fechas, código FIFA, partido, plantel, estadísticas
npm run gen:api      # regenera src/api/schema.d.ts desde ../openapi/openapi.yaml
npm run gen:api:check  # falla si schema.d.ts no coincide con el contrato
```

## Pantallas (Stitch → front)

| Pantalla de Stitch | Ruta | Casos de uso | Qué muestra |
|---|---|---|---|
| Inicio | `/` | CU4 | Buscador por código FIFA y accesos por código (izquierda); partidos destacados (derecha). |
| Ficha de equipo (“Detalle selección”) | `/equipos/:codigo` | CU1, CU2, CU3 | Banda cobalto con código, confederación, grupo, DT, colores y datos (ranking, grupo, jugadores, sede); plantel por línea con filtro por posición y “Ver más”; partidos del equipo. |
| Eventos y comentarios | `/partidos/:id` (`?tab=eventos`) | CU4, CU5, CU8, CU9 | Cabecera de marcador a todo el ancho y tres pestañas. Línea de tiempo (minuto, ícono, protagonista y dorsal, equipo) con filtro por tipo; comentarios paginados y alta idempotente. |
| Estadísticas | `?tab=estadisticas` | CU12 | Período (1T, 2T, completo) y detalle (crudo, 1 min, 5 min); posesión promedio con barra dividida y línea por equipo; comparativa de goles, tiros y pases; evolución de acumulados; tabla de datos. |
| Alineaciones | `?tab=alineaciones` | CU1, CU2 | Dos columnas, una por equipo, con DT y plantel completo. |
| Hoja de Estados | (todas) | — | Vacío, no encontrado, dato inválido y fuente no disponible, cuatro composiciones distintas (`components/Estados.tsx`). |

Vistas de **operación**, fuera de la navegación del hincha (se llega por URL y conservan el detalle técnico de
la versión anterior: status HTTP, `X-Request-Id`, `X-Cache`, `Idempotency-Key`, nombre de cada fuente):

| Ruta | Qué muestra |
|---|---|
| `/partidos/:id/mesa` | Mesa de control (CU6, CU7): alta de eventos idempotente y cierre del partido, sólo si está PROGRAMADO. `?tab=mesa` redirige acá. |
| `/sesiones/:id` | Sesión (CU10, CU11) con TTL e invalidación. |
| `/salud` | Estado y latencia de las cinco fuentes (CU13). |

## Estados

| Situación | Composición | Ejemplo real |
|---|---|---|
| Cargando | Líneas con altura reservada (sin saltos de layout). | Cualquier panel mientras responde la API. |
| Vacío (200 con lista vacía) | Título + texto + acción (“Ver todos los eventos”). | `PAR-D16-01`: partido programado sin eventos. |
| No encontrado (404) | “No encontramos…”, mensaje de la API y buscador FIFA o “Volver al inicio”. | `/equipos/URU` (está en el grafo, no tiene ficha: Hallazgo H1). |
| Dato inválido (400) | Campo para corregir y mensaje. El código FIFA se valida en el navegador (`^[A-Z]{3}$`, el mismo patrón que la API) antes de pedir nada; un 400 de la API se muestra con “Ver detalle”. | `/equipos/12`, o “a1” en el buscador. |
| Fuente no disponible (503/504) | “No pudimos cargar los datos de *comentarios* ahora”, botón **Reintentar** e **ID de solicitud** copiable. La parte de la app sale de `details[campo=dependencia]` sin nombrar la base. | Instancia de la API con Cassandra/InfluxDB inalcanzables (ver evidencia). |
| Sin conexión | “Sin conexión” + Reintentar. | API apagada. |

Cada panel falla por separado: si cae la fuente de comentarios, la línea de tiempo sigue funcionando. Los
códigos del grafo y de las fichas no siempre coinciden (Hallazgo H1), así que la ficha y los partidos de un
equipo se piden por separado y nunca se cruzan.

**Comentarios (CU9).** El alta usa una `Idempotency-Key` nueva por envío; si el envío falla, “Reintentar”
repite la misma clave y el mismo cuerpo, así que un comentario que sí llegó no se duplica (la API responde
200 con `Idempotent-Replayed: true` y la pantalla dice “ya estaba publicado”). El comentario se fecha en el
minuto del partido que elige el hincha (`creadoEn = fechaHora + minuto`, reloj del torneo simulado en UTC).

**Estadísticas (CU12).** Los períodos siguen el reloj de la carga del Hito 8 (primer tiempo 0′–47′, 15 min
de entretiempo sin datos, segundo tiempo desde 62′ de pared): 1T = [0′, 48′), 2T = [60′, 112′),
completo = [0′, 112′), todas dentro del tope de 3 h. El eje X de los gráficos está en minutos de juego.

## Datos que la API no ofrece

Lo que muestran las pantallas de Stitch y no tiene endpoint (PRODUCT.md, principio 3: no se inventa). Donde
el hueco es visible se muestra como “no disponible”; lo decorativo se omitió.

| Pantalla | Dato del diseño | Cómo quedó |
|---|---|---|
| Inicio | Calendario completo, filtros por región y fase, tabla de posiciones de grupos, goleadores históricos, cifras del torneo, sedes con fotos, boletín | Tarjeta “no disponible”. Los destacados son cuatro partidos conocidos de la carga de muestra pedidos uno por uno (no hay listado del fixture). |
| Ficha de equipo | Pizarra táctica con el once titular y formación, posición/puntos/GF/GC/DG del grupo, clubes de los jugadores, ayudantes de campo, capitanes, estrellas/año de fundación | Tarjeta “no disponible” para formación y posiciones; el bloque de datos usa ranking, grupo, jugadores y sede, que sí existen. |
| Partido (cabecera) | Estado “En vivo” con minuto, “Segundo tiempo” | La API sólo informa PROGRAMADO y FINALIZADO; la insignia en píldora existe pero el acento “En vivo” nunca se usa. |
| Eventos | Descripción libre del evento (“Asistencia precisa tras tiro de esquina”), jugador que entra y sale en un cambio | Se muestra tipo, protagonista y dorsal, que es lo que entrega CU5. |
| Comentarios | Usuarios activos, mensaje fijado por moderación, rol del usuario (Hincha/Analista), retardo | Omitido. Sin login (N4 no está implementada): el alias y el usuario se escriben a mano. |
| Estadísticas | xG, tenencia efectiva, secuencias de pases, zonas de ataque, posesión por tercios, duelo de figuras, exportar CSV | Omitido (DESIGN.md también prohíbe xG). Se muestra lo que trae CU12: posesión, pases, tiros y goles acumulados. |
| Alineaciones | Titulares, suplentes y reservas, formación, pizarra dual, duelos clave, ingresos y amonestaciones por jugador | Tarjeta “no disponible” y plantel completo de cada equipo (CU2). |

## Diferencias con el diseño de Stitch

- **Sin selector de tema.** Las pantallas de Stitch tienen un ícono de modo oscuro en la barra y DESIGN.md §5
  lo nombra, pero §6 prohíbe el modo oscuro: se priorizó la prohibición y el front es sólo claro.
- **Sin degradados ni fotos.** La banda de la ficha y la cabecera de Inicio de Stitch usan degradados y fotos
  de estadios; DESIGN.md pide superficies planas y la API no tiene imágenes. La banda es cobalto plano.
- **Inicio más sobrio** que la variante “Editorial Centenario”: se tomó el layout asimétrico de DESIGN.md §5
  (buscador a la izquierda, destacados a la derecha) y se dejaron afuera las secciones sin datos.
- **Sin navegación extra ni pie de página** (DESIGN.md §6): la barra tiene la marca, “volver” y el buscador.
- **Chips de eventos**: Todos, Goles, Amarillas, Rojas y Cambios como chips, y los otros siete tipos del
  catálogo en un selector (“Tarjetas” del diseño agrupaba dos tipos y la API filtra por uno solo).
- **Íconos SVG propios** en lugar de Material Symbols (sin pedidos a terceros); tarjeta amarilla en ámbar y
  roja en el rojo de error, como en la captura.

## Contrato y cliente

- `src/api/schema.d.ts` lo genera `openapi-typescript` desde `../openapi/openapi.yaml` (no se edita a mano).
- `src/api/client.ts` usa `openapi-fetch` sobre esos tipos; `run()` devuelve `{ok, data, meta} | {ok:false, error, meta}`
  con `status`, `X-Request-Id`, `X-Cache`, `Idempotent-Replayed` y `Retry-After`. No se agregó ningún endpoint.
- `src/api/errors.ts` clasifica cada error (404, 400, 409, 403, 503/504, red) y `areaDeFuente()` traduce la
  fuente caída a lo que el hincha deja de ver (“comentarios”, “estadísticas”…).

## Variables

| Variable | Default | Uso |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | URL base de la API (`src/config.ts`) |

Copiar `.env.example` a `.env.local` (ignorado por git) para cambiarla en desarrollo. En Vercel se define en
*Settings → Environment Variables* (se lee en el build).

## Diseño

- **Tokens** en `src/styles/tokens.css`, con la paleta de DESIGN.md §2: blanco roto `#F7F8FA`, blanco,
  azul noche `#14213D`, un único acento cobalto `#1D3FBF`, gris azulado `#C5C5D6` / `#64748B` y rojo de error
  `#BA1A1A`. Esquinas de 10 px; píldoras sólo en estados y chips; sombras teñidas de azul noche.
- **Tipografía**: Plus Jakarta Sans en toda la interfaz (títulos 700–800, texto 400, etiquetas 600–700), con
  cifras tabulares en marcadores, minutos y estadísticas; autoalojada con `@fontsource` (sin llamadas a terceros).
- **CSS propio**: `src/styles/app.css` (base, formularios, tablas, vistas de operación) y `src/styles/fixture.css`
  (pantallas del hincha). Sin Tailwind ni librería de UI.
- **Gráficos** SVG propios: una línea fina por equipo (cobalto y gris azulado; la visitante además discontinua
  con marcadores cuadrados, para no depender sólo del color), sin degradados, tooltip y tabla de datos como
  alternativa accesible.
- **Accesibilidad**: labels visibles, foco visible, “Saltar al contenido”, foco al `h1` al cambiar de ruta,
  pestañas ARIA con flechas, `role="alert"` en errores, chips y segmentos como radios reales.
- **Responsive**: diseñado a 1280–1440 px; por debajo de 1024 px las columnas se apilan y el marcador se
  reacomoda en mobile (375 px) sin scroll horizontal.

## Evidencia

Capturas del recorrido contra la API real y comparativas lado a lado con las capturas de Stitch en
[`../docs/evidencia/front-stitch/`](../docs/evidencia/front-stitch/README.md).

## Deploy a Vercel

1. Importar el repo en Vercel con **Root Directory** = `fixture2030-hito10-api/web` (framework Vite; build
   `npm run build`, output `dist`). `vercel.json` ya trae el rewrite SPA `/(.*) → /index.html`.
2. (Opcional) definir `VITE_API_URL` si la API no está en `http://localhost:8000`.
3. **Agregar el dominio de Vercel a `CORS_ORIGINS` de la API** (en su `.env`) y reiniciar la API.

## Limitaciones (la API es local)

- El front publicado en Vercel (HTTPS) llama a `http://localhost:8000` **en la máquina de quien lo abre**: sólo
  funciona en la notebook donde corre la API. Chrome puede pedir permiso de “acceso a la red local”; Safari y
  Firefox pueden bloquear la llamada como contenido mixto. Recomendación: Chrome, o `npm run dev`.
