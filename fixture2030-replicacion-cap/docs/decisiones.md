# Decisiones de replicación del laboratorio

Cada decisión dice qué se eligió, por qué y de dónde viene. Las que vienen del Hito 3 se citan; las que son propias de este laboratorio (memoria, puertos, cómo provocar una falla) se marcan como tales. El análisis CAP de cada subsistema está en [`analisis_cap.md`](analisis_cap.md).

## 1. MongoDB (N1 Equipos y jugadores): replica set de 3 nodos

| Decisión | Valor | Por qué |
|---|---|---|
| Topología | 1 primario + 2 secundarios (`rs-fixture2030`) | Es la topología "Master-Slave" que pide la guía y la que fijó el Hito 3 para N1: "3 copias, lectura local, escritura confirma en el primario" (tabla de replicación). Tres miembros con voto es el mínimo que tolera la caída de uno y sigue teniendo mayoría (2 de 3) para elegir primario. |
| Prioridades | Las tres en 1 | Cualquier secundario puede asumir. Cuando el nodo caído vuelve, **no** recupera el primario (no hay *priority takeover*): se evita una segunda elección, y una segunda ventana sin escrituras, solo para volver a la situación anterior. |
| `electionTimeoutMillis` | 10 000 (valor por defecto) | Se dejó el valor de fábrica para medir el comportamiento real del motor. Es el término dominante del tiempo de failover medido (≈ 10 s, ver `analisis_cap.md` §2.1). Bajarlo acorta el failover pero aumenta las elecciones falsas ante una pausa de red o de la VM, que en este laboratorio existen (§4). |
| writeConcern de las escrituras | `w: "majority"` (por defecto en MongoDB 7, y el que usa el seed del Hito 4) | El Hito 3 define N1 como **CP en escritura**: un cambio confirmado tiene que sobrevivir a la caída del primario. Con `w:1` el primario confirma solo; si cae antes de replicar, esa escritura se descarta (*rollback*) al volver. Con `majority` eso no puede pasar. Medido: cuesta milisegundos (`analisis_cap.md` §2.2). |
| readPreference de las lecturas | `secondaryPreferred` para el catálogo de equipos y jugadores; `primary` (o `readConcern: "majority"`) para leer-después-de-escribir | El Hito 3 define N1 como **AP en lectura** con "ventana de segundos con datos desactualizados tras un cambio". Leer de secundarios es exactamente eso: reparte la carga y acepta un dato viejo. Medido en `mongo_lecturas_y_concerns`: un secundario devuelve el valor anterior mientras no replicó. |
| Carga | `fixture2030-mongodb/load/seed.js` sin cambios, conectado al replica set | La guía pide replicar el sistema del TPO, no otro. Se reusan esquema (`init/01-validators.js`) y datos (64 equipos, 1 472 jugadores) del Hito 4. |
| Memoria | `--wiredTigerCacheSizeGB 0.25`, `mem_limit: 512m` | Propia del laboratorio. Medido: ~110–130 MB por nodo con los datos cargados. |

## 2. Cassandra (N6 Comentarios): anillo de 3 nodos, RF = 3

