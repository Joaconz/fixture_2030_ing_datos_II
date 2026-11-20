# Guion hablado — qué dice cada uno (18 min)

El texto para decir, diapositiva por diapositiva, de A, B y C. Sigue el mismo orden, los mismos tiempos y el mismo reparto que [`guion_presentacion_final.md`](guion_presentacion_final.md), que sigue siendo el oficial para la demo (acciones exactas, preparación y plan B). Las cifras son las del deck *"Fixture 2030 — Defensa final"*.

| Letra | Quién | Bloques | Tiempo |
|---|---|---|---|
| **A** | Valentina | Inicio, Arquitectura y narración de la demo | 0:00–4:00 y 7:00–13:00 |
| **B** | Joaquín | Decisiones y maneja la demo | 4:00–13:00 |
| **C** | Santiago | Evidencia y Cierre | 13:00–18:00 |

**Cómo usarlo.** No hace falta decirlo de memoria palabra por palabra: es para que cada uno sepa qué idea va en cada diapositiva y con qué frase entra y sale. Leído en voz alta a ritmo normal, cada bloque entra en su tiempo. Lo que está entre corchetes es una acción, no se dice.

---

## Inicio · A · 0:00–1:30

### Diapositiva 1 — Portada (0:20)

> Buenas. Somos el grupo 2: Santiago Pazos, Valentina Frisoli y Joaquín Núñez. Les vamos a presentar el Fixture del Mundial 2030: una plataforma que usa cinco modelos NoSQL distintos. La idea que atraviesa todo el trabajo es simple: cada dato vive en la base que mejor resuelve la forma en que se lo usa, y una API los integra.

### Diapositiva 2 — El problema (0:40)

> El 2030 es el primer Mundial con seis países sede, en tres continentes: Argentina, Paraguay, Uruguay, España, Portugal y Marruecos. Son 64 selecciones y 127 partidos. El enunciado pide soportar entre 2 y 3 millones de usuarios simultáneos, picos de más de 100.000 requests por segundo cuando hay un gol, y menos de 100 milisegundos de latencia.
>
> Pero lo difícil no es el tamaño: es que los accesos son opuestos. Cerrar un partido necesita consistencia fuerte. Los comentarios del minuto 90 necesitan escribir sin esperar a nadie. Las sesiones tienen que vencerse solas. Y las estadísticas se consultan por tiempo. En el Hito 1 identificamos nueve necesidades de datos con estas diferencias.

### Diapositiva 3 — El principio de diseño (0:30)

> Por eso nuestro principio es: un modelo por acceso dominante. Ninguna base resuelve todo. Si usáramos una sola, algún módulo tendría que resignar justo lo que más necesita. El costo lo asumimos y lo vamos a mostrar al final: operar cinco productos distintos.

## Arquitectura · A · 1:30–4:00

### Diapositiva 4 — Cinco bases detrás de una API (0:50)

> Así queda la arquitectura. Arriba, una API REST en FastAPI, que es el único camino para leer y escribir. Abajo, las cinco bases: MongoDB, documental, para equipos y jugadores. Neo4j, grafo, para partidos, eventos y tipos de evento. Cassandra, columnar, para los comentarios de los hinchas. Redis, clave-valor, para sesiones y caché. E InfluxDB, series de tiempo, para las estadísticas en vivo.
>
> Cada ruta de la API consulta una sola base, y las bases comparten identificadores, como el id del partido o del usuario. No hay transacciones entre bases. Eso tiene una consecuencia que vamos a demostrar: si una base se cae, solo fallan sus rutas y el resto sigue funcionando.

### Diapositiva 5 — Qué acceso justifica cada base (0:50)

> Esta tabla resume por qué cada dato está donde está. Les cuento una idea por base.
> A un equipo se lo lee completo, por su código FIFA, desde seis países: eso es un documento.
> Los eventos de un partido se recorren en orden y se relacionan entre sí: eso es un grafo.
> Los comentarios se escriben en masa en el minuto de un gol: eso pide Cassandra.
> La sesión se lee en cada request y tiene que vencerse sola: Redis con TTL.
> Y las estadísticas se agregan por minuto: series de tiempo.
>
> La última columna es el CAP de diseño. El N, R, W explícito está solo en Cassandra, como nos corrigieron en el Hito 3.

