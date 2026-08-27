"""Validación y sincronización — el primer nodo que no produce.

**Hasta acá el proyecto nunca validó nada.** `NodoPoD` sólo produce: cada transición de estado
ocurrió por construcción. Una cadena donde nada puede ser inválido no es una cadena, es un
programa que lleva una lista, y toda la propiedad que §5 le atribuye a la conmutación —*el que no
conmuta es el que se desvía, y eso se verifica con un hash*— presupone que alguien verifica.

## Qué es validar, y qué no

Validar **no** es volver a producir y confiar. Es re-derivar el bloque desde sus transacciones y
**comparar** contra lo que el bloque declara, con la capacidad de decir que no. La diferencia
entera está en la comparación: un validador que no puede rechazar no está validando.

Y hay una cosa que el validador **no puede leer del bloque**, que es la que sostiene §3:

> **Cuándo conmutar.** El productor no lo anuncia y el validador no lo obedece: lo deriva del
> estado que él mismo calculó, con las mismas reglas. Si el productor activó el ruleset nuevo una
> altura antes, el estado que el validador computa es otro, la raíz no coincide y el bloque se
> rechaza. **Es lo que hace que la sucesión no descanse en la buena fe del que produce** — que es
> exactamente para lo que existe todo el diseño.

## Por qué re-ejecutar es la forma correcta

Sin pruebas de conocimiento cero, verificar un bloque es rehacer su cómputo y comparar el
resultado: es lo que hace cualquier cadena que no tenga una prueba sucinta. Lo que importa es que
**el resultado no se toma del bloque sino que se recalcula**, y que el bloque se rechaza entero si
difieren. El costo de eso es el presupuesto de §6.1, que es de donde sale el techo de §6.6.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from nodo.pod import Bloque, NodoPoD


class BloqueInvalido(ValueError):
    """El bloque no sobrevivió la validación. **Es un rechazo, no un error.**

    Un nodo que recibe uno de éstos no se cae: descarta el bloque y sigue con la cadena que
    tenía. Que el rechazo sea un resultado y no una excepción de programa es la misma
    decisión que tomó la máquina de §6.6 con sus veredictos.
    """

    def __init__(self, altura: int, motivo: str) -> None:
        super().__init__(f"bloque {altura}: {motivo}")
        self.altura = altura
        self.motivo = motivo


@dataclass
class Veredicto:
    """Qué dio la validación de una cadena entera."""

    aceptados: int
    rechazado: BloqueInvalido | None = None

    @property
    def entera(self) -> bool:
        return self.rechazado is None


def _respaldo(nodo: NodoPoD) -> dict:
    """Una foto de lo único que `producir_bloque` toca, para poder deshacerla.

    **No se usa `deepcopy` del nodo**, y no por eficiencia: las reglas guardan referencias
    que no se pueden copiar, así que copiar el nodo entero directamente no anda. Se copian
    a mano los contenedores que la producción muta, que además deja a la vista **cuáles
    son** — que es información útil por sí sola.

    El estado se guarda con su propia instantánea, que preserva la identidad del objeto:
    el conmutador verifica I3 también por identidad, así que reemplazarlo por otro igual
    rompería lo que estamos tratando de proteger.
    """
    return {
        "estado": nodo.estado.instantanea(),
        "ruleset": nodo.ruleset,
        "cadena": list(nodo.cadena),
        "conmutaciones": list(nodo.conmutaciones),
        "historial_rulesets": list(nodo.historial_rulesets),
        "historial_progreso": {k: list(v) for k, v in nodo.historial_progreso.items()},
        "instantaneas": dict(nodo.instantaneas),
        "pendientes": dict(nodo.cronograma.pendientes),
        "checkpoints": list(nodo.cronograma.checkpoints),
        "rechazos": list(nodo.cronograma.rechazos),
    }


def _restaurar(nodo: NodoPoD, foto: dict) -> None:
    nodo.estado.restaurar(foto["estado"])
    nodo.ruleset = foto["ruleset"]
    nodo.cadena[:] = foto["cadena"]
    nodo.conmutaciones[:] = foto["conmutaciones"]
    nodo.historial_rulesets[:] = foto["historial_rulesets"]
    for k, v in foto["historial_progreso"].items():
        nodo.historial_progreso[k][:] = v
    nodo.instantaneas.clear()
    nodo.instantaneas.update(foto["instantaneas"])
    nodo.cronograma.pendientes.clear()
    nodo.cronograma.pendientes.update(foto["pendientes"])
    nodo.cronograma.checkpoints[:] = foto["checkpoints"]
    nodo.cronograma.rechazos[:] = foto["rechazos"]


def validar_bloque(nodo: NodoPoD, bloque: Bloque) -> None:
    """Valida `bloque` contra `nodo` y lo aplica. Levanta `BloqueInvalido` si no cierra.

    **El nodo queda intacto si el bloque se rechaza.** Se guarda una copia antes de
    re-ejecutar y se restaura si la comparación falla: un bloque inválido no puede dejar al
    validador en un estado a medio aplicar, porque entonces bastaría con mandar basura para
    envenenarlo.
    """
    # 1 · lo que se puede chequear sin ejecutar nada.
    if bloque.altura != nodo.altura + 1:
        raise BloqueInvalido(bloque.altura, f"altura fuera de orden, se esperaba {nodo.altura + 1}")
    if bloque.padre != nodo.cadena[-1].hash():
        raise BloqueInvalido(bloque.altura, "no encadena con la cabeza")

    # 2 · re-ejecutar. El validador corre **las mismas reglas** que el productor, y de ahí
    #     saca por su cuenta si en esta altura hay que conmutar. No lo lee del bloque.
    respaldo = _respaldo(nodo)
    try:
        propio = nodo.producir_bloque(bloque.transacciones)
    except Exception as e:  # noqa: BLE001 — cualquier fallo de reglas es rechazo, no caída
        _restaurar(nodo, respaldo)
        raise BloqueInvalido(bloque.altura, f"las reglas lo rechazan: {e}") from e

    # 3 · comparar. **Acá está la validación**: la raíz no se toma del bloque, se recalcula.
    if propio.raiz_estado != bloque.raiz_estado:
        _restaurar(nodo, respaldo)
        raise BloqueInvalido(bloque.altura, "la raíz de estado no coincide con la re-ejecución")
    if propio.hash() != bloque.hash():
        _restaurar(nodo, respaldo)
        raise BloqueInvalido(bloque.altura, "el bloque canónico no coincide")


def sincronizar(nodo: NodoPoD, cadena: Sequence[Bloque]) -> Veredicto:
    """Un nodo vacío recibe una cadena que no produjo y la valida bloque a bloque.

    **Incluye cruzar las conmutaciones sin que nadie se las anuncie.** El que sincroniza
    activa el ruleset nuevo en la misma altura porque deriva el disparo del mismo estado,
    y si no coincidiera la raíz no cerraría.

    El bloque 0 no se valida: lo construye el constructor desde `H0` de Genesis, y que dos
    nodos arranquen del mismo bloque 0 es lo que I4 encadena hacia adelante.
    """
    aceptados = 0
    for bloque in cadena:
        if bloque.altura == 0:
            if bloque.hash() != nodo.cadena[0].hash():
                return Veredicto(aceptados, BloqueInvalido(0, "otro bloque 0: otra cadena"))
            continue
        try:
            validar_bloque(nodo, bloque)
        except BloqueInvalido as e:
            return Veredicto(aceptados, e)
        aceptados += 1
    return Veredicto(aceptados)


def mismo_estado(a: NodoPoD, b: NodoPoD) -> bool:
    """Los dos nodos llegaron al mismo lugar, por huella y por generación."""
    return (
        a.estado.huella() == b.estado.huella()
        and a.generacion == b.generacion
        and a.cadena[-1].hash() == b.cadena[-1].hash()
    )
