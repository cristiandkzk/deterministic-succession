"""Fase 2 · caso 2 — el criterio de aprobado del `blobSchedule`.

El mismo criterio del roadmap que el caso de la bomba: *o la regla reproduce la
decisión humana, o queda escrito exactamente dónde difiere y si esa diferencia era
mejor o peor*.

Acá **no reproduce**, y en las dos direcciones a la vez: dispara mucho antes cuando
la decisión es de demanda, y no dispara nunca cuando la decisión es de capacidad.
Los números están anclados para que una corrección del dato obligue a releer la
conclusión en vez de dejarla envejecer.
"""

from __future__ import annotations

import unittest

from herramientas import historial, replay_blobs as blobs

#: Medidos el 19/8/2026 sobre 1.274 muestras. Anclas de regresión.
OCUPACION_POR_TARGET = {
    "Cancun (Dencun)": 83,
    "Prague (Pectra)": 83,
    "BPO1": 43,
    "BPO2": 31,
}
DIAS_DE_DEMORA = {"Prague (Pectra)": 383, "BPO1": 162}


class HayDatos(unittest.TestCase):
    def test_la_serie_esta_en_el_repo(self):
        self.assertGreater(len(blobs.serie()), 1_000, "corré: traer_datos.py blobs")


class LaCandidataEsUnaReglaDeVerdad(unittest.TestCase):
    def setUp(self):
        if not blobs.serie():
            self.skipTest("falta la serie: python herramientas/traer_datos.py blobs")

    def test_pasa_los_predicados_de_i2(self):
        blobs.revisar_invariantes()

    def test_el_progreso_es_monotono_aunque_la_ocupacion_oscile(self):
        """C9.3 validada por segunda vez, y acá era obligatoria.

        La ocupación sube y baja; como progreso violaría I2 en cada bajada. El
        acumulado de blobs no baja nunca, y el umbral se mueve con la ventana.
        """
        serie = blobs.serie()
        ocupaciones = [
            blobs.ocupacion_movil(serie, i, 3) for i in range(blobs.VENTANA, 300)
        ]
        self.assertNotEqual(ocupaciones, sorted(ocupaciones))  # oscila

        acumulado, progresos = 0, []
        for fila in serie:
            acumulado += fila["blobs"]
            progresos.append(acumulado)
        self.assertEqual(progresos, sorted(progresos))  # no retrocede

    def test_el_estado_que_lee_sale_todo_de_la_cadena(self):
        estado = blobs.EstadoBlobs(blobs_acumulados=10, blobs_hace_una_ventana=5)
        self.assertEqual(
            set(estado.canonico()),
            {"blobs_acumulados", "blobs_hace_una_ventana", "target_vigente"},
        )


class LaOcupacionMedida(unittest.TestCase):
    """Medición A · cero parámetros libres."""

    def setUp(self):
        self.tramos = blobs.tramos()
        if not self.tramos:
            self.skipTest("falta la serie")

    def test_hay_un_tramo_por_cada_decision(self):
        self.assertEqual(
            [t.nombre for t in self.tramos],
            [p.nombre for p in historial.BLOB_SCHEDULE],
        )

    def test_la_ocupacion_por_target_es_la_medida(self):
        for tramo in self.tramos:
            self.assertEqual(
                round(tramo.ocupacion), OCUPACION_POR_TARGET[tramo.nombre], tramo.nombre
            )

    def test_los_dos_primeros_targets_corrieron_saturados_y_los_dos_ultimos_no(self):
        """Es el hallazgo, en una línea: la demanda dejó de ser la restricción."""
        primeros = [t for t in self.tramos if t.target <= 6]
        ultimos = [t for t in self.tramos if t.target >= 10]
        for tramo in primeros:
            self.assertGreaterEqual(tramo.ocupacion, 80)
        for tramo in ultimos:
            self.assertLess(tramo.ocupacion, 50)

    def test_un_tramo_mas_corto_que_la_ventana_no_inventa_un_pico(self):
        """BPO1 duró 29 días contra una ventana de 30: `None`, no cero."""
        bpo1 = next(t for t in self.tramos if t.nombre == "BPO1")
        self.assertIsNone(bpo1.pico_ppm)
        self.assertIsNone(bpo1.saturado_ppm)


class ElContrafactico(unittest.TestCase):
    """Medición B · un parámetro libre."""

    def setUp(self):
        self.filas = blobs.contrafactico(800_000)
        if not self.filas:
            self.skipTest("falta la serie")

    def test_hay_respuesta_para_las_tres_decisiones(self):
        self.assertEqual(
            [f.decision for f in self.filas],
            [p.nombre for p in historial.BLOB_SCHEDULE[1:]],
        )

    def test_donde_la_restriccion_era_demanda_los_humanos_tardaron_mas(self):
        for fila in self.filas:
            if fila.decision not in DIAS_DE_DEMORA:
                continue
            self.assertTrue(fila.disparo, fila.decision)
            self.assertEqual(round(fila.dias), DIAS_DE_DEMORA[fila.decision])

    def test_mas_de_un_ano_de_demora_en_la_primera(self):
        """La cuenta de la coordinación, medida: 383 días."""
        prague = next(f for f in self.filas if f.decision == "Prague (Pectra)")
        self.assertGreater(prague.dias, 365)

    def test_donde_la_restriccion_no_era_demanda_la_regla_no_dispara(self):
        """BPO2 subió el target con la ocupación al 43%: no hay estado que lo pida."""
        bpo2 = next(f for f in self.filas if f.decision == "BPO2")
        self.assertFalse(bpo2.disparo)
        self.assertLess(bpo2.ocupacion_al_decidir_ppm, 500_000)

    def test_el_resultado_no_depende_de_elegir_bien_el_umbral(self):
        """De 70% a 90%, la conclusión no cambia — sólo cuánto tardaron de más."""
        for umbral in (700_000, 800_000, 900_000):
            filas = blobs.contrafactico(umbral)
            prague = next(f for f in filas if f.decision == "Prague (Pectra)")
            bpo2 = next(f for f in filas if f.decision == "BPO2")
            self.assertGreater(prague.dias, 300, umbral)
            self.assertFalse(bpo2.disparo, umbral)


if __name__ == "__main__":
    unittest.main()
