# Carga masiva integrada — modo secuencial

- Ejecutado: 2026-11-14T20:26:34+00:00 (UTC) · commit `88bebf9`
- Comando: `python fixture2030-carga-masiva/scripts/orquestador.py --modo secuencial --bases cassandra --cassandra-concurrencia 512 --sin-distribucion --etiqueta c512-r3`
- VM de Docker: 10 CPUs, 7.75 GiB · 33 contenedores ajenos a la prueba ocupaban hasta 3.518 MiB
- Parámetros de los cargadores: Cassandra concurrencia 512 · InfluxDB lote 50.000, hilos 8
- Memoria al empezar: VM 7.934 MiB, 33 contenedores ajenos con 3.423 MiB, RAM libre del host None MiB · presupuesto para la prueba: sin control (secuencial)
- Orden: cassandra
- Desde volúmenes vacíos: sí (limpieza al inicio de la corrida)

## Tiempos por base

| Base | Arranque (s) | Preparación (s) | **Carga (s)** | Carga desde → hasta (s) | Volumen | Throughput de la carga | Verificación (s) | Apagado (s) | Estado |
|---|---:|---:|---:|---|---:|---:|---:|---:|---|
| cassandra | 58,2 | 3,1 | 163,7 | 61,4 → 225,1 | 1.050.000 comentarios | 6.413,7 comentarios/s | 9,4 | 6,5 | ok |

| Total | Valor |
|---|---|
| **Reloj: arranque de la primera → fin de la última carga** | **225,1 s** |
| Reloj total (incluye verificación, distribución y apagado) | 241,0 s |
| Suma de las fases de carga | 163,7 s |
| Suma de arranque + preparación + carga de todas las bases | 225,0 s |
| Registros cargados (de distinta naturaleza) | 1.050.000 |
| Registros por segundo de reloj | 4.664,6 |
| Última carga en terminar | cassandra |
| Carga más larga | cassandra (163,7 s) |

- **cassandra**: 1,050,000 comentarios = 2,100,000 filas en 2 tablas (scripts/carga_masiva.py, concurrencia 512) · 14,069 escrituras/s (medida por carga_masiva.py)

### Admisión (cuándo arrancó cada base)

| Base | Admitida en (s) | Reservado al admitirla (MiB) | Bases en curso | RAM libre del host (MiB) |
|---|---:|---:|---:|---:|
| cassandra | 0,0 | 2.816 | 1 | None |

## Recursos (docker stats durante todas las fases)

114 muestras. Pico de RAM de los contenedores de la prueba: **2.167 MiB**; pico de RAM de toda la VM (prueba + ajenos): **5.574 MiB** de 7.936 MiB; pico de CPU de la prueba: **507,3 %** (100 % = 1 CPU, 10 CPUs = 1000 %). RAM libre mínima del host: **None MiB**.

| Contenedor | Muestras | CPU prom. (%) | CPU máx. (%) | RAM máx. (MiB) |
|---|---:|---:|---:|---:|
| f30cm-cassandra | 113 | 138,3 | 423,0 | 1.812 |
| f30cm-cassandra-cargador | 84 | 100,9 | 114,4 | 367 |

## Validación de integridad

4 de 4 chequeos OK · fallidos: ninguno · informativos: ninguno

| Chequeo | Esperado | Obtenido | Resultado |
|---|---:|---:|---|
| Cassandra · comentarios (comentarios_por_partido) | 1.050.000 | 1.050.000 | OK |
| Cassandra · comentarios (comentarios_por_usuario) | 1.050.000 | 1.050.000 | OK |
| Cassandra · comentario_id duplicados | 0 | 0 | OK |
| Cassandra · comentarios en una sola de las dos vistas | 0 | 0 | OK |
