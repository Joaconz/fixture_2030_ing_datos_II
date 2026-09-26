# Modelo clave/valor — Hito 7 · Caché de Usuarios y Sesiones (Redis)

Cada clave está vinculada a los patrones P1–P11 de [`patrones_de_acceso.md`](./patrones_de_acceso.md) (RNF4). La decisión de vida útil de cada una está en [`ciclo_de_vida_e_invalidacion.md`](./ciclo_de_vida_e_invalidacion.md) (RNF6).

## 1. Convención de nombres (RNF5)

```
f30 : {dominio} : {entidad} : {identificador} [ : {subrecurso} ]
```

| Segmento | Significado | Valores usados |
|---|---|---|
| `f30` | Prefijo de proyecto (Fixture 2030). Permite compartir instancia sin colisiones y limpiar/medir por prefijo | `f30` |
| `{dominio}` | Propósito **y** política de vida | `ses` sesión · `usr` índices por usuario · `cache` copia de una fuente externa · `voto` votaciones · `rank` rankings temporales |
| `{entidad}` | Qué se guarda | `partido`, `usuario`, `mvp`, `tendencia` |
| `{identificador}` | El id de negocio de los otros hitos, sin transformar | `PAR-D16-01` (Hitos 5/6), `USR-0000001` (Hito 6), `demo-ses-…` |
| `{subrecurso}` | Estructura auxiliar de la misma entidad | `ver`, `votantes`, `ranking`, `sesiones`, `perfil` |

Reglas: minúsculas salvo los ids de negocio; `:` como único separador; **el dominio predice el TTL**: todo lo `cache:` y `ses:` vence; lo `voto:` abierto no vence (ver §3). Los ids de sesión de la muestra son ficticios (`demo-ses-…`): no hay tokens reales en el repo (RNF7).

## 2. Catálogo de claves

| Clave | Estructura | Contenido | Patrones | TTL |
|---|---|---|---|---|
| `f30:ses:{session_id}` | HASH | `session_id`, `usuario_id`, `rol` (HINCHA/MODERADOR), `region` (AM/EU/AF), `dispositivo` (web/android/ios), `estado` (ACTIVA/BLOQUEADA), `creada_en`, `ultima_actividad`, `expira_absoluta` (epoch s), `solicitudes` | P1 P2 P4 | 1800 s deslizante, tope 12 h |
| `f30:usr:{usuario_id}:sesiones` | SET | `session_id` de ese usuario | P3 | 12 h (= tope de sesión) |
| `f30:cache:partido:{partido_id}` | STRING (JSON) | ficha + marcador + `version` | P5 | 60 s + invalidación |
| `f30:cache:partido:{partido_id}:ver` | STRING (entero) | versión de la fuente vista por la última invalidación | P6 | 24 h |
| `f30:cache:usuario:{usuario_id}:perfil` | HASH | campos del perfil | P7 | 900 s + invalidación |
| `f30:voto:mvp:{partido_id}:votantes` | SET | `usuario_id` que ya votaron | P8 | sin TTL abierta |
| `f30:voto:mvp:{partido_id}:ranking` | ZSET | candidato → votos | P8 P9 | sin TTL abierta |
| `f30:rank:tendencia:{yyyymmddHH}` | ZSET | `partido_id` → visitas de esa hora | P10 P11 | 7200 s |

## 3. Por qué cada estructura

| Estructura | Elegida porque | Alternativa descartada |
|---|---|---|
| HASH para la sesión | Se lee entero (validación) o por campo (`HMGET`), y se actualiza un campo (`ultima_actividad`, `solicitudes`) sin reescribir el resto. Los hashes chicos usan una codificación compacta (`listpack`, verificado con `OBJECT ENCODING` en [`08_metricas.txt`](./evidencia/08_metricas.txt)) | STRING JSON: cada renovación exigiría leer, deserializar, modificar y reescribir todo (dos viajes y una carrera) |
| SET como índice de sesiones por usuario | Membresía y "cerrar todas" en O(n del usuario), sin `SCAN` global | Buscar por patrón `f30:ses:*` filtrando por usuario: barrido bloqueante (RNF8) |
| STRING para la ficha del partido | Se sirve entera y no se modifica por campo: es una copia de lectura | HASH: no aporta, la app siempre pide la ficha completa |
| STRING `:ver` separado | Un contador atómico (`INCR`) que sobrevive al `DEL` de la copia: es lo que permite detectar una repoblación vieja | Guardar la versión sólo dentro del JSON: desaparece con el `DEL` |
| SET + ZSET para el voto | El SET garantiza unicidad; el ZSET mantiene el ranking ordenado y actualizable con `ZINCRBY` | Sólo ZSET: no permite saber si el usuario ya votó |
| ZSET por hora para tendencia | `ZINCRBY` atómico, top-N ordenado sin ordenar en la app, y un TTL por bucket: el histórico se borra solo | Un ZSET único con reinicios periódicos: necesita un proceso que lo reinicie (prohibido: barridos manuales) |

## 4. Funciones del servidor (librería `f30`)

Las secuencias que no pueden intercalarse están empaquetadas como **Redis Functions** ([`scripts/funciones_f30.lua`](../scripts/funciones_f30.lua)), no como varios comandos sueltos ni como `MULTI/EXEC` con chequeo previo. Qué protege cada una está en [`concurrencia_y_pruebas.md`](./concurrencia_y_pruebas.md) §2.

| Función | Patrón | Reemplaza a |
|---|---|---|
| `ses_crear` | P1 | HSET + EXPIRE + SADD + EXPIRE sueltos |
| `ses_tocar` | P2 | EXISTS + HGET estado + HSET + HINCRBY + EXPIRE sueltos |
| `ses_cerrar`, `ses_cerrar_todas` | P3 | SREM/DEL/SMEMBERS sueltos |
| `cache_poner_si_version`, `cache_invalidar` | P5 P6 | GET ver + SET; DEL + INCR |
| `voto_emitir` | P8 | SISMEMBER + SADD + ZINCRBY |
| `tendencia_registrar` | P10 | ZINCRBY + EXPIRE |

## 5. Limitaciones conocidas del modelo

- **Índice de sesiones por usuario con miembros vencidos.** Cuando una sesión vence por TTL, su `session_id` sigue en el SET del usuario hasta que éste vence o se cierra (no hay evento que lo limpie sin un barrido, que está prohibido). Es inocuo: `ses_cerrar_todas` hace `DEL` sobre ids inexistentes y devuelve sólo las realmente borradas. Se observa en [`03_sesiones.txt`](./evidencia/03_sesiones.txt) §3.8 (`demo-B` sigue indexada).
- **`ses_cerrar_todas` arma claves dentro del script** (`prefijo + id`). Correcto en nodo único; en Redis Cluster habría que usar un *hash tag* común (`f30:{USR-…}:ses:…`) o resolverlo en la aplicación. Ver [`memoria_y_escalabilidad.md`](./memoria_y_escalabilidad.md) §5.
