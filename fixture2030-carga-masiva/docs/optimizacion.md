# Optimización de carga

## 1. Qué se eligió optimizar y por qué

**La concurrencia del cargador de Cassandra** (`carga_masiva.py --concurrencia`, escrituras en vuelo).

- Cassandra es la carga más larga de la arquitectura (1.050.000 comentarios = 2.100.000 filas) y, con la admisión por memoria, corre **sola**. Su tiempo de carga suma directo al reloj total, en paralelo y en secuencial.
- El módulo dejó esta mejora pendiente. `fixture2030-cassandra/docs/rendimiento.md` plantea como hipótesis 1 que *"la tasa sube con la concurrencia hasta un techo… que pone la CPU compartida"* y la marca **"No verificada: solo se midió con concurrencia 128"**.
- InfluxDB ya tiene su barrido de lote y de hilos (`fixture2030-influxdb/docs/pruebas_y_rendimiento.md` §4.1), así que repetirlo no aporta.
- Otra opción era el orden de arranque, pero no cambia nada: con ~1,9 GB de presupuesto solo MongoDB y Redis entran juntos, y las tres bases pesadas van de a una en cualquier orden.

## 2. Hipótesis

Escrita **antes** de medir (2026-11-14), tomada de `fixture2030-cassandra/docs/rendimiento.md` §3, hipótesis 1:

> La tasa de escritura sube con la concurrencia hasta un techo y después se estanca o baja. El techo lo pone la CPU compartida (cliente y servidor corren en la misma máquina), no el disco.

Aplicada a esta prueba: con la concurrencia por defecto (128) todavía no se llegó al techo, así que **subirla a 256 o 512 debería bajar el tiempo de carga de Cassandra**. Si la hipótesis es falsa, 128 ya está en el techo (o pasado) y subir la concurrencia no mejora, o empeora. Cualquiera de los dos resultados se informa tal cual.

## 3. Método

- **Antes**: concurrencia 128 (valor por defecto de `carga_masiva.py`, el de las corridas paralelo y secuencial del hito).
- **Después**: concurrencia 256 y 512. Es el único parámetro que cambia.
- **Comando** (una corrida por combinación, siempre desde volúmenes vacíos, solo Cassandra y en modo secuencial para que no compita con otra base):

  ```bash
  python fixture2030-carga-masiva/scripts/orquestador.py --modo secuencial --bases cassandra --cassandra-concurrencia <N> --sin-distribucion --etiqueta c<N>-r<repetición>
  ```

- **Repeticiones**: 3 por valor, intercaladas (128, 256, 512, 128, 256, 512, …) para que una deriva del entorno no favorezca a un valor. En las corridas completas del hito, la misma configuración midió tasas muy distintas entre una corrida y otra (ver la comparación paralelo vs. secuencial), así que **una sola corrida por valor no alcanza** para sacar conclusiones.
- **Qué se compara**: segundos de la fase de carga de Cassandra (`carga_masiva.py`, 1.050.000 comentarios = 2.100.000 filas) y escrituras/s que informa el propio cargador. Se informa mediana y rango de las 3 repeticiones.
- **Qué debe seguir cumpliéndose**: la validación de integridad de Cassandra (1.050.000 comentarios en cada vista, sin duplicados) en cada corrida. Una mejora de velocidad que rompa la integridad no cuenta.
- **Entorno**: el mismo de las corridas del hito (VM de Docker de 7,75 GiB y 10 CPUs, `f30cm-cassandra` con `mem_limit` 2g y heap de 1 G). Los contenedores ajenos siguen corriendo y compiten por CPU; es parte del ruido y se informa.

## 4. Resultado

Medido el 2026-11-14 (hora local 16:56 a 17:30), commit `88bebf9`, 9 corridas desde volúmenes vacíos. Cada corrida: `evidencia/corridas/20261114-*_secuencial_c<N>-r<k>/` (`reporte.json` con fecha, comando y commit). Comparación completa: [`evidencia/comparacion_optimizacion_cassandra_20261114.md`](../evidencia/comparacion_optimizacion_cassandra_20261114.md), generada con `scripts/comparar.py`.

**Carga de Cassandra** (1.050.000 comentarios = 2.100.000 filas), segundos de la fase de carga:

| Concurrencia | Rep. 1 | Rep. 2 | Rep. 3 | **Mediana** | Rango | Escrituras/s del cargador (mediana) | Cambio de la mediana vs. 128 |
|---:|---:|---:|---:|---:|---|---:|---:|
| 128 (antes) | 158,3 | 168,8 | 153,2 | **158,3** | 153,2 – 168,8 | 14.576 | – |
| 256 | 120,7 | 117,6 | 153,1 | **120,7** | 117,6 – 153,1 | 19.326 | −37,6 s (−23,8 %) |
| 512 | 142,0 | 157,9 | 163,7 | **157,9** | 142,0 – 163,7 | 14.635 | −0,4 s (−0,3 %) |

Reloj hasta el fin de la carga (arranque + preparación + carga, solo Cassandra): mediana 220,5 s con 128, 182,4 s con 256 y 219,6 s con 512.

**Integridad**: las 9 corridas pasaron los 4 chequeos de Cassandra (1.050.000 comentarios en cada una de las dos vistas, 0 `comentario_id` duplicados, 0 comentarios en una sola vista) y con 0 errores de escritura.

**Qué dicen los números**

- **256 mejora en la mediana (−23,8 %), pero no de forma estable.** Dos corridas bajaron a 117,6 y 120,7 s; la tercera (153,1 s) quedó igual que las de 128 (153,2 a 168,8 s). Con 3 repeticiones por valor no se puede descartar que parte de la diferencia sea ruido del entorno.
- **512 no mejora**: la mediana es igual a la de 128 (157,9 contra 158,3 s) y sus otras dos corridas (157,9 y 163,7 s) caen dentro del rango de 128. Su mejor corrida (142,0 s) es 11 s menor que la mejor de 128 en el barrido, pero 128 midió 133,7 s en la corrida completa del hito, así que está dentro del ruido. Más escrituras en vuelo no dan más velocidad más allá de cierto punto.
- **La hipótesis se confirma en parte.** Hay un techo, y 512 está pasado. Que 256 sea mejor que 128 queda como probable, no demostrado.
- **El ruido es del mismo tamaño que el efecto.** La misma configuración (128) midió 133,7 s en la corrida secuencial completa del hito, 188,1 s en la paralela, y 153,2 a 168,8 s en el barrido. Esa dispersión (133,7 a 188,1 s) es mayor que la diferencia entre las medianas de 128 y 256.
- **Qué parece poner el techo (inferido de `docker stats`, no probado con un perfil).** En las 9 corridas el contenedor del cargador de Cassandra usó en promedio 98 a 101 % de CPU, es decir, un núcleo entero, mientras el servidor de Cassandra promedió 133 a 158 %. Un cargador de Python de un solo hilo saturando su núcleo es una explicación coherente con que subir las escrituras en vuelo no ayude a partir de cierto valor. Cambiar eso (por ejemplo, varios procesos cargadores) sería otra optimización y no se probó.
- **Efecto en el total de la arquitectura.** Cassandra es la carga más larga. Si la mejora de 256 fuera real, bajaría el reloj hasta la última carga unos 38 s (de ~325 s en la corrida secuencial completa); con una sola medición de la corrida completa no se verificó.

**No se cambió el valor por defecto de `carga_masiva.py`** (sigue en 128): la evidencia no alcanza para afirmar que 256 es mejor de forma consistente. Para confirmarlo harían falta más repeticiones (por ejemplo, 10 por valor) y, de ser posible, con los contenedores ajenos apagados.
