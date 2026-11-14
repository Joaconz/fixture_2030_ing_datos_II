# Carga masiva integrada — modo secuencial

- Ejecutado: 2026-11-14T20:11:24+00:00 (UTC) · commit `88bebf9`
- Comando: `python fixture2030-carga-masiva/scripts/orquestador.py --modo secuencial --bases cassandra --cassandra-concurrencia 256 --sin-distribucion --etiqueta c256-r2`
- VM de Docker: 10 CPUs, 7.75 GiB · 33 contenedores ajenos a la prueba ocupaban hasta 3.612 MiB
- Parámetros de los cargadores: Cassandra concurrencia 256 · InfluxDB lote 50.000, hilos 8
- Memoria al empezar: VM 7.934 MiB, 33 contenedores ajenos con 3.514 MiB, RAM libre del host None MiB · presupuesto para la prueba: sin control (secuencial)
- Orden: cassandra
- Desde volúmenes vacíos: sí (limpieza al inicio de la corrida)

## Tiempos por base

| Base | Arranque (s) | Preparación (s) | **Carga (s)** | Carga desde → hasta (s) | Volumen | Throughput de la carga | Verificación (s) | Apagado (s) | Estado |
|---|---:|---:|---:|---|---:|---:|---:|---:|---|
| cassandra | 58,2 | 3,4 | 117,6 | 61,6 → 179,3 | 1.050.000 comentarios | 8.926,4 comentarios/s | 7,6 | 6,6 | ok |

| Total | Valor |
|---|---|
| **Reloj: arranque de la primera → fin de la última carga** | **179,3 s** |
| Reloj total (incluye verificación, distribución y apagado) | 193,5 s |
| Suma de las fases de carga | 117,6 s |
| Suma de arranque + preparación + carga de todas las bases | 179,2 s |
| Registros cargados (de distinta naturaleza) | 1.050.000 |
| Registros por segundo de reloj | 5.856,1 |
| Última carga en terminar | cassandra |
| Carga más larga | cassandra (117,6 s) |

- **cassandra**: 1,050,000 comentarios = 2,100,000 filas en 2 tablas (scripts/carga_masiva.py, concurrencia 256) · 19,866 escrituras/s (medida por carga_masiva.py)

### Admisión (cuándo arrancó cada base)

| Base | Admitida en (s) | Reservado al admitirla (MiB) | Bases en curso | RAM libre del host (MiB) |
|---|---:|---:|---:|---:|
| cassandra | 0,0 | 2.816 | 1 | None |

## Recursos (docker stats durante todas las fases)

93 muestras. Pico de RAM de los contenedores de la prueba: **2.166 MiB**; pico de RAM de toda la VM (prueba + ajenos): **5.586 MiB** de 7.936 MiB; pico de CPU de la prueba: **569,3 %** (100 % = 1 CPU, 10 CPUs = 1000 %). RAM libre mínima del host: **None MiB**.

| Contenedor | Muestras | CPU prom. (%) | CPU máx. (%) | RAM máx. (MiB) |
|---|---:|---:|---:|---:|
| f30cm-cassandra | 92 | 133,1 | 484,1 | 1.822 |
| f30cm-cassandra-cargador | 62 | 97,9 | 115,0 | 368 |

## Validación de integridad

4 de 4 chequeos OK · fallidos: ninguno · informativos: ninguno

| Chequeo | Esperado | Obtenido | Resultado |
|---|---:|---:|---|
| Cassandra · comentarios (comentarios_por_partido) | 1.050.000 | 1.050.000 | OK |
| Cassandra · comentarios (comentarios_por_usuario) | 1.050.000 | 1.050.000 | OK |
| Cassandra · comentario_id duplicados | 0 | 0 | OK |
| Cassandra · comentarios en una sola de las dos vistas | 0 | 0 | OK |
