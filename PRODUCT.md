# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

React + Vite + TypeScript, el mismo del front `web/` del PR 13 (Hito 10, rama `claude/hito-10-api-rest-fixture-f1dca3`, todavía abierto). Consume la API REST FastAPI de ese PR con tipos generados desde `openapi/openapi.yaml`.

## Users

Hincha del Mundial 2030 que sigue equipos y partidos desde una pantalla de escritorio. Quiere ver la ficha y el plantel de un equipo, el detalle y la línea de tiempo de un partido, leer y publicar comentarios y mirar las estadísticas en vivo. Su sesión se valida en cada request.

Otros consumidores de la API (mesa de control del partido, moderación, operación) existen en los casos de uso, pero no son el usuario principal de esta UX.

## Product Purpose

Fixture 2030 es la app del hincha sobre una plataforma de datos con cinco fuentes: MongoDB, Neo4j, Cassandra, Redis e InfluxDB. La UX tiene que dejar ver equipos, partidos, eventos, comentarios y estadísticas sin que el hincha sepa qué base responde. El éxito es encontrar un equipo o partido y entender qué pasó, o qué está pasando, en pocos pasos.

## Positioning

Una sola app que junta, en el detalle de un partido, eventos, comentarios de otros hinchas y estadísticas por ventana de tiempo. Esa combinación sale de las cinco bases del TPO.

## Operating Context

- Uso en escritorio; mobile queda como adaptación.
- Los datos vienen de la API del PR 13. Los endpoints existentes son los de los casos de uso CU1–CU13 de `fixture2030-hito10-api/docs/casos_de_uso.md`.
- La UX no puede pedir datos que la API no expone.
- Estados reales que la UX debe resolver: cargando, vacío (por ejemplo, partido sin eventos), no encontrado (404), entrada inválida (400), conflicto (409) y fuente no disponible (503, con reintento).
- Los códigos de equipo del grafo (Neo4j) no coinciden con los de Mongo en algunos países (Hallazgo H1): la UX no debe asumir un cruce directo entre fichas y partidos.
- La estadística en vivo admite ventanas de hasta 3 h y agregación `raw`, `1m` o `5m`.

## Capabilities and Constraints

- Ficha de equipo y plantel paginado, con filtro por posición.
- Partidos de un equipo; detalle de partido con marcador derivado de los goles.
- Línea de tiempo de eventos, con filtro por los 12 tipos del catálogo.
- Comentarios paginados y alta de comentario, idempotente.
- Estadísticas de un partido por ventana temporal.
- Validación de sesión.
- Sin autenticación de usuarios todavía: Usuarios (N4) y Auditoría (N9) no están implementadas.
- IRIS (RF8) queda fuera de la API.
- Sin decidir: login real, idioma distinto del español, y si la mesa de control forma parte de esta app o de otra.

## Brand Commitments

Ninguno confirmado. El nombre de trabajo es "Fixture 2030". No hay logo, paleta ni voz definidos.

## Evidence on Hand

- API y front del PR 13, con datos de muestra (por ejemplo, el partido de demo `PAR-DEMO-API`).
- Casos de uso en `fixture2030-hito10-api/docs/casos_de_uso.md`.
- No hay maquetas, estudios de usuarios ni activos de marca. Nada de eso debe inventarse.

## Product Principles

1. El hincha ve el dato del partido, no la base que lo guarda.
2. Un estado vacío, un 404 y una fuente caída son tres situaciones distintas, y la UX las muestra distinto.
3. La UX solo promete lo que la API entrega; no se diseñan funciones sin endpoint.
4. El detalle del partido es la pantalla central: eventos, comentarios y estadísticas están a un paso.

## Accessibility & Inclusion

Sin requisito específico establecido. Pendiente de confirmar.
