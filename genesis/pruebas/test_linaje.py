"""I4 · el linaje, insumo por insumo.

El criterio de la Fase 1 pide dos cosas y la segunda es la que tiene filo:
`Verify` da TRUE para toda la cadena de generaciones **y falla si se altera
cualquiera de los tres insumos**. Un hash que sólo se prueba contra su propia
entrada no demuestra nada; lo que hay que ver es que los tres cambios rompan.
"""

from __future__ import annotations

import unittest

from protocolo import genesis as g
from protocolo.linaje import calcular_h0, verificar, verificar_linaje
from pruebas.comun import GASTAR_CANARIO, nodo_canario


def cadena_de_dos_generaciones():
    nodo = nodo_canario()
    nodo.producir(2)
    nodo.producir_bloque([GASTAR_CANARIO])
    nodo.producir(20)
    nodo.producir_bloque([GASTAR_CANARIO])
    nodo.producir(20)
    return nodo


class LosTresInsumos(unittest.TestCase):
    def setUp(self):
        self.nodo = cadena_de_dos_generaciones()
        self.checkpoint = self.nodo.cronograma.checkpoints[0]

    def test_verify_da_true_con_los_insumos_reales(self):
        punto = self.checkpoint
        self.assertTrue(
            verificar(punto.h0, punto.h0_ancestro, punto.state_trigger, punto.params)
        )

    def test_falla_si_se_altera_el_ancestro(self):
        punto = self.checkpoint
        self.assertFalse(
            verificar(punto.h0, b"\x00" * 32, punto.state_trigger, punto.params)
        )

    def test_falla_si_se_altera_el_estado_que_disparo(self):
        punto = self.checkpoint
        self.assertFalse(
            verificar(punto.h0, punto.h0_ancestro, b"\x00" * 32, punto.params)
        )

    def test_falla_si_se_altera_un_solo_parametro(self):
        punto = self.checkpoint
        retocado = punto.params.con(tiempo_bloque_ms=5_000)
        self.assertFalse(
            verificar(punto.h0, punto.h0_ancestro, punto.state_trigger, retocado)
        )

    def test_falla_si_se_altera_solo_la_interfaz(self):
        """Los formatos entran al hash igual que los internos."""
        from protocolo.generacion import Params

        punto = self.checkpoint
        retocado = Params(
            punto.params.generacion,
            dict(punto.params.internos),
            punto.params.formatos ^ {"firma/ml-dsa-44"},  # lo agrega o lo saca
        )
        self.assertNotEqual(retocado.formatos, punto.params.formatos)
        self.assertFalse(
            verificar(punto.h0, punto.h0_ancestro, punto.state_trigger, retocado)
        )


class LaCadenaEntera(unittest.TestCase):
    def setUp(self):
        self.nodo = cadena_de_dos_generaciones()
        self.checkpoints = list(self.nodo.cronograma.checkpoints)

    def test_verifica_desde_genesis(self):
        self.assertGreaterEqual(len(self.checkpoints), 2)
        self.assertTrue(verificar_linaje(self.checkpoints, g.H0_GENESIS))

    def test_no_verifica_contra_otra_raiz(self):
        """Una cadena que no conmutó no tiene checkpoint válido (§5)."""
        self.assertFalse(verificar_linaje(self.checkpoints, b"\x00" * 32))

    def test_no_se_puede_sacar_un_eslabon_del_medio(self):
        sin_el_primero = self.checkpoints[1:]
        self.assertFalse(verificar_linaje(sin_el_primero, g.H0_GENESIS))

    def test_no_se_puede_reordenar(self):
        al_reves = list(reversed(self.checkpoints))
        self.assertFalse(verificar_linaje(al_reves, g.H0_GENESIS))

    def test_cada_generacion_commitea_al_h0_de_la_anterior(self):
        anterior = g.H0_GENESIS
        for punto in self.checkpoints:
            self.assertEqual(punto.h0_ancestro, anterior)
            anterior = punto.h0

    def test_genesis_no_puede_conocer_el_hash_de_su_sucesor(self):
        """No es una limitación: es lo que hace que el linaje signifique algo.

        `H0_B` incorpora el estado que disparó, que en el bloque 0 todavía no
        existe. Lo único que Genesis fija es **cómo se calculará**, y eso es
        justamente lo que se puede verificar después.
        """
        punto = self.checkpoints[0]
        self.assertEqual(
            punto.h0,
            calcular_h0(g.H0_GENESIS, punto.state_trigger, punto.params),
        )
        self.assertNotEqual(punto.h0, g.H0_GENESIS)


if __name__ == "__main__":
    unittest.main()
