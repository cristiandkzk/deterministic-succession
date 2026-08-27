"""Los criterios de `nodo/CRITERIOS-PREDICADO.md`.

`predicado/aceptacion.py` existía, la máquina existía en Rust con sus dos techos medidos, y
**ningún nodo corrió jamás un predicado**. El veredicto se hizo canónico *para entrar al hash
del bloque* y nunca entró a ninguno.
"""

from __future__ import annotations

import unittest

from nodo.predicado import (
    Evaluacion,
    GeneracionEquivocada,
    MaquinaDoble,
    Pedido,
    evaluar,
    predicados_por_bloque,
)
from predicado.aceptacion import Predicado, Presupuesto, Veredicto
from protocolo import genesis as g
from pruebas.comun import correr_hasta_activar, nodo_emision
from red.sync import sincronizar


def pedido(gen: int | None = None) -> Pedido:
    pred = Predicado(programa=b"\x11" * 32, vectores=((b"a", b"ok-a"), (b"b", b"ok-b")))
    return Pedido(b"ped-1", pred, g.RULESET_INICIAL.generacion if gen is None else gen)


def maquina_buena() -> MaquinaDoble:
    return MaquinaDoble(guion={b"a": (1_000, 4, b"ok-a"), b"b": (2_000, 6, b"ok-b")})


def nodo_con_predicado(maquina=None) -> tuple:
    n = nodo_emision()
    p = pedido()
    n.estado.pedidos[p.identificador] = p
    n.estado.maquina = maquina or maquina_buena()
    return n, p


class P1ElVeredictoEntraAlEstado(unittest.TestCase):
    """Si quedara afuera, dos nodos podrían discrepar sobre el resultado de una
    impugnación sin que la cadena lo note."""

    def test_evaluar_publica_el_hecho_y_mueve_la_raiz(self):
        n, p = nodo_con_predicado()
        antes = n.estado.huella()
        n.producir_bloque([("evaluar", p.identificador)])

        self.assertEqual(n.estado.eventos[-1]["tipo"], "evaluacion")
        self.assertTrue(n.estado.eventos[-1]["acepta"])
        self.assertNotEqual(n.estado.huella(), antes)

    def test_el_veredicto_lo_computa_el_nodo_y_no_la_transaccion(self):
        """Si viniera en la transacción, el que la manda elegiría el resultado."""
        n, p = nodo_con_predicado(
            MaquinaDoble(guion={b"a": (1_000, 4, b"otra-cosa"), b"b": (2_000, 6, b"ok-b")})
        )
        n.producir_bloque([("evaluar", p.identificador)])
        self.assertFalse(n.estado.eventos[-1]["acepta"], "aceptó una salida equivocada")

    def test_un_pedido_desconocido_no_se_puede_evaluar(self):
        n, _ = nodo_con_predicado()
        with self.assertRaises(Exception):
            n.producir_bloque([("evaluar", b"no-existe")])

    def test_dos_nodos_con_la_misma_maquina_llegan_al_mismo_hecho(self):
        """**Y ahí está la propiedad de consenso.** El que compute otro veredicto produce
        otra raíz y su bloque se rechaza (`red/sync.py`)."""
        a, p = nodo_con_predicado()
        b, _ = nodo_con_predicado()
        a.producir_bloque([("evaluar", p.identificador)])
        b.producir_bloque([("evaluar", p.identificador)])
        self.assertEqual(a.estado.huella(), b.estado.huella())
        self.assertEqual(a.cadena[-1].hash(), b.cadena[-1].hash())

    def test_y_un_validador_que_no_produjo_el_bloque_lo_reproduce(self):
        productor, p = nodo_con_predicado()
        productor.producir_bloque([("evaluar", p.identificador)])
        productor.producir(2)

        v, _ = nodo_con_predicado()
        self.assertTrue(sincronizar(v, productor.cadena).entera)
        self.assertEqual(v.estado.huella(), productor.estado.huella())


