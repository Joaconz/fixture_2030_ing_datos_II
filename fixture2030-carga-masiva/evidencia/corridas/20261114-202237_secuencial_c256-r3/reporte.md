# Carga masiva integrada — modo secuencial

- Ejecutado: 2026-11-14T20:22:39+00:00 (UTC) · commit `88bebf9`
- Comando: `python fixture2030-carga-masiva/scripts/orquestador.py --modo secuencial --bases cassandra --cassandra-concurrencia 256 --sin-distribucion --etiqueta c256-r3`
- VM de Docker: 10 CPUs, 7.75 GiB · 33 contenedores ajenos a la prueba ocupaban hasta 3.488 MiB
- Parámetros de los cargadores: Cassandra concurrencia 256 · InfluxDB lote 50.000, hilos 8
- Memoria al empezar: VM 7.934 MiB, 33 contenedores ajenos con 3.375 MiB, RAM libre del host None MiB · presupuesto para la prueba: sin control (secuencial)
- Orden: cassandra
- Desde volúmenes vacíos: sí (limpieza al inicio de la corrida)

## Tiempos por base

| Base | Arranque (s) | Preparación (s) | **Carga (s)** | Carga desde → hasta (s) | Volumen | Throughput de la carga | Verificación (s) | Apagado (s) | Estado |
|---|---:|---:|---:|---|---:|---:|---:|---:|---|
| cassandra | 58,2 | 3,2 | 153,1 | 61,4 → 214,5 | 1.050.000 comentarios | 6.859,4 comentarios/s | 10,4 | 6,5 | ok |

| Total | Valor |
|---|---|
| **Reloj: arranque de la primera → fin de la última carga** | **214,5 s** |
| Reloj total (incluye verificación, distribución y apagado) | 231,4 s |
| Suma de las fases de carga | 153,1 s |
| Suma de arranque + preparación + carga de todas las bases | 214,5 s |
| Registros cargados (de distinta naturaleza) | 1.050.000 |
| Registros por segundo de reloj | 4.895,1 |
| Última carga en terminar | cassandra |
| Carga más larga | cassandra (153,1 s) |

- **cassandra**: 1,050,000 comentarios = 2,100,000 filas en 2 tablas (scripts/carga_masiva.py, concurrencia 256) · 15,199 escrituras/s (medida por carga_masiva.py)

### Admisión (cuándo arrancó cada base)

| Base | Admitida en (s) | Reservado al admitirla (MiB) | Bases en curso | RAM libre del host (MiB) |
|---|---:|---:|---:|---:|
| cassandra | 0,0 | 2.816 | 1 | None |

## Recursos (docker stats durante todas las fases)

110 muestras. Pico de RAM de los contenedores de la prueba: **2.168 MiB**; pico de RAM de toda la VM (prueba + ajenos): **5.573 MiB** de 7.936 MiB; pico de CPU de la prueba: **620,3 %** (100 % = 1 CPU, 10 CPUs = 1000 %). RAM libre mínima del host: **None MiB**.

| Contenedor | Muestras | CPU prom. (%) | CPU máx. (%) | RAM máx. (MiB) |
|---|---:|---:|---:|---:|
| f30cm-cassandra | 109 | 144,4 | 526,5 | 1.820 |
| f30cm-cassandra-cargador | 80 | 99,8 | 117,4 | 355 |

## Validación de integridad

4 de 4 chequeos OK · fallidos: ninguno · informativos: ninguno

| Chequeo | Esperado | Obtenido | Resultado |
|---|---:|---:|---|
| Cassandra · comentarios (comentarios_por_partido) | 1.050.000 | 1.050.000 | OK |
| Cassandra · comentarios (comentarios_por_usuario) | 1.050.000 | 1.050.000 | OK |
| Cassandra · comentario_id duplicados | 0 | 0 | OK |
| Cassandra · comentarios en una sola de las dos vistas | 0 | 0 | OK |
