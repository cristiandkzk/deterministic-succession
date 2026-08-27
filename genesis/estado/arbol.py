"""El árbol del conjunto activo, con corte `d` — §10.1.

**Guardar todos los nodos internos es una opción, no una obligación.** Un árbol de Merkle sobre
`2^H` hojas tiene `2^H − 1` nodos internos, o sea 32 bytes por entrada de puro árbol. Con el
presupuesto de disco de §10.1 eso es un cuarto del total gastado en estructura.

La alternativa es **guardar los niveles por encima de un corte `d` y recomputar el subárbol de
`2^d` hojas** cada vez que hace falta. El disco baja por un factor de `2^(d−1)`; lo que sube es
el hash.

> **Y el tope que muerde es actualizar, no probar.** Probar pasa cuando alguien revive un objeto
> desalojado; actualizar pasa **en cada transacción**. Por eso la decisión de `d` se toma mirando
> el costo de actualizar, y por eso este módulo cuenta los hashes de las dos operaciones por
> separado en vez de dar un número solo.

## La cuenta, y el número que la Fase 5 usó sin tenerlo

Actualizar una hoja cuesta:

- **recomputar el subárbol** que la contiene: `2^d − 1` nodos internos, porque no está guardado;
- **subir hasta la raíz** por los niveles que sí están: `H − d` nodos.

O sea `2^d − 1 + H − d`. Con `d = 1` eso da exactamente `H`, que es la altura — y **ése es el
número que la Fase 5 usó para derivar el piso de §8.5**, sin que este archivo existiera. `d = 1`
es la fila de *guardar todo*, la que cuesta 32 B por entrada y que el diseño descartó.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


def _h(etiqueta: bytes, *partes: bytes) -> bytes:
    d = hashlib.sha256()
    d.update(etiqueta)
    for p in partes:
        d.update(p)
    return d.digest()


def hoja(datos: bytes) -> bytes:
    return _h(b"genesis/arbol/hoja", datos)


def nodo(izq: bytes, der: bytes) -> bytes:
    return _h(b"genesis/arbol/nodo", izq, der)


VACIO = bytes(32)


@dataclass(frozen=True)
class PruebaHoja:
    indice: int
    datos: bytes
    camino: tuple[bytes, ...]

    def bytes_aproximados(self) -> int:
        return 8 + len(self.datos) + 32 * len(self.camino)


@dataclass
class Arbol:
    """Merkle sobre `2^altura` hojas, con los niveles por debajo de `corte` sin guardar.

    `corte = 1` guarda todo —es el caso degenerado, no el barato—; `corte = altura` no guarda
    ningún nodo interno y recomputa el árbol entero en cada actualización.
    """

    altura: int
    corte: int = 6
    #: Las hojas. En un nodo real esto es la base de datos de entradas, no una lista.
    hojas: dict[int, bytes] = field(default_factory=dict)
    #: Los nodos guardados, indexados por (nivel desde las hojas, índice en el nivel).
    #: **Sólo los niveles `>= corte`.** Ahí está todo el ahorro de disco.
    guardados: dict[tuple[int, int], bytes] = field(default_factory=dict)

    #: Contadores, para que las dos operaciones se midan por separado y no de a una.
    hashes_actualizando: int = 0
    hashes_probando: int = 0

    def __post_init__(self) -> None:
        if not 1 <= self.corte <= self.altura:
            raise ValueError("el corte va entre 1 y la altura")

    # ------------------------------------------------------------------ #
    # Lo que ocupa — la mitad de la decisión de `d`
    # ------------------------------------------------------------------ #

    def nodos_guardados_teoricos(self) -> int:
        """Cuántos nodos internos guarda un árbol lleno con este corte.

        Los niveles guardados son `corte..altura`, y el nivel `k` tiene `2^(altura−k)`
        nodos. La suma es `2^(altura−corte+1) − 1`.
        """
        return (1 << (self.altura - self.corte + 1)) - 1

    def bytes_por_entrada(self) -> float:
        """**El número que decide contra el disco.** Sale `64 / 2^corte`.

        Con `corte = 1` da 32 B por entrada, que es guardar todo; con 6, un byte.
        """
        return 32 * self.nodos_guardados_teoricos() / (1 << self.altura)

    # ------------------------------------------------------------------ #
    # Lo que cuesta — la otra mitad
    # ------------------------------------------------------------------ #

    def hashes_por_actualizacion(self) -> int:
        """`2^corte − 1` para rehacer el subárbol, más `altura − corte` para subir."""
        return (1 << self.corte) - 1 + (self.altura - self.corte)

    def hashes_por_prueba(self) -> int:
        """Lo mismo que actualizar: hay que rehacer el subárbol para sacar los hermanos.

        **Que las dos den igual no quiere decir que cuesten igual**, y ahí está la frase que
        justifica el diseño: probar ocurre cuando alguien revive un desalojado, y actualizar
        ocurre en cada transacción. El mismo costo unitario, multiplicado por frecuencias que
        se llevan órdenes de magnitud.
        """
        return self.hashes_por_actualizacion()

    # ------------------------------------------------------------------ #
    # El árbol de verdad
    # ------------------------------------------------------------------ #

    def _hoja(self, indice: int) -> bytes:
        datos = self.hojas.get(indice)
        return hoja(datos) if datos is not None else VACIO

    def _subarbol(self, base: int, contar: bool) -> tuple[bytes, list[bytes]]:
        """Recomputa el subárbol de `2^corte` hojas que arranca en `base`.

        Devuelve su raíz y todos los niveles, para poder sacar el camino sin recomputarlo.
        """
        nivel = [self._hoja(base + k) for k in range(1 << self.corte)]
        niveles = [nivel]
        while len(nivel) > 1:
            nivel = [nodo(nivel[k], nivel[k + 1]) for k in range(0, len(nivel), 2)]
            if contar:
                self.hashes_actualizando += len(nivel)
            niveles.append(nivel)
        return nivel[0], niveles

    def _guardado(self, nivel: int, indice: int) -> bytes:
        return self.guardados.get((nivel, indice), VACIO)

    def actualizar(self, indice: int, datos: bytes) -> None:
        """Escribe una hoja y rehace lo que haga falta. **Es lo que pasa en cada transacción.**"""
        if not 0 <= indice < (1 << self.altura):
            raise IndexError("fuera del árbol")
        self.hojas[indice] = datos

        ancho = 1 << self.corte
        base = (indice // ancho) * ancho
        raiz_sub, _ = self._subarbol(base, contar=True)

        # Subir por los niveles guardados.
        nivel, pos = self.corte, base >> self.corte
        self.guardados[(nivel, pos)] = raiz_sub
        while nivel < self.altura:
            hermano = self._guardado(nivel, pos ^ 1)
            actual = self.guardados[(nivel, pos)]
            izq, der = (actual, hermano) if pos % 2 == 0 else (hermano, actual)
            pos //= 2
            nivel += 1
            self.guardados[(nivel, pos)] = nodo(izq, der)
            self.hashes_actualizando += 1

    def raiz(self) -> bytes:
        return self._guardado(self.altura, 0)

    def prueba(self, indice: int) -> PruebaHoja:
        """El camino de hermanos hasta la raíz. **Recomputa el subárbol**, igual que actualizar."""
        ancho = 1 << self.corte
        base = (indice // ancho) * ancho
        _, niveles = self._subarbol(base, contar=False)
        self.hashes_probando += (1 << self.corte) - 1

        camino: list[bytes] = []
        pos = indice - base
        for nivel in niveles[:-1]:
            camino.append(nivel[pos ^ 1])
            pos //= 2

        nivel, pos = self.corte, base >> self.corte
        while nivel < self.altura:
            camino.append(self._guardado(nivel, pos ^ 1))
            self.hashes_probando += 1
            pos //= 2
            nivel += 1
        return PruebaHoja(indice, self.hojas.get(indice, b""), tuple(camino))

    def verifica(self, prueba: PruebaHoja) -> bool:
        acumulado = hoja(prueba.datos) if prueba.datos else VACIO
        pos = prueba.indice
        for hermano in prueba.camino:
            acumulado = (
                nodo(acumulado, hermano) if pos % 2 == 0 else nodo(hermano, acumulado)
            )
            pos //= 2
        return acumulado == self.raiz()