### Diapositiva 6 — IRIS salió (0:50)

> Una aclaración que la consigna nos va a pedir: IRIS, el modelo de objetos, no está. Lo implementamos en el Hito 9, pero lo sacamos en la reentrega del Hito 3.
> El problema fue que partidos y tipos de evento vivían a la vez en IRIS y en el grafo, y esa copia ya había dado un calendario distinto: el mismo partido, PAR-A-1, era Argentina–Brasil en una base y Argentina–Países Bajos en la otra. Decidimos dejar todo en Neo4j, una sola fuente, y el profesor lo aprobó el 13 de octubre.
> Lo que resignamos: las reglas por tipo de evento ahora las valida la API, que es el único camino de escritura.
>
> [A, al terminar:] Ahora Joaquín les cuenta las tres decisiones de modelado más importantes.

## Decisiones · B · 4:00–7:00

### Diapositiva 7 — Decisión 1: Cassandra (1:00)

> La primera decisión es cómo guardar los comentarios. El problema es el minuto 90: miles de hinchas escribiendo sobre el mismo partido al mismo tiempo. Si la clave de partición fuera solo el id del partido, todo iría a una partición, en un solo nodo: un punto caliente.
> Por eso la clave es partido, ventana y bucket. La ventana agrupa los comentarios cada 10 minutos, y el bucket los reparte con un hash del id del comentario. El partido más comentado, Argentina–Bélgica, tiene 300.000 comentarios, y su partición más grande quedó en unas 16.000 filas, 2,3 megas. Sin ventanas ni buckets sería una sola partición de 300.000.
> Cargamos 1.050.000 comentarios y sostuvimos 17.774 escrituras por segundo en un nodo; el pedido era 10.000.
> Lo que resignamos: no hay búsquedas arbitrarias, guardamos el mismo comentario en una segunda tabla por usuario, y los buckets solo pueden crecer. Y la consistencia es eventual: N=3, R=1, W=1. Un comentario que tarda un segundo en aparecer no es un comentario incorrecto.

### Diapositiva 8 — Decisión 2: Neo4j (1:00)

> La segunda decisión es la más interesante: un partido tiene dos consistencias distintas en el mismo motor.
> Los eventos, goles, tarjetas y cambios, se cargan sin esperar: es AP. Cada evento se encadena al anterior, así se conserva el orden.
> El cierre del partido, en cambio, es CP: no puede haber dos resultados oficiales. El cierre corre en una transacción que exige que exista el evento de fin de partido. Y el marcador no se guarda: se calcula contando los goles. Así nunca puede contradecir a los eventos.
> Son 127 partidos, de grupos a la final, con 1.572 eventos encadenados y 19 consultas en Cypher. Lo van a ver funcionando en la demo.

### Diapositiva 9 — Decisión 3: Redis (1:00)

> La tercera decisión es una que parece un error y es a propósito: las sesiones no se replican entre regiones.
> Cada sesión es un hash en Redis con 30 minutos de vida; cada request la renueva, con un tope de 12 horas. Si se cae una región, el usuario vuelve a iniciar sesión. Perder una sesión es tolerable. Replicarla entre continentes agregaría latencia a todas las requests para proteger un dato descartable.
> Cargamos 100.000 usuarios con sesión en menos de 3 segundos, medimos 136.799 renovaciones por segundo sin errores, y Redis borra solo 100.000 sesiones vencidas en unos 15 segundos.
> Ahora lo vemos andando.

## Demo en vivo · B maneja, A narra · 7:00–13:00

### Diapositiva 10 — Demo (0:10)

> [B:] Vamos a hacer el recorrido de un hincha, y en cada pantalla les decimos qué base la responde. Yo manejo y Valentina les va contando.
>
> [B pasa al navegador. Las acciones exactas de cada paso, clic por clic, están en `guion_presentacion_final.md`.]

### D1 — Inicio y búsqueda (0:30)

