"""Fase 2 · el criterio de aprobado, escrito antes de correr el replay.

El roadmap pide: *para cada caso, o la regla reproduce la decisión humana, o queda
escrito **exactamente dónde difiere y si esa diferencia era mejor o peor**. Un
empate cuenta como aprobado; lo que no cuenta es no poder explicar la diferencia.*

Las tres cosas que estas pruebas exigen, en ese orden:

1. que la candidata sea una `TRANSITION_RULE` **de verdad** — que pase los mismos
   predicados de I2 que las reglas del protocolo. Si no, esto es una planilla y no
   dice nada sobre este diseño;
2. que **cada** decisión humana tenga su contrafáctico, sin huecos;
3. que la diferencia esté **medida y anclada**. Los números están fijados acá a
   propósito: si mañana se corrige una altura del historial, la prueba se cae y
   obliga a releer la conclusión en vez de dejarla envejecer sola.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from herramientas import historial, replay
from protocolo import invariantes as inv

RAIZ = Path(__file__).resolve().parent.parent

#: El umbral que minimiza el desvío máximo, medido. Si cambia, cambió el dato.
UMBRAL_MEDIDO = 40
#: Desvío máximo medido, en bloques (~37 días). Ancla de regresión.
DESVIO_MAXIMO_MEDIDO = 235_000


class LaCandidataEsUnaReglaDeVerdad(unittest.TestCase):
    """Sin esto, el replay no dice nada sobre este diseño."""

    def test_pasa_los_predicados_de_i2_del_protocolo(self):
        replay.revisar_invariantes(UMBRAL_MEDIDO, 1_000_000)

    def test_el_trigger_lee_dos_numeros_y_los_dos_estan_en_la_cadena(self):
        estado = replay.EstadoBomba(altura=10_000_000, offset_bomba=9_000_000)
        self.assertEqual(
            set(estado.canonico()), {"altura", "offset_bomba"}
        )

    def test_el_progreso_es_monotono_aunque_el_exponente_baje(self):
        """La razón por la que el progreso es la altura y no el exponente."""
        regla = replay.ReglaRetrasoBomba(UMBRAL_MEDIDO, 1_000_000)
        antes = replay.EstadoBomba(altura=13_200_000, offset_bomba=9_000_000)
        despues = replay.EstadoBomba(altura=13_200_000, offset_bomba=10_000_000)

        self.assertLess(despues.exponente, antes.exponente)  # el exponente baja
        self.assertEqual(regla.progreso(antes), regla.progreso(despues))  # el progreso no
        self.assertGreater(regla.umbral(despues), regla.umbral(antes))  # sube el umbral

    def test_la_distancia_al_disparo_es_exacta_y_no_una_proyeccion(self):
        """Un bloque de progreso por bloque: la cuenta regresiva no estima nada."""
        distancia = replay.distancia_en(10_000_000, UMBRAL_MEDIDO)
        self.assertEqual(distancia.bloques, distancia.umbral - distancia.progreso)


class ElContrafactico(unittest.TestCase):
    """Un parámetro libre, y el offset lo pone el historial real."""

    def setUp(self):
        self.umbral, self.filas = replay.mejor_umbral()

    def test_hay_respuesta_para_las_seis_decisiones(self):
        self.assertEqual(len(self.filas), len(historial.RETRASOS))
        self.assertEqual(
            [f.fork for f in self.filas], [r.fork for r in historial.RETRASOS]
        )

    def test_el_umbral_que_mejor_ajusta_es_el_medido(self):
        self.assertEqual(self.umbral, UMBRAL_MEDIDO)

    def test_el_desvio_maximo_es_el_medido(self):
        desvios = [abs(f.diferencia) for f in self.filas]
        self.assertEqual(max(desvios), DESVIO_MAXIMO_MEDIDO)

    def test_al_menos_una_decision_se_reproduce_exacta(self):
        exactos = [f.fork for f in self.filas if f.diferencia == 0]
        self.assertEqual(exactos, ["Muir Glacier"])

    def test_el_replay_es_determinista(self):
        """Es un replay, no una simulación: dos corridas dan lo mismo."""
        self.assertEqual(replay.mejor_umbral(), (self.umbral, self.filas))


class LaCotaDeLaBomba(unittest.TestCase):
    """La diferencia que sí se puede llamar mejor, y sin datos externos."""

    def test_la_regla_acota_por_construccion(self):
        self.assertEqual(replay.cota_regla(UMBRAL_MEDIDO, 1_000_000), UMBRAL_MEDIDO)

    def test_el_proceso_humano_no_estaba_acotado(self):
        self.assertGreater(replay.cota_humana(), UMBRAL_MEDIDO)


class ElDatoTieneProcedencia(unittest.TestCase):
    """La regla que el propio módulo de datos declara, vuelta ejecutable."""

    def test_ningun_retraso_entra_sin_decir_de_donde_salio(self):
        for retraso in historial.RETRASOS:
            self.assertIn(retraso.eip, retraso.procedencia)

    def test_cada_numero_dice_contra_que_se_verifico(self):
        """Los EIPs traen el offset pero **no** la altura: hacen falta dos fuentes.

        Es la trampa del caso: los EIPs usan un placeholder (`FORK_BLOCK_NUMBER`)
        y quien transcriba de ahí se queda sin la mitad del dato.
        """
        for retraso in historial.RETRASOS:
            self.assertIn("offset verificado", retraso.procedencia, retraso.fork)
            self.assertIn("MainnetChainConfig", retraso.procedencia, retraso.fork)

    def test_los_seis_estan_en_orden_y_los_offsets_solo_crecen(self):
        alturas = [r.altura for r in historial.RETRASOS]
        offsets = [r.offset for r in historial.RETRASOS]
        self.assertEqual(alturas, sorted(alturas))
        self.assertEqual(offsets, sorted(offsets))
        self.assertEqual(len(alturas), 6)

    def test_todo_ocurre_antes_de_la_fusion(self):
        for retraso in historial.RETRASOS:
            self.assertLess(retraso.altura, historial.ALTURA_FUSION)

    def test_las_series_que_faltan_estan_declaradas(self):
        self.assertEqual(
            set(historial.SERIES_QUE_FALTAN),
            {"blobs_por_bloque", "gas_usado_sobre_limite", "dificultad_de_la_red"},
        )


class LaPresionReal(unittest.TestCase):
    """Medición 1b · lo que la serie de dificultad vino a contestar.

    El informe anterior declaraba abierta esta pregunta: la bomba varió 16x en sus
    propias unidades, pero *cuál de las dos lecturas importa* dependía de un dato
    que no estaba. Ahora está, y contesta — en contra de la lectura optimista.

    Se saltea si falta la serie, y eso no es una excepción a una invariante: es una
    medición que depende de un dato externo. Sin el dato no se estima, se dice.
    """

    def setUp(self):
        self.presiones = replay.presion_de_la_bomba()
        if not self.presiones:
            self.skipTest("falta la serie: python herramientas/traer_datos.py dificultad")

    def test_hay_presion_para_las_seis_decisiones(self):
        self.assertEqual(len(self.presiones), len(historial.RETRASOS))

    def test_solo_uno_de_los_seis_ocurrio_bajo_presion_real(self):
        """**Cinco de seis forks fueron preventivos**, no reactivos."""
        sentidos = [p.fork for p in self.presiones if p.se_sentia]
        self.assertEqual(sentidos, ["Byzantium"])

    def test_muir_glacier_estaba_al_borde_y_la_historia_lo_confirma(self):
        """Fue un fork de emergencia porque los bloques treparon a ~17 s.

        El modelo, que no sabe nada de esa historia, da 17,2 s de piso. Es la
        validación externa del cálculo: no se ajustó nada para que diera eso.
        """
        muir = next(p for p in self.presiones if p.fork == "Muir Glacier")
        self.assertAlmostEqual(muir.escalones, 0.916, places=2)
        self.assertAlmostEqual(muir.piso_de_tiempo_de_bloque, 17.2, places=1)

    def test_la_dispersion_en_presion_es_peor_que_en_unidades_de_bomba(self):
        """41x contra 16x: la lectura optimista era la incompleta."""
        escalones = [p.escalones for p in self.presiones]
        dispersion = max(escalones) / min(escalones)
        self.assertGreater(dispersion, 40)
        self.assertLess(dispersion, 42)

    def test_la_serie_bajada_tiene_procedencia_adentro(self):
        from herramientas.traer_datos import leer_serie

        comentarios, filas = leer_serie(replay.RUTA_DIFICULTAD)
        self.assertGreater(len(filas), 1_000)
        junto = " ".join(comentarios)
        self.assertIn("eth_getBlockByNumber", junto)
        self.assertIn("muestreada", junto)


class ElCasoDeLosBlobs(unittest.TestCase):
    """La verdad de base del caso 2, verificada. Falta el observable, no el dato."""

    def test_las_cuatro_recalibraciones_estan_y_en_orden(self):
        schedule = historial.BLOB_SCHEDULE
        self.assertEqual(len(schedule), 4)
        marcas = [p.marca_activacion for p in schedule]
        self.assertEqual(marcas, sorted(marcas))

    def test_el_target_solo_sube_y_nunca_pasa_el_maximo(self):
        targets = [p.target for p in historial.BLOB_SCHEDULE]
        self.assertEqual(targets, sorted(targets))
        for parametros in historial.BLOB_SCHEDULE:
            self.assertLess(parametros.target, parametros.maximo)

    def test_la_capacidad_se_multiplico_y_eso_es_el_caso(self):
        primero, ultimo = historial.BLOB_SCHEDULE[0], historial.BLOB_SCHEDULE[-1]
        self.assertEqual((primero.target, primero.maximo), (3, 6))
        self.assertEqual((ultimo.target, ultimo.maximo), (14, 21))

    def test_cada_parametro_dice_de_donde_salio(self):
        for parametros in historial.BLOB_SCHEDULE:
            self.assertIn("config.go", parametros.procedencia)
            self.assertTrue(parametros.eip.startswith("EIP-"))

    def test_la_fecha_se_deriva_del_timestamp_y_no_se_transcribe(self):
        self.assertEqual(historial.BLOB_SCHEDULE[0].fecha, "2024-03-13")
        self.assertEqual(
            historial.fecha_utc(historial.BLOB_SCHEDULE[1].marca_activacion),
            historial.BLOB_SCHEDULE[1].fecha,
        )


class LaDiferenciaQuedaEscrita(unittest.TestCase):
    """*"Lo que no cuenta es no poder explicar la diferencia."*

    El criterio de la fase no lo cierra un número: lo cierra un texto. Esta prueba
    lo vuelve verificable — el informe existe y nombra las seis decisiones.
    """

    def test_hay_resultados_y_nombran_las_seis(self):
        resultados = RAIZ / "herramientas" / "RESULTADOS.md"
        self.assertTrue(resultados.exists(), "falta herramientas/RESULTADOS.md")
        texto = resultados.read_text(encoding="utf-8")
        for retraso in historial.RETRASOS:
            self.assertIn(retraso.fork, texto)
        self.assertIn("VERIFICADO", texto)
        self.assertIn("MainnetChainConfig", texto)


if __name__ == "__main__":
    unittest.main()
