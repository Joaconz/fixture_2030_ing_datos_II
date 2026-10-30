# Datos de prueba (RF3)

| Dato | Origen | Volumen | Distribución |
|---|---|---|---|
| Comentarios base | Hito 6: `fixture2030-cassandra/scripts/carga_masiva.py` (generador determinista) | 1.050.000 comentarios en 112 partidos; `PAR-D16-01` = 300.000 (audiencia MÁXIMA) | Ventana pico 17:30 de `PAR-D16-01`: ≈ 64.640 filas en 4 buckets (16.161 / 16.160 / 16.160 / 16.159) |
| Comentarios de la prueba | Generados por k6 en cada corrida | ≈ 20 % de las requests | Usuarios `USR-LT<CORRIDA><VU>` (uno por usuario virtual), todos en `PAR-D16-01`, ventana pico 17:30; `Idempotency-Key` única por request |

- **Clave caliente a propósito:** todas las requests van al mismo partido, que es lo que pasa en un pico real después de un gol.
- **Reproducible:** la base viene de un generador determinista; las escrituras de la prueba se identifican por usuario y se borran con `limpiar_datos_de_prueba.sh` sin tocar el resto.
- **Volumen probado vs. proyectado (RNF6):** se prueba un partido y 20 usuarios virtuales concurrentes en una notebook. El escenario del TPO (2–3 M usuarios, 100.000+ req/s, Hito 1) no se ejecuta: ver `docs/integridad_y_limitaciones.md`.
- **Validación de la carga base:** `preparar_datos.sh` cuenta las filas de la ventana pico y, si faltan, corre la carga masiva del Hito 6.
