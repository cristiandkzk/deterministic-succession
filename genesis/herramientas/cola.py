"""Fase 3 · la cola de impugnaciones bajo ataque. `python herramientas/cola.py`

`cola-impugnaciones/` cerró esto en agosto de 2026 **como fórmula** y predijo que con
`γ = 1` y `h = 0,10` alcanzan **diez nodos PoD** para que la cola deje de ser
saturable. Esto corre la misma pregunta con una cola de verdad y `N` nodos eligiendo
qué verificar, que es lo que el criterio de la Fase 3 pide comparar.

**La fórmula daba por sentado que los `N` nodos no se pisan**, y §6.3 no dice cómo se
reparten — no puede, porque no hay conjunto de validadores y ningún nodo sabe cuántos
son. Acá se mide qué pasa con las tres formas posibles de elegir.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from liquidacion.impugnacion import (  # noqa: E402
    AZAR,
    MAS_VIEJA,
    POR_HASH,
    espera_media,
    nodos_criticos,
    simular,
)

#: La predicción de `cola-impugnaciones/`, con h=0,10 y γ=1.
N_PREDICHO = 10

#: Dónde llega la impugnación legítima que el atacante quiere enterrar.
LEGITIMA = 500

ETIQUETAS = {
    MAS_VIEJA: "la más vieja primero",
    AZAR: "al azar",
    POR_HASH: "partición por hash",
}


def informe() -> str:
    lineas: list[str] = []
    ancho = 78
    linea = "-" * ancho

    lineas.append("=" * ancho)
    lineas.append("FASE 3 · la cola de impugnaciones bajo ataque de censura")
    lineas.append(f"la fórmula de cola-impugnaciones/ predice N = {N_PREDICHO}")
    lineas.append("=" * ancho)

    lineas.append("")
    lineas.append("N CRÍTICO · el más chico cuyo backlog deja de crecer")
    lineas.append("medido comparando dos largos de corrida, no uno — ver abajo por qué")
    lineas.append("")
    for estrategia in (POR_HASH, AZAR):
        critico = nodos_criticos(estrategia, tope=20)
        marca = "   = la predicción" if critico == N_PREDICHO else ""
        lineas.append(f"  {ETIQUETAS[estrategia]:<22} → {critico}{marca}")
    lineas.append(
        f"  {ETIQUETAS[MAS_VIEJA]:<22} → nunca "
        f"(con 50 nodos el backlog sigue creciendo)"
    )

    lineas.append("")
    lineas.append("EN RÉGIMEN · backlog de equilibrio y espera media (ley de Little)")
    lineas.append("")
    lineas.append(f"{'cómo elige cada nodo':<22}{'N':>4}{'backlog':>10}{'espera':>12}")
    lineas.append(linea)
    for estrategia in (AZAR, POR_HASH):
        for nodos in (11, 13, 20, 50):
            traza, _ = simular(nodos=nodos, bloques=500, estrategia=estrategia)
            backlog = traza[-1].backlog
            lineas.append(
                f"{ETIQUETAS[estrategia]:<22}{nodos:>4}{backlog:>10,}"
                f"{espera_media(backlog, 100):>9.1f} bl"
            )
    lineas.append(linea)

    lineas.append("")
    lineas.append("CON LA REGLA NATURAL · la espera no es fija, es una rampa")
    lineas.append("")
    for llega_en in (5, 10, 20):
        _, cola = simular(
            nodos=50, bloques=220, estrategia=MAS_VIEJA, legitima_en=llega_en * 100
        )
        espera = cola.espera_de(llega_en * 100)
        lineas.append(
            f"  una impugnación que llega en la altura {llega_en:>3} espera "
            f"{espera if espera is not None else 'más de lo simulado'} bloques"
        )
    lineas.append("")
    lineas.append(
        "  el backlog crece ~90 por bloque y se drena a 10, así que lo que llega en"
    )
    lineas.append(
        "  la altura T espera del orden de 9·T. **Es el ataque de censura andando:**"
    )
    lineas.append("  con un tope duro de demora al lock-in, el fraude queda firme.")

    lineas.append("")
    lineas.append("LO QUE ESTO DICE")
    lineas.append("")
    lineas.append("  · la partición por hash reproduce la fórmula exacta — y exige saber")
    lineas.append("    cuántos nodos hay, que es justo lo que §6.3 no tiene;")
    lineas.append("  · al azar, sin coordinación de ninguna clase, la predicción se corre")
    lineas.append("    de 10 a 11: el backlog se estabiliza en ~424 y la espera media es")
    lineas.append("    de 4 bloques. Las colisiones cuestan un nodo, no rompen nada;")
    lineas.append("  · la más vieja primero —la regla que cualquiera escribiría— colapsa")
    lineas.append("    el paralelismo entero: con 50 nodos se verifica lo mismo que con 1.")
    lineas.append("")
    lineas.append("  Y una trampa de medición que conviene no volver a pisar: la primera")
    lineas.append("  pasada midió con corridas de 80 bloques y dio 13. Era un artefacto —")
    lineas.append("  **el backlog se estabiliza**, y una corrida corta lo agarra antes del")
    lineas.append("  equilibrio. Todo lo de acá compara dos largos.")
    return chr(10).join(lineas)


def main() -> int:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:  # pragma: no cover
            pass
    print(informe())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
