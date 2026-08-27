"""El estado mínimo de la Fase 1. **Desechable por declaración.**

No es el estado del protocolo: es lo mínimo que hace falta para que la sucesión
tenga algo real que atravesar. La Fase 3 lo reemplaza por `cuentas.py`,
`entradas.py` y `arbol.py`, y nada de lo que haya acá debería sobrevivir a eso.

Aun siendo de juguete, hay tres cosas que no son de juguete y por eso están:

- **la huella canónica.** Es lo que hace verificable I3: *bit a bit idéntico* no
  es una figura, es una comparación de 32 bytes;
- **las distancias al disparo viven adentro del estado**, no en un log del nodo.
  I2 exige que la aproximación sea consultable on-chain, y un valor que sólo
  existe en la memoria del nodo no lo es;
- **los eventos de lock-in también son estado.** El checkpoint se emite on-chain
  `Δ` bloques antes de la activación, y que esté en el estado es lo que le
  permite a una regla saber que ya transicionó sin preguntarle a nadie.

Las operaciones son tres y alcanzan para ejercitar el mecanismo: transferir,
crear un objeto etiquetado por generación (I5) y gastar un canario (§6.6).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from protocolo.generacion import Objeto, Ruleset
from protocolo.serializacion import huella

RESERVA = "reserva"


class OperacionInvalida(ValueError):
    """La transacción no se puede aplicar. El bloque que la trae es inválido."""


@dataclass
class EstadoSintetico:
    """El estado que cruza la transición. **Nunca se reemplaza, sólo se muta.**

    Que sea mutable es deliberado: I3 se verifica también por identidad de
    objeto, y un estado que se reconstruye en cada bloque no puede distinguirse
    de una migración.
    """

    altura: int = 0
    emitido: int = 0
    quemado: int = 0
    canarios_gastados: int = 0
    saldos: dict[str, int] = field(default_factory=lambda: {RESERVA: 0})
    objetos: dict[str, Objeto] = field(default_factory=dict)
    #: Publicadas por el nodo en cada bloque (I2). Clave: nombre de la regla.
    distancias: dict[str, Any] = field(default_factory=dict)
    #: Los checkpoints emitidos en su lock-in, en forma canónica, **y desde el
    #: 22/8/2026 también las evaluaciones de predicados de §6.2**: un veredicto es
    #: un hecho publicado, de la misma clase que un lock-in, y por eso va acá y no
    #: en un campo aparte.
    eventos: list[dict] = field(default_factory=list)

    #: **Configuración del nodo, no estado de consenso.** No entra en `canonico()`
    #: ni en la instantánea, igual que las reglas: dos nodos con la misma máquina y
    #: los mismos pedidos computan el mismo veredicto, y si uno computara otro la
    #: raíz no cerraría y su bloque se rechazaría. Ahí está la propiedad.
    maquina: Any = None
    pedidos: dict[bytes, Any] = field(default_factory=dict, repr=False)

    # -- huella ------------------------------------------------------------ #

    def canonico(self) -> dict:
        return {
            "altura": self.altura,
            "emitido": self.emitido,
            "quemado": self.quemado,
            "canarios_gastados": self.canarios_gastados,
            "saldos": dict(self.saldos),
            "objetos": {clave: obj.canonico() for clave, obj in self.objetos.items()},
            "distancias": {
                nombre: dist.canonico() for nombre, dist in self.distancias.items()
            },
            "eventos": list(self.eventos),
        }

    def huella(self) -> bytes:
        return huella(self.canonico(), dominio="estado/sintetico")

    # -- transiciones de estado -------------------------------------------- #

    def emitir(self, ruleset: Ruleset) -> None:
        """La emisión del bloque, que va a la reserva.

        **No va al nodo que hizo el trabajo**, y eso no es un detalle de la
        implementación de juguete: §7.1 separa emisión de fees justamente para
        que fabricar trabajo no produzca unidades.
        """
        monto = ruleset.interno("emision_por_bloque")
        self.emitido += monto
        self.saldos[RESERVA] = self.saldos.get(RESERVA, 0) + monto

    def aplicar(self, transaccion: tuple, ruleset: Ruleset) -> None:
        operacion, *argumentos = transaccion
        if operacion == "transferir":
            self._transferir(*argumentos, ruleset=ruleset)
        elif operacion == "crear_objeto":
            self._crear_objeto(*argumentos, ruleset=ruleset)
        elif operacion == "gastar_canario":
            self.canarios_gastados += 1
        elif operacion == "evaluar":
            self._evaluar(*argumentos, ruleset=ruleset)
        else:
            raise OperacionInvalida(f"operación desconocida: {operacion!r}")

    def _transferir(self, origen: str, destino: str, monto: int, *, ruleset: Ruleset) -> None:
        if monto < 0:
            raise OperacionInvalida("monto negativo")
        if self.saldos.get(origen, 0) < monto:
            raise OperacionInvalida(f"saldo insuficiente en {origen!r}")
        quema = monto * ruleset.interno("fee_quema_ppm") // 1_000_000
        self.saldos[origen] -= monto
        self.saldos[destino] = self.saldos.get(destino, 0) + (monto - quema)
        self.quemado += quema

    def _evaluar(self, identificador: bytes, *, ruleset: Ruleset) -> None:
        """Corre el predicado de un pedido y publica el veredicto.

        **El veredicto lo computa el nodo, no lo trae la transacción.** Si viniera en la
        transacción, el que la manda elegiría el resultado; computándolo, dos nodos que
        corran la misma máquina llegan al mismo hecho — y el que llegue a otro produce una
        raíz distinta y su bloque se rechaza (`red/sync.py`).
        """
        from nodo.predicado import evaluar as correr_predicado

        pedido = self.pedidos.get(identificador)
        if pedido is None:
            raise OperacionInvalida(f"pedido desconocido: {identificador!r}")
        if self.maquina is None:
            raise OperacionInvalida("el nodo no tiene máquina para correr predicados")
        self.eventos.append(correr_predicado(self.maquina, pedido, ruleset).canonico())

    def _crear_objeto(self, clave: str, formato: str, *, ruleset: Ruleset) -> None:
        if formato not in ruleset.formatos:
            raise OperacionInvalida(
                f"la generación {ruleset.generacion} no conoce el formato {formato!r}"
            )
        if clave in self.objetos:
            raise OperacionInvalida(f"la clave {clave!r} ya existe")
        # La etiqueta de generación se pone acá y no se toca nunca más (I5).
        self.objetos[clave] = Objeto(generacion=ruleset.generacion, formato=formato)

    # -- reorganización ---------------------------------------------------- #

    def instantanea(self) -> dict:
        """Copia profunda de los campos, para deshacer una reorganización."""
        return copy.deepcopy(
            {
                "altura": self.altura,
                "emitido": self.emitido,
                "quemado": self.quemado,
                "canarios_gastados": self.canarios_gastados,
                "saldos": self.saldos,
                "objetos": self.objetos,
                "distancias": self.distancias,
                "eventos": self.eventos,
            }
        )

    def restaurar(self, instantanea: dict) -> None:
        """Vuelve a un estado anterior **sin dejar de ser el mismo objeto**.

        Una reorganización deshace bloques; no reinicia el nodo ni reemplaza el
        estado. Si esto devolviera un `EstadoSintetico` nuevo, I3 no tendría
        forma de distinguir una reorganización de una migración.
        """
        copia = copy.deepcopy(instantanea)
        self.altura = copia["altura"]
        self.emitido = copia["emitido"]
        self.quemado = copia["quemado"]
        self.canarios_gastados = copia["canarios_gastados"]
        self.saldos = copia["saldos"]
        self.objetos = copia["objetos"]
        self.distancias = copia["distancias"]
        self.eventos = copia["eventos"]

    # -- lecturas ---------------------------------------------------------- #

    def lockins_de(self, nombre_de_regla: str) -> int:
        """Cuántas veces esta regla ya produjo un lock-in, según el estado.

        Cuenta lock-ins, no eventos: un **rechazo** también lleva el nombre de la
        regla y no mueve nada, porque nada pasó.
        """
        return sum(
            1
            for e in self.eventos
            if e.get("tipo") == "lock-in" and e.get("regla") == nombre_de_regla
        )

    def congelar(self) -> "EstadoSintetico":
        """Una copia independiente, para guardar el estado que disparó.

        **No es el estado**: es un registro histórico. El estado vivo es uno solo
        y nunca se reemplaza (I3) — esto existe porque `params_nuevos` se computa
        en el lock-in y tiene que salir del estado del bloque `N`, no del de `F`
        bloques después.
        """
        copia = EstadoSintetico()
        copia.restaurar(self.instantanea())
        return copia
