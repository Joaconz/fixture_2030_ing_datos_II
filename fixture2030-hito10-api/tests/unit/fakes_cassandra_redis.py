"""Fakes en memoria de CassandraPort y RedisPort (app/services/ports.py).

FakeCassandra respeta lo que importa del Hito 6: la partición es
(partido_id, ventana, bucket), dentro de ella el orden es (creado_en DESC,
comentario_id ASC), `ventana`/`bucket` se calculan con las mismas fórmulas,
`creado_en` tiene precisión de milisegundos y el INSERT es upsert.

Ambos fakes devuelven `self` en `__deepcopy__`: `make_client` pasa el fake como
valor por defecto de la dependencia (`lambda f=fake: f`) y FastAPI copia
(deepcopy) ese default en cada request; sin esto, lo que escribe una request no
lo vería la siguiente ni el test.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from app.schemas.comentarios import Comentario
from app.services.comentarios import bucket_de, clave_orden, clave_posicion, piso_ventana, truncar_ms
from app.services.ports import ConfigParticion, PosicionLectura, SesionCruda

UTC = timezone.utc
INICIO = datetime(2030, 6, 9, 13, 0, tzinfo=UTC)


class _SinCopia:
    def __deepcopy__(self, memo: dict) -> "_SinCopia":
        return self


class FakeCassandra(_SinCopia):
    nombre = "cassandra"

    def __init__(self) -> None:
        self.configs: dict[str, ConfigParticion] = {}
        self.particiones: dict[tuple[str, datetime, int], dict[tuple[datetime, str], Comentario]] = {}
        self.por_usuario: dict[tuple[str, str], dict[tuple[datetime, str], Comentario]] = {}
        self.lecturas_particion = 0
        self.inserciones = 0

    # --- ciclo
    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def ping(self) -> None: ...

    # --- carga de prueba
    def agregar_partido(self, partido_id: str, buckets: int = 1, inicio: datetime = INICIO,
                        ventana_minutos: int = 10) -> ConfigParticion:
        cfg = ConfigParticion(partido_id, buckets, ventana_minutos, inicio)
        self.configs[partido_id] = cfg
        return cfg

    def sembrar(self, partido_id: str, n: int, *, semilla: int = 7, estados: list[str] | None = None,
                mismo_instante_cada: int = 0) -> list[Comentario]:
        """n comentarios repartidos en el tramo del partido (varias ventanas).
        `mismo_instante_cada` > 0 fuerza empates de creado_en (desempate por id)."""
        cfg = self.configs[partido_id]
        rng = random.Random(semilla)
        creados = []
        anterior: datetime | None = None
        for i in range(n):
            if mismo_instante_cada and anterior is not None and i % mismo_instante_cada:
                creado = anterior
            else:
                creado = truncar_ms(cfg.inicio + timedelta(milliseconds=rng.randint(-15 * 60_000, 125 * 60_000 - 1)))
            anterior = creado
            estado = estados[i % len(estados)] if estados else "PUBLICADO"
            c = Comentario(comentarioId=f"{partido_id}-C{i:07d}", partidoId=partido_id,
                           usuarioId=f"USR-{i % 50:07d}", alias=f"hincha_{i}", contenido=f"comentario {i}",
                           idioma="es", creadoEn=creado, estadoModeracion=estado)
            self._guardar(c, piso_ventana(creado, cfg.ventana_minutos), bucket_de(c.comentarioId, cfg.buckets))
            creados.append(c)
        return creados

    def _guardar(self, c: Comentario, ventana: datetime, bucket: int) -> None:
        self.particiones.setdefault((c.partidoId, ventana, bucket), {})[(c.creadoEn, c.comentarioId)] = c
        mes = c.creadoEn.strftime("%Y-%m")
        self.por_usuario.setdefault((c.usuarioId, mes), {})[(c.creadoEn, c.comentarioId)] = c

    def total_filas(self) -> int:
        return sum(len(p) for p in self.particiones.values())

    # --- puerto
    async def get_config(self, partido_id: str) -> ConfigParticion | None:
        return self.configs.get(partido_id)

    async def leer_particion(self, partido_id: str, ventana: datetime, bucket: int,
                             despues_de: PosicionLectura | None, limite: int) -> list[Comentario]:
        self.lecturas_particion += 1
        filas = sorted(self.particiones.get((partido_id, ventana, bucket), {}).values(), key=clave_orden)
        if despues_de is not None:
            p = clave_posicion(despues_de)
            filas = [c for c in filas if clave_orden(c) > p]
        return filas[:limite]

    async def get_comentario(self, partido_id: str, ventana: datetime, bucket: int,
                             creado_en: datetime, comentario_id: str) -> Comentario | None:
        return self.particiones.get((partido_id, ventana, bucket), {}).get((creado_en, comentario_id))

    async def insertar_comentario(self, c: Comentario, ventana: datetime, bucket: int) -> None:
        self.inserciones += 1
        self._guardar(c, ventana, bucket)


class FakeRedis(_SinCopia):
    nombre = "redis"

    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = {}
        self.ttls: dict[str, int] = {}
        self.sets: dict[str, set[str]] = {}
        self.strings: dict[str, str] = {}

    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def ping(self) -> None: ...

    def crear_sesion(self, sesion_id: str, usuario_id: str = "USR-DEMO1", estado: str = "ACTIVA",
                     ttl: int = 1800, **extra: str) -> None:
        campos = {"session_id": sesion_id, "usuario_id": usuario_id, "rol": "HINCHA", "region": "AM",
                  "dispositivo": "web", "estado": estado, "creada_en": "1908979200",
                  "ultima_actividad": "1908979260", "expira_absoluta": "1909022400", "solicitudes": "7"}
        campos.update(extra)
        self.hashes[f"f30:ses:{sesion_id}"] = campos
        self.ttls[f"f30:ses:{sesion_id}"] = ttl
        self.sets.setdefault(f"f30:usr:{usuario_id}:sesiones", set()).add(sesion_id)

    async def get_sesion(self, sesion_id: str) -> SesionCruda | None:
        clave = f"f30:ses:{sesion_id}"
        if clave not in self.hashes:
            return None
        return SesionCruda(campos=dict(self.hashes[clave]), ttl_s=self.ttls.get(clave, -1))

    async def cerrar_sesion(self, sesion_id: str) -> bool:
        clave = f"f30:ses:{sesion_id}"
        campos = self.hashes.pop(clave, None)
        if campos is None:
            return False
        self.ttls.pop(clave, None)
        if campos.get("usuario_id"):
            self.sets.get(f"f30:usr:{campos['usuario_id']}:sesiones", set()).discard(sesion_id)
        return True

    async def cache_get_partido(self, partido_id: str) -> str | None:
        return self.strings.get(f"f30:cache:partido:{partido_id}")

    async def cache_set_partido(self, partido_id: str, valor_json: str, ttl_s: int) -> None:
        self.strings[f"f30:cache:partido:{partido_id}"] = valor_json

    async def cache_del_partido(self, partido_id: str) -> None:
        self.strings.pop(f"f30:cache:partido:{partido_id}", None)
