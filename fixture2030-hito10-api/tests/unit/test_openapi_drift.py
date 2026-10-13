"""RNF2: el contrato versionado es exactamente el que genera la API."""
from scripts.exportar_openapi import DESTINO, generar


def test_openapi_versionado_coincide_con_la_api():
    assert DESTINO.read_text(encoding="utf-8") == generar(), (
        "openapi/openapi.yaml desactualizado: correr .venv/bin/python scripts/exportar_openapi.py")


def test_contrato_no_documenta_422():
    import yaml
    contrato = yaml.safe_load(DESTINO.read_text(encoding="utf-8"))
    for ruta, ops in contrato["paths"].items():
        for metodo, op in ops.items():
            assert "422" not in op["responses"], f"{metodo.upper()} {ruta} documenta 422"
