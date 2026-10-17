"""Capas 3 a 6 con los MISMOS drivers que usa la API (RF6–RF14, RNF4, RNF14).

Corre con el .venv de la API del Hito 10 (pymongo, neo4j, cassandra-driver,
redis, httpx), desde la notebook: mismo origen, mismo driver y misma
configuración que la API, pero sin pasar por ella. Así se puede comparar
"cliente/driver funciona" contra "endpoint de la API falla" (§5.5).

Por producto, de menor a mayor costo:
    protocolo → autenticación → autorización → contexto → operación mínima
y, en cada capa, los CONTROLES negativos que pide §5.4 (database/keyspace
inexistente, credencial inválida, clave ausente, ventana sin puntos…), todos
de sólo lectura (RNF6). Un control da OK cuando la falla provocada se observa
y se clasifica como se esperaba.

    ../fixture2030-hito10-api/.venv/bin/python scripts/prueba_drivers.py [--producto X ...]

Qué NO demuestra: rendimiento, concurrencia ni que la API use bien el driver
(eso lo prueba prueba_api.py).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from registro import Registro, cargar_config, influx_token, neo4j_password, ruta_publica  # noqa: E402

CFG = cargar_config()
R = Registro("resultados_clientes", "Capas 3-6 — protocolo, identidad, contexto y operación (drivers)")
T = float(CFG.get("CONNECT_TIMEOUT", "2"))
TOP = float(CFG.get("OPERACION_TIMEOUT", "3"))
UTC = timezone.utc


def medir(fn: Callable[[], Any]) -> tuple[Any, float, BaseException | None]:
    t0 = time.perf_counter()
    try:
        return fn(), (time.perf_counter() - t0) * 1000, None
    except Exception as exc:  # noqa: BLE001 — se registra y se clasifica
        return None, (time.perf_counter() - t0) * 1000, exc


def nombre_error(exc: BaseException) -> str:
    """Tipo + primera línea, sin hosts largos (se redacta igual al registrar)."""
    texto = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
    return f"{type(exc).__name__}: {texto[:140]}"


def reg(producto: str, capa: str, prueba: str, objetivo: str, ok: bool, ms: float, detalle: str,
        interpretacion: str, no_demuestra: str = "", resultado: str | None = None) -> bool:
    R.agregar(producto=producto, capa=capa, prueba=prueba, objetivo=objetivo,
              resultado=resultado or ("OK" if ok else "FAIL"), latencia_ms=ms, detalle=detalle,
              interpretacion=interpretacion, no_demuestra=no_demuestra)
    return ok


def nc(producto: str, capa: str, prueba: str, objetivo: str, detalle: str, interpretacion: str) -> None:
    R.agregar(producto=producto, capa=capa, prueba=prueba, objetivo=objetivo, resultado="N/C",
              detalle=detalle, interpretacion=interpretacion)


def saltar(producto: str, desde: str, motivo: str) -> None:
    """Las capas siguientes no se prueban si falla una anterior (no saltar capas)."""
    capas = ["protocolo", "autenticacion", "autorizacion", "contexto", "operacion"]
    for capa in capas[capas.index(desde) + 1:]:
        R.agregar(producto=producto, capa=capa, prueba="(no ejecutada)", objetivo="-", resultado="SKIP",
                  detalle=f"no se ejecuta porque falló la capa {desde}: {motivo}",
                  interpretacion="SKIP = no probado; corregir primero la capa anterior")


# =========================================================================== MongoDB
def mongodb() -> None:
    from pymongo import MongoClient

    ms_t = int(T * 1000)
    host, puerto, db = CFG["MONGO_HOST"], int(CFG["MONGO_PORT"]), CFG["MONGO_DB"]
    obj = f"mongodb://{host}:{puerto}"
    cli = MongoClient(host, puerto, serverSelectionTimeoutMS=ms_t, connectTimeoutMS=ms_t,
                      socketTimeoutMS=int(TOP * 1000), appname="fixture2030-hito11")
    try:
        hello, ms, err = medir(lambda: cli.admin.command("hello"))
        ver = cli.server_info().get("version") if not err else None
        if not reg("mongodb", "protocolo", "hello (handshake del wire protocol)", obj, err is None, ms,
                   f"MongoDB {ver} · maxWireVersion {hello.get('maxWireVersion')} · "
                   f"isWritablePrimary {hello.get('isWritablePrimary')}" if not err else nombre_error(err),
                   "el servidor habla el protocolo de MongoDB y aceptó la sesión",
                   "que la base del Fixture exista ni que haya datos"):
            return saltar("mongodb", "protocolo", nombre_error(err))

        st, ms, err = medir(lambda: cli.admin.command("connectionStatus"))
        usuarios = (st or {}).get("authInfo", {}).get("authenticatedUsers", [])
        nc("mongodb", "autenticacion", "connectionStatus.authInfo", obj,
           f"usuarios autenticados: {len(usuarios)} — el laboratorio corre sin --auth (Hito 4)",
           "N/C: no hay identidad que probar; en un entorno real esta capa sería obligatoria")
        nc("mongodb", "autorizacion", "roles del usuario", obj,
           "sin control de acceso: cualquier cliente local puede leer y escribir",
           "N/C: documentado como limitación del laboratorio")

        dbs, ms, err = medir(lambda: cli.list_database_names())
        reg("mongodb", "contexto", "listDatabases contiene la base configurada", f"{obj}/{db}",
            err is None and db in (dbs or []), ms,
            f"bases: {', '.join(dbs)}" if not err else nombre_error(err),
            "la database que usa la API existe en el servidor")
        cols, ms, err = medir(lambda: cli[db].list_collection_names(filter={"name": {"$in": ["equipos", "jugadores"]}}))
        reg("mongodb", "contexto", "listCollections equipos/jugadores", f"{db}.{{equipos,jugadores}}",
            err is None and set(cols or []) == {"equipos", "jugadores"}, ms,
            f"colecciones: {sorted(cols or [])}" if not err else nombre_error(err),
            "las colecciones del módulo documental existen (sin leer documentos)")
        falso = db + "_inexistente"
        cols2, ms, err = medir(lambda: cli[falso].list_collection_names())
        reg("mongodb", "contexto", "control: database inexistente", f"{obj}/{falso}",
            err is None and cols2 == [], ms,
            f"sin error y sin colecciones ({cols2})" if not err else nombre_error(err),
            "Mongo NO falla con una database mal escrita: crea el contexto al vuelo y devuelve vacío. "
            "Por eso la API verifica la colección en /health/dependencias (no basta con ping)",
            "que la API lo detecte en cada request (la API respondería 404 TEAM_NOT_FOUND)")

        cod = CFG["MONGO_EQUIPO_DEMO"]
        doc, ms, err = medir(lambda: cli[db]["equipos"].find_one({"_id": cod}, {"_id": 1, "nombre": 1}, max_time_ms=int(TOP * 1000)))
        reg("mongodb", "operacion", "equipos.findOne({_id}) con proyección", f"{db}.equipos _id={cod}",
            err is None and doc is not None, ms,
            f"{doc}" if doc else (nombre_error(err) if err else "sin documento"),
            "lectura mínima del caso de uso CU1 (ficha de equipo) desde el mismo origen que la API",
            "rendimiento ni índices bajo carga")
        n, ms, err = medir(lambda: cli[db]["jugadores"].count_documents({"equipoId": cod}, limit=50, maxTimeMS=int(TOP * 1000)))
        reg("mongodb", "operacion", "jugadores.countDocuments({equipoId}, limit 50)", f"{db}.jugadores equipoId={cod}",
            err is None and (n or 0) > 0, ms, f"{n} jugadores" if not err else nombre_error(err),
            "el plantel (CU2) es legible con el índice {equipoId, posicion}")
        doc, ms, err = medir(lambda: cli[db]["equipos"].find_one({"_id": "XXX"}, {"_id": 1}))
        reg("mongodb", "operacion", "control: documento inexistente", f"{db}.equipos _id=XXX",
            err is None and doc is None, ms, "None (sin error)" if err is None else nombre_error(err),
            "ausencia válida: la API debe responder 404, no 503")
    finally:
        cli.close()


# =========================================================================== Neo4j
def neo4j() -> None:
    import httpx
    from neo4j import GraphDatabase, Query
    from neo4j.exceptions import AuthError, ClientError

    host, bolt, http, dbn = CFG["NEO4J_HOST"], CFG["NEO4J_BOLT_PORT"], CFG["NEO4J_HTTP_PORT"], CFG["NEO4J_DATABASE"]
    uri = f"bolt://{host}:{bolt}"
    r, ms, err = medir(lambda: httpx.get(f"http://{host}:{http}/", timeout=T))
    disc = r.json() if (r is not None and r.status_code == 200) else {}
    reg("neo4j", "protocolo", "HTTP discovery del Browser (GET /)", f"http://{host}:{http}",
        bool(disc.get("bolt_direct")), ms,
        f"HTTP {r.status_code} · Neo4j {disc.get('neo4j_version')} {disc.get('neo4j_edition')} · anuncia {disc.get('bolt_direct')}"
        if r is not None else nombre_error(err),
        "el portal HTTP responde; NO es el camino de la API",
        "que Bolt (7687) esté accesible ni que la credencial sirva")

    user = CFG.get("NEO4J_USER", "neo4j")
    pwd, origen = neo4j_password(CFG)
    drv = GraphDatabase.driver(uri, auth=(user, pwd or ""), connection_timeout=T,
                               connection_acquisition_timeout=T, max_transaction_retry_time=TOP,
                               user_agent="fixture2030-hito11")
    try:
        _, ms, err = medir(drv.verify_connectivity)
        info = None if err else drv.get_server_info()
        if err and not isinstance(err, AuthError):
            reg("neo4j", "protocolo", "verify_connectivity (handshake Bolt)", uri, False, ms, nombre_error(err),
                "no se pudo negociar Bolt", "")
            return saltar("neo4j", "protocolo", nombre_error(err))
        reg("neo4j", "protocolo", "verify_connectivity (handshake Bolt)", uri, True, ms,
            f"Bolt {'.'.join(map(str, info.protocol_version))} · {info.agent}" if info else
            "handshake Bolt completo (la autenticación falló después)",
            "el driver de la API negocia Bolt en el puerto publicado",
            "que la database exista ni que haya partidos")

        ok, ms, err = medir(drv.verify_authentication)
        if not reg("neo4j", "autenticacion", f"verify_authentication (usuario {user}, contraseña de {origen})", uri,
                   err is None and ok is True, ms, "credencial aceptada" if err is None else nombre_error(err),
                   "la identidad configurada para la API es válida"):
            return saltar("neo4j", "autenticacion", nombre_error(err))
        malo = GraphDatabase.driver(uri, auth=(user, "contrasena-invalida-de-diagnostico"), connection_timeout=T)
        try:
            # verify_authentication devuelve False ante credencial rechazada; verify_connectivity lanza AuthError
            aceptada, ms, err = medir(malo.verify_authentication)
            _, _, err2 = medir(malo.verify_connectivity)
        finally:
            malo.close()
        reg("neo4j", "autenticacion", "control: contraseña inválida (un solo intento)", uri,
            aceptada is False and isinstance(err2, AuthError), ms,
            f"verify_authentication={aceptada} · {nombre_error(err2) if err2 else 'sin excepción'}",
            "una credencial mala da AuthError (identidad), no ServiceUnavailable (red): son fallas distintas")

        def _usuario() -> Any:
            with drv.session(database="system") as s:
                return s.run("SHOW CURRENT USER YIELD user, roles").single()
        fila, ms, err = medir(_usuario)
        if err is None:
            reg("neo4j", "autorizacion", "SHOW CURRENT USER", f"{uri} (database system)", True, ms,
                f"usuario {fila['user']} · roles {fila['roles'] or '(Community: sin RBAC)'}",
                "la identidad puede consultar su propio perfil; Community no tiene roles de lectura/escritura finos")
        else:
            reg("neo4j", "autorizacion", "SHOW CURRENT USER", f"{uri} (database system)", False, ms,
                nombre_error(err), "no se pudo verificar la identidad del lado servidor", resultado="WARN")

        def _dbs() -> Any:
            with drv.session(database="system") as s:
                return [(r["name"], r["currentStatus"]) for r in s.run("SHOW DATABASES YIELD name, currentStatus")]
        dbs, ms, err = medir(_dbs)
        estado = dict(dbs or []).get(dbn)
        reg("neo4j", "contexto", "SHOW DATABASES: database configurada online", f"{uri} database={dbn}",
            estado == "online", ms, f"{dbs}" if not err else nombre_error(err),
            "la database que selecciona la API existe y está online")

        def _en(db: str) -> Any:
            with drv.session(database=db) as s:
                return s.run("RETURN 1 AS ok").single()["ok"]
        _, ms, err = medir(lambda: _en("fixture2030inexistente"))
        reg("neo4j", "contexto", "control: database inexistente", f"{uri} database=fixture2030inexistente",
            isinstance(err, ClientError) and "DatabaseNotFound" in (getattr(err, "code", "") or ""), ms,
            f"{getattr(err, 'code', '')}" if err else "¡aceptada!",
            "Neo4j sí rechaza un contexto inexistente (a diferencia de Mongo). La API lo traduce a 503 "
            "con motivo `contexto` (antes del Hito 11 era 500)")

        q = ("MATCH (p:Partido {partidoId: $id}) OPTIONAL MATCH (ev:Evento)-[:OCURRE_EN]->(p) "
             "RETURN p.partidoId AS id, p.estado AS estado, count(ev) AS eventos LIMIT 1")

        def _leer(pid: str) -> Any:
            with drv.session(database=dbn, default_access_mode="READ") as s:
                return s.run(Query(q, timeout=TOP), id=pid).single()   # timeout del lado servidor
        for pid, esperado, explicacion in [
            (CFG["NEO4J_PARTIDO_DEMO"], "con_eventos", "lectura Cypher parametrizada y acotada (CU4/CU5)"),
            (CFG["NEO4J_PARTIDO_SIN_EVENTOS"], "sin_eventos", "partido existente sin eventos: resultado vacío VÁLIDO (la API da 200 con items: [])"),
            (CFG["NEO4J_PARTIDO_INEXISTENTE"], "inexistente", "sin fila: partido inexistente (la API da 404 MATCH_NOT_FOUND), no error de conexión"),
        ]:
            fila, ms, err = medir(lambda pid=pid: _leer(pid))
            if err:
                reg("neo4j", "operacion", f"lectura partido {pid}", f"database={dbn} partidoId={pid}", False, ms,
                    nombre_error(err), "error de conexión/consulta: distinto de 'vacío' y de 'inexistente'")
                continue
            obs = "inexistente" if fila is None else ("con_eventos" if fila["eventos"] > 0 else "sin_eventos")
            reg("neo4j", "operacion", f"lectura partido {pid}", f"database={dbn} partidoId={pid}",
                obs == esperado, ms,
                "sin fila" if fila is None else f"estado {fila['estado']} · {fila['eventos']} eventos",
                explicacion, "rendimiento de recorridos multisalto")
    finally:
        drv.close()


# =========================================================================== Cassandra
def cassandra() -> None:
    from cassandra import InvalidRequest
    from cassandra.cluster import EXEC_PROFILE_DEFAULT, Cluster, ExecutionProfile, NoHostAvailable
    from cassandra.policies import DCAwareRoundRobinPolicy
    from cassandra.protocol import SyntaxException

    host, puerto, ks, tabla = CFG["CASSANDRA_HOST"], int(CFG["CASSANDRA_PORT"]), CFG["CASSANDRA_KEYSPACE"], CFG["CASSANDRA_TABLA"]
    obj = f"{host}:{puerto}"
    perfil = ExecutionProfile(load_balancing_policy=DCAwareRoundRobinPolicy(local_dc=CFG["CASSANDRA_DC"]),
                              request_timeout=TOP)
    cl = Cluster([host], port=puerto, connect_timeout=T, control_connection_timeout=T,
                 execution_profiles={EXEC_PROFILE_DEFAULT: perfil})
    ses, ms, err = medir(cl.connect)
    try:
        if err:
            reg("cassandra", "protocolo", "Cluster.connect (handshake CQL)", obj, False, ms, nombre_error(err),
                "no se pudo negociar el protocolo nativo de CQL"
                + (" (NoHostAvailable: revisar host/puerto/DC)" if isinstance(err, NoHostAvailable) else ""))
            return saltar("cassandra", "protocolo", nombre_error(err))
        local = ses.execute("SELECT release_version, data_center, cluster_name FROM system.local").one()
        reg("cassandra", "protocolo", "Cluster.connect + system.local", obj, True, ms,
            f"Cassandra {local.release_version} · protocolo v{cl.protocol_version} · DC {local.data_center} · "
            f"cluster {local.cluster_name}",
            "el driver de la API negocia CQL y el DC local coincide con CASSANDRA_DC",
            "que el keyspace del Fixture exista")
        nc("cassandra", "autenticacion", "sesión sin credenciales aceptada", obj,
           "AllowAllAuthenticator: el servidor no pide usuario (Hito 6, laboratorio)",
           "N/C: la capa no aplica en este entorno; con PasswordAuthenticator fallaría con AuthenticationFailed")
        nc("cassandra", "autorizacion", "permisos sobre el keyspace", obj,
           "AllowAllAuthorizer: sin GRANT/REVOKE", "N/C: documentado como limitación del laboratorio")

        f, ms, err = medir(lambda: ses.execute(
            "SELECT keyspace_name, replication FROM system_schema.keyspaces WHERE keyspace_name = %s", (ks,)).one())
        reg("cassandra", "contexto", "keyspace configurado en system_schema", f"keyspace={ks}",
            f is not None, ms, f"replicación {dict(f.replication)}" if f else (nombre_error(err) if err else "no existe"),
            "el keyspace que usa la API existe (con su estrategia de replicación del Hito 6)")
        cols, ms, err = medir(lambda: list(ses.execute(
            "SELECT column_name, kind, position FROM system_schema.columns WHERE keyspace_name=%s AND table_name=%s",
            (ks, tabla))))
        pk = [c.column_name for c in sorted(cols or [], key=lambda c: c.position) if c.kind == "partition_key"]
        ck = [c.column_name for c in sorted(cols or [], key=lambda c: c.position) if c.kind == "clustering"]
        reg("cassandra", "contexto", "tabla y patrón de partición", f"{ks}.{tabla}", bool(pk), ms,
            f"partition key ({', '.join(pk)}) · clustering ({', '.join(ck)})" if pk else "tabla inexistente",
            "toda lectura de la API filtra por la partición completa (partido, ventana de 10 min, bucket)")
        _, ms, err = medir(lambda: ses.set_keyspace(ks + "_inexistente"))
        reg("cassandra", "contexto", "control: keyspace inexistente (USE)", f"keyspace={ks}_inexistente",
            isinstance(err, InvalidRequest), ms, nombre_error(err) if err else "¡aceptado!",
            "keyspace mal configurado = InvalidRequest al preparar: la API responde 503 con motivo `contexto`")
        _, ms, err = medir(lambda: ses.execute(f"SELECT * FROM {ks}.tabla_inexistente LIMIT 1"))
        reg("cassandra", "contexto", "control: tabla inexistente", f"{ks}.tabla_inexistente",
            isinstance(err, InvalidRequest), ms, nombre_error(err) if err else "¡aceptada!",
            "error de esquema: la conexión está bien, el contexto no")
        _, ms, err = medir(lambda: ses.execute("SELEC 1"))
        reg("cassandra", "contexto", "control: consulta inválida (sintaxis)", obj,
            isinstance(err, SyntaxException), ms, nombre_error(err) if err else "¡aceptada!",
            "SyntaxException responde al instante: no es un timeout de conexión (que tardaría CONNECT_TIMEOUT)")

        pid = CFG["CASSANDRA_PARTIDO_DEMO"]
        cfgp, ms, err = medir(lambda: ses.execute(
            f"SELECT buckets, ventana_minutos, inicio FROM {ks}.config_particion_partido WHERE partido_id = %s", (pid,)).one())
        if not reg("cassandra", "operacion", "config de partición del partido", f"{ks}.config_particion_partido partido_id={pid}",
                   cfgp is not None, ms,
                   f"{cfgp.buckets} buckets · ventana {cfgp.ventana_minutos} min · inicio {cfgp.inicio}Z" if cfgp
                   else (nombre_error(err) if err else "sin fila"),
                   "lectura por clave primaria (Q0 del Hito 6)"):
            return
        inicio = cfgp.inicio.replace(tzinfo=None)
        paso = timedelta(minutes=cfgp.ventana_minutos)
        v = datetime(inicio.year, inicio.month, inicio.day, inicio.hour, inicio.minute - inicio.minute % cfgp.ventana_minutos)
        t0, filas, particion, consultas = time.perf_counter(), [], None, 0
        for _ in range(16):                    # tramo del partido: a lo sumo 16 ventanas × buckets
            for b in range(cfgp.buckets):
                consultas += 1
                filas = list(ses.execute(f"SELECT comentario_id, creado_en FROM {ks}.{tabla} "
                                         "WHERE partido_id=%s AND ventana=%s AND bucket=%s LIMIT 5", (pid, v, b)))
                if filas:
                    particion = (v, b)
                    break
            if filas:
                break
            v += paso
        reg("cassandra", "operacion", "SELECT … WHERE partición completa LIMIT 5", f"{ks}.{tabla} partido_id={pid}",
            bool(filas), (time.perf_counter() - t0) * 1000,
            f"{len(filas)} comentarios en (ventana {particion[0]:%H:%M}, bucket {particion[1]}) tras {consultas} consultas acotadas"
            if filas else f"sin comentarios en {consultas} particiones",
            "lectura limitada del módulo de comentarios (CU7), sin escaneo de tabla",
            "throughput de escritura ni distribución de particiones (Hito 12)")
    finally:
        cl.shutdown()


# =========================================================================== Redis
def redis_() -> None:
    import redis

    host, puerto, db = CFG["REDIS_HOST"], int(CFG["REDIS_PORT"]), int(CFG["REDIS_DB"])
    obj = f"{host}:{puerto}/{db}"
    r = redis.Redis(host=host, port=puerto, db=db, socket_connect_timeout=T, socket_timeout=TOP, decode_responses=True)
    try:
        pong, ms, err = medir(r.ping)
        if not reg("redis", "protocolo", "PING (RESP)", obj, pong is True, ms, "PONG" if pong else nombre_error(err),
                   "el servidor habla RESP y responde", "que exista ninguna clave"):
            return saltar("redis", "protocolo", nombre_error(err))
        info = r.info("server")
        R.agregar(producto="redis", capa="protocolo", prueba="INFO server", objetivo=obj, resultado="OK",
                  detalle=f"Redis {info.get('redis_version')} · modo {info.get('redis_mode')}",
                  interpretacion="versión observada (RNF18)")
        quien, ms, err = medir(lambda: r.execute_command("ACL", "WHOAMI"))
        nc("redis", "autenticacion", "ACL WHOAMI", obj,
           f"usuario '{quien}' sin contraseña (requirepass vacío, publicado sólo en 127.0.0.1 — Hito 7)",
           "N/C: con contraseña, un cliente sin AUTH recibiría NOAUTH (identidad), no un error de red")
        nc("redis", "autorizacion", "ACL del usuario", obj, "usuario default con todos los comandos",
           "N/C: con ACL restrictiva un comando prohibido da NOPERM → la API responde 503 motivo `autorizacion`")
        ks = r.info("keyspace").get(f"db{db}", {})
        R.agregar(producto="redis", capa="contexto", prueba=f"INFO keyspace db{db}", objetivo=obj, resultado="OK",
                  detalle=f"keys={ks.get('keys', 0)} · expires={ks.get('expires', 0)}",
                  interpretacion="la base lógica que usa la API (REDIS_URL …/0) es la consultada",
                  no_demuestra="que las claves de la demo estén cargadas")

        def estado_clave(clave: str) -> tuple[str, str]:
            existe, tipo, ttl = r.exists(clave), r.type(clave), r.ttl(clave)
            if not existe:
                return "ausente", f"EXISTS 0 · TTL {ttl}"
            campos = r.hlen(clave) if tipo == "hash" else "-"
            if ttl == -1:
                return "sin_expiracion", f"EXISTS 1 · TYPE {tipo} · {campos} campos · TTL -1"
            return "vigente", f"EXISTS 1 · TYPE {tipo} · {campos} campos · vence en {ttl} s"
        clave = CFG["REDIS_PREFIJO_SESION"] + CFG["REDIS_SESION_DEMO"]
        (estado, det), ms, err = medir(lambda: estado_clave(clave))
        vencidas = r.info("stats").get("expired_keys", 0)
        if estado == "vigente":
            interp = "sesión de demo presente y con TTL: la API responderá 200"
        elif estado == "ausente":
            interp = (f"ausente. Redis no distingue 'expiró' de 'nunca existió' (ambas dan TTL -2); "
                      f"el servidor expiró {vencidas} claves desde que arrancó y la carga de muestra del Hito 7 "
                      "pone 30 min de TTL, así que lo más probable es que haya vencido. La API responderá 404, "
                      "no 503: Redis está disponible. Recargar: docker exec fixture2030-redis sh /scripts/carga_muestra.sh")
        else:
            interp = "clave sin TTL: una sesión nunca debería quedar sin expiración (revisar la carga)"
        R.agregar(producto="redis", capa="operacion", prueba="EXISTS + TYPE + HLEN + TTL (sin leer valores)",
                  objetivo=clave, resultado="OK" if estado != "sin_expiracion" else "WARN", latencia_ms=ms,
                  detalle=f"{estado}: {det}", interpretacion=interp,
                  no_demuestra="el contenido de la sesión (no se lee: dato personal)", estado_clave=estado)
        (estado, det), ms, _ = medir(lambda: estado_clave(CFG["REDIS_PREFIJO_SESION"] + "diag-no-existe"))
        reg("redis", "operacion", "control: clave inexistente", CFG["REDIS_PREFIJO_SESION"] + "diag-no-existe",
            estado == "ausente", ms, det, "ausencia válida (TTL -2): Redis responde; 'clave ausente' ≠ 'Redis caído'")
        malo = redis.Redis(host=host, port=puerto + 1, socket_connect_timeout=T)
        _, ms, err = medir(malo.ping)
        reg("redis", "operacion", "control: Redis no disponible (puerto sin listener)", f"{host}:{puerto + 1}",
            isinstance(err, redis.ConnectionError), ms, nombre_error(err) if err else "¡respondió!",
            "Redis no disponible = ConnectionError en el cliente (la API: 503), distinto de clave ausente (404)")
    finally:
        r.close()


# =========================================================================== InfluxDB
def influxdb() -> None:
    import httpx

    url, db, tabla = CFG["INFLUX_URL"].rstrip("/"), CFG["INFLUX_DB"], CFG["INFLUX_TABLA"]
    token, origen = influx_token(CFG)
    cli = httpx.Client(base_url=url, timeout=httpx.Timeout(TOP, connect=T))

    def q(sql: str, params: dict[str, Any] | None = None, *, base: str = db, tok: str | None = token) -> httpx.Response:
        h = {"Authorization": f"Bearer {tok}"} if tok else {}
        return cli.post("/api/v3/query_sql", json={"db": base, "q": sql, "format": "json", "params": params or {}}, headers=h)

    def det(resp: httpx.Response | None, err: BaseException | None) -> str:
        if resp is None:
            return nombre_error(err) if err else "-"
        return f"HTTP {resp.status_code} · {resp.text.strip()[:110]}"
    try:
        h, ms, err = medir(lambda: cli.get("/health"))
        if not reg("influxdb", "protocolo", "GET /health (sin token)", f"{url}/health", h is not None and h.status_code == 200,
                   ms, det(h, err), "el servicio HTTP responde",
                   "que el token sirva, que la database exista ni que haya puntos"):
            return saltar("influxdb", "protocolo", det(h, err))
        p, ms, err = medir(lambda: cli.get("/ping"))
        ver = p.json() if (p is not None and p.status_code == 200) else {}
        reg("influxdb", "protocolo", "GET /ping (versión)", f"{url}/ping", bool(ver), ms,
            f"{ver.get('product_name')} {ver.get('version')}" if ver else det(p, err), "versión observada (RNF18)")

        r_, ms, err = medir(lambda: q("SELECT 1 AS ok", tok=None))
        reg("influxdb", "autenticacion", "control: consulta sin token", f"{url} db={db}",
            r_ is not None and r_.status_code == 401, ms, det(r_, err),
            "sin token el servidor rechaza (401): /health accesible ≠ consulta autorizada")
        r_, ms, err = medir(lambda: q("SELECT 1 AS ok", tok="apiv3_token-invalido-de-diagnostico"))
        reg("influxdb", "autenticacion", "control: token inválido", f"{url} db={db}",
            r_ is not None and r_.status_code == 401, ms, det(r_, err),
            "token inválido = 401 (identidad); la API responde 503 con motivo `autenticacion`")
        if not token:
            R.agregar(producto="influxdb", capa="autenticacion", prueba="token configurado", objetivo=origen,
                      resultado="FAIL", detalle="no hay token (INFLUX_TOKEN o INFLUX_TOKEN_FILE)",
                      interpretacion="crear con fixture2030-influxdb/scripts/autorizacion_local.sh")
            return saltar("influxdb", "autenticacion", "sin token")
        r_, ms, err = medir(lambda: q("SELECT 1 AS ok"))
        ok = r_ is not None and r_.status_code == 200
        reg("influxdb", "autenticacion", f"SELECT 1 con el token ({origen})", f"{url} db={db}", ok, ms,
            "HTTP 200 (token aceptado; valor no mostrado)" if ok else det(r_, err), "la identidad de la API es válida")
        if not ok:
            return saltar("influxdb", "autenticacion", det(r_, err))
        reg("influxdb", "autorizacion", "permiso de consulta sobre la database", f"db={db}", True, ms,
            "el token puede consultar (token de administración local del Hito 8)",
            "autorizado; en producción se usaría un token de sólo lectura por database")

        r_, ms, err = medir(lambda: q("SELECT table_name FROM information_schema.tables WHERE table_name = $t", {"t": tabla}))
        filas = r_.json() if (r_ is not None and r_.status_code == 200 and r_.text.strip()) else []
        reg("influxdb", "contexto", "database y tabla (information_schema)", f"db={db} tabla={tabla}", bool(filas), ms,
            f"tabla {tabla} presente" if filas else det(r_, err), "el contexto que usa la API existe")
        r_, ms, err = medir(lambda: q("SELECT 1 AS ok", base=db + "_inexistente"))
        reg("influxdb", "contexto", "control: database inexistente", f"db={db}_inexistente",
            r_ is not None and r_.status_code == 404, ms, det(r_, err),
            "database mal configurada = 404 'database not found': servicio accesible, contexto inválido")

        pid, desde, hasta = CFG["INFLUX_PARTIDO_DEMO"], CFG["INFLUX_DESDE"], CFG["INFLUX_HASTA"]
        sql = (f"SELECT date_bin(INTERVAL '5 minutes', time) AS tramo, count(*) AS puntos FROM {tabla} "
               "WHERE partido_id = $p AND time >= $d AND time < $h GROUP BY tramo ORDER BY tramo LIMIT 12")
        r_, ms, err = medir(lambda: q(sql, {"p": pid, "d": desde, "h": hasta}))
        filas = r_.json() if (r_ is not None and r_.status_code == 200 and r_.text.strip()) else []
        total = sum(f.get("puntos", 0) for f in filas)
        reg("influxdb", "operacion", "consulta temporal acotada (date_bin 5 min, LIMIT 12)",
            f"{tabla} partido_id={pid} [{desde}, {hasta})", total > 0, ms,
            f"{len(filas)} tramos · {total} puntos" if filas else det(r_, err),
            "ventana de 30 min agregada por tramos: misma tabla y filtros que CU12",
            "consultas sobre el torneo completo ni cardinalidad (Hito 8 / Hito 12)")
        r_, ms, err = medir(lambda: q(f"SELECT count(*) AS puntos FROM {tabla} WHERE partido_id = $p AND time >= $d AND time < $h",
                                      {"p": pid, "d": "2031-01-01T00:00:00Z", "h": "2031-01-01T00:30:00Z"}))
        filas = r_.json() if (r_ is not None and r_.status_code == 200 and r_.text.strip()) else []
        reg("influxdb", "operacion", "control: ventana sin puntos", f"{tabla} [2031-01-01T00:00Z, +30 min)",
            r_ is not None and r_.status_code == 200 and (not filas or filas[0].get("puntos", 0) == 0), ms,
            f"HTTP 200 · {filas or '[]'}" if r_ is not None else det(r_, err),
            "ausencia de puntos = 200 vacío (la API: 200 con puntos: []), no 404 ni 503")
    finally:
        cli.close()


# =========================================================================== IRIS
def iris() -> None:
    capas = [("protocolo", "Superserver / portal"), ("autenticacion", "usuario IRIS"),
             ("autorizacion", "roles del namespace"), ("contexto", f"namespace {CFG['IRIS_NAMESPACE']}"),
             ("operacion", f"lectura de {CFG['IRIS_CLASE']}")]
    if CFG.get("IRIS_HABILITADO", "0") != "1":
        for capa, prueba in capas:
            nc("iris", capa, prueba, f"{CFG['IRIS_HOST']}:{CFG['IRIS_PORT']}",
               "no evaluado: IRIS está fuera de la arquitectura vigente (reentrega del Hito 3) y la API no tiene adaptador",
               "NOT_CONFIGURED: no se inventan resultados (Restricción 'Productos')")
        return
    # Camino habilitado (IRIS_HABILITADO=1): portal HTTP + namespace/clase con la terminal del contenedor.
    import httpx
    url = CFG["IRIS_PORTAL_URL"].rstrip("/") + "/csp/sys/UtilHome.csp"
    r, ms, err = medir(lambda: httpx.get(url, timeout=T, follow_redirects=False))
    reg("iris", "protocolo", "Management Portal (HTTP)", url, r is not None and r.status_code < 500, ms,
        f"HTTP {r.status_code}" if r is not None else nombre_error(err),
        "el portal web responde", "que el Superserver ni el namespace estén disponibles")
    nc("iris", "autenticacion", "usuario IRIS", "docker exec iris session",
       "la terminal del contenedor entra como irisowner (sin contraseña): no prueba la credencial de un cliente externo",
       "un cliente SQL/Native API externo exigiría usuario y contraseña")
    nc("iris", "autorizacion", "roles del namespace", CFG["IRIS_NAMESPACE"], "no evaluado (no hay cliente externo)", "")
    script = (f'write ##class(%SYSTEM.Process).NameSpace(),"|",'
              f'##class(%Dictionary.CompiledClass).%ExistsId("{CFG["IRIS_CLASE"]}"),!\nhalt\n')
    t0 = time.perf_counter()
    try:
        p = subprocess.run(["docker", "exec", "-i", CFG["IRIS_CONTAINER"], "iris", "session", "IRIS", "-U",
                            CFG["IRIS_NAMESPACE"]], input=script, capture_output=True, text=True, timeout=TOP + 10)
        salida = [ln for ln in p.stdout.splitlines() if "|" in ln]
        ns, existe = (salida[-1].split("|") + ["", ""])[:2] if salida else ("", "")
    except (OSError, subprocess.SubprocessError) as exc:
        ns, existe, p = "", "", None
        salida = [str(exc)]
    ms = (time.perf_counter() - t0) * 1000
    reg("iris", "contexto", f"namespace {CFG['IRIS_NAMESPACE']}", CFG["IRIS_CONTAINER"],
        ns.strip().upper() == CFG["IRIS_NAMESPACE"].upper(), ms, f"namespace activo: {ns or '-'}",
        "namespace correcto (origen: dentro del contenedor)")
    reg("iris", "operacion", f"%Dictionary.CompiledClass.%ExistsId({CFG['IRIS_CLASE']})", CFG["IRIS_NAMESPACE"],
        existe.strip() == "1", ms, f"existe={existe or '-'}", "lectura de metadato de la clase persistente")


PRODUCTOS: dict[str, Callable[[], None]] = {"mongodb": mongodb, "neo4j": neo4j, "cassandra": cassandra,
                                            "redis": redis_, "influxdb": influxdb, "iris": iris}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--producto", action="append", choices=list(PRODUCTOS))
    for nombre in p.parse_args().producto or list(PRODUCTOS):
        try:
            PRODUCTOS[nombre]()
        except ModuleNotFoundError as exc:
            R.agregar(producto=nombre, capa="protocolo", prueba="driver de la API", objetivo=nombre, resultado="SKIP",
                      detalle=f"falta el módulo {exc.name}: correr con ../fixture2030-hito10-api/.venv/bin/python",
                      interpretacion="SKIP = herramienta no disponible, no 'producto caído'")
        except Exception as exc:  # noqa: BLE001 — una falla inesperada no corta los demás productos
            R.agregar(producto=nombre, capa="protocolo", prueba="ejecución del diagnóstico", objetivo=nombre,
                      resultado="FAIL", detalle=nombre_error(exc),
                      interpretacion="DESCONOCIDO: el diagnóstico no pudo terminar; revisar la traza localmente")
    print(f"Evidencia: {ruta_publica(R.md)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
