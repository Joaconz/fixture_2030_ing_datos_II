#!lua name=f30
-- ============================================================
--  Fixture 2030 — Hito 7 · Librería de Redis Functions `f30`
--  Carga:  redis-cli -x FUNCTION LOAD REPLACE < funciones_f30.lua
--
--  ATOMICIDAD (RF8, §5.5): Redis ejecuta cada función como una unidad
--  indivisible: ningún otro cliente intercala comandos mientras corre.
--  Por eso cada "leer y luego escribir" de abajo NO tiene ventana de
--  carrera. Las funciones se persisten con AOF/RDB (sobreviven al reinicio).
--  No usan reloj del cliente: el tiempo sale de `TIME` del servidor.
-- ============================================================

local function ahora()
  return tonumber(redis.call('TIME')[1])
end

-- ------------------------------------------------------------
-- ses_crear  KEYS[1]=f30:ses:{id}  KEYS[2]=f30:usr:{usuario}:sesiones
--   ARGV: usuario_id rol region dispositivo ttl_inactividad_s ttl_absoluto_s
-- Crea el hash completo y su TTL en un solo paso: nunca queda una
-- sesión sin TTL (zombie) si el cliente cae a mitad de camino.
-- ------------------------------------------------------------
local function ses_crear(keys, argv)
  local t = ahora()
  local ttl_inact = tonumber(argv[5])
  local ttl_abs = tonumber(argv[6])
  local id = string.match(keys[1], '[^:]+$')
  redis.call('HSET', keys[1],
    'session_id', id, 'usuario_id', argv[1], 'rol', argv[2],
    'region', argv[3], 'dispositivo', argv[4], 'estado', 'ACTIVA',
    'creada_en', t, 'ultima_actividad', t,
    'expira_absoluta', t + ttl_abs, 'solicitudes', 0)
  redis.call('EXPIRE', keys[1], math.min(ttl_inact, ttl_abs))
  redis.call('SADD', keys[2], id)
  -- el índice por usuario nunca vive menos que su sesión más larga posible
  redis.call('EXPIRE', keys[2], ttl_abs, 'GT')
  if redis.call('TTL', keys[2]) < 0 then redis.call('EXPIRE', keys[2], ttl_abs) end
  return id
end

-- ------------------------------------------------------------
-- ses_tocar  KEYS[1]=f30:ses:{id}   ARGV[1]=ttl_inactividad_s
-- Valida y renueva (TTL deslizante con tope absoluto). Devuelve:
--   nil            -> la sesión no existe/venció (la app pide login)
--   error          -> SESION_BLOQUEADA (no se renueva)
--   {usuario_id, region, rol, solicitudes, ttl_restante}
-- Hecho con comandos sueltos, la clave podría vencer entre el EXISTS y el
-- HSET/EXPIRE y HSET recrearía un hash parcial SIN TTL. Acá es imposible.
-- ------------------------------------------------------------
local function ses_tocar(keys, argv)
  local k = keys[1]
  if redis.call('EXISTS', k) == 0 then return false end
  local d = redis.call('HMGET', k, 'estado', 'expira_absoluta', 'usuario_id', 'region', 'rol')
  if d[1] == 'BLOQUEADA' then return redis.error_reply('SESION_BLOQUEADA') end
  local t = ahora()
  local restante_abs = tonumber(d[2]) - t
  if restante_abs <= 0 then
    redis.call('DEL', k)          -- tope absoluto alcanzado: fin de sesión
    return false
  end
  local ttl = math.min(tonumber(argv[1]), restante_abs)
  redis.call('HSET', k, 'ultima_actividad', t)
  local n = redis.call('HINCRBY', k, 'solicitudes', 1)
  redis.call('EXPIRE', k, ttl)
  return {d[3], d[4], d[5], n, ttl}
end

-- ------------------------------------------------------------
-- ses_cerrar  KEYS[1]=f30:ses:{id}  KEYS[2]=f30:usr:{usuario}:sesiones
-- Logout: borra la sesión y la saca del índice. Devuelve 1 si existía.
-- ------------------------------------------------------------
local function ses_cerrar(keys, argv)
  local id = string.match(keys[1], '[^:]+$')
  redis.call('SREM', keys[2], id)
  return redis.call('DEL', keys[1])
