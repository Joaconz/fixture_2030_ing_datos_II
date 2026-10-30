# Auditoría del Hito 12 — Pruebas de carga y optimización

Rama `hito12-carga` (PR 15), estado `1381730`. Contra: PDF «Hito 12 — Requisitos Técnicos» y Clase 13. Hecha el 29–30/10/2026, en dos pasadas: la primera sobre el PR original (`25720a5`) y la segunda tras los commits de corrección del equipo.

**Qué se ejecutó y qué no:** se leyó todo el PR, se recalcularon con un script las cifras de las dos corridas oficiales desde `k6_resumen.json` y `recursos.csv` (coinciden con las tablas), y se corrió el test de la caché (3 pasan). **No se repitió la prueba de carga** (requiere macOS/Linux, `lsof` y el volumen de Cassandra): las cifras se auditaron como evidencia, no se reprodujeron.

## 1. Requisitos

| Req. | Estado | Evidencia |
|---|---|---|
| RF1 flujo | PASS | `docs/flujo_y_escenario_de_carga.md` responde los 8 puntos de §5.1 |
| RF2 escenario | PASS | Mismo doc: datos, VUs, rampa, sostenimiento, bajada, corte seguro, timeout, limpieza |
| RF3 datos | PASS | `datos-o-generadores/README.md` |
| RF4 línea base | PASS | Commit `ef271d9` en `ambiente.md` (corrida desde clon), versiones de Cassandra y k6, recursos de Docker |
| RF5 métricas | PASS | p50/p95/p99/máx, throughput, 201, errores, CPU y memoria. Recalculado: 58.281 req, 364,3 req/s; optimizada 62.557 req, 391,0 req/s |
| RF6 diferenciar capas | PASS parcial | CPU de API, Cassandra y generador k6 (18 %), y lecturas de Q0. Falta la latencia propia de Cassandra y red/disco/conexiones: declarado en limitaciones |
| RF7 hipótesis | PASS | H1/H2 con prueba asociada (`lecturas_q0.txt`: 186.989−128.708 = 58.281; 187.003−186.990 = 13) |
| RF8 optimización | PASS | Una sola (caché de Q0) con hipótesis, costo y decisión |
| RF9 repetición | PASS | Mismo escenario y mismo código; las dos corridas arrancan con las 64.640 filas del Hito 6 |
| RF10 comparación | PASS (tras ajuste) | `comparar.py` marcaba ✅ variaciones de −0,4 %; ahora ≈ si es menor al 15 % |
| RF11 trade-off | PASS | Frescura 60 s, memoria, sin invalidación entre procesos |
| RF12–RF13 Data Mart | PASS (tras ajuste) | Fuentes verificadas en los módulos. Faltaba la procedencia de la Clase 13 |
| RF14 relacional | PASS | `comparacion_relacional.md` cubre los 9 puntos de §5.6 y separa lo conceptual de lo medido |
| RF15 integridad | PASS | I1–I5 leyendo Cassandra directo: 11.732 y 12.402 filas = POST 201, 0 duplicados, 0 sin par, 0 alterados |
| RF16 evidencia | PASS con reserva | Corridas oficiales completas. Los 2 pares previos solo existen como tabla (§3) |
| RNF1 reproducibilidad | PASS (tras ajuste) | README no decía que los scripts exigen macOS/Linux + `lsof` |
| RNF2 trazabilidad | PASS | Commit, fecha, configuración, volumen y entorno por corrida |
| RNF3 comparabilidad | PASS | Limpieza entre corridas; diferencia de tombstones declarada |
| RNF4–RNF6 | PASS | Conteos, método/unidad/entorno por cifra, volumen probado vs. proyectado |
| RNF7 aislamiento | PASS | Usuarios `USR-LT<corrida><vu>`, limpieza por clave primaria |
| RNF8 seguridad | PASS | Sin credenciales ni URI con secretos en la carpeta |
| RNF9 recursos | PASS | 20 VUs, corte al 20 % de errores, timeout de 10 s |
| RNF10 legibilidad | PASS | Scripts comentados por etapa |
| RNF11 no destructivo | PASS | Las corridas anteriores se archivan en `anteriores/`, no se borran |
| RNF12 procedencia | PASS (tras ajuste) | Columnas `fuente_*`, `extraido_en`, `lote_carga`, `version_transformacion` |
| RNF13 GitHub | PASS | `config/.gitignore` y `evidencia/.gitignore` presentes |
| RNF14 honestidad | PASS (tras ajuste) | Tombstones rotulados como calculados; los pares previos, como no recalculables |

## 2. Hallazgos del PR original y estado

| Hallazgo | Estado |
|---|---|
| `settings.py` y el test subidos a la raíz del repo: la API real no tenía `comentarios_config_cache_s` y GET/POST de comentarios daban `AttributeError` (500) | **Corregido por el equipo** (`d33f515`) |
| Commit de las corridas sin registrar («copia sin git (ZIP)») | **Corregido**: corridas nuevas desde clon |
| Sin CPU del generador (RF6) | **Corregido** (`docker stats` de k6) |
| `rm -rf` de la evidencia anterior (RNF11) | **Corregido** |
| Partición +20 % más grande en la segunda corrida (RNF3) | **Corregido** con limpieza entre corridas |
| Falta `config/.gitignore` | **Corregido** |

## 3. Cambios de esta auditoría
1. `comparar.py`: variaciones menores al 15 % se marcan ≈ (antes cualquier baja era ✅). El umbral sale de los pares sin limpiar (±8 % en throughput, hasta ~20 % en latencias). Se regeneró `comparacion.md` y se recalcularon los símbolos de `pares_sin_limpieza.md`.
2. `hipotesis_y_optimizacion.md`: sección **Conclusiones** (§8) y tombstones rotulados como calculados.
3. `integridad_y_limitaciones.md`: fila de lo que no se midió (red, disco, conexiones, latencia de Cassandra).
4. `integracion_data_mart.md`: procedencia y punto de control (Clase 13).
5. `pares_sin_limpieza.md`: aviso de que sus cifras no se pueden recalcular desde el repo.
6. `README.md`: requisitos reales (macOS/Linux, `lsof`).

## 4. Pendientes y decisiones para el equipo
- **Evidencia cruda de los 2 pares sin limpiar:** está en `anteriores/` en la notebook con Mac y no pude versionarla. Hay que copiar `k6_resumen.json`, `recursos.csv` e `integridad.json` de cada corrida a `docs/evidencia/pares_sin_limpieza/`, o dejar el aviso del punto 5.
- **«Suite completa: 210 en verde»** no se verificó (el driver de Cassandra no carga en Windows con Python 3.13). Confirmar con `pytest`.
- **Test unitario de la caché:** el PDF no lo pide; el README lo cita. Decidir si queda.
- **Sin fase de recuperación ni prueba de humo:** la Clase 13 las muestra; el PDF no las exige.
- **Latencia propia de Cassandra** (`nodetool tablehistograms`): cerraría RF6 pero obliga a repetir las corridas; hoy está declarada como limitación.
- **Corridas únicas por configuración:** reconocido en los docs.
