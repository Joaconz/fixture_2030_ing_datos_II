"""Hito 12 · caché de la configuración de partición (Q0) de comentarios."""
import asyncio
from datetime import datetime, timezone

from app.services import comentarios as mod
from app.services.comentarios import ComentariosService
from app.services.ports import ConfigParticion


class CassandraContador:
    def __init__(self) -> None:
        self.lecturas_config = 0

    async def get_config(self, partido_id: str):
        self.lecturas_config += 1
        if partido_id == "PAR-X-9":
            return None
        return ConfigParticion(partido_id=partido_id, buckets=4, ventana_minutos=10,
                               inicio=datetime(2030, 6, 29, 16, 0, tzinfo=timezone.utc))


def _config_n_veces(svc, partido, n):
    async def correr():
        for _ in range(n):
            try:
                await svc._config(partido)
            except Exception:
                pass
    asyncio.run(correr())


def test_sin_cache_lee_q0_en_cada_request():
    mod._CACHE_CONFIG.clear()
    db = CassandraContador()
    _config_n_veces(ComentariosService(db, config_cache_s=0), "PAR-D16-01", 5)
    assert db.lecturas_config == 5


def test_con_cache_lee_q0_una_vez():
    mod._CACHE_CONFIG.clear()
    db = CassandraContador()
    for _ in range(5):                      # el servicio se crea en cada request
        _config_n_veces(ComentariosService(db, config_cache_s=60), "PAR-D16-01", 1)
    assert db.lecturas_config == 1


def test_un_partido_inexistente_no_se_cachea():
    mod._CACHE_CONFIG.clear()
    db = CassandraContador()
    _config_n_veces(ComentariosService(db, config_cache_s=60), "PAR-X-9", 3)
    assert db.lecturas_config == 3 and "PAR-X-9" not in mod._CACHE_CONFIG
