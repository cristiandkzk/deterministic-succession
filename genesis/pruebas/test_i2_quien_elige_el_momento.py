"""I2 · nadie elige el momento — las dos formas de cumplirlo.

La letra vieja de la invariante pedía *aproximación monótona observable* y cerraba
con **un trigger que no se puede ver venir no es admisible**. Con eso, el canario
de §6.6 —la sección de vidriera del paper— no cumplía I2: la rotura de una
primitiva no se aproxima, ocurre.

Lo que estas pruebas fijan es la reformulación:

- **por aproximación observable** — y entonces la regla *no puede disparar desde el
  reposo*, que es lo que caza la puerta trasera disfrazada;
- **por capacidad demostrada** — y entonces tiene que declarar qué capacidad, no
  inventar una cuenta regresiva, y no tener rampa.

Y fijan la condición que la segunda forma le impone a §6.6 y que **no estaba
escrita**: la instancia debilitada del canario se **deriva** de una semilla
pública. Si alguien la generara, retendría su trampa, y *capacidad demostrada*
sería *un secreto que alguien se guardó*.
"""

from __future__ import annotations

import unittest

from nodo.pod import NodoPoD
from protocolo import genesis as g
from protocolo import invariantes as inv
from protocolo.generacion import Params
from protocolo.invariantes import MODO_APROXIMACION, MODO_CAPACIDAD, ViolacionInvariante
from pruebas.comun import GASTAR_CANARIO, nodo_canario, nodo_emision
from sucesion.regla import ReglaTransicion

CUENTA = "la-puerta"
ABRIR = ("transferir", "reserva", CUENTA, 1)


class ReglaPuertaTrasera(ReglaTransicion):
    """*"Cuando la dirección X reciba 1 wei."* Se computa desde el estado.

    Es el caso que I2 existe para excluir y el que la letra vieja no podía
    distinguir del canario: los dos saltan de 0 al umbral sin aviso. La diferencia
    no está en la forma de la curva — está en **quién puede producir el hecho y
    qué le cuesta**. Acá, cualquiera con la clave de una dirección, gratis.
    """

    nombre = "puerta/trasera"
    clase = g.CIRCULACION
    modo = MODO_APROXIMACION

    def progreso(self, estado) -> int:
        return estado.saldos.get(CUENTA, 0)

    def umbral(self, estado) -> int:
        return 1

    def params_sucesor(self, estado, ruleset) -> Params:
        internos = dict(ruleset.params.internos)
        internos["emision_por_bloque"] = 0
        return Params(ruleset.generacion + 1, internos, ruleset.formatos)


class ReglaPuertaDeclarada(ReglaPuertaTrasera):
    """La misma puerta, declarada por lo que es. Pasa — y queda a la vista."""

    nombre = "puerta/declarada"
    modo = MODO_CAPACIDAD
    capacidad = "conocer la clave de la dirección la-puerta"


class ReglaCapacidadConRampa(ReglaPuertaTrasera):
    """Se declara por capacidad y en realidad se aproxima: mal declarada."""

    nombre = "capacidad/con-rampa"
    modo = MODO_CAPACIDAD
    capacidad = "algo que en realidad se ve venir"

    def umbral(self, estado) -> int:
        return 5


class LaPuertaTrasera(unittest.TestCase):
    def test_declarada_por_aproximacion_no_pasa(self):
        """El chequeo con filo: disparar desde el reposo no es aproximarse."""
        nodo = NodoPoD(reglas=[ReglaPuertaTrasera()])
        nodo.producir(5)
        self.assertIsNone(nodo.distancia("puerta/trasera").bloques)

        with self.assertRaises(ViolacionInvariante) as caso:
            nodo.producir_bloque([ABRIR])
        self.assertEqual(caso.exception.invariante, "I2")
        self.assertIn("escalón", caso.exception.motivo)

    def test_declarada_por_capacidad_pasa_y_queda_a_la_vista(self):
        """**El límite, declarado.** El protocolo no la puede distinguir.

        Un trigger de capacidad es admisible por una razón que ninguna máquina
        verifica: que producir el hecho exija exactamente la capacidad a la que la
        transición responde. Lo que el protocolo sí puede exigir es que la razón
        esté **escrita y on-chain**, y que sea la que se lea al auditar Genesis.
        Acá la declaración dice *conocer la clave de una dirección*, que a
        cualquier revisor le grita lo que es.
        """
        nodo = NodoPoD(reglas=[ReglaPuertaDeclarada()])
        nodo.producir(5)
        nodo.producir_bloque([ABRIR])

        self.assertIn("puerta/declarada", nodo.cronograma.pendientes)
        publicada = nodo.distancia("puerta/declarada")
        self.assertEqual(publicada.modo, MODO_CAPACIDAD)
        self.assertIn("clave", publicada.capacidad)

    def test_una_capacidad_con_rampa_se_caza(self):
        nodo = NodoPoD(reglas=[ReglaCapacidadConRampa()])
        nodo.producir(3)
        with self.assertRaises(ViolacionInvariante) as caso:
            nodo.producir_bloque([ABRIR])  # progreso 0 → 1, con umbral 5
        self.assertIn("aproximación", caso.exception.motivo)