end

-- ------------------------------------------------------------
-- ses_cerrar_todas  KEYS[1]=f30:usr:{usuario}:sesiones  ARGV[1]=prefijo f30:ses:
-- Cierra todas las sesiones de un usuario (cambio de contraseña, baja).
-- Nota: construye claves dentro del script; válido en nodo único. En
-- Redis Cluster habría que usar un hash tag común (ver memoria_y_escalabilidad §5).
-- ------------------------------------------------------------
local function ses_cerrar_todas(keys, argv)
  local ids = redis.call('SMEMBERS', keys[1])
  local borradas = 0
  for _, id in ipairs(ids) do
    borradas = borradas + redis.call('DEL', argv[1] .. id)
  end
  redis.call('DEL', keys[1])
  return borradas
end

-- ------------------------------------------------------------
-- cache_poner_si_version  KEYS[1]=f30:cache:...  KEYS[2]=f30:cache:...:ver
--   ARGV: json ttl_s version_leida
-- Cache-aside sin "stale set": el lector anota la versión ANTES de leer la
-- fuente; si mientras tanto alguien invalidó (INCR de :ver), la versión
-- actual es mayor y la copia vieja se descarta. Devuelve 1 si escribió.
-- ------------------------------------------------------------
local function cache_poner_si_version(keys, argv)
  local actual = tonumber(redis.call('GET', keys[2]) or '0')
  if actual > tonumber(argv[3]) then return 0 end
  redis.call('SET', keys[1], argv[1], 'EX', tonumber(argv[2]))
  return 1
end

-- ------------------------------------------------------------
-- cache_invalidar  KEYS[1]=f30:cache:...  KEYS[2]=f30:cache:...:ver
-- Se llama cuando cambia la fuente de verdad: borra la copia y sube la
-- versión, todo junto. Devuelve la nueva versión.
-- ------------------------------------------------------------
local function cache_invalidar(keys, argv)
  redis.call('DEL', keys[1])
  local v = redis.call('INCR', keys[2])
  redis.call('EXPIRE', keys[2], 86400)
  return v
end

-- ------------------------------------------------------------
-- voto_emitir  KEYS[1]=...:votantes (SET)  KEYS[2]=...:ranking (ZSET)
--   ARGV: usuario_id candidato_id
-- Un voto por usuario. SADD y ZINCRBY van juntos: sin función, dos clientes
-- con el mismo usuario podrían pasar ambos el chequeo (check-then-act) y
-- contar doble; o el proceso caer entre SADD y ZINCRBY (voto sin contar).
-- Devuelve {1, puntaje} si contó, {0, puntaje_actual} si ya había votado.
-- ------------------------------------------------------------
local function voto_emitir(keys, argv)
  if redis.call('SADD', keys[1], argv[1]) == 1 then
    local p = redis.call('ZINCRBY', keys[2], 1, argv[2])
    return {1, tonumber(p)}
  end
  return {0, 0}
end

-- ------------------------------------------------------------
-- tendencia_registrar  KEYS[1]=f30:rank:tendencia:{yyyymmddHH}
--   ARGV: partido_id ttl_s
-- Cuenta una visita a un partido en el bucket horario; el TTL se fija sólo
-- la primera vez (NX): el bucket vence solo, sin barridos.
-- ------------------------------------------------------------
local function tendencia_registrar(keys, argv)
  local p = redis.call('ZINCRBY', keys[1], 1, argv[1])
  redis.call('EXPIRE', keys[1], tonumber(argv[2]), 'NX')
  return tonumber(p)
end

redis.register_function('ses_crear', ses_crear)
redis.register_function('ses_tocar', ses_tocar)
redis.register_function('ses_cerrar', ses_cerrar)
redis.register_function('ses_cerrar_todas', ses_cerrar_todas)
redis.register_function('cache_poner_si_version', cache_poner_si_version)
redis.register_function('cache_invalidar', cache_invalidar)
redis.register_function('voto_emitir', voto_emitir)
redis.register_function('tendencia_registrar', tendencia_registrar)
