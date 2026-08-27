"""*Cuántos bloques faltan al ritmo actual* — una de las dos formas de cumplir I2.

Que el trigger sea computable no alcanza: **nadie tiene que poder elegir el
momento**. Una variable volátil es computable y sorpresiva a la vez. La forma
más fuerte de garantizarlo es una aproximación observable sobre una cantidad
agregada que ningún actor mueve solo, y eso es lo que se calcula acá.

La otra forma —**capacidad demostrada**, el canario de §6.6— no tiene distancia y
no puede tenerla. Este módulo no le inventa una: publica `None`, y publica también
el modo y la capacidad declarada, que es lo que un tercero necesita para auditar
por qué ese trigger es admisible.

Tres decisiones que no son de implementación:

- **aritmética entera, sin flotantes.** La distancia entra al estado y el estado
  se hashea; un flotante haría que dos nodos con la misma información publiquen
  huellas distintas. Se redondea **hacia arriba**: informar de menos es prometer
  un aviso que después no se cumple;
- **el ritmo se mide en una ventana, no desde el principio.** *Al ritmo actual*
  es literal: si la actividad se duplicó ayer, la distancia tiene que reflejarlo
  hoy;
- **ritmo cero no es distancia infinita: es `None`.** Son cosas distintas y
  fundirlas miente. `None` dice *no hay aproximación observable*, que es la
  situación honesta del canario de §6.6 mientras nadie lo gasta, y es la que hay
  que mostrarle al integrador tal cual es.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from protocolo.invariantes import MODO_CAPACIDAD

#: Cuántos bloques mira hacia atrás la medición del ritmo.
VENTANA_RITMO = 8


@dataclass(frozen=True)
class Distancia:
    """Lo que se publica on-chain por cada regla, en cada bloque."""

    regla: str
    progreso: int
    umbral: int
    #: Bloques que faltan al ritmo actual. `0` = puede disparar ya.
    #: `None` = sin aproximación observable (ritmo cero).
    bloques: int | None
    #: El ritmo medido, como fracción exacta: `avance / ventana`.
    avance: int
    ventana: int
    #: La regla tiene una transición commiteada y sin activar, así que **no puede
    #: volver a disparar** hasta la activación. Mientras tanto la distancia no
    #: baja de ahí: decir *"faltan 0"* durante `Δ` bloques sería mentir.
    en_vuelo: bool = False
    piso: int = 0
    #: Cómo cumple esta regla la segunda mitad de I2. Va on-chain porque es lo
    #: que le permite a un tercero auditar por qué el trigger es admisible: una
    #: regla sin aproximación tiene que decir **qué capacidad** hay que ejercer
    #: para producir el hecho, y esa frase es la que se lee en Genesis.
    modo: str = ""
    capacidad: str | None = None

    def canonico(self) -> dict:
        return {
            "regla": self.regla,
            "progreso": self.progreso,
            "umbral": self.umbral,
            "bloques": self.bloques,
            "avance": self.avance,
            "ventana": self.ventana,
            "en_vuelo": self.en_vuelo,
            "piso": self.piso,
            "modo": self.modo,
            "capacidad": self.capacidad,
        }

    @property
    def observable(self) -> bool:
        return self.bloques is not None

    def __str__(self) -> str:
        cola = " (en vuelo)" if self.en_vuelo else ""
        if self.bloques is None:
            return (
                f"{self.regla}: {self.progreso}/{self.umbral}, "
                f"sin aproximación observable{cola}"
            )
        return (
            f"{self.regla}: {self.progreso}/{self.umbral}, "
            f"faltan {self.bloques} bloques{cola}"
        )


def calcular(
    regla: Any,
    estado: Any,
    historial: Sequence[int],
    ventana: int = VENTANA_RITMO,
    piso: int = 0,
) -> Distancia:
    """La distancia de `regla` al disparo, leyendo el progreso ya registrado.

    `historial` son los valores de `progreso` de los bloques anteriores, el más
    reciente al final. No hace falta que esté completo: con menos bloques que la
    ventana se mide sobre lo que hay, que es lo correcto al arrancar la cadena.

    `piso` son los bloques que faltan para que la regla **pueda** volver a
    disparar, cuando tiene una transición en vuelo: no se rearma hasta la
    activación, así que ninguna cuenta de ritmo puede dar menos que eso.
    """
    en_vuelo = piso > 0
    progreso = regla.progreso(estado)
    umbral = regla.umbral(estado)

    def armar(bloques: int | None, avance: int, tramo: int) -> Distancia:
        if bloques is not None:
            bloques = max(bloques, piso)
        return Distancia(
            regla.nombre,
            progreso,
            umbral,
            bloques,
            avance,
            tramo,
            en_vuelo,
            piso,
            getattr(regla, "modo", ""),
            getattr(regla, "capacidad", None),
        )

    if progreso >= umbral:
        return armar(0, 0, ventana)

    # Para un trigger de capacidad, el ritmo no significa nada: su progreso salta
    # de golpe, así que proyectarlo daría una fecha inventada — *"la primitiva se
    # va a romper en ocho bloques"*. No se proyecta y se dice que no se proyecta.
    if getattr(regla, "modo", "") == MODO_CAPACIDAD:
        return armar(None, 0, ventana)

    tramo = min(ventana, len(historial))
    if tramo == 0:
        return armar(None, 0, ventana)

    avance = progreso - historial[-tramo]
    if avance <= 0:
        return armar(None, avance, tramo)

    falta = umbral - progreso
    # Redondeo hacia arriba con enteros: -(-a // b).
    return armar(-(-(falta * tramo) // avance), avance, tramo)
