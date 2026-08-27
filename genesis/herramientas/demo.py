"""`python herramientas/demo.py` — la conmutación corriendo, en una pantalla.

No es una prueba: las pruebas están en `pruebas/`. Esto existe para poder *ver*
el mecanismo, que es distinto de que pase el test — sobre todo porque §3 nunca
había corrido ni una vez antes de esta fase.

Muestra las dos clases de transición juntas, que es donde se entiende por qué `Δ`
no es global: la de circulación avisa con 64 bloques y la criptográfica con 8. Y las
muestra **superpuestas**, que es el caso incómodo: el canario se gasta mientras la
de circulación está en vuelo, así que se commitea enseguida pero activa recién
cuando le toca a la anterior — el residuo declarado de §3.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nodo.pod import NodoPoD  # noqa: E402
from protocolo import genesis as g  # noqa: E402
from sucesion.regla import (  # noqa: E402
    ReglaCanarioCriptografico,
    ReglaEmisionAcumulada,
)

GASTAR_CANARIO = ("gastar_canario",)
#: A propósito **dentro** de la ventana de vuelo de la transición de
#: circulación: es el caso que muestra la cola de activación.
ALTURA_DEL_CANARIO = 130
BLOQUES = 260


def main() -> int:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:  # pragma: no cover
            pass

    nodo = NodoPoD(
        reglas=[
            ReglaEmisionAcumulada(paso=100_000),
            ReglaCanarioCriptografico(),
        ]
    )
    identidad = id(nodo.estado)

    nodo.producir_bloque([("transferir", "reserva", "alice", 500)])
    nodo.producir_bloque([("crear_objeto", "recibo-1", "recibo/gen0")])

    eventos: list[str] = []
    disparos_vistos: set[tuple[str, int]] = set()
    lockins_vistos: set[bytes] = set()

    for _ in range(BLOQUES):
        altura = nodo.altura + 1
        txs = [GASTAR_CANARIO] if altura == ALTURA_DEL_CANARIO else []
        nodo.producir_bloque(txs)

        for regla, disparo in nodo.cronograma.pendientes.items():
            clave = (regla, disparo.altura)
            if clave not in disparos_vistos:
                disparos_vistos.add(clave)
                eventos.append(
                    f"  {disparo.altura:>4}  disparo (advisorio)  {regla}"
                )
        for punto in nodo.cronograma.checkpoints:
            if punto.h0 not in lockins_vistos:
                lockins_vistos.add(punto.h0)
                aviso = punto.altura_activacion - punto.altura_lockin
                delta = g.delta(punto.clase)
                cola = "" if aviso == delta else f", esperó {aviso - delta} a la anterior"
                eventos.append(
                    f"  {punto.altura_lockin:>4}  LOCK-IN gen {punto.generacion}"
                    f"  {punto.regla}"
                    f"  ->  activa en {punto.altura_activacion}"
                    f"  (aviso {aviso}; Δ de {punto.clase} = {delta}{cola})"
                )
        for conmutacion in nodo.conmutaciones:
            clave = (f"conmuta/{conmutacion.generacion}", conmutacion.altura)
            if clave not in disparos_vistos:
                disparos_vistos.add(clave)
                eventos.append(
                    f"  {conmutacion.altura:>4}  CONMUTA a la generación "
                    f"{conmutacion.generacion}"
                )

    print(f"Genesis · {BLOQUES + 2} bloques, ventana de finalidad "
          f"{g.VENTANA_FINALIDAD}\n")
    print("\n".join(eventos))
    print()
    print(nodo.resumen())
    print()
    print(
        "el mismo proceso, el mismo estado: "
        f"arranques={nodo.arranques}, estado={'el mismo' if id(nodo.estado) == identidad else 'OTRO'}, "
        f"alice={nodo.estado.saldos['alice']}, "
        f"recibo-1 nació en la generación {nodo.estado.objetos['recibo-1'].generacion}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
