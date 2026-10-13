"""Exporta el contrato OpenAPI que genera la propia API a openapi/openapi.yaml.

    .venv/bin/python scripts/exportar_openapi.py          # escribe el archivo
    .venv/bin/python scripts/exportar_openapi.py --check  # falla si el versionado quedó desactualizado

El contrato sale del código (rutas + schemas Pydantic): por construcción
describe lo que el servidor implementa (RNF2). tests/unit/test_openapi_drift.py
corre el --check en cada `pytest`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
DESTINO = RAIZ / "openapi" / "openapi.yaml"


def generar() -> str:
    from app.main import create_app
    return yaml.safe_dump(create_app().openapi(), sort_keys=False, allow_unicode=True, width=110)


def main() -> int:
    texto = generar()
    if "--check" in sys.argv:
        actual = DESTINO.read_text(encoding="utf-8") if DESTINO.exists() else ""
        if actual != texto:
            print("openapi/openapi.yaml está desactualizado: correr scripts/exportar_openapi.py", file=sys.stderr)
            return 1
        print("openapi/openapi.yaml coincide con la API")
        return 0
    DESTINO.write_text(texto, encoding="utf-8")
    print(f"escrito {DESTINO.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
