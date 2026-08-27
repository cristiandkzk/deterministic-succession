"""La auditoría de `protocolo/UNIDADES.md`, como criterios.

**La pregunta:** para cada cantidad que el protocolo guarda o declara, ¿su significado depende
de un parámetro que una transición puede mover?

Existe porque las Fases 4 y 6 encontraron cada una un defecto que **no violaba ninguna de las
cinco invariantes** —el techo de páginas constante y el depósito en byte-épocas— y los dos eran
la misma forma: **I3 protege los bytes; nada protege lo que los bytes significan.**
"""

from __future__ import annotations

import unittest

from estado import permanencia as perm
from protocolo import genesis as g


def con(**cambios):
    from protocolo.generacion import Params, Ruleset

    internos = dict(g.PARAMS_INICIALES.internos)
    internos.update(cambios)
    return Ruleset(params=Params(2, internos, g.RULESET_INICIAL.formatos), h0=bytes(32))


#: Los tres parámetros que redefinen unidades de otras cosas. Los demás del espacio
#: —emisión, tamaño de bloque, fee— no le cambian el significado a nada guardado.
REDEFINEN_UNIDADES = ("tiempo_bloque_ms", "tx_por_bloque", "paginas_vm")


class LoQueYaSeCorrigio(unittest.TestCase):
    """Las dos correcciones que salieron de construir, fijadas para que no vuelvan."""

    def test_el_deposito_no_lo_reinterpreta_ninguna_transicion(self):
        """C20/B3. Se prueba contra **los tres** parámetros que redefinen unidades, no
        sólo contra el que falló: un arreglo verificado contra su propio caso prueba poco.
        """
        e = perm.Entrada(identificador=b"x", dueno=b"a")
        e.recargar(10)
        antes = e.segundos_restantes()

        for ms in (1_000, 12_000, 60_000):
            con(tiempo_bloque_ms=ms)
            self.assertEqual(e.segundos_restantes(), antes)
        for tx in (1, 100, 10_000):
            con(tx_por_bloque=tx)
            self.assertEqual(e.segundos_restantes(), antes)
        for pg in sorted(g.R_DECLARADO_POR_PAGINAS):
            con(paginas_vm=pg)
            self.assertEqual(e.segundos_restantes(), antes)

    def test_el_techo_de_paginas_encarece_en_vez_de_excluir(self):
        """C18. Toda primitiva tiene algún punto de la curva donde entra."""
        for paginas in (26, 40, 65, 300, 1_000):
            punto = min(
                (p for p in g.R_DECLARADO_POR_PAGINAS if p >= paginas), default=None
            )
            self.assertIsNotNone(punto, f"{paginas} páginas quedan sin precio")

    def test_el_techo_de_pasos_se_deriva_a_proposito(self):
        """Que el techo cambie con el ruleset **no** es este defecto: es el mecanismo. La
        diferencia es que se recalcula en cada generación en vez de quedar congelado con
        una unidad vieja."""
        base = g.techo_vigente(g.RULESET_INICIAL)
        self.assertNotEqual(base, g.techo_vigente(con(tx_por_bloque=30)))
        self.assertNotEqual(base, g.techo_vigente(con(paginas_vm=512)))


class LoQueSigueAbierto(unittest.TestCase):
    """`Δ`, y las dos cosas distintas que tiene mal.

    **Estas pruebas afirman el defecto, no lo arreglan.** Se caen el día que se decida qué
    vale `Δ`, y esa caída es la señal de que hay que reescribirlas — no un fallo.
    """

    def test_delta_esta_en_bloques_y_el_aviso_real_varia_sesenta_veces(self):
        """El mismo defecto que B3, en el mecanismo central en vez de en la permanencia."""
        rango = g.ESPACIO_INTERNO["tiempo_bloque_ms"]
        for clase, delta in g.DELTA_POR_CLASE.items():
            corto = delta * rango.minimo / 1_000
            largo = delta * rango.maximo / 1_000
            self.assertAlmostEqual(largo / corto, 60, places=0, msg=clase)

    def test_el_aviso_a_los_valores_actuales_es_de_minutos(self):
        """§10.1 dice que `Δ` *compra seguridad de integración con tiempo de reacción*.

        A los valores que están en Genesis compra seis minutos y cuarenta y ocho segundos.
        **La tensión que §10.1 describe no existe a estos números**: los dos valores están
        del mismo lado, el de *ningún aviso*.
        """
        ms = g.RULESET_INICIAL.interno("tiempo_bloque_ms")
        minutos = {
            clase: delta * ms / 1_000 / 60 for clase, delta in g.DELTA_POR_CLASE.items()
        }
        self.assertLess(minutos[g.CIRCULACION], 10)
        self.assertLess(minutos[g.CRIPTOGRAFICA], 1)

    def test_lo_que_de_verdad_protege_al_integrador_es_I5(self):
        """Y por eso el número chico no es catastrófico: quien no llegó a soportar la
        generación nueva sigue operando en la anterior y degrada en vez de detenerse.

        Pero entonces `Δ` está haciendo mucho menos de lo que §10.1 le atribuye.
        """
        from protocolo.invariantes import i5_aditiva

        viejo = g.PARAMS_INICIALES
        nuevo = type(viejo)(
            viejo.generacion + 1, dict(viejo.internos), viejo.formatos | {"firma/nueva"}
        )
        i5_aditiva(viejo, nuevo)  # agregar no rompe

        quitando = type(viejo)(
            viejo.generacion + 1, dict(viejo.internos), frozenset()
        )
        with self.assertRaises(Exception):
            i5_aditiva(viejo, quitando)


class LaAuditoriaSeMantieneAlDia(unittest.TestCase):
    """Si aparece un parámetro nuevo en el espacio, hay que volver a pasar el barrido."""

    def test_el_espacio_no_crecio_sin_auditar(self):
        self.assertEqual(
            set(g.ESPACIO_INTERNO),
            {
                "emision_por_bloque",
                "tamano_bloque_kib",
                "tiempo_bloque_ms",
                "fee_quema_ppm",
                "tx_por_bloque",
                "paginas_vm",
            },
            "cambió el espacio: rehacer el barrido de protocolo/UNIDADES.md",
        )

    def test_los_que_redefinen_unidades_siguen_siendo_tres(self):
        for nombre in REDEFINEN_UNIDADES:
            self.assertIn(nombre, g.ESPACIO_INTERNO)