| Decisión | Valor | Por qué |
|---|---|---|
| Topología | 3 nodos iguales en `datacenter1`, `rack1`; semillas `cas1,cas2` | Es la topología "Peer-to-Peer" que pide la guía: no hay primario, cualquier nodo coordina cualquier operación. Dos semillas para que un nodo que reinicia encuentre el anillo aunque una esté caída. |
| Estrategia y factor de réplica | `NetworkTopologyStrategy`, `{'datacenter1': 3}` | N = 3 es el valor del Hito 3 para Comentarios ("N=3, R=1, W=1"). La estrategia es la misma que eligió el Hito 6 (`esquema.cql` §1), donde quedó en RF = 1 solo porque había un nodo. Con 3 nodos y RF = 3, cada nodo tiene una copia de todo (medido: `Owns (effective) 100 %`). |
| Cómo se aplica el RF = 3 | Se crea el keyspace con RF = 3 **antes** de correr `esquema.cql` del Hito 6 | Así se usa el archivo del Hito 6 sin modificarlo: su `CREATE KEYSPACE IF NOT EXISTS` (RF = 1) queda sin efecto y el resto (tablas, índice SAI) se aplica tal cual. |
| Nivel de consistencia de diseño | Escritura y lectura de comentarios con `ONE` (W = 1, R = 1) | Hito 3. R + W = 2 ≤ N = 3: no garantiza leer lo último; se acepta porque un comentario que tarda en aparecer es tolerable (AP). Las pruebas muestran las tres variantes (ONE, QUORUM, ALL) para justificar la elección con datos. |
| Carga inicial | `carga_muestra.cql` del Hito 6 con `CONSISTENCY ALL` | Para arrancar las pruebas con las tres réplicas iguales. No es el nivel de operación: es una condición de la prueba. |
| Heap | `MAX_HEAP_SIZE=256M`, `HEAP_NEWSIZE=64M`, `mem_limit: 900m` | Propia del laboratorio. Por defecto Cassandra toma 1/4 de la RAM (~2 GB por nodo en esta VM de 7,7 GB), y tres nodos no entran junto a los módulos de un nodo. 256 MB alcanza para el volumen de la carga de muestra; **no** es un tamaño de producción (ahí se usan 8–16 GB). RAM medida: ver `analisis_cap.md` §3.4. |
| Filas de prueba | Partición real `PAR-A-1 / 13:00 / bucket 0`, `comentario_id` `PAR-A-1-REP-*`, borradas al final con `ALL` | Se prueba sobre la tabla y la partición reales del Hito 6, no sobre una tabla inventada. Las pruebas escriben solo en `comentarios_por_partido` (no en `comentarios_por_usuario`), porque lo que se mide es la réplica de una fila, no el *batch* de la aplicación. |

## 3. Cómo se provocan las fallas

| Falla | Cómo | Qué simula |
|---|---|---|
| Caída abrupta del primario de MongoDB | `docker kill` (SIGKILL) | Corte de energía o del proceso: nadie avisa, los secundarios lo detectan por falta de *heartbeats*. Es el caso que mide el tiempo de elección real. |
| Apagado ordenado del primario | `docker stop` (SIGTERM) | Mantenimiento planificado: el primario renuncia (*stepdown*) y pide a un secundario que asuma. Se mide para comparar. |
| Caída de un nodo de Cassandra | `docker stop` de `cas3` | Un nodo fuera del anillo. Para Cassandra no cambia el resultado entre `stop` y `kill`: no hay primario que renunciar. |
| Retraso de replicación determinista en MongoDB | `db.fsyncLock()` en los secundarios | Bloquea la aplicación del oplog: permite ver una lectura vieja y la diferencia entre `readConcern` sin depender de la suerte. |
| Réplica desactualizada determinista en Cassandra | `nodetool pausehandoff` / `disablehandoff` antes de que vuelva el nodo | Sin esto el *hinted handoff* repara en segundos y la lectura vieja casi nunca se ve. |

Ninguna prueba borra volúmenes. Todas devuelven el clúster al estado inicial (dato de Argentina restaurado, base `fixture2030_pruebas` y filas `PAR-A-1-REP-*` borradas, hints reactivados) aunque fallen a la mitad (`trap`).

## 4. Decisiones propias del entorno

- **Perfiles de compose separados** (`mongo`, `cassandra`, `carga`). Con los dos clústeres arriba a la vez, más los módulos de un nodo, la VM de Docker Desktop se quedaba sin memoria. Se prueban de a uno.
- **Nombres, puertos y red propios** (`fixture2030-rep-*`, 27041–27043, 19041–19043, `fixture2030-replicacion-net`, proyecto `fixture2030-replicacion`): pueden convivir con `fixture2030-mongodb` (27017) y `fixture2030-cassandra` (9042).
- **Reintento ante la API de Docker** (`dk` en `scripts/_comun.sh`): durante las pruebas Docker Desktop respondió `500 Internal Server Error` durante segundos, con la notebook sin memoria libre. El reintento es solo para ese error; un fallo de `mongosh` o `cqlsh` se informa tal cual.
- **Horas en el reloj de la VM de Docker**: las mediciones de failover usan horas de los contenedores y de `docker inspect`, que comparten reloj. El reloj de Windows no se mezcla.
