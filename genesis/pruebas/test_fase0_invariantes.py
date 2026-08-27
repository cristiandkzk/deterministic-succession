"""Fase 0 · las cinco invariantes, cada una con su caso que **tiene** que fallar.

Un predicado que sólo se prueba contra lo que ya funciona no prueba nada: pasaría
igual si su cuerpo fuera `return`. Por eso cada invariante lleva acá dos pruebas
—una que pasa y una que rompe— y la que importa es la segunda.
"""

from __future__ import annotations

import unittest

from protocolo import genesis as g
from protocolo import invariantes as inv
from protocolo.generacion import Objeto, Params
from protocolo.invariantes import ViolacionInvariante
from protocolo.serializacion import FlotanteProhibido, codificar, huella
from sucesion.regla import ReglaTransicion


class ReglaConOraculo(ReglaTransicion):
    """El trigger pide un insumo de afuera. La firma sola ya lo delata."""

    nombre = "mala/oraculo"

    def progreso(self, estado, reloj=0) -> int:  # type: ignore[override]
        return estado.emitido

    def umbral(self, estado) -> int:
        return 1

    def params_sucesor(self, estado, ruleset) -> Params:
        return ruleset.params


class ReglaImpura(ReglaTransicion):
    """Pasa el chequeo de firma y falla el de pureza: lee algo que no es estado."""

    nombre = "mala/impura"

    def __init__(self) -> None:
        self.llamadas = 0

    def progreso(self, estado) -> int:
        self.llamadas += 1
        return estado.emitido + self.llamadas

    def umbral(self, estado) -> int:
        return 1

    def params_sucesor(self, estado, ruleset) -> Params:
        return ruleset.params


class ReglaQueEscribe(ReglaTransicion):
    """Devuelve siempre lo mismo, pero deja rastro. Un trigger no puede escribir."""

    nombre = "mala/escribe"

    def progreso(self, estado) -> int:
        estado.quemado += 1
        return estado.emitido

    def umbral(self, estado) -> int:
        return 1

    def params_sucesor(self, estado, ruleset) -> Params:
        return ruleset.params


class I1(unittest.TestCase):
    def test_el_interprete_de_genesis_pasa(self):
        inv.i1_interprete_congelado(g.HUELLA_INTERPRETE)

    def test_otro_interprete_no_es_una_transicion_es_un_fork(self):
        with self.assertRaises(ViolacionInvariante) as caso:
            inv.i1_interprete_congelado(huella("genesis-vm/1", dominio="interprete"))
        self.assertEqual(caso.exception.invariante, "I1")

    def test_el_ruleset_inicial_es_un_punto_del_espacio(self):
        inv.i1_sucesor_en_el_espacio(g.PARAMS_INICIALES)

    def test_un_valor_fuera_de_dominio_no_es_un_punto_del_espacio(self):
        fuera = g.PARAMS_INICIALES.con(tamano_bloque_kib=3_000)
        with self.assertRaises(ViolacionInvariante):
            inv.i1_sucesor_en_el_espacio(fuera)

    def test_agregar_un_parametro_es_cambiar_la_maquina(self):
        internos = dict(g.PARAMS_INICIALES.internos)
        internos["palanca_nueva"] = 1
        with self.assertRaises(ViolacionInvariante):
            inv.i1_sucesor_en_el_espacio(
                Params(1, internos, g.PARAMS_INICIALES.formatos)
            )

    def test_un_formato_que_la_maquina_no_conoce_no_se_puede_activar(self):
        con_formato_inventado = Params(
            1,
            dict(g.PARAMS_INICIALES.internos),
            g.PARAMS_INICIALES.formatos | {"firma/inventada"},
        )
        with self.assertRaises(ViolacionInvariante):
            inv.i1_sucesor_en_el_espacio(con_formato_inventado)


