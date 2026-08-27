"""§6.5 · Toda transferencia es bilateral, y el pedido de trabajo es una oferta abierta.

Dos formas y una sola mecánica:

- **dirigida** — Alice nombra a Bob. Nadie más puede aceptarla. Es una transferencia
  común, y el que no hay es el envío unilateral: **no se le puede pagar a alguien que
  está offline**, porque hasta que el receptor no firma no hay transacción;
- **abierta** — el pedido de trabajo de §6.2 **no nombra a nadie**. Lo toma el nodo
  que pueda cumplirlo. Es *pull*, no *push*: **nadie asigna pedidos**, y de eso
  depende que el certificado fundacional no filtre ventaja off-chain.

**Lo que vuelve exclusiva a una oferta abierta no es un candado ni un turno: es el
lock.** Los fondos salen del disponible al publicarla, así que una oferta ya tomada
no tiene con qué pagarle a un segundo. La contienda se resuelve por aritmética, no
por orden de llegada — y por eso no hace falta un orden global (§6.3).

El `timeout` lo declara el cliente **junto con el precio y el predicado**: sin él, un
nodo que acepta y no entrega deja los fondos comprometidos para siempre.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from estado.cuentas import Libro
from protocolo.serializacion import huella


class OfertaInvalida(ValueError):
    """La oferta no se puede publicar, aceptar o liquidar como se pidió."""


ESTADOS = ("abierta", "tomada", "liquidada", "vencida")


@dataclass
class Oferta:
    """`receptor is None` es una oferta abierta; con nombre, es dirigida."""

    identidad: str
    oferente: str
    monto: int
    #: `None` = abierta (pull). Con nombre = dirigida.
    receptor: str | None
    #: Altura a partir de la cual la oferta vence y el lock se libera.
    vence_en: int
    #: Lo que el que la toma tiene que satisfacer (§6.2). En la Fase 3 es opcional
    #: y determinista; la máquina que lo corre es la Fase 4.
    predicado: Callable[[bytes], bool] | None = None
    estado: str = "abierta"
    tomada_por: str | None = None

    @property
    def es_abierta(self) -> bool:
        return self.receptor is None

    def canonico(self) -> dict:
        return {
            "identidad": self.identidad,
            "oferente": self.oferente,
            "monto": self.monto,
            "receptor": self.receptor,
            "vence_en": self.vence_en,
            "estado": self.estado,
            "tomada_por": self.tomada_por,
        }


@dataclass
class Mercado:
    """Las ofertas vivas y el libro sobre el que se liquidan."""

    libro: Libro
    ofertas: dict[str, Oferta] = field(default_factory=dict)

    def publicar(
        self,
        identidad: str,
        oferente: str,
        monto: int,
        vence_en: int,
        receptor: str | None = None,
        predicado: Callable[[bytes], bool] | None = None,
    ) -> Oferta:
        """Publica y **compromete los fondos en el mismo acto**.

        Que el lock ocurra al publicar y no al aceptar es lo que hace que una oferta
        abierta no pueda pagarle a dos: cuando el segundo llega, no hay disponible.
        """
        if identidad in self.ofertas:
            raise OfertaInvalida(f"la oferta {identidad!r} ya existe")
        self.libro.comprometer(oferente, monto)
        oferta = Oferta(
            identidad=identidad,
            oferente=oferente,
            monto=monto,
            receptor=receptor,
            vence_en=vence_en,
            predicado=predicado,
        )
        self.ofertas[identidad] = oferta
        return oferta

    def aceptar(self, identidad: str, quien: str, altura: int) -> Oferta:
        """El receptor firma. **Sin esto no hay transacción**, ni siquiera parcial."""
        oferta = self._viva(identidad, altura)
        if oferta.estado != "abierta":
            raise OfertaInvalida(f"{identidad}: ya está {oferta.estado}")
        if not oferta.es_abierta and oferta.receptor != quien:
            raise OfertaInvalida(
                f"{identidad}: es dirigida a {oferta.receptor!r} y la quiso tomar {quien!r}"
            )
        oferta.estado = "tomada"
        oferta.tomada_por = quien
        return oferta

    def liquidar(self, identidad: str, altura: int, entrega: bytes = b"") -> Oferta:
        """Ejecuta el lock: sale del saldo del oferente y entra al que la tomó."""
        oferta = self._viva(identidad, altura)
        if oferta.estado != "tomada":
            raise OfertaInvalida(f"{identidad}: está {oferta.estado}, no tomada")
        if oferta.predicado is not None and not oferta.predicado(entrega):
            raise OfertaInvalida(f"{identidad}: la entrega no satisface el predicado")
        self.libro.liquidar(oferta.oferente, oferta.tomada_por, oferta.monto)
        oferta.estado = "liquidada"
        return oferta

    def vencer(self, altura: int) -> list[Oferta]:
        """Libera el lock de todo lo que expiró sin liquidarse."""
        vencidas = []
        for oferta in self.ofertas.values():
            if oferta.estado in ("abierta", "tomada") and altura >= oferta.vence_en:
                self.libro.liberar(oferta.oferente, oferta.monto)
                oferta.estado = "vencida"
                vencidas.append(oferta)
        return vencidas

    def abiertas(self) -> list[Oferta]:
        return [o for o in self.ofertas.values() if o.estado == "abierta"]

    def canonico(self) -> dict:
        return {
            "libro": self.libro.canonico(),
            "ofertas": {k: o.canonico() for k, o in sorted(self.ofertas.items())},
        }

    def huella(self) -> bytes:
        return huella(self.canonico(), dominio="liquidacion/mercado")

    def _viva(self, identidad: str, altura: int) -> Oferta:
        oferta = self.ofertas.get(identidad)
        if oferta is None:
            raise OfertaInvalida(f"no existe la oferta {identidad!r}")
        if altura >= oferta.vence_en and oferta.estado in ("abierta", "tomada"):
            raise OfertaInvalida(f"{identidad}: venció en {oferta.vence_en}")
        return oferta
