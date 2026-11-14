# Carga masiva integrada — modo secuencial

- Ejecutado: 2026-11-14T20:03:30+00:00 (UTC) · commit `88bebf9`
- Comando: `python fixture2030-carga-masiva/scripts/orquestador.py --modo secuencial --bases cassandra --cassandra-concurrencia 512 --sin-distribucion --etiqueta c512-r1`
- VM de Docker: 10 CPUs, 7.75 GiB · 33 contenedores ajenos a la prueba ocupaban hasta 3.598 MiB
- Parámetros de los cargadores: Cassandra concurrencia 512 · InfluxDB lote 50.000, hilos 8
- Memoria al empezar: VM 7.934 MiB, 33 contenedores ajenos con 3.498 MiB, RAM libre del host None MiB · presupuesto para la prueba: sin control (secuencial)
- Orden: cassandra
- Desde volúmenes vacíos: sí (limpieza al inicio de la corrida)

## Tiempos por base

| Base | Arranque (s) | Preparación (s) | **Carga (s)** | Carga desde → hasta (s) | Volumen | Throughput de la carga | Verificación (s) | Apagado (s) | Estado |
|---|---:|---:|---:|---|---:|---:|---:|---:|---|
| cassandra | 58,2 | 3,4 | 142,0 | 61,6 → 203,5 | 1.050.000 comentarios | 7.396,9 comentarios/s | 10,1 | 6,6 | ok |

| Total | Valor |
|---|---|
| **Reloj: arranque de la primera → fin de la última carga** | **203,5 s** |
| Reloj total (incluye verificación, distribución y apagado) | 220,2 s |
| Suma de las fases de carga | 142,0 s |
| Suma de arranque + preparación + carga de todas las bases | 203,6 s |
| Registros cargados (de distinta naturaleza) | 1.050.000 |
| Registros por segundo de reloj | 5.159,7 |
| Última carga en terminar | cassandra |
| Carga más larga | cassandra (142,0 s) |

- **cassandra**: 1,050,000 comentarios = 2,100,000 filas en 2 tablas (scripts/carga_masiva.py, concurrencia 512) · 16,284 escrituras/s (medida por carga_masiva.py)

### Admisión (cuándo arrancó cada base)

| Base | Admitida en (s) | Reservado al admitirla (MiB) | Bases en curso | RAM libre del host (MiB) |
|---|---:|---:|---:|---:|
| cassandra | 0,0 | 2.816 | 1 | None |

## Recursos (docker stats durante todas las fases)

105 muestras. Pico de RAM de los contenedores de la prueba: **2.170 MiB**; pico de RAM de toda la VM (prueba + ajenos): **5.694 MiB** de 7.936 MiB; pico de CPU de la prueba: **650,3 %** (100 % = 1 CPU, 10 CPUs = 1000 %). RAM libre mínima del host: **None MiB**.

| Contenedor | Muestras | CPU prom. (%) | CPU máx. (%) | RAM máx. (MiB) |
|---|---:|---:|---:|---:|
| f30cm-cassandra | 104 | 143,1 | 550,2 | 1.832 |
| f30cm-cassandra-cargador | 75 | 101,0 | 114,5 | 338 |

## Validación de integridad

4 de 4 chequeos OK · fallidos: ninguno · informativos: ninguno

| Chequeo | Esperado | Obtenido | Resultado |
|---|---:|---:|---|
| Cassandra · comentarios (comentarios_por_partido) | 1.050.000 | 1.050.000 | OK |
| Cassandra · comentarios (comentarios_por_usuario) | 1.050.000 | 1.050.000 | OK |
| Cassandra · comentario_id duplicados | 0 | 0 | OK |
| Cassandra · comentarios en una sola de las dos vistas | 0 | 0 | OK |
