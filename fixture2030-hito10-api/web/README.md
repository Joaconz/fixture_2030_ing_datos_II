# Fixture 2030 · Centro de datos (front del Hito 10)

Front de consumo de la API REST integrada (`../app`, FastAPI). Muestra equipos, partidos, eventos, comentarios,
estadísticas, sesiones y la salud de las cinco fuentes. Cada panel indica de qué base sale el dato
(MongoDB, Neo4j, Cassandra, Redis, InfluxDB) y el `X-Request-Id` de la respuesta.

## Requisitos

- Node 20.19+ (probado con Node 24) y npm.
- La API corriendo en `http://localhost:8000` (ver el README de la API). El front compila y testea sin ella.

## Comandos

```bash
npm install          # dependencias
npm run dev          # http://localhost:5173 (puerto fijo: es el que está en CORS_ORIGINS por defecto)
npm run build        # tsc -b (estricto) + vite build → dist/
npm run lint         # ESLint (typescript-eslint, react-hooks, react-refresh; no-explicit-any = error)
npm test             # Vitest: cliente, errores, Idempotency-Key, cursor, fechas UTC
npm run gen:api      # regenera src/api/schema.d.ts desde ../openapi/openapi.yaml
npm run gen:api:check  # falla si schema.d.ts no coincide con el contrato
```

## Contrato y cliente

- `src/api/schema.d.ts` lo genera `openapi-typescript` desde `../openapi/openapi.yaml` (no se edita a mano; se
  versiona para que el build no dependa de la carpeta de la API). Se genera con `--default-non-nullable false`
  para que los campos con `default` (p. ej. `idioma` de `ComentarioNuevo`) sigan siendo opcionales en los cuerpos.
- `src/api/client.ts` usa `openapi-fetch` sobre esos tipos: rutas, parámetros, cabeceras y cuerpos quedan tipados
  por el contrato. `run()` devuelve `{ok, data, meta} | {ok:false, error, meta}` con `status`, `X-Request-Id`,
  `X-Cache`, `Idempotent-Replayed` y `Retry-After`.
- `src/api/enums.ts` tiene las listas de los enums para los selects; si el contrato agrega o quita un valor, no compila.
- Errores (`src/api/errors.ts` + `components/ErrorPanel.tsx`): todos los errores son `{code, message, requestId, details?}`
  y se muestran con `code`, `message` y `requestId` copiable. Tratamiento por clase:
  404 *no existe*, 400 *entrada inválida* (con detalle por campo), 409 *conflicto de estado*, 403 *acceso denegado*,
  503 *“La fuente X no está disponible”* (la fuente sale de `details[campo=dependencia]`) con botón Reintentar, y
  *sin conexión* cuando no hubo respuesta HTTP (API apagada, CORS, permiso de red local).
- `/health/dependencias` con 503 trae el mismo cuerpo que el 200: se muestra como dato, no como error.

## Variables

| Variable | Default | Uso |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | URL base de la API (`src/config.ts`) |

Copiar `.env.example` a `.env.local` (ignorado por git) para cambiarla en desarrollo. En Vercel se define en
*Settings → Environment Variables* (se lee en el build).

## Vistas

| Ruta | Qué muestra | Fuentes |
|---|---|---|
| `/` | Buscadores (equipo, partido, sesión) y accesos de demo | — |
| `/equipos/:codigo` | Ficha, plantel paginado (filtro por posición, “Cargar más” por `nextCursor`) y partidos | MongoDB, Neo4j |
| `/partidos/:id` | Detalle con marcador y badge `X-Cache`; pestañas Eventos, Comentarios, Estadísticas y Mesa de control (sólo si está PROGRAMADO) | Neo4j, Redis, Cassandra, InfluxDB |
| `/sesiones/:id` | Campos y TTL (cuenta regresiva local), invalidar con confirmación | Redis |
| `/salud` | Estado y latencia de las cinco dependencias | todas |

La pestaña activa del partido va en la URL (`?tab=eventos|comentarios|estadisticas|mesa`).

**Idempotencia (comentarios y mesa de control).** Cada envío genera una `Idempotency-Key` nueva
(`com-`/`evt-` + 32 hex, cumple `^[A-Za-z0-9_-]{8,64}$`). “Reenviar la misma request” repite clave y cuerpo: la
API responde 200 + `Idempotent-Replayed: true` en vez de 201. En la mesa, la casilla “usar la clave del último envío”
manda otro cuerpo con la misma clave para mostrar `409 IDEMPOTENCY_KEY_REUSED`. El historial de envíos muestra todo
lado a lado.

**Fechas.** Todo se muestra y se edita en UTC (reloj del torneo). `creadoEn` se precarga en `fechaHora + 47 min`;
la ventana de estadísticas, en `fechaHora .. fechaHora + 30 min`.

## Deploy a Vercel

1. Importar el repo en Vercel con **Root Directory** = `fixture2030-hito10-api/web` (framework Vite; build
   `npm run build`, output `dist`). `vercel.json` ya trae el rewrite SPA `/(.*) → /index.html`.
2. (Opcional) definir `VITE_API_URL` si la API no está en `http://localhost:8000`.
3. **Agregar el dominio de Vercel a `CORS_ORIGINS` de la API** (en su `.env`), por ejemplo
   `CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,https://<proyecto>.vercel.app`, y reiniciar la API.

## Limitaciones (la API es local)

- El front publicado en Vercel (HTTPS) llama a `http://localhost:8000` **en la máquina de quien lo abre**: sólo
  funciona en la notebook donde corre la API.
- La API responde `Access-Control-Allow-Private-Network: true`. **Chrome** puede pedir permiso de “acceso a la red
  local” la primera vez: hay que aceptarlo. **Safari y Firefox** pueden bloquear la llamada como contenido mixto
  (HTTPS → HTTP). Recomendación: usar Chrome, o correr el front local con `npm run dev`.
- Si la API no responde, el indicador de arriba pasa a “API sin conexión” y cada panel muestra el error de red con
  las causas posibles.

## Diseño

Sistema visual definido con la guía *ui-ux-pro-max* para dashboards de datos en tiempo real:

- **Paleta**: azul de datos (`#1D4ED8` claro / `#6AA8FF` oscuro) con acento naranja para identificadores y la serie
  visitante; tokens semánticos (ok, warn, danger, info, conflict) en `src/styles/tokens.css`. Contrastes AA en los
  dos temas. Tema claro/oscuro: sigue al sistema y se puede fijar desde el encabezado.
- **Tipografía**: Fira Sans (texto) y Fira Code (ids, códigos, números tabulares), autoalojadas con `@fontsource`
  (sin llamadas a terceros).
- **CSS propio con variables** en lugar de Tailwind o una librería de UI: son pocas vistas, los tokens alcanzan, y
  así no hay configuración extra ni dependencias pesadas. Íconos SVG inline de trazo uniforme (sin emojis).
- **Gráficos** SVG propios (sin librería): serie local con línea continua y círculos, visitante discontinua con
  cuadrados (no depende sólo del color), tooltip al pasar el puntero, y tabla de datos como alternativa accesible.
  “Sin puntos en la ventana” (200 vacío) se muestra distinto del 503.
- **Accesibilidad**: labels visibles, foco visible, enlace “Saltar al contenido”, foco al `h1` en cada cambio de
  ruta, pestañas ARIA con flechas, `role="alert"` en errores, confirmación modal con `<dialog>` para acciones
  destructivas, `prefers-reduced-motion`. Responsive desde 360 px sin scroll horizontal de página.
