# Carga masiva integrada — modo secuencial

- Ejecutado: 2026-11-11T20:32:55+00:00 (UTC) · commit `67e7db3 + cambios sin commitear`
- Comando: `python fixture2030-carga-masiva/scripts/orquestador.py --modo secuencial --bases influxdb --sin-distribucion --conservar --etiqueta diag-influx`
- VM de Docker: 12 CPUs, 7.68 GiB · 18 contenedores ajenos a la prueba ocupaban hasta 4.326 MiB
- Parámetros de los cargadores: Cassandra concurrencia 128 · InfluxDB lote 50.000, hilos 8
- Memoria al empezar: VM 7.869 MiB, 17 contenedores ajenos con 4.182 MiB, RAM libre del host 1.055 MiB · presupuesto para la prueba: sin control (secuencial)
- Orden: influxdb
- Desde volúmenes vacíos: sí (limpieza al inicio de la corrida)
- Insumos de InfluxDB: reutilizados (deterministas)

## Tiempos por base

| Base | Arranque (s) | Preparación (s) | **Carga (s)** | Carga desde → hasta (s) | Volumen | Throughput de la carga | Verificación (s) | Apagado (s) | Estado |
|---|---:|---:|---:|---|---:|---:|---:|---:|---|
| influxdb | 14,3 | 31,7 | 63,4 | 46,0 → 109,4 | 10.094.400 puntos | 159.186,4 puntos/s | 2,0 | – | ok |

| Total | Valor |
|---|---|
| **Reloj: arranque de la primera → fin de la última carga** | **109,4 s** |
| Reloj total (incluye verificación, distribución y apagado) | 111,4 s |
| Suma de las fases de carga | 63,4 s |
| Suma de arranque + preparación + carga de todas las bases | 109,4 s |
| Registros cargados (de distinta naturaleza) | 10.094.400 |
| Registros por segundo de reloj | 92.270,6 |
| Última carga en terminar | influxdb |
| Carga más larga | influxdb (63,4 s) |

- **influxdb**: 10,094,400 puntos en fixture2030_vivo (scripts/carga_lotes.py --perfil completo, lote 50000, hilos 8) · 169,422.2 puntos/s (medida por carga_lotes.py)
  - error: `verificacion: ErrorPaso: InfluxDB HTTP 500 en «SELECT count(*) AS n FROM audiencia_partido»: External error: Query would scan 432 Parquet files, exceeding the file limit. InfluxDB 3 Core caps file access to prevent performance degradation and memory issues. Use a narrower time range, or increase the limit with --query-file-limit (this may cause slower queries or instability).

To remove this limitation, upgrade to InfluxDB 3 Enterprise, which automatically compacts files for efficient que`

### Admisión (cuándo arrancó cada base)

| Base | Admitida en (s) | Reservado al admitirla (MiB) | Bases en curso | RAM libre del host (MiB) |
|---|---:|---:|---:|---:|
| influxdb | 0,0 | 2.560 | 1 | 1.098 |

## Recursos (docker stats durante todas las fases)

36 muestras. Pico de RAM de los contenedores de la prueba: **1.960 MiB**; pico de RAM de toda la VM (prueba + ajenos): **5.996 MiB** de 7.864 MiB; pico de CPU de la prueba: **338,8 %** (100 % = 1 CPU, 12 CPUs = 1200 %). RAM libre mínima del host: **337 MiB**.

| Contenedor | Muestras | CPU prom. (%) | CPU máx. (%) | RAM máx. (MiB) |
|---|---:|---:|---:|---:|
| f30cm-influxdb | 35 | 94,2 | 327,9 | 1.960 |
| f30cm-influxdb-cargador | 18 | 29,1 | 55,1 | 115 |

## Validación de integridad

0 de 1 chequeos OK · fallidos: ['influxdb · verificación completa'] · informativos: ninguno

| Chequeo | Esperado | Obtenido | Resultado |
|---|---:|---:|---|
| influxdb · verificación completa | sin error | ErrorPaso: InfluxDB HTTP 500 en «SELECT count(*) AS n FROM audiencia_partido»: External error: Query would scan 432 Parquet files, exceeding the file limit. InfluxDB 3 Cor | FALLA |
