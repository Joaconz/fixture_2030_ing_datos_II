# Flujo y escenario de carga (RF1, RF2)

## Flujo seleccionado

| Pregunta de la consigna (§5.1) | Respuesta |
|---|---|
| Quién genera la operación | Hinchas en la app durante el pico posterior a un gol |
| Qué datos recibe | Lectura: `partido_id` y `limit=50`. Escritura: usuario, alias, texto, `creadoEn` del reloj del torneo e `Idempotency-Key` |
| Qué fuente consulta o actualiza | **Cassandra** (Hito 6) a través de la **API** (Hito 10). Lectura: Q0 (`config_particion_partido`) + las 4 particiones `(partido, ventana, bucket)` más recientes en paralelo. Escritura: Q0 + lectura por clave primaria (idempotencia) + LOGGED BATCH en `comentarios_por_partido` y `comentarios_por_usuario` |
| Tipo | Combinación: 80 % lectura, 20 % escritura |
| Respuesta esperada | GET 200 con 50 comentarios; POST 201 con el comentario guardado |
| Volumen y frecuencia proyectados | `PAR-D16-01`: 300.000 comentarios en el partido; en el TPO, 2–3 M usuarios simultáneos (Hito 1) |
| Criterio de éxito | GET 200 con comentarios; POST 201 **y** la fila existe en las dos tablas (verificado leyendo Cassandra) |
| Errores o respuestas degradadas que se registran | Cualquier status distinto de 200/201, timeouts (10 s del cliente), 503/504 de la API y POST con error que igual se hayan guardado |

**Por qué este flujo:** es la clave caliente real del sistema (el partido de mayor audiencia), combina lectura y escritura y **nunca se había medido a través de la API**: el Hito 6 midió Cassandra directo (17.774 escrituras/s con el driver).

## Escenario (situación del Fixture: "pico posterior a un evento")

| Parámetro (§5.2) | Valor |
|---|---|
| Datos iniciales | 1.050.000 comentarios del Hito 6; ≈ 64.640 en la ventana pico de `PAR-D16-01` |
| Concurrencia | 20 usuarios virtuales (k6, `ramping-vus`), configurable |
| Tasa objetivo | Sin pausa entre requests (lazo cerrado): cada usuario manda la siguiente al recibir la anterior. Mide la capacidad máxima de este ambiente, no una tasa fija |
| Proporción | 80 % GET / 20 % POST (sorteo por request) |
| Distribución de claves | Un solo partido (clave caliente); escrituras en la ventana pico 17:30, un usuario por VU |
| Calentamiento | 20 GET sin medir antes de cada corrida |
| Rampa | 0 → 20 VUs en 30 s |
| Sostenimiento | 120 s con 20 VUs |
| Bajada | 10 s |
| Duración total | ≈ 160 s por corrida |
| Interrupción segura | k6 aborta si las requests fallidas superan el 20 % durante 20 s; timeout de 10 s por request |
| Ante timeout o error | Se cuenta como fallida y se sigue; la validación detecta si un POST con error igual se guardó |
| Limpieza / reutilización | `limpiar_datos_de_prueba.sh` borra solo los usuarios `USR-LT…` de las corridas registradas |
