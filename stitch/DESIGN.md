# Design System: Fixture 2030 (Estadio de día)

App web de escritorio para hinchas del Mundial 2030. Interfaz de uso: se lee rápido, se compara y se vuelve a consultar durante un partido. Proyecto de Stitch: "Fixture 2030 - B Estadio de día".

## 1. Visual Theme & Atmosphere

Institucional, limpio y luminoso, como un estadio de día. Superficies blancas sobre un fondo blanco roto, texto azul noche y un único acento azul cobalto. Densidad media, sin ornamento: la jerarquía sale del peso, el tamaño y el color. Sin modo oscuro, sin verde neón, sin aspecto tecnológico.

## 2. Color Palette & Roles

- **Blanco Roto** (#F7F8FA) — Fondo de página
- **Blanco Puro** (#FFFFFF) — Superficies y tarjetas
- **Azul Noche** (#14213D) — Texto principal
- **Cobalto Profundo** (#1D3FBF) — Único acento: botón primario, pestaña activa, chip activo, foco
- **Gris Azulado** (#C5C5D6) — Bordes y divisores suaves
- **Gris Azulado Medio** (#64748B) — Texto secundario y segunda serie en gráficos
- **Rojo Error** (#BA1A1A) — Solo errores

Un solo acento. Sin negro puro. Las sombras se tiñen hacia el azul noche.

## 3. Typography Rules

- **Toda la interfaz:** Plus Jakarta Sans. Títulos 700 (40/32/24/20 px), texto 400 (16/14 px), etiquetas 600 (14/12/11 px).
- **Cifras, minutos, marcadores, estadísticas y códigos FIFA:** cifras tabulares, grandes en los marcadores.
- **Prohibido:** Inter, fuentes serif.

## 4. Component Stylings

* **Esquinas:** 10 px en botones, entradas, tarjetas y contenedores. Las píldoras solo para estados y chips.
* **Botones:** El primario es cobalto con texto blanco; el secundario es blanco con borde gris azulado. Al pasar el cursor oscurecen un 10 %.
* **Chips:** En píldora. Inactivo: fondo blanco roto con borde sutil. Activo: cobalto con texto blanco.
* **Pestañas:** Subrayado cobalto en la activa.
* **Entradas:** Fondo blanco, borde gris azulado, foco en cobalto. Etiqueta arriba y error debajo.
* **Tarjetas:** Blancas, con borde sutil y sombra difusa teñida de azul noche.
* **Insignia de estado de partido:** "En vivo", "Programado" y "Finalizado" en píldora; solo "En vivo" usa el acento.
* **Línea de tiempo de eventos:** Eje vertical con el minuto, el tipo de evento, el protagonista y el dorsal, sin emojis.
* **Gráfico de estadísticas:** Una línea fina por equipo (cobalto y gris azulado), ejes legibles, sin degradados.
* **Estados:** Vacío, no encontrado, dato inválido y fuente no disponible, cuatro composiciones distintas, cada una con título y acción. "Fuente no disponible" lleva el botón "Reintentar" y el identificador de la solicitud.

## 5. Layout Principles

- Escritorio a 1440 px, cuadrícula de 12 columnas y margen de 24 a 32 px. Una sola columna por debajo de 768 px.
- Barra superior fina: "Fixture 2030", buscador de equipo por código FIFA y cambio de tema. Sin pestañas de navegación extra.
- Detalle de partido: cabecera de marcador a todo el ancho (con sede, estado y fecha) y tres pestañas: "Eventos y comentarios", "Estadísticas" y "Alineaciones". En "Eventos y comentarios" el cuerpo son dos columnas del mismo peso: línea de tiempo de eventos a la izquierda y comentarios a la derecha. "Alineaciones" muestra dos columnas, una por equipo, con titulares, suplentes y reservas. No hay columna lateral de fichas de equipo.
- Inicio asimétrico: buscador y accesos por código a la izquierda, partidos destacados a la derecha.

## 6. Anti-Patterns (Banned)

- Sin emojis. Sin modo oscuro. Sin degradados de texto ni resplandores.
- Sin árbitro, xG, audio, noticias, tienda, login ni pie de página.
- Sin pestañas "Summary", "Lineups", "Matches", "Groups" ni "Knockout" (las pestañas del partido son solo las tres indicadas arriba).
- Sin datos que la API no entrega (fundación, títulos mundiales).
- Sin nombres de bases de datos ni paneles técnicos.
