# Datos — Hito 8 · Series temporales

Los puntos son **sintéticos** y **deterministas**: los produce `scripts/generacion_puntos.py` a partir del calendario canónico del Hito 5 (`scripts/comun.py`). No se versionan (`data/lp/` está en `.gitignore`): generar dos veces produce archivos idénticos byte a byte.

## Qué se genera

```
data/lp/<perfil>/
├── manifiesto.json                    puntos esperados por tabla, partido y archivo; series esperadas
├── estadisticas_equipo/<partido>.lp.gz
├── audiencia_partido/<partido>.lp.gz
└── operacion_plataforma/<día>.lp.gz
```

| Perfil | Partidos | Puntos | Uso |
|---|---:|---:|---|
| `muestra` | 2 (`PAR-A-1`, `PAR-D16-01`) | 176.400 | Desarrollo y demostración rápida |
| `completo` | 112 | **10.094.400** | Objetivo de volumen (RF12) |
| `completo_N` | los primeros N por fecha | proporcional | Medición intermedia si la notebook no alcanza |

## Distribución

| Dimensión | Cómo se genera |
|---|---|
| Partidos y fechas | Los 112 del Hito 5 (96 de grupos entre el 9 y el 22 de junio de 2030, 16 de dieciseisavos del 29 de junio al 3 de julio). Máximo 8 partidos por día |
| Equipos por partido | Cruces del Hito 5 (paso 6); dieciseisavos: 1° del grupo N contra 2° del grupo N+1, con los resultados de la plantilla de eventos del Hito 5 |
| Goles | Grupos: plantilla del Hito 5 (gol local al 13'; al 75' visitante u 82' local según el partido). Dieciseisavos: 1 a 4 goles con semilla por partido |
| Feed del juego | 1 punto por equipo por segundo de juego (47' + 48'); nada en el entretiempo. Posesión como paseo aleatorio, pases y tiros con probabilidad por segundo de posesión, recuperación en cada cambio de posesión |
| Audiencia | Pico por partido según el ranking de los equipos (normal ≈ 0,5–1,5 M; dieciseisavos ≈ 1,4–1,8 M; `PAR-D16-01` 2,5 M). Curva continua: previa, primer tiempo, baja en el entretiempo, segundo tiempo, salida. Reacción a goles distinta por región (+40 % si hizo el gol la selección del país anfitrión, −10 % si lo recibió, +10 % neutral) |
| Regiones | 8: los 6 países anfitriones + resto de América + resto del mundo, con cuota ×3 cuando juega la selección local |
| Operación | 5 servicios cada 10 s durante todo el torneo; solicitudes proporcionales a los usuarios en línea (0,04 req/s por usuario); latencia y errores crecen con la carga |
| Timestamps | Segundos UTC (`precision=second`), calculados desde la fecha del partido |