class I2(unittest.TestCase):
    def setUp(self):
        from estado.sintetico import EstadoSintetico

        self.estado = EstadoSintetico()

    def test_un_insumo_de_mas_en_la_firma_es_una_puerta_para_un_oraculo(self):
        with self.assertRaises(ViolacionInvariante) as caso:
            inv.i2_trigger_solo_estado(ReglaConOraculo(), self.estado)
        self.assertEqual(caso.exception.invariante, "I2")

    def test_un_trigger_que_no_es_funcion_del_estado_falla(self):
        with self.assertRaises(ViolacionInvariante):
            inv.i2_trigger_solo_estado(ReglaImpura(), self.estado)

    def test_un_trigger_que_escribe_el_estado_falla(self):
        with self.assertRaises(ViolacionInvariante):
            inv.i2_trigger_solo_estado(ReglaQueEscribe(), self.estado)

    def test_la_aproximacion_no_puede_retroceder(self):
        inv.i2_aproximacion_monotona("ok", [0, 1, 1, 7, 7, 9])
        with self.assertRaises(ViolacionInvariante):
            inv.i2_aproximacion_monotona("mala", [0, 5, 4])

    def test_la_distancia_tiene_que_estar_en_el_estado(self):
        with self.assertRaises(ViolacionInvariante):
            inv.i2_distancia_publicada(self.estado, ["alguna/regla"])


class I3(unittest.TestCase):
    def test_misma_huella_y_mismo_objeto_pasa(self):
        inv.i3_estado_intacto(b"\x01", b"\x01", 7, 7)

    def test_si_el_estado_cambio_no_cruzo_intacto(self):
        with self.assertRaises(ViolacionInvariante) as caso:
            inv.i3_estado_intacto(b"\x01", b"\x02", 7, 7)
        self.assertEqual(caso.exception.invariante, "I3")

    def test_un_estado_reconstruido_es_una_migracion_con_otro_nombre(self):
        with self.assertRaises(ViolacionInvariante):
            inv.i3_estado_intacto(b"\x01", b"\x01", 7, 8)


class I5(unittest.TestCase):
    def test_agregar_un_formato_es_aditivo(self):
        nuevo = Params(
            1,
            dict(g.PARAMS_INICIALES.internos),
            g.PARAMS_INICIALES.formatos | {"firma/ml-dsa-44"},
        )
        inv.i5_aditiva(g.PARAMS_INICIALES, nuevo)

    def test_retirar_un_formato_no_lo_es(self):
        nuevo = Params(
            1,
            dict(g.PARAMS_INICIALES.internos),
            g.PARAMS_INICIALES.formatos - {"firma/ed25519"},
        )
        with self.assertRaises(ViolacionInvariante) as caso:
            inv.i5_aditiva(g.PARAMS_INICIALES, nuevo)
        self.assertEqual(caso.exception.invariante, "I5")

    def test_todo_objeto_lleva_generacion_y_ninguna_es_del_futuro(self):
        inv.i5_objetos_etiquetados([Objeto(0, "recibo/gen0")], generacion_maxima=1)
        with self.assertRaises(ViolacionInvariante):
            inv.i5_objetos_etiquetados([Objeto(3, "recibo/gen0")], generacion_maxima=1)

    def test_un_ruleset_viejo_falla_cerrado_ante_un_formato_nuevo(self):
        """La falla de I5 que importa: ruidosa, no silenciosa."""
        from protocolo.generacion import FormatoDesconocido, decodificar

        objeto_nuevo = Objeto(generacion=1, formato="firma/ml-dsa-44")
        with self.assertRaises(FormatoDesconocido):
            decodificar(objeto_nuevo, g.RULESET_INICIAL)

        # …y el objeto viejo sigue siendo válido, que es la otra mitad de I5.
        decodificar(Objeto(0, "recibo/gen0"), g.RULESET_INICIAL)


class Serializacion(unittest.TestCase):
    """No es una invariante, pero todas dependen de que esto sea determinista."""

    def test_el_flotante_esta_prohibido_desde_el_primer_archivo(self):
        with self.assertRaises(FlotanteProhibido):
            codificar({"tasa": 0.5})

    def test_el_orden_de_insercion_no_cambia_la_huella(self):
        uno = {"a": 1, "b": 2}
        otro = {"b": 2, "a": 1}
        self.assertEqual(codificar(uno), codificar(otro))

    def test_la_codificacion_es_autodelimitada(self):
        self.assertNotEqual(codificar(["ab", "c"]), codificar(["a", "bc"]))

    def test_dominios_distintos_no_colisionan(self):
        self.assertNotEqual(huella(1, dominio="bloque"), huella(1, dominio="estado"))


if __name__ == "__main__":
    unittest.main()
