# Fixture 2030 — Hito 12 · Pruebas de carga y optimización

**Repositorio:** https://github.com/Joaconz/fixture_2030_ing_datos_II
**Ingeniería de Datos II · Grupo 2** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

**Flujo bajo carga:** pico de comentarios después de un gol en `PAR-D16-01` (ARG–BEL, el partido de audiencia MÁXIMA de los Hitos 6 y 8), **a través de la API del Hito 10** hacia **Cassandra** (Hito 6): 80 % lecturas de los últimos comentarios, 20 % publicaciones.
**Optimización medida:** reutilizar en memoria la configuración de partición del partido (Q0), que la API leía de Cassandra en **cada** request. Se activa con una variable (`COMENTARIOS_CONFIG_CACHE_S`), así la línea base y la prueba optimizada corren **el mismo código** cambiando solo eso.

**Resultado (30/10/2026, commit `ef271d9`):** línea base de **364,3 req/s**, GET p50 46,3 ms y POST p50 50,3 ms, con 0 % de errores. La caché elimina el **99,98 %** de las lecturas de Q0 (58.281 → 13) y baja la CPU de Cassandra un 7 %. La mejora de latencia del par (+7 % throughput, −10 % GET p50) está dentro de la variación entre corridas, así que no se da por demostrada: **el límite medido es la CPU del proceso de la API** (~95 %), con el generador k6 al 18 %. Integridad verificada en las dos corridas (11.732 y 12.402 filas, sin duplicados). Detalle en `docs/hipotesis_y_optimizacion.md`.

> Alcance deliberadamente acotado (corrección del Hito 10): un flujo, una optimización, sin funcionalidades nuevas. El Data Mart y la alternativa relacional son de **diseño**, como pide la consigna.

## 1. Estructura

```
fixture2030-hito12-carga/
├── README.md
├── compose-o-instrucciones-del-entorno.md   qué servicios corren dónde y por qué
├── config/configuracion-ejemplo.env         escenario (VUs, rampa, sostenimiento) — sin secretos
├── config/.gitignore                        excluye config/configuracion.env
├── scripts/
│   ├── preparar_datos.sh                    Cassandra + datos del Hito 6 + entorno de la API + k6
│   ├── ejecutar_linea_base.sh               corrida SIN optimizar (caché de Q0 = 0)
│   ├── ejecutar_carga.sh                    una corrida completa (la usan los dos de arriba y abajo)
│   ├── escenario_k6.js                      el escenario de carga (rampa, sostenimiento, corte seguro)
│   ├── validar_integridad.py                lee Cassandra directo: escritos = confirmados, sin duplicados
│   ├── ejecutar_prueba_optimizada.sh        mismo escenario CON la optimización + comparación
│   ├── comparar.py                          tabla antes/después generada solo desde los archivos
│   ├── limpiar_datos_de_prueba.sh/.py       borra SOLO lo escrito por las corridas
│   └── _comun.sh
├── datos-o-generadores/README.md
└── docs/
    ├── flujo_y_escenario_de_carga.md
    ├── linea_base.md
    ├── hipotesis_y_optimizacion.md
    ├── integracion_data_mart.md
    ├── comparacion_relacional.md
    ├── integridad_y_limitaciones.md
    └── evidencia/                            resultados_linea_base/, resultados_optimizada/, comparacion.md, pares_sin_limpieza.md
```

La optimización vive en la API: `fixture2030-hito10-api/app/services/comentarios.py` (caché de Q0), `app/config/settings.py` (`comentarios_config_cache_s`, por defecto 0 = comportamiento del Hito 10) y `tests/unit/test_cache_config_comentarios.py`.

## 2. Requisitos
- macOS o Linux con `bash`, `curl` y `lsof` (los scripts usan `.venv/bin/python` y `lsof`; en Windows, desde WSL).
- Docker Desktop (k6 y Cassandra corren en contenedores). Recomendado: ≥ 4 GB para Docker.
- `uv` para el entorno de la API (`curl -LsSf https://astral.sh/uv/install.sh | sh`).
- Puerto 8000 libre: **la prueba levanta y apaga la API sola**, con la configuración de cada corrida. No tiene que haber otra API corriendo.

## 3. Orden de ejecución (desde esta carpeta)

```bash
bash scripts/preparar_datos.sh            # 1. ambiente y datos (repetible, no borra nada)
bash scripts/limpiar_datos_de_prueba.sh   # 2. borra solo los comentarios de corridas anteriores
bash scripts/ejecutar_linea_base.sh       # 3. línea base (~3 min)
bash scripts/limpiar_datos_de_prueba.sh   # 4. borra lo que escribió la línea base
bash scripts/ejecutar_prueba_optimizada.sh  # 5. misma prueba optimizada (~3 min) + docs/evidencia/comparacion.md
```

**Por qué limpiar antes de cada corrida (RNF3):** cada corrida escribe ~12.000 comentarios en la ventana pico. Sin limpiar, la segunda corrida trabaja sobre una partición un 20 % más grande que la primera, y la comparación deja de ser justa. Lo comprobamos: en dos pares de corridas sin limpieza, la diferencia de latencia entre línea base y optimizada cambió de signo de un par a otro.

Cada corrida deja en `docs/evidencia/resultados_<etiqueta>/`: `ambiente.md` (fecha, commit, versiones, recursos), `k6_resumen.json` y `k6_salida.txt` (latencias, percentiles, throughput, errores), `recursos.csv` (CPU y memoria de Cassandra, de la API y del generador k6 cada 2 s), `lecturas_q0.txt` (lecturas de la tabla de configuración: la prueba de la hipótesis) e `integridad.md/.json`. Si ya había una corrida con la misma etiqueta, no se borra: se archiva en `docs/evidencia/anteriores/` (ignorado por git), y la limpieza también borra sus comentarios de prueba.

**Las corridas tienen que hacerse desde un clon de git** (no desde un ZIP): `ambiente.md` registra el commit con el que se midió.

Para cambiar el escenario (por ejemplo, más usuarios virtuales): copiar `config/configuracion-ejemplo.env` como `config/configuracion.env` y editarlo. Las dos corridas tienen que usar los mismos valores.

## 4. Seguridad
No hay credenciales en esta carpeta: la API usa su propio `fixture2030-hito10-api/.env` (ignorado por git) y Cassandra no tiene autenticación en el laboratorio. Los logs de la API quedan en `docs/evidencia/resultados_*/api.log` con nivel WARNING (sin datos sensibles); revisarlos antes de subir.