> [B:] Primero busco a Argentina por código FIFA. Si escribo algo inválido, como "a1"…
>
> [A:] …el front lo rechaza antes de llamar a la API, con el mismo patrón que valida la API. Ningún dato inválido llega a una base.

### D2 — Ficha del equipo (1:00)

> [B:] Escribo ARG y entramos a la ficha. Filtro el plantel por delanteros.
>
> [A:] Todo lo que ven acá es un documento de MongoDB, leído por su id, que es el código FIFA: ranking, grupo, y los 26 jugadores. Es lectura intensiva y escritura rara, que es justo lo que resuelve un modelo documental.

### D3 — Partido y eventos (1:00)

> [B:] Entro al partido Argentina–Bélgica, de dieciseisavos, y filtro los goles.
>
> [A:] El partido y sus eventos vienen del grafo. El 1 a 0 de arriba no está guardado en ningún lado: se calcula contando los eventos de gol, y acá ven el único gol, de Fernández al minuto 13. Cada evento está encadenado al anterior.

### D4 — Comentarios (1:00)

> [B:] Ahora los comentarios. Publico uno: "Golazo en vivo desde la defensa", al minuto 90.
>
> [A:] Este es el partido de audiencia máxima, así que su ventana de 10 minutos está repartida en 4 buckets. La lista muestra primero la ventana más reciente, la del final del partido. Por eso el comentario que acabamos de publicar, del minuto 90, no aparece arriba: se guardó en la partición de su propia ventana. Esa es la clave de partición que explicó Joaquín: nunca se escanea el partido entero. Y la escritura lleva una clave de idempotencia: si se reintenta, no se duplica.

### D5 — Estadísticas (0:45)

> [B:] Pestaña de estadísticas. Son 190 filas. Cambio a segundo tiempo, de a 5 minutos…
>
> [A:] …y quedan 20. Esa agregación por tiempo la hace InfluxDB, no la pantalla: es para lo que sirve una base de series de tiempo. Y fíjense que los goles de la serie dan 1 a 0, igual que el marcador que sale del grafo.

### D6 — Mesa de control: cierre del partido (1:15)

> [B:] Vamos a la mesa de control de otro partido, Argentina–Brasil. Intento cerrarlo…
>
> [A:] …y la API lo rechaza: falta el evento de fin de partido. Esta es la operación que no admite dos verdades.
>
> [B:] Registro el fin del partido, al minuto 90, y ahora sí cierro.
>
> [A:] La transacción calcula el marcador desde los goles: 1 a 0, del gol que ya estaba cargado. Si intentamos cerrarlo otra vez…
>
> [B:] [Intenta cerrar de nuevo.]
>
> [A:] …se rechaza. No puede haber dos resultados oficiales: eso es el cierre CP del que hablamos.

### D7 — Salud de las fuentes (0:30)

> [B:] Por último, la salud de las fuentes.
>
> [A:] La API ve cada base por separado, cada una con su propio timeout. Las cinco están arriba. Si una se cae, solo esa queda en rojo y sus pantallas muestran que no pudieron cargar; el resto sigue funcionando. Santiago les va a mostrar justamente eso, con datos.

## Evidencia · C · 13:00–15:30

### Grafana en vivo (en lugar de la diapositiva 13) (0:40)

> [C pasa a la pestaña de Grafana, dashboard "2. API integrada".]
>
> Todo lo que acaban de ver ya quedó medido. Acá están las requests de la demo: las respuestas 200, el 201 del evento que registramos y los 409 de los cierres rechazados. Acá, la latencia de cada pantalla. Y el porcentaje de errores del servidor dice "No data": no hubo ninguno.
> [Pasa al dashboard "3. Comparación entre bases".] Y acá, la latencia de cada base vista desde la API. En total son cinco dashboards y ocho alertas, cada una con su riesgo y su responsable.

### Diapositiva 11 — Volúmenes (0:25)

> [Vuelve a las diapositivas.] Esto es lo que pedía la guía y lo que cargamos. En todos los casos llegamos o pasamos el pedido: 1.664 jugadores, 1.572 eventos, 100.000 usuarios, más de un millón de comentarios y más de 10 millones de puntos. Y todas las cargas son deterministas: correrlas dos veces deja exactamente los mismos datos, como nos corrigieron en el Hito 4.

