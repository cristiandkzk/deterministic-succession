"""Más de una transición en vuelo — el hueco que apareció al hacer correr §3.

Entre el lock-in y la activación pasan `Δ` bloques con las reglas viejas todavía
en vigor y las nuevas ya commiteadas. El paper no decía qué pasa ahí, y **pasa
solo**: la primera corrida del motor con una regla de acumulación se rompió sin
que nadie forzara nada.

Lo que estas pruebas fijan es la respuesta, en cuatro piezas:

1. una regla **no se rearma hasta su activación** — el lazo lo cierra el efecto,
   no el compromiso;
2. las **otras** reglas no esperan: la serialización es por regla, no global;
3. las **activaciones van en orden de lock-in**, aunque las `Δ` sean distintas;
4. `params_nuevos` se computa **en el lock-in**, y si el sucesor no se puede
   commitear hay **rechazo** on-chain, no una cadena parada.
"""

from __future__ import annotations

import unittest

from nodo.pod import NodoPoD
from protocolo import genesis as g
from protocolo.generacion import Objeto, Params, decodificar
from protocolo.linaje import verificar_linaje
from pruebas.comun import GASTAR_CANARIO, nodo_emision
from sucesion.cronograma import avisos
from sucesion.regla import ReglaCanarioCriptografico, ReglaEmisionAcumulada

#: Con este paso la regla vuelve a estar por encima del umbral apenas hace
#: lock-in: es el caso que rompía, no uno inventado para la prueba.
PASO_CASCADA = 10_000


class ReglaEscalon(ReglaEmisionAcumulada):
    """Sube la emisión un escalón fijo. Existe para chocar contra el techo.

    Es la única forma de ejercitar el rechazo: las dos reglas del protocolo de
    juguete nunca se salen del espacio —bajar a la mitad converge a cero y el
    canario agrega un formato que la máquina ya conoce—, y un camino que ninguna
    prueba recorre es un camino que no existe.
    """

    def __init__(self, paso: int, salto: int, nombre: str = "emision/escalon") -> None:
        super().__init__(paso=paso, nombre=nombre)
        self.salto = salto

    def params_sucesor(self, estado, ruleset) -> Params:
        internos = dict(ruleset.params.internos)
        internos["emision_por_bloque"] = ruleset.interno("emision_por_bloque") + self.salto
        return Params(
            generacion=ruleset.generacion + 1,
            internos=internos,
            formatos=ruleset.formatos,
        )


class UnaReglaEsperaSuPropiaActivacion(unittest.TestCase):
    """El lazo se cierra con el efecto, no con el compromiso.

    Si una regla pudiera volver a disparar entre su lock-in y su activación,
    estaría midiendo un estado que **no refleja el cambio que ella misma acaba de
    comprometer**. Eso es un lazo de control con tiempo muerto, y es cómo falló la
    EDA de Bitcoin Cash: una regla automática escrita de antemano, actuando sobre
    información que su acción anterior todavía no había corregido.
    """

    def setUp(self):
        self.nodo = nodo_emision(paso=PASO_CASCADA)
        self.nodo.producir(22)  # disparo en 10, lock-in en 22
        self.checkpoint = self.nodo.cronograma.checkpoints[0]

    def test_el_umbral_ya_quedo_atras_apenas_hace_lockin(self):
        """Sin la espera, acá mismo volvería a disparar. La prueba lo verifica."""
        regla = self.nodo.reglas[0]
        self.assertGreater(
            regla.progreso(self.nodo.estado), regla.umbral(self.nodo.estado)
        )

    def test_no_dispara_de_nuevo_en_toda_la_ventana(self):
        while self.nodo.altura < self.checkpoint.altura_activacion - 1:
            self.nodo.producir_bloque()
            self.assertEqual(self.nodo.cronograma.pendientes, {})
            self.assertEqual(len(self.nodo.cronograma.checkpoints), 1)

    def test_se_rearma_exactamente_en_la_activacion(self):
        while self.nodo.altura < self.checkpoint.altura_activacion:
            self.nodo.producir_bloque()

        self.assertEqual(self.nodo.generacion, 1)
        self.assertIn("emision/mitad", self.nodo.cronograma.pendientes)
        self.assertEqual(
            self.nodo.cronograma.pendientes["emision/mitad"].altura,
            self.checkpoint.altura_activacion,
        )

    def test_la_distancia_no_dice_cero_durante_la_espera(self):
        self.nodo.producir_bloque()
        distancia = self.nodo.distancia("emision/mitad")
        self.assertTrue(distancia.en_vuelo)
        self.assertEqual(
            distancia.bloques, self.checkpoint.altura_activacion - self.nodo.altura
        )


