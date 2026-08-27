"""El devnet desechable — Fase 6, y lo único que junta todas las piezas a la vez.

**Desechable por declaración**, y conviene que esté escrito acá arriba y no sólo en el roadmap:
un devnet con tokens gratis contesta preguntas de software, no de economía. Con tokens sin valor
no hay ingreso, no hay atesoramiento, no se mide la elasticidad de la demanda de guardado y el
antispam no se prueba. **Fecha de reset: el día que se elija la regla de la tasa de permanencia**
(§10.3), porque ése es el número que cambia el espacio de parámetros que Genesis tiene que
anticipar.

Y la fase se acota a lo que ninguna otra midió. De las cuatro preguntas que el roadmap le asigna,
la cola con `N` real la contestó la Fase 3 y el presupuesto bajo bloques reales la Fase 4.
**Quedan la conmutación bajo carga y el ciclo de desalojo**, que son las dos que sólo aparecen
cuando las piezas corren juntas.

## Lo que sólo se ve integrando

Cada fase suelta probó su mecanismo contra un mundo quieto. Acá el mundo se mueve mientras el
mecanismo corre, y aparecen los acoples que ninguna prueba de módulo puede ver — el más caro es
que **el depósito se compra en una unidad que un parámetro del ruleset puede reinterpretar**
(ver `RESULTADOS.md`, B3).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from estado import permanencia as perm
from estado.desalojo import Acumulador
from estado.permanencia import Entrada
from nodo.pod import NodoPoD


@dataclass
class Registro:
    """El conjunto activo y el acumulador de desalojados, corriendo juntos."""

    entradas: dict[bytes, Entrada] = field(default_factory=dict)
    acumulador: Acumulador = field(default_factory=Acumulador)
    #: Posición en el acumulador de cada objeto desalojado, para poder revivirlo.
    desalojados: dict[bytes, int] = field(default_factory=dict)
    #: Byte-segundos quemados. Van al sumidero de §8.4: no tienen destinatario.
    quemado: int = 0
    #: Cuántas veces se cobró y cuántas se desalojó — para el número de B4.
    cobros: int = 0
    desalojos: int = 0

    def crear(self, identificador: bytes, dueno: bytes, epocas: int, ruleset) -> Entrada:
        e = Entrada(identificador=identificador, dueno=dueno)
        e.recargar(epocas, ruleset)
        self.entradas[identificador] = e
        return e

    def cobrar_epoca(self, epoca: int, ruleset) -> list[bytes]:
        """Cobra una época a todas las entradas y desaloja a las que se agotaron.

        Devuelve los identificadores desalojados. **El orden es el de inserción**, que es
        determinístico: si dependiera de un recorrido de diccionario por hash, dos nodos
        podrían desalojar en órdenes distintos y el acumulador les quedaría distinto.
        """
        vencidas = []
        for identificador, entrada in list(self.entradas.items()):
            self.quemado += entrada.cobrar(epoca, ruleset)
            self.cobros += 1
            if entrada.epocas_restantes(ruleset) <= 0:
                vencidas.append(identificador)

        for identificador in vencidas:
            entrada = self.entradas.pop(identificador)
            self.desalojados[identificador] = self.acumulador.desalojar(entrada.canonico())
            self.desalojos += 1
        return vencidas

    def revivir(self, identificador: bytes, epocas: int, ruleset) -> Entrada:
        """Reactiva con prueba. **La doble reactivación se frena contra el conjunto
        activo**, no contra una lista de gastados (§8.5)."""
        if identificador in self.entradas:
            raise ValueError("ya está viva: la doble reactivación se frena acá")
        posicion = self.desalojados[identificador]
        prueba = self.acumulador.prueba_de(posicion)
        if not self.acumulador.verifica(prueba):
            raise ValueError("la prueba no verifica contra los picos vigentes")

        largo_id = int.from_bytes(prueba.datos[:2], "little")
        ident = prueba.datos[2 : 2 + largo_id]
        largo_dueno = int.from_bytes(prueba.datos[2 + largo_id : 4 + largo_id], "little")
        dueno = prueba.datos[4 + largo_id : 4 + largo_id + largo_dueno]
        assert ident == identificador

        e = Entrada(identificador=ident, dueno=dueno)
        e.recargar(epocas, ruleset)
        self.entradas[identificador] = e
        return e


@dataclass
class Devnet:
    """Una cadena con todo prendido a la vez."""

    nodo: NodoPoD
    registro: Registro = field(default_factory=Registro)
    #: Épocas ya cobradas, para no cobrar dos veces la misma.
    ultima_epoca: int = 0
    #: (altura, identificador) de cada desalojo, para B5.
    historia_desalojos: list[tuple[int, bytes]] = field(default_factory=list)

    @property
    def ruleset(self):
        return self.nodo.ruleset

    def epoca_de(self, altura: int) -> int:
        return altura // perm.EPOCA_BLOQUES

    def producir(self, bloques: int, transacciones_por_bloque=lambda altura: ()) -> None:
        """Produce bloques y cobra permanencia en cada frontera de época.

        El cobro va **después** de la activación de la conmutación, que es el orden que
        obliga §3: el ruleset nuevo gobierna el bloque entero, así que también gobierna lo
        que se cobre en él.
        """
        for _ in range(bloques):
            altura = self.nodo.altura + 1
            self.nodo.producir_bloque(transacciones_por_bloque(altura))

            epoca = self.epoca_de(self.nodo.altura)
            if epoca > self.ultima_epoca:
                for e in range(self.ultima_epoca + 1, epoca + 1):
                    for identificador in self.registro.cobrar_epoca(e, self.ruleset):
                        self.historia_desalojos.append((self.nodo.altura, identificador))
                self.ultima_epoca = epoca

    # ------------------------------------------------------------------ #
    # Los números que la fase tiene que dejar escritos
    # ------------------------------------------------------------------ #

    def costo_del_desalojo_por_bloque(self) -> dict[str, float]:
        """**B4: qué fracción del bloque se lleva el ciclo de desalojo en régimen.**

        La Fase 3 midió la cola sin permanencia corriendo y la Fase 5 midió la permanencia
        sin cola. En un nodo real las dos salen del mismo presupuesto, y §6.3 depende de
        que sobre headroom para drenar.

        El peor caso es el estado lleno donde nadie recarga: todo vence dentro de `L_max`,
        así que se desaloja el conjunto entero cada `L_max` épocas.
        """
        from protocolo import genesis as g

        entradas = perm.entradas_que_entran()
        por_epoca = entradas / g.L_MAX_EPOCAS
        por_bloque = por_epoca / perm.EPOCA_BLOQUES

        pasos_por_desalojo = perm.costo_del_ciclo_en_pasos() // 2  # una actualización
        pasos_por_bloque = por_bloque * pasos_por_desalojo

        ritmo = g.ritmo_declarado(self.ruleset.interno("paginas_vm"))
        presupuesto = ritmo * self.ruleset.interno("tiempo_bloque_ms") / 1_000
        return {
            "desalojos_por_bloque": por_bloque,
            "pasos_por_bloque": pasos_por_bloque,
            "presupuesto_del_bloque": presupuesto,
            "fraccion": pasos_por_bloque / presupuesto,
        }
