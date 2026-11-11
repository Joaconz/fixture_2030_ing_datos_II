"""Fixture 2030 — Replicación y CAP · resumen del escritor continuo del failover.

USO: python3 scripts/analizar_escritor.py T_FALLA_ISO < ESCRITOR.jsonl
Lee las líneas JSON de scripts/mongo_escritor.js y resume qué vio el cliente
alrededor de la falla: escrituras confirmadas antes y después, la que quedó
esperando durante la elección y a qué primario fue cada tramo.
Todas las horas son del reloj de la VM de Docker (contenedores y `docker
inspect` comparten ese reloj).
"""
import json
import sys
from datetime import datetime


def t(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def main():
    falla = t(sys.argv[1])
    intentos = [json.loads(l) for l in sys.stdin if l.startswith("{")]
    if not intentos:
        print("   el escritor no registró intentos")
        return
    ok = [i for i in intentos if i["ok"]]
    err = [i for i in intentos if not i["ok"]]
    print(f"   intentos: {len(intentos)} · confirmados (w:majority): {len(ok)} · con error: {len(err)}")
    for e in err:
        print(f"   error seq={e['seq']} {e['error']} a los {(t(e['fin']) - falla).total_seconds():.2f} s de la falla")
    # Primario viejo = el de la última confirmación antes de la falla. El cambio
    # se ve en la primera confirmación hecha por OTRO primario (con `docker stop`
    # el viejo todavía confirma alrededor de un segundo, hasta renunciar).
    antes = [i for i in ok if t(i["fin"]) <= falla]
    if not antes:
        print("   no hubo confirmaciones antes de la falla")
        return
    viejo = antes[-1]["primario"]
    idx_nuevo = next((k for k, i in enumerate(ok) if t(i["fin"]) > falla and i["primario"] != viejo), None)
    if idx_nuevo is None:
        print(f"   ninguna escritura llegó a un primario distinto de {viejo}")
    else:
        p, u = ok[idx_nuevo], ok[idx_nuevo - 1]
        print(f"   última confirmada por el primario viejo ({viejo}): seq={u['seq']} fin={u['fin']} "
              f"({(t(u['fin']) - falla).total_seconds():+.2f} s respecto de la falla)")
        print(f"   primera confirmada por el primario nuevo ({p['primario']}): seq={p['seq']} ini={p['ini']} "
              f"fin={p['fin']} ({p['ms']} ms de latencia)")
        print(f"   => hueco sin confirmaciones: {(t(p['fin']) - t(u['fin'])).total_seconds():.2f} s · "
              f"primera escritura en el primario nuevo a los {(t(p['fin']) - falla).total_seconds():.2f} s de la falla"
              + ("" if err else " (sin errores en el cliente: la operación esperó al nuevo primario y se reintentó)"))
        print(f"   después del cambio se confirmaron {len(ok) - idx_nuevo} escrituras en {p['primario']}")
    lat = sorted(i["ms"] for i in ok)
    print(f"   latencia de escritura: mediana {lat[len(lat) // 2]} ms · máxima {lat[-1]} ms")
    # Registro crudo alrededor de la falla: 2 intentos antes y 2 después de la
    # primera escritura confirmada en el primario nuevo.
    desde = max(0, len([i for i in intentos if t(i["ini"]) <= falla]) - 2)
    hasta = intentos.index(ok[idx_nuevo]) + 3 if idx_nuevo is not None else len(intentos)
    print("   registro del escritor alrededor de la falla:")
    for i in intentos[desde:hasta]:
        print("     " + json.dumps(i, ensure_ascii=False))


if __name__ == "__main__":
    main()
