"""El predicado de §6.2 corriendo adentro de un nodo.

**Hasta acá la máquina y la cadena nunca se habían tocado.** `predicado/aceptacion.py` modelaba
el predicado, la máquina de §6.6 vivía en Rust con sus dos techos medidos, y ningún nodo corrió
jamás uno: los techos se midieron sueltos y el veredicto se hizo canónico *para entrar al hash
del bloque* sin entrar a ninguno.

Este módulo es la cañería que faltaba: **evaluar un pedido, cobrarle los dos techos, y dejar el
veredicto en el estado** — que es lo que lo vuelve un hecho de consenso y no una opinión del
nodo que lo corrió.

## Quién ejecuta

La máquina no se reimplementa acá. El nodo la **invoca**, y quién la implementa es la decisión de
I1: hoy es el crate de `predicado/vm/`, en Rust, y mañana puede ser otra implementación mientras
dé los mismos veredictos sobre los mismos vectores (C3).

Para que las pruebas no dependan de tener `cargo` instalado, la ejecución entra por una interfaz
—`Maquina`— con dos implementaciones: la que llama al binario y **un doble que devuelve
veredictos canónicos**. El doble no simplifica la semántica: devuelve los mismos cinco bytes, y
por eso sirve para probar la cañería sin probar la máquina, que ya está probada aparte.

## Lo que se descubrió al conectarlos

Ver `RESULTADOS-PREDICADO.md`, P4: **un pedido publicado bajo una generación y aceptado bajo otra
se juzga con un techo distinto**, y nadie lo tocó. Es la misma forma que B3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from predicado.aceptacion import Corrida, Predicado, Presupuesto, Veredicto
from protocolo import genesis as g


class Maquina(Protocol):
    """Lo que el nodo necesita de la máquina, y nada más."""

    def correr(self, programa: bytes, entrada: bytes, presupuesto: Presupuesto) -> Corrida:
        ...


@dataclass
class MaquinaDoble:
    """Un doble para las pruebas. **Devuelve veredictos canónicos, no simplificados.**

    Se le dice de antemano qué gasta cada entrada; lo que se prueba con esto es la cañería
    —que el nodo cobre los techos y guarde el veredicto—, no la máquina, que está probada
    en `predicado/vm/tests/criterios.rs` y en siete vectores sobre dos arquitecturas.
    """

    #: entrada → (pasos, páginas, salida)
    guion: dict[bytes, tuple[int, int, bytes]] = field(default_factory=dict)

    def correr(self, programa: bytes, entrada: bytes, presupuesto: Presupuesto) -> Corrida:
        pasos, paginas, salida = self.guion.get(entrada, (1_000, 4, b""))

        # **Los dos techos se cobran acá, y cortan.** Es lo mismo que hace la máquina de
        # verdad: al agotarse el presupuesto para en el paso exacto y devuelve un veredicto.
        if paginas > presupuesto.paginas:
            return Corrida(Veredicto.PAGINAS_EXCEDIDAS, 0, min(pasos, presupuesto.pasos),
                           presupuesto.paginas, b"")
        if pasos > presupuesto.pasos:
            return Corrida(Veredicto.TECHO_EXCEDIDO, 0, presupuesto.pasos, paginas, b"")
        return Corrida(Veredicto.RETORNO, 0, pasos, paginas, salida)


@dataclass(frozen=True)
class Pedido:
    """Un pedido de trabajo de §6.2, tal como se publica.

    **Lleva la generación en la que se publicó**, y eso no es decoración: el techo de §6.6
    se deriva del ruleset, así que un pedido evaluado en otra generación se juzga con otro
    presupuesto. Sin este campo, el resultado dependería de cuándo se lo mire y nada lo
    declararía — que es la forma que B3 encontró en el depósito de permanencia.
    """

    identificador: bytes
    predicado: Predicado
    generacion: int

    def presupuesto(self, ruleset) -> Presupuesto:
        """El presupuesto con el que se lo juzga. **El de su generación, no el de ahora.**

        Es la salida que se eligió para P4: un pedido se juzga con las reglas bajo las que
        se publicó. Lo contrario —juzgarlo con el techo vigente— haría que aceptar el mismo
        trabajo diera distinto según cuándo llegue la respuesta, sin que nadie haya tocado
        el pedido.
        """
        if ruleset.generacion != self.generacion:
            raise GeneracionEquivocada(
                f"el pedido es de la generación {self.generacion} y el ruleset es "
                f"{ruleset.generacion}: hay que buscar el ruleset de entonces"
            )
        return Presupuesto.de(ruleset)


class GeneracionEquivocada(ValueError):
    """Se quiso juzgar un pedido con el ruleset de otra generación."""


@dataclass(frozen=True)
class Evaluacion:
    """Lo que queda en el estado. **Es un hecho, no una opinión del nodo que lo corrió.**"""

    pedido: bytes
    generacion: int
    acepta: bool
    corridas: tuple[bytes, ...]

    def canonico(self) -> dict:
        return {
            "tipo": "evaluacion",
            "pedido": self.pedido,
            "generacion": self.generacion,
            "acepta": self.acepta,
            "corridas": [list(c) for c in self.corridas],
        }


def evaluar(maquina: Maquina, pedido: Pedido, ruleset) -> Evaluacion:
    """Corre el predicado sobre todos sus vectores y devuelve el hecho que va al estado.

    **Los vectores se corren todos**, no los que convengan: un predicado que se evalúa sobre
    un subconjunto elegido no es un predicado (§6.2).
    """
    presupuesto = pedido.presupuesto(ruleset)
    corridas: list[bytes] = []
    acepta = True

    for entrada, esperada in pedido.predicado.vectores:
        corrida = maquina.correr(pedido.predicado.programa, entrada, presupuesto)
        corridas.append(corrida.canonico())
        if not corrida.veredicto.acepta or not corrida.entra_en(presupuesto):
            acepta = False
        elif corrida.salida != esperada:
            acepta = False

    return Evaluacion(pedido.identificador, pedido.generacion, acepta, tuple(corridas))


def predicados_por_bloque(ruleset) -> dict[str, float]:
    """**P5: de qué presupuesto sale correr predicados, y cuántos entran.**

    `f*` es la fracción del nodo **para verificar firmas** y §6.2 pide que el predicado sea
    *barato de correr en la capa liviana* sin decir con cargo a qué. Lo que queda fuera de
    `f*` es todo lo demás junto: el predicado, la red, la liquidación de §6.5 y —desde la
    Fase 6— el ciclo de desalojo, que se lleva un 3%.

    Esta cuenta no elige una fracción nueva: informa **cuántos predicados del tamaño del
    techo entran en lo que sobra**, para que se vea contra qué compiten.
    """
    ritmo = g.ritmo_declarado(ruleset.interno("paginas_vm"))
    del_bloque = ritmo * ruleset.interno("tiempo_bloque_ms") / 1_000
    de_firmas = del_bloque * g.F_VERIFICACION_PPM / 1_000_000
    sobra = del_bloque - de_firmas
    techo = g.techo_vigente(ruleset)
    return {
        "pasos_del_bloque": del_bloque,
        "para_firmas": de_firmas,
        "fuera_de_f_estrella": sobra,
        "predicados_al_techo": sobra / techo,
    }
