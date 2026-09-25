# Spec de Auditoría — Hito 4: Módulo Documental de Equipos y Jugadores (Fixture 2030)

Este documento es la referencia para auditar un repositorio ya implementado contra los
requisitos oficiales del Hito 4. No es una guía de diseño desde cero: el módulo ya existe,
la tarea es **verificar, señalar problemas y corregir lo que sea objetivamente incorrecto**.

## Reglas de la auditoría (leer antes de tocar nada)

- **Podés corregir directamente:** errores de sintaxis, scripts que no ejecutan, el
  `docker-compose.yml` no levanta, la carga de datos genera duplicados al re-ejecutarse,
  una consulta pedida en los requisitos no existe o tira error, un índice que la propia
  documentación del repo dice que existe pero no está creado, rutas hardcodeadas que
  rompen portabilidad (RNF7), inconsistencias entre lo documentado y lo implementado.
- **NO podés cambiar sin señalarlo explícitamente en el informe final:** la decisión de
  embedding vs. referencias entre equipos y jugadores, la elección de qué índices crear,
  las reglas de validación de negocio, la estructura de colecciones. Si te parecen
  mejorables, anotalo como recomendación en el informe — no lo reescribas silenciosamente.
  Estas decisiones las tiene que poder defender el grupo en una evaluación oral.
- Si algo no se puede verificar porque falta información (por ejemplo, no hay evidencia de
  la matriz del Hito 2 o de las decisiones del Hito 3 en el repo), marcalo como
  **"No verificable — falta insumo"**, no lo asumas ni lo inventes.

## Cómo verificar el ambiente

```bash
docker compose config          # valida sintaxis del compose sin levantar nada
docker compose up -d           # debe levantar sin errores desde cero
docker compose ps              # todos los servicios en estado running/healthy
docker compose down            # bajar sin borrar volumen
docker compose up -d           # volver a levantar → los datos deben seguir estando
```

Correr `db.equipos.countDocuments()` y `db.jugadores.countDocuments()` antes y después del
`down`/`up` para confirmar persistencia real, no solo que el volumen esté declarado.

## Checklist — Requisitos Funcionales

| ID | Requisito | Cómo verificar | Criterio de PASS |
|---|---|---|---|
| RF1 | Entorno local reproducible con Docker Compose | `docker compose config` + `docker compose up -d` desde estado limpio | Levanta sin errores, sin pasos manuales no documentados |
| RF2 | Persistencia entre reinicios | Insertar doc, `docker compose down` (sin `-v`), `up -d`, releer | El documento sigue existiendo |
| RF3 | Colecciones documentales para equipos y jugadores | `show collections` en mongosh | Existen colecciones claramente identificables para cada entidad |
| RF4 | 64 equipos persistidos | `db.equipos.countDocuments()` | Resultado == 64, no aproximado |
| RF5 | ≥1000 jugadores vinculados coherentemente | `db.jugadores.countDocuments()` + verificación de integridad (ver RNF3) | ≥1000 Y cada jugador referencia un equipo que existe |
| RF6 | Estrategia de relación equipo-jugador documentada | Buscar archivo de decisiones en el repo | Explica embedding o referencia, con justificación, no solo la afirma |
| RF7 | Validaciones para atributos críticos | Revisar `$jsonSchema` o validación a nivel de carga; intentar insertar un documento inválido | El sistema rechaza o marca el documento inválido, no lo acepta silenciosamente |
| RF8 | Carga reproducible sin duplicados | Ejecutar el script de carga dos veces seguidas | El conteo de documentos es igual después de la segunda ejecución |
| RF9 | Insert y update para equipos y jugadores | Ejecutar cada operación provista | Cada una corre sin error y el cambio se refleja en una lectura posterior |
| RF10 | Consultas: id directo, filtrado, proyección, ordenamiento, paginación | Ejecutar cada tipo por separado | Las 5 variantes existen como consultas distintas y devuelven resultados correctos |
| RF11 | Al menos una agregación pertinente | Ejecutar el pipeline | Corre sin error y el resultado tiene sentido funcional (no un `$match` disfrazado de agregación) |
| RF12 | Índices creados y justificados | `db.coleccion.getIndexes()` + comparar contra qué consultas dice el repo que optimizan | Cada índice tiene una consulta real asociada y documentada, no índices "por las dudas" |
| RF13 | Evidencia de carga, consultas y rendimiento | Revisar carpeta de evidencia | Hay salidas reales (capturas o output de consola/`explain()`), no solo texto afirmando que se hizo |

## Checklist — Requisitos No Funcionales

| ID | Requisito | Cómo verificar |
|---|---|---|
| RNF1 Reproducibilidad | Simular clon nuevo: seguir el README literal, sin conocimiento previo del repo, y ver si se levanta y carga todo |
| RNF2 Volumen mínimo | 64 equipos y ≥1000 jugadores, y que sean **recuperables** por consulta, no solo insertados |
| RNF3 Integridad documental | Pipeline de agregación buscando: IDs duplicados (`$group` + `$count > 1`), jugadores cuyo `equipo_id` no existe en `equipos` (`$lookup` con array vacío), campos críticos nulos o ausentes |
| RNF4 Eficiencia | `explain("executionStats")` de al menos una consulta principal antes y después del índice — comparar `totalDocsExamined` vs `nReturned` |
| RNF5 Trazabilidad | ¿El documento de decisiones menciona explícitamente el Hito 2 y el Hito 3, o solo dice "se decidió X"? Si no hay ese vínculo, marcarlo como gap de documentación, no inventarlo |
| RNF6 Mantenibilidad | Carga, consultas y documentación están en archivos/carpetas separados y con nombres claros (no todo en un único script gigante) |
| RNF7 Portabilidad | Buscar rutas absolutas tipo `/Users/nombre/...` o similar hardcodeadas — deberían ser relativas o vía variables |
| RNF8 Tiempo | No verificable técnicamente — omitir del informe |

## Estructura y entregables esperados (verificar que existan)

- Docker Compose
- Mecanismo de carga de datos
- Definición de validaciones
- Archivos de consultas (identificación, filtrado, proyección, orden/paginación, agregación)
- Documentación de diseño con la tabla de decisiones (relación equipo-jugador, validación
  documental, estrategia de identificadores, índices principales, carga y actualización)
- Evidencia (capturas, salidas de consola, resultados de `explain`)
- README con: requisitos, pasos de inicio, carga, ejecución de consultas, estructura de
  archivos, limitaciones conocidas
- Documento de decisiones técnicas separado (`.md` o `.pdf`)

## Formato del informe final esperado

Generar `docs/auditoria_hito4.md` con:

1. Tabla RF1-RF13 y RNF1-RNF8: estado (`PASS` / `FAIL` / `No verificable — falta insumo`),
   evidencia concreta (comando ejecutado + output relevante, no solo la conclusión).
2. Lista de cambios aplicados automáticamente, con el motivo de cada uno.
3. Lista de decisiones de diseño **no tocadas** que quedan señaladas para revisión humana,
   con la razón por la que se marcaron (ej: "el índice en `jugadores.equipo_id` no tiene
   ninguna consulta documentada que lo use — revisar si corresponde o si falta la consulta").
4. Gaps de documentación (RNF5 en particular) que el grupo necesita completar a mano porque
   requieren conocimiento del Hito 2/3 que no está en este repo.
