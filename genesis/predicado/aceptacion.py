"""El predicado de aceptación de §6.2 — qué puede pagar la red.

**La inferencia no se verifica.** Se verifica que la salida satisfaga un predicado
declarado de antemano, determinista y barato de correr en la capa liviana. Lo que no
se puede expresar así, la red no lo puede liquidar — y ésa es la frontera declarada
de §10.1, no un defecto a arreglar.

Este módulo es la **parte de protocolo** del predicado: qué se declara, qué se
publica y qué se compara. La máquina que lo ejecuta está en `vm/`, en Rust, y no
acá — ver `vm/LEEME.md` para por qué cambia el lenguaje justo en esa pieza.

## Los dos filtros, y por qué son dos

Un predicado pasa si **las dos** cosas:

1. **los vectores dan.** La salida propuesta satisface la condición declarada;
2. **la verificación entra bajo los techos.** No alcanza con dar bien: hay que dar
   bien *dentro del presupuesto*. Es una **condición de seguridad y no de
   rendimiento** — es lo que impide que exista una impugnación más cara de
   verificar que de crear.

Y desde la Fase 4 los techos son **dos**, que es el hallazgo que costó la mitad de
esa fase:

- **pasos**, derivado por generación con la fórmula de `protocolo/genesis.py`;
- **páginas distintas tocadas**, también del ruleset. Fue constante hasta el
  21/8/2026, y mientras lo fue **excluía en vez de encarecer**: una primitiva que
  necesitara más memoria no tenía precio que pagar. Ahora pedir más páginas baja el
  ritmo declarado y con él el techo de pasos, así que la memoria se paga en capacidad.

> **Por qué no alcanza el techo de pasos solo.** `lw` cuesta lo mismo que `addi`
> cuando el dato está en caché y veintitrés veces más cuando no, **y es el mismo
> opcode**. Ninguna lectura del binario los distingue, así que ningún peso por clase
> de instrucción —ningún gas— puede separarlos: lo que los separa es cuánta memoria
> toca el programa, y eso sólo se sabe corriéndolo. Un techo de pasos sin el de
> páginas al lado promete un presupuesto que no cumple por un factor de 23, y la
> cadena se atrasa de forma determinista sin que ninguna invariante lo vea.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum

from protocolo import genesis as g

#: Los veredictos de la máquina, en la codificación canónica de `vm/maquina.rs`.
#: **Están duplicados a propósito y hay una prueba que los verifica contra el Rust.**
#: Que el mismo dato viva en dos lenguajes es exactamente el riesgo que señala I1: se
#: chequea, no se confía.
class Veredicto(Enum):
    RETORNO = 0
    ECALL = 1
    TECHO_EXCEDIDO = 2
    TRAMPA = 3
    PAGINAS_EXCEDIDAS = 4

    def canonico(self, dato: int = 0) -> bytes:
        """Los cinco bytes que entran al hash del bloque.

        Sin texto: el texto es donde se cuelan las diferencias entre
        implementaciones, y el veredicto lo tienen que leer igual las dos partes de
        una impugnación.
        """
        return bytes([self.value]) + dato.to_bytes(4, "little")

    @property
    def acepta(self) -> bool:
        """Sólo un retorno con la salida correcta acepta. Todo lo demás rechaza —y
        **rechazar es un resultado, no un error**: entra al bloque como cualquier
        otro."""
        return self is Veredicto.RETORNO


@dataclass(frozen=True)
class Predicado:
    """Lo que acompaña a todo pedido de trabajo.

    `programa` es el hash del binario RV32IM que verifica; `vectores` son los pares
    (entrada, salida esperada) que fijan qué significa *correcto*. Los dos viajan en
    el pedido y los dos quedan en el estado: **el predicado se declara antes de que
    exista la respuesta**, que es lo que impide discutir después qué se había pedido.
    """

    programa: bytes
    vectores: tuple[tuple[bytes, bytes], ...]

    def __post_init__(self) -> None:
        if len(self.programa) != 32:
            raise ValueError("el programa se nombra por su hash de 32 bytes")
        if not self.vectores:
            # Un predicado sin vectores acepta cualquier cosa que no se cuelgue.
            raise ValueError("un predicado sin vectores no dice nada")

    def huella(self) -> bytes:
        """Identidad canónica. Entra en `H0_B` cuando el predicado es de Genesis."""
        h = hashlib.sha256()
        h.update(self.programa)
        for entrada, salida in self.vectores:
            h.update(len(entrada).to_bytes(4, "little"))
            h.update(entrada)
            h.update(len(salida).to_bytes(4, "little"))
            h.update(salida)
        return h.digest()


@dataclass(frozen=True)
class Presupuesto:
    """Los dos techos vigentes. Se leen del ruleset, no se guardan."""

    pasos: int
    paginas: int

    @classmethod
    def de(cls, ruleset) -> "Presupuesto":
        return cls(g.techo_vigente(ruleset), g.paginas_vigentes(ruleset))

    def margen_de(self, pasos: int, paginas: int) -> tuple[float, float]:
        """Cuánto sobra, en cada dimensión. Genesis eligió capacidad para que la
        primitiva del bloque 0 entre con 2× en pasos."""
        return (self.pasos / pasos, self.paginas / paginas)


@dataclass(frozen=True)
class Corrida:
    """El resultado de correr un predicado. **Es dato de consenso**, así que se
    compara byte a byte y no campo por campo."""

    veredicto: Veredicto
    dato: int
    pasos: int
    paginas: int
    salida: bytes

    def canonico(self) -> bytes:
        return (
            self.veredicto.canonico(self.dato)
            + self.pasos.to_bytes(8, "little")
            + self.paginas.to_bytes(4, "little")
            + hashlib.sha256(self.salida).digest()
        )

    def entra_en(self, presupuesto: Presupuesto) -> bool:
        return self.pasos <= presupuesto.pasos and self.paginas <= presupuesto.paginas


def acepta(predicado: Predicado, corridas: dict[bytes, Corrida], presupuesto: Presupuesto) -> bool:
    """Los dos filtros, en el orden en que se cobran.

    `corridas` mapea cada entrada de los vectores a lo que dio la máquina. Se exige
    que **estén todas**: un predicado que se evalúa sobre los vectores que le
    convienen no es un predicado.
    """
    for entrada, esperada in predicado.vectores:
        corrida = corridas.get(entrada)
        if corrida is None:
            return False
        if not corrida.veredicto.acepta:
            return False
        if not corrida.entra_en(presupuesto):
            return False
        if corrida.salida != esperada:
            return False
    return True
