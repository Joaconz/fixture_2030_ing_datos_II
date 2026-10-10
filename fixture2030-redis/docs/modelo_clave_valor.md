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
| `{subrecurso}` | Estructura auxiliar de la misma entidad | `votantes`, `ranking`, `sesiones`, `perfil` |

Reglas: minúsculas salvo los ids de negocio; `:` como único separador; **el dominio predice el TTL**: todo lo `cache:` y `ses:` vence; lo `voto:` abierto no vence (ver §3). Los ids de sesión de la muestra son ficticios (`demo-ses-…`): no hay tokens reales en el repo (RNF7).

## 2. Catálogo de claves

| Clave | Estructura | Contenido | Patrones | TTL |
|---|---|---|---|---|
| `f30:ses:{session_id}` | HASH | `session_id`, `usuario_id`, `rol` (HINCHA/MODERADOR), `region` (AM/EU/AF), `dispositivo` (web/android/ios), `estado` (ACTIVA/BLOQUEADA), `creada_en`, `ultima_actividad`, `expira_absoluta` (epoch s), `solicitudes` | P1 P2 P4 | 1800 s deslizante, tope 12 h |
| `f30:usr:{usuario_id}:sesiones` | SET | `session_id` de ese usuario | P3 | 12 h (= tope de sesión) |
| `f30:cache:partido:{partido_id}` | STRING (JSON) | ficha + marcador | P5 P6 | 60 s + invalidación |
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
| SET + ZSET para el voto | El SET garantiza unicidad: `SADD` registra y a la vez dice si el usuario ya estaba (devuelve 1 o 0). El ZSET mantiene el ranking ordenado y actualizable con `ZINCRBY` | Sólo ZSET: no permite saber si el usuario ya votó |
| ZSET por hora para tendencia | `ZINCRBY` atómico, top-N ordenado sin ordenar en la app, y un TTL por bucket: el histórico se borra solo | Un ZSET único con reinicios periódicos: necesita un proceso que lo reinicie (prohibido: barridos manuales) |

## 4. Operaciones atómicas: comandos nativos y `MULTI/EXEC`

El módulo usa solo los dos mecanismos de atomicidad de la Clase 8:

- **Un comando nativo** (`INCR`, `HINCRBY`, `ZINCRBY`, `SADD`, `SET … EX`, `DEL`) se ejecuta entero, sin intercalarse con otro cliente.
- **`MULTI/EXEC`** encola varios comandos y los ejecuta uno detrás de otro, sin comandos de otro cliente en el medio. No tiene condiciones adentro ni *rollback*: las decisiones (¿la sesión existe? ¿está bloqueada?) las toma la aplicación **antes**, con una lectura.

Qué protege cada una y qué riesgo queda está en [`concurrencia_y_pruebas.md`](./concurrencia_y_pruebas.md) §2.

| Operación | Patrón | Comandos | Mecanismo |
|---|---|---|---|
| Crear sesión | P1 | `HSET` + `EXPIRE` + `SADD` + `EXPIRE` del índice | `MULTI/EXEC` |
| Validar sesión | P2 | `HMGET usuario_id estado expira_absoluta` | lectura (decide la app) |
| Renovar sesión | P2 | `HSET ultima_actividad` + `HINCRBY solicitudes 1` + `EXPIRE` | `MULTI/EXEC` |
| Cerrar sesión | P3 | `SREM` del índice + `DEL` | `MULTI/EXEC` |
| Cerrar todas | P3 | `SMEMBERS` (lectura) y después `DEL` de cada sesión + `DEL` del índice | lectura + `MULTI/EXEC` |
| Repoblar caché | P5 | `SET … EX 60` | comando nativo |
| Invalidar caché | P6 | `DEL` | comando nativo |
| Cachear perfil | P7 | `HSET` + `EXPIRE` | `MULTI/EXEC` |
| Voto único | P8 | `SADD` (devuelve 1 solo la primera vez) y, si dio 1, `ZINCRBY` | comandos nativos |
| Visita a tendencia | P10 | `ZINCRBY` + `EXPIRE … NX` | `MULTI/EXEC` |

## 5. Limitaciones conocidas del modelo

- **Índice de sesiones por usuario con miembros vencidos.** Cuando una sesión vence por TTL, su `session_id` sigue en el SET del usuario hasta que éste vence o se cierra (no hay evento que lo limpie sin un barrido, que está prohibido). Es inocuo: "cerrar todas" hace `DEL` sobre ids inexistentes y `DEL` devuelve solo las realmente borradas. Se observa en [`03_sesiones.txt`](./evidencia/03_sesiones.txt) §3.9 (`demo-B` seguía indexada y se borró junto con `demo-A`).
- **"Cerrar todas" y los `MULTI/EXEC` usan varias claves a la vez.** Correcto en nodo único. En Redis Cluster, todas las claves de una transacción tienen que caer en el mismo slot: habría que usar un *hash tag* común (`f30:{USR-…}:ses:…`). Ver [`memoria_y_escalabilidad.md`](./memoria_y_escalabilidad.md) §5.
