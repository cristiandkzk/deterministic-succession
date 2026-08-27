"""El evento de lock-in es estado derivado de la cadena, no un anuncio.

El lock-in ocurre en el bloque en que `N` pasa a ser final — un bloque que, por
ser el último, **todavía no es final él mismo**. Una reorganización legítima puede
reemplazarlo.

Lo que estas pruebas fijan es que eso no importe: el evento se emite **en función
de la altura**, no de que el nodo acabe de enterarse, así que cualquiera que
reproduzca los mismos bloques lo vuelve a producir idéntico.

**La falla que previenen no es de lectura, es de consenso.** Un nodo que publicara
sólo *lo recién madurado* terminaría, después de una reorganización, con un lock-in
vigente sin registro en el estado — y su raíz se separaría de la de un nodo que no
reorganizó. Eso no es un aviso que no se puede leer: es una bifurcación.
"""

from __future__ import annotations

import unittest

from nodo.pod import NodoPoD
from pruebas.comun import GASTAR_CANARIO, nodo_canario
from pruebas.test_transiciones_en_vuelo import PASO_CASCADA, ReglaEscalon

#: El canario se gasta en el bloque 5; con finalidad de 12, el lock-in cae en 17.
ALTURA_DEL_CANARIO = 5


def cadena_con_lockin() -> NodoPoD:
    nodo = nodo_canario()
    nodo.producir(ALTURA_DEL_CANARIO - 1)
    nodo.producir_bloque([GASTAR_CANARIO])
    nodo.producir(nodo.ventana_finalidad)
    assert nodo.cronograma.checkpoints, "esta cadena tiene que llegar al lock-in"
    return nodo


class DosNodosLaMismaRaiz(unittest.TestCase):
    """El que reorganizó el bloque del lock-in y el que no, terminan iguales."""

    def setUp(self):
        self.derecho = cadena_con_lockin()
        self.reorganizado = cadena_con_lockin()
        self.checkpoint = self.derecho.cronograma.checkpoints[0]
        # El bloque del lock-in es la cabeza: reemplazarlo es legítimo.
        self.reorganizado.reorganizar(self.checkpoint.altura_lockin, bloques=[()])

    def test_la_raiz_de_estado_coincide(self):
        self.assertEqual(
            self.derecho.cadena[-1].raiz_estado,
            self.reorganizado.cadena[-1].raiz_estado,
        )

    def test_la_cadena_entera_coincide(self):
        """Misma raíz y mismo hash de bloque: no hay dos historias."""
        self.assertEqual(
            self.derecho.cadena[-1].hash(), self.reorganizado.cadena[-1].hash()
        )

    def test_el_evento_esta_una_sola_vez_y_es_el_mismo(self):
        for nodo in (self.derecho, self.reorganizado):
            eventos = [e for e in nodo.estado.eventos if e["tipo"] == "lock-in"]
            self.assertEqual(len(eventos), 1)
            self.assertEqual(eventos[0]["h0"], self.checkpoint.h0)

    def test_y_siguen_iguales_hasta_después_de_conmutar(self):
        for nodo in (self.derecho, self.reorganizado):
            while nodo.altura < self.checkpoint.altura_activacion + 3:
                nodo.producir_bloque()

        self.assertEqual(self.derecho.generacion, 1)
        self.assertEqual(
            self.derecho.cadena[-1].raiz_estado,
            self.reorganizado.cadena[-1].raiz_estado,
        )


class ElRechazoTambien(unittest.TestCase):
    """Un rechazo es tan irrevocable como un lock-in, y se reemite igual."""

    def setUp(self):
        self.nodo = NodoPoD(reglas=[ReglaEscalon(paso=PASO_CASCADA, salto=4_000)])
        while not self.nodo.cronograma.rechazos and self.nodo.altura < 400:
            self.nodo.producir_bloque()
        self.rechazo = self.nodo.cronograma.rechazos[0]
        self.assertEqual(self.rechazo.altura, self.nodo.altura)

    def test_deshacer_el_bloque_del_rechazo_no_lo_borra_del_estado(self):
        raiz_antes = self.nodo.cadena[-1].raiz_estado

        self.nodo.reorganizar(self.rechazo.altura, bloques=[()])

        self.assertEqual(self.nodo.cronograma.rechazos, [self.rechazo])
        eventos = [e for e in self.nodo.estado.eventos if e["tipo"] == "rechazo"]
        self.assertEqual(len(eventos), 1)
        self.assertEqual(self.nodo.cadena[-1].raiz_estado, raiz_antes)


class ResincronizarDaLoMismo(unittest.TestCase):
    """*Derivado de la cadena* quiere decir esto, y es falsable.

    Un nodo que nunca vio la transición ocurrir, y que sólo reproduce los bloques,
    tiene que llegar al mismo estado y al mismo checkpoint. Si el evento
    dependiera de haber estado presente, acá se vería.
    """

    def test_un_nodo_nuevo_reproduce_el_estado_y_el_checkpoint(self):
        original = cadena_con_lockin()
        checkpoint = original.cronograma.checkpoints[0]
        while original.altura < checkpoint.altura_activacion:
            original.producir_bloque()

        copia = nodo_canario()
        for bloque in original.cadena[1:]:
            copia.producir_bloque(bloque.transacciones)

        self.assertEqual(copia.cronograma.checkpoints, original.cronograma.checkpoints)
        self.assertEqual(copia.generacion, original.generacion)
        self.assertEqual(
            copia.cadena[-1].raiz_estado, original.cadena[-1].raiz_estado
        )
        self.assertEqual(copia.arranques, 1)


if __name__ == "__main__":
    unittest.main()
