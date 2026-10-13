"""Pruebas de integración: la API real (uvicorn en :8000) contra las cinco fuentes en Docker.

Prerrequisitos (ver tests/README.md): contenedores arriba con sus cargas de
muestra, `scripts/sembrar_demo_neo4j.cypher` ejecutado y la API iniciada con
`scripts/iniciar_api.sh`. Si la API no responde, todo el módulo se saltea.

El contraste con clientes nativos (RF17) se hace con `docker exec` sobre los
mismos contenedores: la API no debe inventar datos.
"""
from __future__ import annotations

import os
import subprocess
import uuid

import httpx
import pytest

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "fixture2030")


@pytest.fixture(scope="session")
def api() -> httpx.Client:
    cliente = httpx.Client(base_url=BASE_URL, timeout=10)
    try:
        cliente.get("/health").raise_for_status()
    except httpx.HTTPError:
        pytest.skip(f"La API no responde en {BASE_URL}: iniciarla con scripts/iniciar_api.sh")
    return cliente


@pytest.fixture
def idem_key() -> str:
    return "it-" + uuid.uuid4().hex[:20]


def nativo(*cmd: str) -> str:
    """Ejecuta un cliente nativo dentro de su contenedor y devuelve stdout."""
    r = subprocess.run(["docker", "exec", *cmd], capture_output=True, text=True, timeout=60, check=True)
    return r.stdout


def cypher(consulta: str) -> list[str]:
    salida = nativo("fixture2030-neo4j", "cypher-shell", "-u", "neo4j", "-p", NEO4J_PASSWORD,
                    "--format", "plain", consulta)
    return [l for l in salida.strip().splitlines()[1:] if l]


def cql(consulta: str) -> str:
    return nativo("fixture2030-cassandra", "cqlsh", "-e", consulta)


def redis_cli(*args: str) -> str:
    return nativo("fixture2030-redis", "redis-cli", *args).strip()


def mongo_eval(js: str) -> str:
    return nativo("fixture2030_mongo", "mongosh", "--quiet", "fixture2030", "--eval", js).strip()


def assert_error(r: httpx.Response, status: int, code: str | None = None) -> dict:
    assert r.status_code == status, r.text
    body = r.json()
    assert set(body) <= {"code", "message", "requestId", "details"}
    assert body["requestId"] == r.headers["X-Request-Id"]
    if code:
        assert body["code"] == code, body
    return body
