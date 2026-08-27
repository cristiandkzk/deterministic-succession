"""Los criterios de `estado/CRITERIOS-ARBOL.md` — el árbol con corte `d`.

El roadmap lo lista y ninguna fase lo construyó. La Fase 5 usó su costo de actualización
para derivar el piso de §8.5 **sin que el árbol existiera**, y ahí estaba el problema.
"""

from __future__ import annotations

import unittest

from estado import permanencia as perm
from estado.arbol import Arbol, PruebaHoja
from protocolo import genesis as g


class T1ElArbolAnda(unittest.TestCase):
    def test_insertar_probar_y_verificar(self):
        a = Arbol(altura=10, corte=3)
        for k in range(40):
            a.actualizar(k, f"hoja-{k}".encode())
        prueba = a.prueba(7)
        self.assertTrue(a.verifica(prueba))
        self.assertEqual(len(prueba.camino), a.altura)

    def test_alterar_la_hoja_el_camino_o_la_raiz_la_rompe(self):
        a = Arbol(altura=8, corte=2)
        for k in range(20):
            a.actualizar(k, f"h{k}".encode())
        buena = a.prueba(5)

        self.assertFalse(a.verifica(PruebaHoja(5, b"otra", buena.camino)))
        torcido = (bytes(32),) + buena.camino[1:]
        self.assertFalse(a.verifica(PruebaHoja(5, buena.datos, torcido)))

        a.actualizar(6, b"cambio")  # mueve la raíz
        self.assertFalse(a.verifica(buena))

    def test_actualizar_una_hoja_cambia_la_raiz(self):
        a = Arbol(altura=6, corte=2)
        a.actualizar(0, b"x")
        antes = a.raiz()
        a.actualizar(1, b"y")
        self.assertNotEqual(a.raiz(), antes)


class T2ProbarEsBaratoYActualizarEsLoQueMuerde(unittest.TestCase):
    """La frase con la que el roadmap justifica el diseño, medida."""

    def test_el_costo_unitario_es_el_mismo_y_la_frecuencia_no(self):
        """Las dos operaciones cuestan lo mismo por vez. **Lo que las separa es cuántas
        veces pasan**: actualizar, en cada transacción; probar, sólo cuando alguien revive
        un desalojado."""
        a = Arbol(altura=26, corte=g.CORTE_ARBOL)
        self.assertEqual(a.hashes_por_actualizacion(), a.hashes_por_prueba())

    def test_el_costo_crece_con_el_corte(self):
        anterior = 0
        for d in (1, 3, 6, 9):
            h = Arbol(altura=26, corte=d).hashes_por_actualizacion()
            self.assertGreater(h, anterior)
            anterior = h


class T3LaTablaYaMedidaSeReproduce(unittest.TestCase):
    """`presupuesto-nodo/RESULTADOS.md`, 18/8/2026. Es una medición cerrada."""

    def test_los_bytes_por_entrada_coinciden(self):
        for d, esperado in ((1, 32.0), (6, 1.0), (9, 0.125)):
            self.assertAlmostEqual(
                Arbol(altura=26, corte=d).bytes_por_entrada(), esperado, places=3
            )

    def test_la_formula_es_64_sobre_dos_a_la_d(self):
        for d in (1, 4, 6, 9, 12):
            self.assertAlmostEqual(
                Arbol(altura=26, corte=d).bytes_por_entrada(), 64 / 2**d, places=6
            )


class T4ElVeintiseisDeLaFase5EraElArbolQueNoSeUsa(unittest.TestCase):
    """**El criterio que reprobó.**"""

    def test_veintiseis_es_el_costo_de_guardar_todo(self):
        """O sea `d = 1`: la fila de 32 B por entrada, que el diseño descartó."""
        self.assertEqual(Arbol(altura=26, corte=1).hashes_por_actualizacion(), 26)

    def test_el_corte_elegido_cuesta_tres_veces_mas(self):
        elegido = Arbol(altura=26, corte=g.CORTE_ARBOL).hashes_por_actualizacion()
        self.assertEqual(elegido, 83)
        self.assertAlmostEqual(elegido / 26, 3.2, places=1)

    def test_permanencia_ya_lo_saca_del_arbol_y_no_de_la_altura(self):
        self.assertEqual(perm.hashes_por_actualizacion(), 83)


class ElCorteEsConsensoYNoImplementacion(unittest.TestCase):
    """**Lo más grande que salió de construir el árbol.**

    `presupuesto-nodo/RESULTADOS.md` cierra diciendo que el corte *"es una decisión de
    implementación que hay que tomar, no un costo que se sufre"*. No puede serlo: **el piso
    de permanencia se deriva del costo de actualizar el árbol, y el piso se quema.** Dos
    nodos con `d` distinto no coincidirían sobre cuánto se quemó al crear una entrada.
    """

    def test_el_corte_es_una_constante_de_genesis(self):
        self.assertIsInstance(g.CORTE_ARBOL, int)
        self.assertNotIn("corte_arbol", g.ESPACIO_INTERNO)

    def test_cambiar_el_corte_mueve_el_piso(self):
        """La prueba de que es consenso: si moverlo no cambiara nada, daría igual."""
        pisos = set()
        for d in (1, 4, 6):
            pisos.add(round(6.03 * Arbol(altura=26, corte=d).hashes_por_actualizacion() / 26, 2))
        self.assertEqual(len(pisos), 3, "el corte no afecta el piso: revisar la cuenta")

    def test_a_partir_de_siete_el_piso_supera_el_deposito_maximo(self):
        """Y por eso el margen es más fino de lo que parecía cuando se miraban dos monedas."""
        siete = 6.03 * Arbol(altura=26, corte=7).hashes_por_actualizacion() / 26
        self.assertGreater(siete, g.L_MAX_EPOCAS)
