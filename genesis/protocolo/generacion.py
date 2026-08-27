"""Generación, ruleset y etiquetado de objetos (I5).

Una **generación** es una versión del ruleset. No es una cadena nueva: es la
misma cadena con otros parámetros, así que acá no hay nada parecido a un fork ni
a una migración — sólo un `Ruleset` distinto vigente a partir de cierta altura.

El **ruleset** se parte en dos mitades con reglas distintas, y la partición es de
I1, no una comodidad de implementación:

- `internos` — emisión, tamaño de bloque, tiempos. Cambian en cualquier
  transición, mientras el valor nuevo esté dentro del espacio que Genesis fijó.
- `formatos` — lo visible en la interfaz. Sólo por la vía de I5: **se agregan,
  nunca se quitan**.

Y el etiquetado de objetos es lo que hace que I5 sirva de algo: todo objeto lleva
su generación desde el bloque 0, así que un integrador que no llegó a soportar la
generación nueva sigue operando con los objetos viejos y, cuando encuentra uno
nuevo, falla cerrado y ruidoso (`FormatoDesconocido`) en vez de malinterpretarlo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Sequence


class FormatoDesconocido(ValueError):
    """El objeto usa un formato que este ruleset no conoce.

    Es la falla *deseada* de I5: ruidosa y cerrada. La alternativa —adivinar el
    formato— es la que pierde fondos.
    """


@dataclass(frozen=True)
class Params:
    """El punto del espacio de descendientes que una transición selecciona.

    Es lo que se hashea en el linaje como `params_nuevos` (§3), y por eso no
    incluye `h0`: `h0` se calcula *a partir* de esto.
    """

    generacion: int
    internos: Mapping[str, int]
    formatos: frozenset[str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "internos", MappingProxyType(dict(self.internos)))
        object.__setattr__(self, "formatos", frozenset(self.formatos))

    def canonico(self) -> dict:
        return {
            "generacion": self.generacion,
            "internos": dict(self.internos),
            "formatos": set(self.formatos),
        }

    def con(self, **cambios: int) -> "Params":
        """Copia con algunos internos cambiados. No toca formatos ni generación."""
        internos = dict(self.internos)
        internos.update(cambios)
        return Params(self.generacion, internos, self.formatos)


@dataclass(frozen=True)
class Ruleset:
    """Params + el checkpoint generacional que los commitea a su ancestro (I4)."""

    params: Params
    h0: bytes

    @property
    def generacion(self) -> int:
        return self.params.generacion

    @property
    def formatos(self) -> frozenset[str]:
        return self.params.formatos

    def interno(self, nombre: str) -> int:
        return self.params.internos[nombre]

    def canonico(self) -> dict:
        return {"params": self.params.canonico(), "h0": self.h0}


@dataclass(frozen=True)
class Objeto:
    """Cualquier cosa que viva en el estado. Lleva etiqueta de generación (I5)."""

    generacion: int
    formato: str
    carga: bytes = b""

    def canonico(self) -> dict:
        return {
            "generacion": self.generacion,
            "formato": self.formato,
            "carga": self.carga,
        }


def decodificar(objeto: Objeto, ruleset: Ruleset) -> bytes:
    """Devuelve la carga si este ruleset conoce el formato; si no, falla cerrado.

    Nótese qué *no* se chequea: que la generación del objeto sea la vigente. Un
    objeto de la generación 0 sigue siendo válido en la 7 — eso es exactamente lo
    que I5 promete. Lo que decide es el formato.
    """
    if objeto.formato not in ruleset.formatos:
        raise FormatoDesconocido(
            f"formato {objeto.formato!r} (generación {objeto.generacion}) "
            f"desconocido para el ruleset de la generación {ruleset.generacion}"
        )
    return objeto.carga


def es_aditivo(viejo: Params, nuevo: Params) -> bool:
    """I5: la interfaz nueva contiene a la vieja. Agregar sí, quitar no."""
    return nuevo.formatos >= viejo.formatos


def formatos_retirados(viejo: Params, nuevo: Params) -> frozenset[str]:
    """Los que la transición sacaría. Vacío es la única respuesta admisible."""
    return frozenset(viejo.formatos - nuevo.formatos)


def vigente(historial: Sequence[tuple[int, Ruleset]], altura: int) -> Ruleset:
    """El ruleset en vigor a la altura dada.

    `historial` es la secuencia de (altura de activación, ruleset), empezando por
    (0, ruleset de Genesis). No se interpola ni se adivina: se toma el último
    cuya activación ya ocurrió.
    """
    if not historial or historial[0][0] != 0:
        raise ValueError("el historial de rulesets arranca en la altura 0")
    elegido = historial[0][1]
    for altura_activacion, ruleset in historial:
        if altura_activacion <= altura:
            elegido = ruleset
        else:
            break
    return elegido
