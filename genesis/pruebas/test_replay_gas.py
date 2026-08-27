"""Fase 2 · caso 3 — el criterio de aprobado del gas limit.

Es el único de los tres casos donde el mecanismo del paper **no compite contra un
fork**: el gas limit ya se vota bloque a bloque, sin coordinación pesada. Y es el
único donde el resultado no es *la regla difiere* sino **no hay regla admisible**, por
una razón estructural que estas pruebas fijan con números.

Las tres, en orden de importancia:

1. **la ocupación no lleva información** — correlación −0,02 con el base fee mientras
   el fee se mueve 650×. Es la medición que cierra la puerta de §7.6;
2. **el base fee nominal se derrumba** — cualquier umbral en gwei elegido en Genesis
   caduca;
3. **la forma adimensional arregla eso y trae un trinquete** — dispara de nuevo con el
   fee en 0,26 gwei, porque sin referencia absoluta *caro* es sólo *más que recién*.
"""

from __future__ import annotations

import unittest

from herramientas import replay_gas as gas

#: Medidos el 19/8/2026 sobre 1.026 muestras. Anclas de regresión.
DIAS_CONGELADO = 870
CORRELACION_MILESIMAS = -21
DISPAROS_K15 = 4


class HayDatos(unittest.TestCase):
    def test_la_serie_esta_en_el_repo(self):
        self.assertGreater(len(gas.serie()), 1_000, "corré: traer_datos.py gas")


class LaTrayectoriaHumana(unittest.TestCase):
    def setUp(self):
        self.mesetas = gas.mesetas()
        if not self.mesetas:
            self.skipTest("falta la serie")

    def test_el_limite_estuvo_congelado_mas_de_dos_años(self):
        primera = self.mesetas[0]
        self.assertEqual(round(primera.dias), DIAS_CONGELADO)
        self.assertEqual(round(primera.limite_desde / 1e6), 30)

    def test_y_despues_se_duplico_en_menos_de_un_año(self):
        """Del primer movimiento hasta quedarse quieto otra vez, sin contar la
        meseta final: es el tramo en que efectivamente se movió."""
        ultimo = self.mesetas[-1]
        self.assertGreaterEqual(ultimo.limite_hasta / self.mesetas[0].limite_desde, 2.0)
        movimiento = sum(m.dias for m in self.mesetas[1:-1])
        self.assertLess(movimiento, 365)
        self.assertGreater(movimiento, 250)

    def test_los_saltos_son_de_dias_y_las_mesetas_de_meses(self):
        """La forma de una coordinación off-chain: nada, nada, nada, y de golpe."""
        saltos = [m for m in self.mesetas if m.dias <= 5]
        self.assertGreaterEqual(len(saltos), 4)


class LaOcupacionNoLlevaInformacion(unittest.TestCase):
    """La medición que cierra la puerta del observable de cantidad."""

    def setUp(self):
        self.senal = gas.senal_de_ocupacion()
        if self.senal is None:
            self.skipTest("falta la serie")

    def test_la_ocupacion_se_queda_pegada_al_target(self):
        self.assertAlmostEqual(self.senal.ocupacion_media_ppm, gas.TARGET_PPM, delta=20_000)

    def test_no_se_mueve_ni_cuando_el_fee_se_mueve_650_veces(self):
        self.assertGreater(self.senal.caida_del_fee, 100)
        recorrido = self.senal.ocupacion_maxima_ppm - self.senal.ocupacion_minima_ppm
        self.assertLess(recorrido, 200_000)  # menos de 20 puntos porcentuales

    def test_la_correlacion_con_el_base_fee_es_practicamente_cero(self):
        """−0,02 sobre 1.026 muestras: no es débil, es nula."""
        self.assertEqual(self.senal.correlacion_milesimas, CORRELACION_MILESIMAS)
        self.assertLess(abs(self.senal.correlacion_milesimas), 50)


class LaReglaCandidata(unittest.TestCase):
    def setUp(self):
        if not gas.serie():
            self.skipTest("falta la serie")

    def test_pasa_los_predicados_de_i2(self):
        """Y aun así no sirve: el problema no es de dónde sale el dato."""
        gas.revisar_invariantes()

    def test_la_forma_adimensional_dispara_mucho_antes_que_los_humanos(self):
        disparos = gas.contrafactico(1_500)
        self.assertEqual(len(disparos), DISPAROS_K15)
        for disparo in disparos:
            self.assertEqual(round(disparo.limite / 1e6), 30)
            self.assertLess(disparo.fecha, "2025-01-31")  # antes del primer movimiento

    def test_pero_tiene_trinquete_y_se_ve(self):
        """Sin referencia absoluta, *caro* es sólo *más que recién*."""
        disparos = gas.contrafactico(1_000)
        tardios = [d for d in disparos if d.fecha > "2025-06-01"]
        self.assertTrue(tardios, "el trinquete tiene que aparecer en el dato")
        for disparo in tardios:
            self.assertLess(disparo.base_fee_gwei, 1.0)

    def test_el_trinquete_no_es_un_artefacto_del_umbral(self):
        """A k más alto no aparece — pero entonces tampoco dispara donde hace falta."""
        self.assertFalse([d for d in gas.contrafactico(1_500) if d.fecha > "2025-06-01"])


if __name__ == "__main__":
    unittest.main()