class LaDeclaracionEsObligatoria(unittest.TestCase):
    def test_no_hay_modo_por_defecto_valido_fuera_de_los_dos(self):
        regla = ReglaPuertaTrasera()
        regla.modo = "ninguno"
        with self.assertRaises(ViolacionInvariante):
            inv.i2_modo_declarado(regla)

    def test_por_capacidad_hay_que_decir_cual(self):
        regla = ReglaPuertaDeclarada()
        regla.capacidad = None
        with self.assertRaises(ViolacionInvariante) as caso:
            inv.i2_modo_declarado(regla)
        self.assertIn("no declara cuál", caso.exception.motivo)


class ElCanario(unittest.TestCase):
    def test_la_instancia_se_deriva_de_la_semilla_publica(self):
        inv.i2_canario_sin_trampa(g.CANARIO_SEMILLA, g.CANARIO_INSTANCIA)

    def test_una_instancia_generada_no_pasa(self):
        """Si no salió de la semilla, alguien la eligió — y retiene la trampa."""
        with self.assertRaises(ViolacionInvariante) as caso:
            inv.i2_canario_sin_trampa(g.CANARIO_SEMILLA, b"\x00" * 32)
        self.assertIn("trampa", caso.exception.motivo)

    def test_no_publica_una_fecha_inventada_nunca(self):
        """Ni antes de gastarse, ni —y esto es lo que fallaba— después.

        El escalón 0 → 1 queda dentro de la ventana de ritmo durante los bloques
        siguientes, así que una cuenta *al ritmo actual* proyectaba una segunda
        rotura para dentro de unos bloques. Para un trigger de capacidad el ritmo
        no significa nada y no se proyecta.

        **La finalidad corta no es un detalle de la prueba: es la condición que
        destapa el bug.** Con `Δ` de finalidad largo, el escalón ya salió de la
        ventana de ritmo cuando el umbral se mueve, y la cuenta inventada no
        aparece. Medirlo sólo así habría dejado pasar el error.
        """
        nodo = nodo_canario(ventana_finalidad=1)
        nodo.producir(4)
        self.assertIsNone(nodo.distancia("cripto/canario").bloques)

        nodo.producir_bloque([GASTAR_CANARIO])
        nodo.producir(1)  # lock-in inmediato: el umbral pasa a 2

        distancia = nodo.distancia("cripto/canario")
        self.assertEqual((distancia.progreso, distancia.umbral), (1, 2))
        self.assertGreater(distancia.progreso, 0)  # el escalón sigue en la ventana
        self.assertIsNone(distancia.bloques)
        self.assertEqual(distancia.modo, MODO_CAPACIDAD)

    def test_el_nodo_no_produce_bloques_con_un_canario_adulterado(self):
        """El chequeo no alcanza con existir: tiene que estar en el lazo."""
        nodo = nodo_canario()
        nodo.producir(2)

        original = g.CANARIO_INSTANCIA
        g.CANARIO_INSTANCIA = b"\x00" * 32
        try:
            with self.assertRaises(ViolacionInvariante):
                nodo.producir_bloque()
        finally:
            g.CANARIO_INSTANCIA = original

    def test_la_capacidad_declarada_esta_on_chain(self):
        nodo = nodo_canario()
        nodo.producir(2)
        publicada = nodo.estado.distancias["cripto/canario"]
        self.assertIn("romper la instancia debilitada", publicada.capacidad)


class LaAproximacionSigueValiendo(unittest.TestCase):
    """La forma fuerte no se tocó: la regla de emisión se ve venir y dispara."""

    def test_la_emision_publica_su_cuenta_antes_de_disparar(self):
        nodo = nodo_emision(paso=20_000)
        nodo.producir(19)
        previa = nodo.distancia("emision/mitad")
        self.assertEqual(previa.modo, MODO_APROXIMACION)
        self.assertEqual(previa.bloques, 1)

        nodo.producir_bloque()
        self.assertIn("emision/mitad", nodo.cronograma.pendientes)


if __name__ == "__main__":
    unittest.main()
