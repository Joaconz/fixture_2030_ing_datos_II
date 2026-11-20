# Repaso express — lo mínimo para defender

Para leer en 30 minutos. Si sobra tiempo, el detalle está en [`estudio_de_la_aplicacion.md`](estudio_de_la_aplicacion.md).

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

## 5. Lo que NO hay que decir

- Que soporta 100.000 req/s: medimos **~400 req/s** en una notebook.
- Que la app corre con réplicas: corre con un nodo por base.
- Que la caché del Hito 12 mejoró la latencia: bajó lecturas (−99,98 %), no latencia.

## 6. La demo en una línea por paso

1. **D1** Buscar `a1` (error) y `ARG` → validación en el front.
2. **D2** Ficha de ARG, chip Delanteros (26 → 9) → MongoDB, un documento.
3. **D3** ARG–BEL, Eventos, chip Goles → Neo4j, el 1–0 se calcula.
4. **D4** Publicar comentario minuto 90, no aparece arriba → Cassandra, va a su ventana.
5. **D5** Estadísticas, 2T y 5 min (190 → 20 filas) → InfluxDB agrega.
6. **D6** Mesa ARG–BRA: cerrar (409) → fin *Sin equipo*, dorsal vacío (201) → cerrar (200, 1–0) → otra vez (409) → cierre CP.
7. **D7** Salud: las cinco en UP → cada base con su timeout.

Después pasás a Santiago con Grafana. Entre ensayos, reiniciá D6 con el comando de [`como_correr_la_app.md`](como_correr_la_app.md) §3.
