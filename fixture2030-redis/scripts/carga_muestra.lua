#!lua name=f30carga
-- ============================================================
--  Fixture 2030 — Hito 7 · Generador determinista de la muestra (RF11)
--  Librería aparte de `f30` a propósito: es utilería de laboratorio,
--  no parte del módulo. Se invoca desde carga_muestra.redis.
--
--  DETERMINISMO: sin math.random ni TIME para decidir valores; todo sale
--  de fórmulas sobre el índice. Correrlo dos veces deja el MISMO dataset
--  (HSET/SADD/ZADD son idempotentes). Lo único que cambia entre corridas
--  son los timestamps y TTL, que dependen del reloj del servidor.
-- ============================================================

local REGIONES = {'AM', 'EU', 'AF'}                  -- regiones del Hito 3
local DISPOSITIVOS = {'web', 'android', 'ios'}
local GRUPOS = 'ABCDEFGHIJKLMNOP'                    -- mismos partido_id que Hitos 5 y 6

local function ids_partidos()
  local ids = {}
  for g = 1, #GRUPOS do
    for k = 1, 6 do ids[#ids + 1] = 'PAR-' .. GRUPOS:sub(g, g) .. '-' .. k end
  end
  for i = 1, 16 do ids[#ids + 1] = string.format('PAR-D16-%02d', i) end
  return ids  -- 112
end

-- ARGV[1] = cantidad de sesiones (default 2000)
local function carga_muestra(keys, argv)
  local n = tonumber(argv[1] or '2000')
  local t = tonumber(redis.call('TIME')[1])
  local TTL_INACT, TTL_ABS = 1800, 43200

  -- Sesiones: usuario i -> USR-000000i; cada 10º usuario tiene 2 sesiones (web + móvil).
  local creadas = 0
  for i = 1, n do
    local uid = string.format('USR-%07d', i)
    local nsesiones = (i % 10 == 0) and 2 or 1
    for s = 1, nsesiones do
      local sid = string.format('demo-ses-%07d-%d', i, s)
      local estado = (i % 33 == 0) and 'BLOQUEADA' or 'ACTIVA'   -- ~3 %
      local rol = (i % 200 == 0) and 'MODERADOR' or 'HINCHA'
      -- actividad reciente escalonada: 0..29 min atrás, así los TTL restantes se reparten
      local hace = (i * 7) % 1800
      local k = 'f30:ses:' .. sid
      redis.call('HSET', k,
        'session_id', sid, 'usuario_id', uid, 'rol', rol,
        'region', REGIONES[(i % 3) + 1], 'dispositivo', DISPOSITIVOS[((i + s) % 3) + 1],
        'estado', estado, 'creada_en', t - hace - 60, 'ultima_actividad', t - hace,
        'expira_absoluta', t - hace - 60 + TTL_ABS, 'solicitudes', (i * 13) % 50)
      redis.call('EXPIRE', k, TTL_INACT - hace)
      redis.call('SADD', 'f30:usr:' .. uid .. ':sesiones', sid)
      redis.call('EXPIRE', 'f30:usr:' .. uid .. ':sesiones', TTL_ABS)
      creadas = creadas + 1
    end
  end

  -- Ranking de tendencia de la hora fija 2030-06-29 16h: visitas sesgadas
  -- (los primeros partidos de cada fase concentran la audiencia).
  local ids = ids_partidos()
  local rk = 'f30:rank:tendencia:2030062916'
  redis.call('DEL', rk)
  for idx, pid in ipairs(ids) do
    local visitas = math.floor(100000 / (idx * idx * 0.02 + 1)) + (idx * 37) % 101
    if pid == 'PAR-D16-01' then visitas = 250000 end     -- partido de audiencia máxima
    redis.call('ZADD', rk, visitas, pid)
  end
  redis.call('EXPIRE', rk, 7200)

  -- Votación MVP abierta de PAR-D16-01: SIN TTL a propósito (ver memoria_y_escalabilidad §3).
  local base = 'f30:voto:mvp:PAR-D16-01'
  redis.call('DEL', base .. ':votantes', base .. ':ranking')
  local candidatos = {'ARG-10', 'ARG-9', 'FRA-10', 'FRA-7', 'BRA-11'}
  for i = 1, 500 do
    local uid = string.format('USR-%07d', i)
    local cand = candidatos[((i * 7 + math.floor(i / 3)) % 5) + 1]
    redis.call('SADD', base .. ':votantes', uid)
    redis.call('ZINCRBY', base .. ':ranking', 1, cand)
  end
  return {creadas, #ids, 500}
end

redis.register_function('carga_muestra', carga_muestra)
