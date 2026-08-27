"""§6.3 · Orden sin consenso global: cada cuenta lleva su propia secuencia.

**No hay orden global y eso no es una carencia: es el diseño.** Dos interacciones
que no comparten colateral **no tienen orden relativo**, que es distinto de tenerlo
indefinido — aplicarlas en cualquier orden deja exactamente el mismo estado. Lo que
sí tiene orden es cada cuenta consigo misma, por su índice.

De ahí salen las dos propiedades que la Fase 3 tiene que falsar:

- **el doble gasto lo imposibilita el lock, no el orden.** Comprometer fondos los
  saca del disponible; comprometerlos dos veces es aritméticamente imposible, sin
  que nadie tenga que decidir cuál transacción "va primero";
- **el índice es el que hace suicida la doble firma** (§6.4): el nonce se deriva de
  él, así que reusarlo publica la clave privada. Ver `liquidacion/doble_firma.py`.

> **`saldo` no es lo mismo que `disponible`.** `disponible = saldo − comprometido`.
> Un saldo comprometido sigue siendo del dueño; lo que no puede es comprometerse
> otra vez. Confundirlos es exactamente el bug que permite el doble gasto.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from protocolo.serializacion import huella


class SaldoInsuficiente(ValueError):
    """No hay disponible para comprometer. **No** es un error de orden."""


class IndiceUsado(ValueError):
    """Se intentó firmar dos veces con el mismo índice desde el protocolo.

    El protocolo no lo prohíbe *afuera* —§6.4 dice que la equivocación no se
    prohíbe, se vuelve suicida— pero un nodo honesto no se pisa a sí mismo.
    """


@dataclass
class Cuenta:
    saldo: int = 0
    comprometido: int = 0
    #: La secuencia propia de esta cuenta. No hay contador global.
    indice: int = 0

    @property
    def disponible(self) -> int:
        return self.saldo - self.comprometido

    def canonico(self) -> dict:
        return {
            "saldo": self.saldo,
            "comprometido": self.comprometido,
            "indice": self.indice,
        }


@dataclass
class Libro:
    """El conjunto de cuentas. Todo el estado de liquidación de la Fase 3."""

    cuentas: dict[str, Cuenta] = field(default_factory=dict)

    # -- lecturas ---------------------------------------------------------- #

    def cuenta(self, nombre: str) -> Cuenta:
        return self.cuentas.setdefault(nombre, Cuenta())

    def disponible(self, nombre: str) -> int:
        return self.cuenta(nombre).disponible

    def canonico(self) -> dict:
        return {nombre: c.canonico() for nombre, c in sorted(self.cuentas.items())}

    def huella(self) -> bytes:
        return huella(self.canonico(), dominio="estado/cuentas")

    # -- escrituras -------------------------------------------------------- #

    def acreditar(self, nombre: str, monto: int) -> None:
        self.cuenta(nombre).saldo += monto

    def comprometer(self, nombre: str, monto: int) -> None:
        """Saca `monto` del disponible. **Es lo que elimina la contienda.**"""
        cuenta = self.cuenta(nombre)
        if monto <= 0:
            raise SaldoInsuficiente("un compromiso es positivo")
        if cuenta.disponible < monto:
            raise SaldoInsuficiente(
                f"{nombre}: disponible {cuenta.disponible}, se pidió {monto} "
                f"(saldo {cuenta.saldo}, ya comprometido {cuenta.comprometido})"
            )
        cuenta.comprometido += monto

    def liberar(self, nombre: str, monto: int) -> None:
        """Devuelve al disponible sin mover el saldo: la oferta venció o se canceló."""
        cuenta = self.cuenta(nombre)
        if cuenta.comprometido < monto:
            raise SaldoInsuficiente(f"{nombre}: no hay {monto} comprometido")
        cuenta.comprometido -= monto

    def liquidar(self, origen: str, destino: str, monto: int) -> None:
        """Ejecuta lo comprometido: sale del saldo del origen y entra al destino."""
        cuenta = self.cuenta(origen)
        if cuenta.comprometido < monto:
            raise SaldoInsuficiente(f"{origen}: no hay {monto} comprometido")
        cuenta.comprometido -= monto
        cuenta.saldo -= monto
        self.acreditar(destino, monto)

    def avanzar_indice(self, nombre: str) -> int:
        """Consume el índice de esta cuenta y devuelve el que se usó."""
        cuenta = self.cuenta(nombre)
        usado = cuenta.indice
        cuenta.indice += 1
        return usado

    # -- invariante -------------------------------------------------------- #

    def motivo_inconsistente(self) -> str | None:
        """`None` si el libro cierra. Se corre después de cada operación."""
        for nombre, cuenta in self.cuentas.items():
            if cuenta.saldo < 0:
                return f"{nombre}: saldo negativo ({cuenta.saldo})"
            if cuenta.comprometido < 0:
                return f"{nombre}: comprometido negativo ({cuenta.comprometido})"
            if cuenta.comprometido > cuenta.saldo:
                return (
                    f"{nombre}: comprometido {cuenta.comprometido} > saldo {cuenta.saldo}"
                    " — el lock dejó de proteger algo"
                )
        return None
