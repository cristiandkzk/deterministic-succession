"""El acumulador de desalojados — §8.5, y la condición que lo hace posible.

**Desalojar no es destruir.** El objeto sale del conjunto activo y el tenedor lo revive con una
prueba, pagando el costo de entonces. Ésa es la pieza que impide que el desalojo sea
confiscación, y por eso no hay quema final del activo.

**Pero el compromiso contra el que se prueba no puede ser uno por objeto**, o el atacante habría
comprado permanencia igual, sólo que más barata: una lápida de 32 bytes por desalojado son 1 GB
por nodo para siempre, un cuarto del presupuesto de §10.1. Todo el mecanismo de §8.5 se cae si
esta pieza es O(n).

Por eso el acumulador es **uno solo, de sólo-append, y del tipo donde insertar necesita apenas
los picos del árbol**: unos cientos de bytes en total, no por objeto. Es un *Merkle Mountain
Range* — una lista de árboles binarios perfectos de tamaños decrecientes, que se fusionan de a
pares cuando dos quedan del mismo alto. Insertar `n` objetos deja `popcount(n)` picos, o sea a lo
sumo `log2(n)` hashes de 32 bytes: **con mil millones de desalojos, treinta picos.**

## La doble reactivación no necesita lista de nulificadores

Que sería el residuo O(n) volviendo a entrar por la otra puerta. Revivir dos veces se frena
chequeando contra el **conjunto activo**, que está acotado por construcción: si el objeto ya está
vivo, la prueba es válida y la reactivación se rechaza igual.

Es la misma forma que usa el resto del diseño: no llevar una lista de lo que pasó, sino hacer que
el estado presente alcance para decidir.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


def _h(etiqueta: bytes, *partes: bytes) -> bytes:
    """Hash con dominio separado. Sin dominio, un nodo interno del árbol se puede
    presentar como una hoja y la prueba deja de significar lo que dice."""
    d = hashlib.sha256()
    d.update(etiqueta)
    for p in partes:
        d.update(p)
    return d.digest()


def hoja(datos: bytes) -> bytes:
    return _h(b"genesis/desalojo/hoja", datos)


def nodo(izq: bytes, der: bytes) -> bytes:
    return _h(b"genesis/desalojo/nodo", izq, der)


@dataclass(frozen=True)
class Prueba:
    """Lo que el tenedor guarda para revivir. **Menos de un kilobyte** (§10.2).

    `posicion` es el índice de inserción; `camino` son los hermanos desde la hoja hasta
    el pico de su árbol; `picos` es la lista de picos al momento de probar.
    """

    posicion: int
    datos: bytes
    camino: tuple[bytes, ...]
    picos: tuple[bytes, ...]

    def bytes_aproximados(self) -> int:
        return 8 + len(self.datos) + 32 * (len(self.camino) + len(self.picos))


@dataclass
class Acumulador:
    """Sólo-append. **Lo único que vive en el estado son los picos.**"""

    #: Los picos, del árbol más alto al más bajo. Es todo el estado que ocupa.
    picos: list[bytes] = field(default_factory=list)
    #: Cuántos objetos se desalojaron en total. Ocho bytes, no crece.
    tamano: int = 0
    #: Las hojas, **fuera del estado de consenso**: las guarda quien quiera archivar.
    #: Viven acá para que las pruebas se puedan construir en las pruebas de esta fase;
    #: un nodo real no las tiene, y ésa es exactamente la dependencia de §10.2.
    _hojas: list[bytes] = field(default_factory=list, repr=False)

    # ------------------------------------------------------------------ #
    # Lo que ocupa en el estado — el número que decide A2
    # ------------------------------------------------------------------ #

    def bytes_en_estado(self) -> int:
        """Cuánto pesa el acumulador para un nodo. **No depende de `tamano`.**"""
        return 32 * len(self.picos) + 8

    def raiz(self) -> bytes:
        """Un compromiso único, plegando los picos de derecha a izquierda."""
        if not self.picos:
            return b"\x00" * 32
        r = self.picos[-1]
        for p in reversed(self.picos[:-1]):
            r = nodo(p, r)
        return r

    # ------------------------------------------------------------------ #
    # Insertar
    # ------------------------------------------------------------------ #

    def desalojar(self, datos: bytes) -> int:
        """Agrega un objeto y devuelve su posición. **No construye la prueba.**

        Ésa es la forma correcta y además la barata: un nodo desaloja y no prueba nada.
        La primera versión devolvía la prueba armada, que cuesta recorrer el subárbol
        entero —O(n) por inserción— y volvió tan lento el arnés de mutaciones que dejó de
        poder correrse. **Construir la prueba es trabajo de quien archiva** (§10.2), y que
        el protocolo no lo haga es justamente lo que hace el desalojo barato.
        """
        posicion = self.tamano
        self._hojas.append(datos)
        self.tamano += 1

        # Fusionar mientras los dos últimos picos tengan el mismo alto. La altura sale
        # del tamaño: el pico k-ésimo cubre una potencia de dos, y dos potencias iguales
        # se juntan. Se lleva la cuenta con los bits del tamaño.
        self.picos.append(hoja(datos))
        n = self.tamano
        while n % 2 == 0:
            der = self.picos.pop()
            izq = self.picos.pop()
            self.picos.append(nodo(izq, der))
            n //= 2

        return posicion

    # ------------------------------------------------------------------ #
    # Probar
    # ------------------------------------------------------------------ #

    def _alturas(self) -> list[int]:
        """Altura de cada pico, del más alto al más bajo. Son los bits de `tamano`."""
        return [b for b in range(self.tamano.bit_length() - 1, -1, -1) if self.tamano >> b & 1]

    def prueba_de(self, posicion: int) -> Prueba:
        """Reconstruye la prueba de una hoja. Necesita las hojas — o sea, archivo."""
        if not 0 <= posicion < self.tamano:
            raise IndexError("esa posición no fue desalojada")

        inicio = 0
        for altura in self._alturas():
            ancho = 1 << altura
            if posicion < inicio + ancho:
                camino: list[bytes] = []
                nivel = [hoja(d) for d in self._hojas[inicio : inicio + ancho]]
                idx = posicion - inicio
                while len(nivel) > 1:
                    par = idx ^ 1
                    camino.append(nivel[par])
                    nivel = [nodo(nivel[k], nivel[k + 1]) for k in range(0, len(nivel), 2)]
                    idx //= 2
                return Prueba(
                    posicion, self._hojas[posicion], tuple(camino), tuple(self.picos)
                )
            inicio += ancho
        raise AssertionError("los picos no cubren el tamaño")

    def verifica(self, prueba: Prueba) -> bool:
        """Verifica contra **los picos vigentes**, no contra los que había al emitirla.

        Ahí está la dependencia de §10.2 hecha código: si el acumulador creció, los picos
        de la prueba ya no son los de la cadena y hay que reconstruirla. La prueba pesa
        menos de un kilobyte y guardarla es gratis; **mantenerla al día es lo que cuesta.**
        """
        if tuple(prueba.picos) != tuple(self.picos):
            return False

        inicio = 0
        for k, altura in enumerate(self._alturas()):
            ancho = 1 << altura
            if prueba.posicion < inicio + ancho:
                if len(prueba.camino) != altura:
                    return False
                acumulado = hoja(prueba.datos)
                idx = prueba.posicion - inicio
                for hermano in prueba.camino:
                    acumulado = (
                        nodo(acumulado, hermano) if idx % 2 == 0 else nodo(hermano, acumulado)
                    )
                    idx //= 2
                return acumulado == self.picos[k]
            inicio += ancho
        return False
