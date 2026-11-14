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

<!-- RESULTADO -->
