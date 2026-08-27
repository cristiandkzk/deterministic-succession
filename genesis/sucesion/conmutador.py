"""La conmutación: el mismo proceso, el mismo estado, otras reglas (§3).

Este archivo es corto y eso es el punto. **Si conmutar necesitara mover datos, no
sería conmutar.** Todo lo que hace es reemplazar el ruleset vigente por el que ya
está commiteado en el checkpoint, y después demostrar —no suponer— que el estado
quedó igual.

Lo que se verifica en el acto, y por qué cada cosa:

- **el checkpoint commitea al ruleset que está saliendo** (I4). Si el ancestro no
  es el `h0` vigente, esta cadena no es la que produjo ese checkpoint;
- **el sucesor es un punto del espacio de Genesis** (I1). Un parámetro fuera de
  dominio no es una transición: es un fork;
- **la interfaz sólo creció** (I5);
- **el estado no se movió** (I3), por huella *y* por identidad de objeto.

Nótese lo que **no** hace: no serializa, no migra, no reconstruye índices, no
avisa. El aviso ya se dio `Δ` bloques antes, en el lock-in, y está on-chain.
"""

from __future__ import annotations

from typing import Any

from protocolo.generacion import Ruleset
from protocolo.invariantes import ViolacionInvariante, revisar_transicion
from protocolo.linaje import Checkpoint
from protocolo.serializacion import corto


def conmutar(estado: Any, ruleset_actual: Ruleset, checkpoint: Checkpoint) -> Ruleset:
    """Devuelve el ruleset nuevo. **No toca el estado.**

    Levanta `ViolacionInvariante` si algo de I1, I3, I4 o I5 no se cumple. No hay
    modo degradado: un nodo que no puede conmutar tiene que parar, porque seguir
    con las reglas viejas es desviarse de Genesis (§5).
    """
    if checkpoint.h0_ancestro != ruleset_actual.h0:
        raise ViolacionInvariante(
            "I4",
            f"el checkpoint commitea a {corto(checkpoint.h0_ancestro)}... y el "
            f"ruleset vigente es {corto(ruleset_actual.h0)}...",
        )
    if checkpoint.generacion != ruleset_actual.generacion + 1:
        raise ViolacionInvariante(
            "I4",
            f"salto de generación: de la {ruleset_actual.generacion} a la "
            f"{checkpoint.generacion}",
        )

    huella_antes = estado.huella()
    identidad_antes = id(estado)

    nuevo = Ruleset(params=checkpoint.params, h0=checkpoint.h0)

    revisar_transicion(
        viejo=ruleset_actual,
        nuevo=nuevo,
        huella_antes=huella_antes,
        huella_despues=estado.huella(),
        identidad_antes=identidad_antes,
        identidad_despues=id(estado),
    )
    return nuevo
