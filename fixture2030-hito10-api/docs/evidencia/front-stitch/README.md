# Evidencia · front implementado desde Stitch

Recorrido del front de `web/` contra la API real (10/11/2026), con las pantallas del proyecto de Google Stitch
**“Fixture 2030 - B Estadio de día”** (`8584982924763569966`) como referencia. Detalle de pantallas, datos
que la API no ofrece y diferencias con el diseño en [`web/README.md`](../../../web/README.md).

## Entorno

- **Bases:** las cinco de los Hitos 4–8 que ya corrían en la notebook (`fixture2030_mongo`, `fixture2030-neo4j`,
  `fixture2030-cassandra`, `fixture2030-redis`, `fixture2030-influxdb`), con sus cargas de muestra. Sólo lectura,
  salvo un comentario de prueba en `PAR-A-1` (captura 14).
- **API:** contenedor propio `python:3.12-slim` (`front-stitch-api`, `127.0.0.1:8010`) con el código de esta rama,
  conectado a las redes de las cinco bases. `/health/dependencias` → las cinco `UP`.
- **Fuente caída:** segunda instancia (`front-stitch-api-caida`, `:8011`) con Cassandra e InfluxDB apuntando a
  un host inexistente, para mostrar 503/504 sin detener contenedores compartidos.
- **Front:** `vite` en `:5183` (contra `:8010`) y `:5184` (contra `:8011`). Capturas de escritorio con Chrome
  headless a 1280 px de ancho; las de mobile y las `.jpg` salen del navegador del IDE (375 px).

Todo lo levantado para esta prueba se apagó y borró al terminar (los dos contenedores de la API y los dos `vite`);
las bases compartidas no se tocaron.

## Pantallas

| Captura | Qué muestra |
|---|---|
| `01-inicio.png` | Inicio asimétrico: buscador y accesos por código; partidos destacados con marcador, estado, fecha y sede. |
| `02-equipo-ARG.png` | Ficha de Argentina: banda cobalto, plantel por línea, partidos del equipo. |
| `03-partido-eventos-comentarios.png` | `PAR-A-1`: cabecera de marcador, línea de tiempo y comentarios en dos columnas iguales. |
| `04-partido-estadisticas.png` | Posesión promedio y por minuto, comparativa y evolución (período completo, 1 min). |
| `05-partido-alineaciones.png` | Plantel de cada equipo con DT; aviso de que no hay titulares/suplentes. |
| `13-mobile-partido.jpg` | Detalle de partido a 375 px: marcador reacomodado, sin scroll horizontal de página. |
| `14-comentario-publicado.jpg` | Alta de comentario (CU9): 201, lista recargada, “Comentario publicado.” |

## Estados

| Captura | Estado | Origen |
|---|---|---|
| `06-estado-vacio-partido-sin-eventos.png` | Vacío | `PAR-D16-01` (programado): `GET /eventos` → 200 con `items: []`. |
| `07-estado-404-equipo-sin-ficha.png` | No encontrado | `/equipos/URU` → 404 `TEAM_NOT_FOUND`; los partidos de URU (grafo) cargan igual (Hallazgo H1). |
| `08-estado-dato-invalido.png` | Dato inválido | `/equipos/12`: el código se valida en el navegador antes de pedir nada. |
| `09-estado-503-comentarios.png` | Fuente no disponible | Instancia `:8011`: `503 DEPENDENCY_UNAVAILABLE` (cassandra) con Reintentar e ID de solicitud; la línea de tiempo sigue andando. |
| `10-estado-504-estadisticas.png` | Fuente no disponible (timeout) | Instancia `:8011`: `504 DEPENDENCY_TIMEOUT` (influxdb). |
| `11-estado-sin-conexion.jpg` | Sin conexión | API que acepta la conexión pero no responde: el tope de 15 s del cliente corta la carga. |
| `12-estado-504-eventos-y-404-comentarios-real.png` | 504 + 404 en la misma pantalla | `PAR-DEMO-API` en la instancia normal: Neo4j tardó más de 2 s con su línea de tiempo (504 real, no provocado) y el partido no tiene configuración de comentarios (404). |

## Lado a lado con Stitch

`comparativa-*.jpg`: a la izquierda la captura de Stitch, a la derecha la implementación con datos reales.
Las diferencias de contenido (en vivo, xG, pizarra táctica, fotos, tablas de grupos) son datos que la API no
ofrece o que DESIGN.md prohíbe; están listadas en el README del front.

## Verificación

- `npm ci` · `npm run lint` · `npm run build` · `npm test` (40 tests) en verde.
- Ninguna request a endpoints fuera de `openapi/openapi.yaml`.