class LasOtrasReglasNoEsperan(unittest.TestCase):
    """La serialización es por regla, no global.

    Bloquear todos los disparos mientras haya uno en vuelo pondría una migración
    criptográfica de urgencia a esperar detrás de una transición de circulación.
    Lo que sí comparten es el **orden de activación**, y eso tiene un costo que se
    mide acá en vez de declararse de memoria.
    """

    def setUp(self):
        self.nodo = NodoPoD(
            reglas=[
                ReglaEmisionAcumulada(paso=PASO_CASCADA),
                ReglaCanarioCriptografico(),
            ]
        )
        self.nodo.producir(29)
        self.nodo.producir_bloque([GASTAR_CANARIO])  # altura 30, con la otra en vuelo
        self.nodo.producir(20)
        self.lento, self.urgente = self.nodo.cronograma.checkpoints

    def test_la_urgente_se_commitea_sin_esperar_a_la_lenta(self):
        """El lock-in no espera: llega a su ventana de finalidad y listo."""
        self.assertEqual(self.urgente.regla, "cripto/canario")
        self.assertEqual(self.urgente.altura_lockin, 30 + g.VENTANA_FINALIDAD)
        self.assertLess(self.urgente.altura_lockin, self.lento.altura_activacion)

    def test_pero_activa_en_orden_y_eso_cuesta(self):
        """El residuo declarado: la urgente espera a la lenta, y está acotado."""
        propia = self.urgente.altura_lockin + g.delta(g.CRIPTOGRAFICA)
        self.assertLess(propia, self.lento.altura_activacion)
        self.assertEqual(self.urgente.altura_activacion, self.lento.altura_activacion)

        espera = self.urgente.altura_activacion - propia
        self.assertLessEqual(espera, g.delta(g.CIRCULACION))

    def test_ningun_aviso_es_menor_que_su_delta(self):
        for checkpoint, aviso in zip(
            self.nodo.cronograma.checkpoints, avisos(self.nodo.cronograma.checkpoints)
        ):
            self.assertGreaterEqual(aviso, g.delta(checkpoint.clase))

    def test_las_dos_conmutan_en_orden_y_el_linaje_cierra(self):
        while self.nodo.altura < self.urgente.altura_activacion:
            self.nodo.producir_bloque()

        self.assertEqual(
            [(c.altura, c.generacion) for c in self.nodo.conmutaciones],
            [(self.lento.altura_activacion, 1), (self.urgente.altura_activacion, 2)],
        )
        self.assertEqual(self.nodo.generacion, 2)
        self.assertTrue(
            verificar_linaje(self.nodo.cronograma.checkpoints, g.H0_GENESIS)
        )

    def test_las_dos_transiciones_se_aplican_de_verdad(self):
        while self.nodo.altura < self.urgente.altura_activacion:
            self.nodo.producir_bloque()

        self.assertEqual(self.nodo.ruleset.interno("emision_por_bloque"), 500)
        decodificar(Objeto(2, "firma/ml-dsa-44"), self.nodo.ruleset)


class ElSucesorSeComputaEnElLockin(unittest.TestCase):
    """Computarlo en el disparo deja el linaje colgando de un ancestro viejo."""

    def test_la_segunda_transicion_cuelga_de_la_primera(self):
        nodo = NodoPoD(
            reglas=[
                ReglaEmisionAcumulada(paso=PASO_CASCADA),
                ReglaCanarioCriptografico(),
            ]
        )
        nodo.producir(29)
        nodo.producir_bloque([GASTAR_CANARIO])
        nodo.producir(20)

        lento, urgente = nodo.cronograma.checkpoints
        # En el disparo del canario (altura 30) el comprometido era la generación
        # 1, que en ese momento **todavía no había activado**. El sucesor sale de
        # ahí igual, y por eso las generaciones son consecutivas.
        self.assertEqual(urgente.h0_ancestro, lento.h0)
        self.assertEqual(urgente.generacion, 2)
        self.assertEqual(
            urgente.params.internos["emision_por_bloque"],
            lento.params.internos["emision_por_bloque"],
        )


class ElSucesorQueNoSePuedeCommitear(unittest.TestCase):
    """Un checkpoint irrevocable con un punto fuera del espacio pararía la cadena.

    Por eso el lock-in valida antes de comprometer, y si no pasa hay rechazo: la
    transición no ocurre, queda on-chain, y el consenso sigue.
    """

    def setUp(self):
        self.regla = ReglaEscalon(paso=PASO_CASCADA, salto=4_000)
        self.nodo = NodoPoD(reglas=[self.regla])
        limite = 400
        while not self.nodo.cronograma.rechazos and self.nodo.altura < limite:
            self.nodo.producir_bloque()
        self.assertTrue(self.nodo.cronograma.rechazos, "no se llegó al techo")

    def test_el_techo_del_espacio_se_alcanza_y_no_se_recorta(self):
        techo = g.ESPACIO_INTERNO["emision_por_bloque"].maximo
        comprometido = self.nodo.ruleset_comprometido.interno("emision_por_bloque")
        self.assertLessEqual(comprometido, techo)
        self.assertEqual(comprometido, 9_000)  # 1.000 → 5.000 → 9.000, y 13.000 no

    def test_hay_rechazo_on_chain_y_no_hay_checkpoint(self):
        rechazo = self.nodo.cronograma.rechazos[0]
        self.assertEqual(rechazo.regla, "emision/escalon")
        self.assertNotIn(
            rechazo.altura,
            [c.altura_lockin for c in self.nodo.cronograma.checkpoints],
        )
        evento = [e for e in self.nodo.estado.eventos if e["tipo"] == "rechazo"]
        self.assertEqual(len(evento), 1)
        self.assertIn("emision_por_bloque", evento[0]["motivo"])

    def test_la_cadena_sigue_produciendo(self):
        altura = self.nodo.altura
        self.nodo.producir(10)
        self.assertEqual(self.nodo.altura, altura + 10)

    def test_no_reintenta_contra_el_mismo_ancestro(self):
        """Si no, sería un rechazo cada `F` bloques, para siempre."""
        self.nodo.producir(120)
        self.assertEqual(len(self.nodo.cronograma.rechazos), 1)

    def test_el_rechazo_no_mueve_el_umbral(self):
        """Nada pasó, así que la regla no cuenta una transición que no hubo."""
        lockins = len(self.nodo.cronograma.checkpoints)
        self.assertEqual(
            self.regla.umbral(self.nodo.estado), PASO_CASCADA * (lockins + 1)
        )


if __name__ == "__main__":
    unittest.main()