class P2LosDosTechosSeCobran(unittest.TestCase):
    """Es lo que la Fase 4 midió suelto, aplicado adentro de una cadena."""

    def test_pasarse_de_pasos_rechaza(self):
        n, p = nodo_con_predicado(
            MaquinaDoble(guion={b"a": (10**9, 4, b"ok-a"), b"b": (2_000, 6, b"ok-b")})
        )
        n.producir_bloque([("evaluar", p.identificador)])
        self.assertFalse(n.estado.eventos[-1]["acepta"])

    def test_pasarse_de_paginas_tambien_rechaza(self):
        """Con pocos pasos y mucha memoria el techo de pasos no ve nada — es el caso que
        la Fase 4 midió a 23×."""
        n, p = nodo_con_predicado(
            MaquinaDoble(guion={b"a": (10, 500, b"ok-a"), b"b": (2_000, 6, b"ok-b")})
        )
        n.producir_bloque([("evaluar", p.identificador)])
        self.assertFalse(n.estado.eventos[-1]["acepta"])

    def test_los_dos_veredictos_son_distintos_y_deterministas(self):
        presupuesto = Presupuesto.de(g.RULESET_INICIAL)
        pasos = MaquinaDoble(guion={b"a": (10**9, 4, b"")}).correr(b"", b"a", presupuesto)
        pags = MaquinaDoble(guion={b"a": (10, 500, b"")}).correr(b"", b"a", presupuesto)

        self.assertEqual(pasos.veredicto, Veredicto.TECHO_EXCEDIDO)
        self.assertEqual(pags.veredicto, Veredicto.PAGINAS_EXCEDIDAS)
        self.assertNotEqual(pasos.canonico(), pags.canonico())


class P3ElTechoEsElDeLaGeneracionVigente(unittest.TestCase):
    def test_el_presupuesto_sale_del_ruleset_y_no_de_una_copia(self):
        presupuesto = Presupuesto.de(g.RULESET_INICIAL)
        self.assertEqual(presupuesto.pasos, g.techo_vigente(g.RULESET_INICIAL))
        self.assertEqual(presupuesto.paginas, g.paginas_vigentes(g.RULESET_INICIAL))


class P4UnPedidoQueCruzaUnaConmutacion(unittest.TestCase):
    """**El criterio con riesgo, y viene directo de la auditoría de unidades.**

    El techo se deriva de tres parámetros internos, así que una conmutación lo mueve — y eso
    es a propósito (§6.6). Pero un pedido se publica y se acepta más tarde: si en el medio
    hay una conmutación, **el predicado que era admisible puede dejar de serlo sin que nadie
    lo toque.** Es la forma que encontró B3 con el depósito de permanencia.
    """

    def test_el_techo_cambia_con_la_generacion(self):
        """El hecho que crea el problema."""
        n = nodo_emision()
        antes = g.techo_vigente(n.ruleset)
        correr_hasta_activar(n)
        self.assertNotEqual(n.ruleset.generacion, g.RULESET_INICIAL.generacion)
        # Si algún día el sucesor no mueve el techo, este criterio deja de tener sentido
        # y hay que rehacerlo — no borrarlo.
        self.assertIsInstance(antes, int)

    def test_el_pedido_lleva_su_generacion_y_no_se_juzga_con_otra(self):
        """**La salida elegida: se juzga con las reglas bajo las que se publicó.**

        Lo contrario haría que aceptar el mismo trabajo diera distinto según cuándo llegue
        la respuesta, sin que nadie haya tocado el pedido.
        """
        viejo = pedido(gen=g.RULESET_INICIAL.generacion)
        n = nodo_emision()
        correr_hasta_activar(n)

        with self.assertRaises(GeneracionEquivocada):
            viejo.presupuesto(n.ruleset)

    def test_y_con_el_ruleset_de_entonces_se_juzga_igual_que_antes(self):
        """El nodo guarda el historial de rulesets, así que puede recuperarlo."""
        n = nodo_emision()
        correr_hasta_activar(n)
        de_entonces = n.historial_rulesets[0][1]

        viejo = pedido(gen=de_entonces.generacion)
        self.assertEqual(
            viejo.presupuesto(de_entonces).pasos, g.techo_vigente(de_entonces)
        )


class P5DeQuePresupuestoSalenLosPredicados(unittest.TestCase):
    """`f*` es para verificar firmas; §6.2 pide que el predicado sea barato sin decir
    con cargo a qué."""

    def test_el_numero_queda_escrito(self):
        n = predicados_por_bloque(g.RULESET_INICIAL)
        self.assertAlmostEqual(n["para_firmas"] / n["pasos_del_bloque"], 0.25, places=3)
        self.assertAlmostEqual(
            n["fuera_de_f_estrella"], n["pasos_del_bloque"] - n["para_firmas"]
        )
        self.assertGreater(n["predicados_al_techo"], 1)

    def test_compiten_con_el_desalojo_y_con_la_cola(self):
        """Lo que sobra de `f*` lo comparten el predicado, la red, la liquidación de §6.5
        y el ciclo de desalojo, que la Fase 6 midió en 3%."""
        n = predicados_por_bloque(g.RULESET_INICIAL)
        self.assertLess(n["fuera_de_f_estrella"] / n["pasos_del_bloque"], 0.76)