### Diapositiva 12 — Replicación (0:30)

> También probamos réplicas, en un laboratorio aparte. En MongoDB armamos un replica set de 3 nodos y matamos el primario: a los 10 segundos se eligió uno nuevo, y de 226 escrituras no se perdió ninguna. En Cassandra armamos un anillo de 3 nodos, con los datos en los tres.
> Y medimos el costo de leer cerca del usuario: con la replicación frenada, un secundario devuelve el valor viejo. Es la consistencia eventual, vista en vivo.

### Diapositiva 14 — El cuello de botella (0:30)

> Este es el hallazgo más importante de las mediciones. Con unas 400 requests por segundo, Cassandra responde por dentro en 1,1 milisegundos. Pero la request completa en la API tarda entre 42 y 91. ¿Dónde está la diferencia? En la API: un solo proceso de Python, al 97 % de CPU. El cuello de botella es la API, no la base. Eso confirmó una hipótesis que habíamos dejado planteada en el Hito 12.

### Diapositiva 15 — Prueba de falla (0:25)

> Y la prueba de falla. Apagamos Redis con tráfico. A los 10 segundos Prometheus lo detectó, y al minuto saltó la alerta. Durante la caída, las sesiones respondían 503, con un código de error explícito, mientras que la ficha de equipos seguía respondiendo 200: MongoDB nunca se enteró. Al prenderlo de nuevo se recuperó solo, sin reiniciar la API. La falla quedó en su módulo.

## Cierre · C (y los tres en Lecciones) · 15:30–18:00

### Diapositiva 16 — Medido vs. proyección (0:50)

> Queremos ser claros con qué medimos y qué no. Medido, en una notebook y con un nodo por base: los volúmenes, las escrituras por segundo, las latencias, el failover y la caída de Redis. La API atendió entre 364 y 399 requests por segundo sin errores.
> Lo que es diseño y no medimos: los 2 a 3 millones de usuarios, las 100.000 requests por segundo, las réplicas por región. Una sola API saturada no llega a 100.000. Lo que sí demuestran las mediciones es dónde está el límite y qué hay que escalar primero.

### Diapositiva 17 — Lecciones aprendidas (0:50)

> [C:] Cada uno les cuenta lo que se lleva.
>
> [A:] Primero, una sola fuente por dato: duplicar partidos en dos bases nos dio dos calendarios distintos. Y segundo, cargas deterministas desde el inicio, para poder comparar entre hitos.
>
> [B:] Para mí, medir antes de optimizar: creíamos que el límite era Cassandra y era la API. Y cumplir los requisitos al pie de la letra: un detalle de infraestructura, como un volumen nombrado, también se evalúa.
>
> [C:] Y separar lo medido de lo diseñado, que hace creíble la evidencia. Por último, cada base cuesta operarla: Cassandra pidió un agente aparte, Neo4j un exporter propio e InfluxDB un token.

### Diapositiva 18 — Cierre y preguntas (0:50)

> En resumen: cinco bases, cada una elegida por su acceso dominante. Cuando una falla, la falla queda en su módulo. Y el límite medido está en la API, no en las bases.
> Aceptamos consistencia eventual en comentarios, sesiones y estadísticas, desnormalizar, y el costo de operar cinco productos. Lo próximo que haríamos es correr varios procesos de la API con la caché de partición activa, y después sumar nodos de Cassandra.
> Eso es todo. Gracias, y quedamos para las preguntas.

---

## Antes del ensayo

- **Validar las lecciones de la diapositiva 17.** En el deck figuran como borrador; si algún integrante prefiere contar otra, reemplazarla acá y en la diapositiva.
- **Ensayar con cronómetro.** El texto está pensado para entrar en 18 minutos leído en voz alta. Si un bloque se pasa, recortar los ejemplos, no las frases de entrada y salida.
- **Preguntas.** Las respuestas preparadas están en [`../docs/defensa_final.md`](../docs/defensa_final.md) y en [`estudio_de_la_aplicacion.md`](estudio_de_la_aplicacion.md) §12 y §14.
