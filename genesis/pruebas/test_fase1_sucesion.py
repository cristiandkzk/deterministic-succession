"""Fase 1 · el criterio de aprobado, escrito antes de correrlo.

Son los seis puntos que el `ROADMAP.md` fijó para esta fase, uno por clase, con
el texto del criterio en el docstring. **El orden es el del roadmap**, no el de
conveniencia: si alguno se cae, la fase no está aprobada y no hay media
aprobación.

Lo que estas pruebas **no** miden, para que nadie lo lea de más: nada de esto
dice si el mecanismo sirve. Dicen que hace lo que el paper describe, con una
cadena de juguete y parámetros de juguete. La evidencia externa es la Fase 2.
"""

from __future__ import annotations

import unittest

from nodo.pod import ReorganizacionProfunda
from protocolo import genesis as g
from protocolo.generacion import FormatoDesconocido, Objeto, decodificar
from pruebas.comun import GASTAR_CANARIO, correr_hasta_activar, nodo_canario, nodo_emision


class ElEstadoCruzaIntacto(unittest.TestCase):
    """*"Una cadena con estado sintético conmuta y el estado cruza bit a bit
    idéntico (I3)."*"""

    def test_la_huella_es_la_misma_de_los_dos_lados_de_la_conmutacion(self):
        nodo = nodo_canario()
        nodo.producir_bloque([("transferir", "reserva", "alice", 400)])
        nodo.producir_bloque([("crear_objeto", "recibo-1", "recibo/gen0")])
        correr_hasta_activar(nodo, {3: GASTAR_CANARIO})

        conmutacion = nodo.conmutaciones[0]
        anterior = nodo.cadena[conmutacion.altura - 1]

        # La raíz del bloque anterior es el estado con el que arranca el bloque
        # de activación: si la conmutación hubiera tocado algo, no coincidirían.
        self.assertEqual(conmutacion.huella_estado, anterior.raiz_estado)

    def test_los_saldos_y_los_objetos_estan_del_otro_lado(self):
        nodo = nodo_canario()
        nodo.producir_bloque([("transferir", "reserva", "alice", 400)])
        nodo.producir_bloque([("crear_objeto", "recibo-1", "recibo/gen0")])
        saldo_alice = nodo.estado.saldos["alice"]
        objeto = nodo.estado.objetos["recibo-1"]

        correr_hasta_activar(nodo, {3: GASTAR_CANARIO})

        self.assertEqual(nodo.generacion, 1)
        self.assertEqual(nodo.estado.saldos["alice"], saldo_alice)
        self.assertEqual(nodo.estado.objetos["recibo-1"], objeto)
        # Y sigue etiquetado en la generación en que nació (I5).
        self.assertEqual(nodo.estado.objetos["recibo-1"].generacion, 0)

    def test_la_transicion_efectivamente_cambio_las_reglas(self):
        """Sin esto, todo lo demás pasaría con una conmutación que no hace nada."""
        nodo = nodo_emision(paso=100_000)
        antes = nodo.ruleset.interno("emision_por_bloque")
        correr_hasta_activar(nodo)
        self.assertEqual(nodo.ruleset.interno("emision_por_bloque"), antes // 2)


class ElLinajeVerifica(unittest.TestCase):
    """*"`Verify(H0_B, H0_A, state_trigger, params)` da TRUE para toda la cadena
    de generaciones."*  El detalle de los tres insumos está en `test_linaje.py`."""

    def test_dos_generaciones_encadenadas_verifican_contra_genesis(self):
        from protocolo.linaje import verificar_linaje

        nodo = nodo_canario()
        nodo.producir(2)
        nodo.producir_bloque([GASTAR_CANARIO])  # disparo en 3
        nodo.producir(20)
        nodo.producir_bloque([GASTAR_CANARIO])  # segundo disparo
        nodo.producir(20)

        self.assertGreaterEqual(len(nodo.cronograma.checkpoints), 2)
        self.assertTrue(verificar_linaje(nodo.cronograma.checkpoints, g.H0_GENESIS))
        self.assertEqual(
            [c.generacion for c in nodo.cronograma.checkpoints],
            list(range(1, len(nodo.cronograma.checkpoints) + 1)),
        )


class LaReorganizacion(unittest.TestCase):
    """*"Una reorganización **antes** del lock-in deshace el disparo; **después**,
    no lo deshace."*"""

    def test_antes_del_lockin_el_disparo_se_borra_sin_dejar_rastro(self):
        nodo = nodo_canario()
        nodo.producir(4)
        nodo.producir_bloque([GASTAR_CANARIO])  # altura 5
        self.assertIn("cripto/canario", nodo.cronograma.pendientes)
        nodo.producir(3)  # altura 8, todavía dentro de la ventana de finalidad

        nodo.reorganizar(5, bloques=[(), (), (), ()])

        self.assertEqual(nodo.cronograma.pendientes, {})
        self.assertEqual(nodo.cronograma.checkpoints, [])
        self.assertEqual(nodo.estado.canarios_gastados, 0)
        self.assertEqual(nodo.altura, 8)

    def test_despues_del_lockin_no_se_puede_ni_pedir(self):
        nodo = nodo_canario()
        nodo.producir(4)
        nodo.producir_bloque([GASTAR_CANARIO])  # altura 5
        nodo.producir(12)  # altura 17: el bloque 5 es final, hay lock-in

        self.assertEqual(len(nodo.cronograma.checkpoints), 1)
        with self.assertRaises(ReorganizacionProfunda):
            nodo.reorganizar(5)

    def test_deshacer_el_bloque_del_lockin_no_deshace_el_lockin(self):
        """El caso incómodo: reorganizar el bloque *que contenía el evento*.

        El bloque del lock-in no es final —recién se produjo— así que la
        reorganización es legítima. Lo que no puede pasar es que la activación
        se evapore con él: el checkpoint sobrevive y el evento se vuelve a
        publicar cuando esa altura se reproduce.
        """
        nodo = nodo_canario()
        nodo.producir(4)
        nodo.producir_bloque([GASTAR_CANARIO])  # altura 5
        nodo.producir(12)  # altura 17 = lock-in
        checkpoint = nodo.cronograma.checkpoints[0]
        self.assertEqual(checkpoint.altura_lockin, 17)

        nodo.reorganizar(17, bloques=[()])

        self.assertEqual(nodo.cronograma.checkpoints, [checkpoint])
        self.assertEqual(
            [e["h0"] for e in nodo.estado.eventos], [checkpoint.h0]
        )

        while nodo.altura < checkpoint.altura_activacion:
            nodo.producir_bloque()
        self.assertEqual(nodo.generacion, 1)

    def test_el_cronograma_nunca_suelta_un_lockin_aunque_se_lo_pidan(self):
        """La garantía vive en el cronograma, no en la guarda del nodo."""
        nodo = nodo_canario()
        nodo.producir(4)
        nodo.producir_bloque([GASTAR_CANARIO])
        nodo.producir(12)

        antes = list(nodo.cronograma.checkpoints)
        nodo.cronograma.reorganizar(1)  # pedido brutal, directo a la pieza
        self.assertEqual(nodo.cronograma.checkpoints, antes)


class ElAvisoEsDelta(unittest.TestCase):
    """*"El aviso entre lock-in y activación es exactamente `Δ`, **independiente**
    de cuánto tardó la finalidad."*"""

    def _correr(self, ventana_finalidad: int):
        nodo = nodo_canario(ventana_finalidad=ventana_finalidad)
        nodo.producir(2)
        nodo.producir_bloque([GASTAR_CANARIO])  # disparo en 3
        nodo.producir(ventana_finalidad + 2)
        return nodo.cronograma.checkpoints[0]

    def test_delta_es_el_mismo_con_finalidades_muy_distintas(self):
        delta = g.delta(g.CRIPTOGRAFICA)
        lockins = []
        for ventana in (1, 4, 12, 30):
            checkpoint = self._correr(ventana)
            self.assertEqual(checkpoint.altura_lockin, 3 + ventana)
            self.assertEqual(
                checkpoint.altura_activacion - checkpoint.altura_lockin, delta
            )
            lockins.append(checkpoint.altura_lockin)

        # Y que la finalidad de verdad se movió, para que la prueba no sea vacía.
        self.assertEqual(len(set(lockins)), 4)

    def test_el_tope_duro_acota_la_demora_del_lockin(self):
        """C7.4: el residuo se declara, no compone. Inerte hasta la Fase 3."""
        tope = g.VENTANA_FINALIDAD + g.tope_demora(g.CRIPTOGRAFICA)
        checkpoint = self._correr(tope + 40)
        self.assertEqual(checkpoint.altura_lockin, 3 + tope)


class LaDistanciaSeVeVenir(unittest.TestCase):
    """*"La distancia al disparo es consultable y monótona en la aproximación (I2)."*"""

    def test_el_progreso_no_retrocede_nunca(self):
        nodo = nodo_emision(paso=20_000)
        nodo.producir(40)
        progresos = nodo.historial_progreso["emision/mitad"]
        self.assertEqual(progresos, sorted(progresos))

    def test_a_ritmo_constante_la_cuenta_es_exacta(self):
        nodo = nodo_emision(paso=20_000)
        nodo.producir(10)  # emitido 10.000 de 20.000, a 1.000 por bloque
        distancia = nodo.distancia("emision/mitad")
        self.assertEqual(distancia.progreso, 10_000)
        self.assertEqual(distancia.umbral, 20_000)
        self.assertEqual(distancia.bloques, 10)

        nodo.producir(10)
        self.assertEqual(nodo.distancia("emision/mitad").bloques, 0)

    def test_sin_ritmo_no_se_inventa_una_fecha(self):
        """El caso débil de C3.2: el canario no se ve venir, y se dice así."""
        nodo = nodo_canario()
        nodo.producir(10)
        distancia = nodo.distancia("cripto/canario")
        self.assertIsNone(distancia.bloques)
        self.assertFalse(distancia.observable)

    def test_la_distancia_esta_en_el_estado_no_en_el_nodo(self):
        nodo = nodo_emision(paso=20_000)
        nodo.producir(3)
        self.assertIn("emision/mitad", nodo.estado.distancias)
        # La misma que devuelve la consulta: no hay dos fuentes.
        self.assertIs(
            nodo.distancia("emision/mitad"), nodo.estado.distancias["emision/mitad"]
        )


class ElNodoNoSeReinicia(unittest.TestCase):
    """*"El nodo no se reinicia. Si hace falta reiniciar, la fase no está
    aprobada."*"""

    def test_un_solo_arranque_y_un_solo_estado_de_punta_a_punta(self):
        nodo = nodo_canario()
        identidad = id(nodo.estado)

        nodo.producir(4)
        nodo.producir_bloque([GASTAR_CANARIO])
        nodo.producir(3)
        nodo.reorganizar(6, bloques=[(), ()])
        correr_hasta_activar(nodo, {nodo.altura + 1: GASTAR_CANARIO})

        self.assertEqual(nodo.generacion, 1)
        self.assertEqual(nodo.arranques, 1)
        self.assertEqual(id(nodo.estado), identidad)


class LaInterfazEsAditiva(unittest.TestCase):
    """I5 sobre la cadena corriendo, no sobre parámetros sueltos."""

    def test_el_formato_nuevo_recien_existe_despues_de_activar(self):
        nodo = nodo_canario()
        with self.assertRaises(FormatoDesconocido):
            decodificar(Objeto(1, "firma/ml-dsa-44"), nodo.ruleset)

        correr_hasta_activar(nodo, {3: GASTAR_CANARIO})

        decodificar(Objeto(1, "firma/ml-dsa-44"), nodo.ruleset)
        # Y el formato viejo sigue vivo: agregar no es reemplazar.
        decodificar(Objeto(0, "firma/ed25519"), nodo.ruleset)


if __name__ == "__main__":
    unittest.main()
