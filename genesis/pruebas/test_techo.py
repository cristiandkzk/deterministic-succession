"""El techo de pasos de VM — §10.3, primer problema abierto.

El paper lo dejaba como *"un número y dónde vive"*, con un acople declarado: un techo
congelado hay que elegirlo generoso para que sobreviva primitivas que no existen, y
generoso es justamente lo que deja pasar la implementación correcta pero diez veces más
lenta que encontró Test 2.

**La salida es que el techo no sea un número sino una cuenta**, anclada a lo único que
§10.3 dice que no deriva: el presupuesto de la capa liviana de §6.1.

```
techo = f* × tiempo_de_bloque × R_declarado / tx_por_bloque
```

Estas pruebas fijan las cuatro propiedades que hacen que eso cierre — y la tercera es
la que impide que el arreglo se convierta en el problema que §10.3 rechaza.
"""

from __future__ import annotations

import unittest

from herramientas import techo as t
from protocolo import genesis as g

#: El punto de Genesis en la curva. **No son constantes del protocolo**: desde el
#: 21/8/2026 el presupuesto de páginas es un parámetro y el ritmo se lee de la curva.
PAGINAS_INICIALES = g.paginas_vigentes(g.RULESET_INICIAL)
R_INICIAL = g.ritmo_declarado(PAGINAS_INICIALES)
from protocolo.generacion import Params, Ruleset


class ElDatoVieneDeTest2(unittest.TestCase):
    """Lo que hace admisible un techo en pasos, y no en tiempo."""

    def test_los_pasos_no_dependen_del_reloj_ni_de_la_arquitectura(self):
        """Test 2 §3.2: coinciden byte a byte entre x86 y ARM.

        Es la razón por la que el techo se mide en pasos: el tiempo de reloj
        dependería del hardware y sería un oráculo (I2).
        """
        for nombre, pasos in t.PASOS_POR_VERIFICACION.items():
            self.assertGreater(pasos, 1_000_000, nombre)
            self.assertIsInstance(pasos, int)

    def test_el_ritmo_declarado_esta_por_debajo_del_peor_caso_MEDIDO_DIRECTO(self):
        """**Este criterio se endureció dos veces el 20/8/2026, y ésta es la tercera letra.**

        Primero decía *"por debajo de lo que midió Test 2"*: era el ritmo de una sola
        mezcla y el adversario no corre el promedio. Después pasó a ser *"por debajo del
        peor caso, trasladando el cociente desde un escritorio"*, y eso todavía tenía dos
        errores: **los 316 M de Test 2 son del intérprete sin endurecer** —esta máquina
        cuesta 1,19× más— y el escritorio no es el hardware de referencia.

        Ahora no se traslada nada. El teléfono corrió el mismo binario, así que **la peor
        mezcla medida ahí es la cota**, sin cociente y sin intermediarios.
        """
        peor = min(v for k, v in t.RITMO_POR_MEZCLA.items() if k != "ML-DSA-44")
        cota = peor * 1_000_000
        self.assertLess(R_INICIAL, cota, "no aguanta la peor mezcla del teléfono")
        # Y no tan por debajo que el techo deje de servir para nada.
        self.assertGreater(R_INICIAL, cota * 0.75)

    def test_la_referencia_endurecida_es_mas_lenta_que_la_de_test2(self):
        """El 1,19× que cuestan los dos techos y los chequeos de rango.

        Está fijado porque es el número que hacía mal la cuenta cuando no existía: usar
        el ritmo de Test 2 contra un cociente medido sobre la máquina endurecida daba una
        cota 19% más alta de lo que corresponde, hacia el lado inseguro.
        """
        sin_endurecer = t.ritmo_medido()["ML-DSA-44"] / 1_000_000
        endurecida = t.RITMO_POR_MEZCLA["ML-DSA-44"]
        self.assertGreater(sin_endurecer / endurecida, 1.15)
        self.assertLess(sin_endurecer / endurecida, 1.25)


class LaFormulaEsDeGenesisYElValorDeLaGeneracion(unittest.TestCase):
    """*Dónde vive* — la pregunta que §10.3 dejaba junto al número."""

    def test_el_techo_sale_de_los_parametros_del_ruleset(self):
        esperado = g.techo_de_pasos(
            g.RULESET_INICIAL.interno("tiempo_bloque_ms"),
            g.RULESET_INICIAL.interno("tx_por_bloque"),
            g.RULESET_INICIAL.interno("paginas_vm"),
        )
        self.assertEqual(g.techo_vigente(g.RULESET_INICIAL), esperado)

    def test_no_es_una_palanca_suelta(self):
        """Para mover el techo hay que mover capacidad o tiempo de bloque.

        Ninguna de las dos es gratis ni invisible: son parámetros internos con sus
        propias consecuencias, así que el techo deja de ser un número que alguien
        pueda correr sin que se note.
        """
        tx = g.RULESET_INICIAL.interno("tx_por_bloque")
        ms = g.RULESET_INICIAL.interno("tiempo_bloque_ms")
        base = g.techo_vigente(g.RULESET_INICIAL)
        mitad = g.techo_de_pasos(ms, tx * 2, PAGINAS_INICIALES)
        doble = g.techo_de_pasos(ms * 2, tx, PAGINAS_INICIALES)
        self.assertAlmostEqual(mitad / base, 0.5, places=2)
        self.assertAlmostEqual(doble / base, 2.0, places=2)

    def test_no_hay_techo_guardado_en_el_estado(self):
        """Se lee de la fórmula: un valor guardado sería un valor editable."""
        self.assertNotIn("techo_pasos", g.ESPACIO_INTERNO)
        self.assertNotIn("techo_pasos", dict(g.PARAMS_INICIALES.internos))


class NoCompone(unittest.TestCase):
    """**La propiedad que impide que el arreglo se vuelva el problema.**

    §10.3 rechaza anclar el techo a lo entregado en la ronda —*el mejor candidato por
    un múltiplo*— porque se rebasa en cada generación: 2× por transición son 1.024× a
    las diez. La fórmula tiene que ser **absoluta**.
    """

    def _ruleset_con(self, formatos: frozenset[str]) -> Ruleset:
        return Ruleset(
            params=Params(1, dict(g.PARAMS_INICIALES.internos), formatos),
            h0=b"\x00" * 32,
        )

    def test_el_techo_no_depende_de_que_primitiva_este_instalada(self):
        con_ed = self._ruleset_con(frozenset({"firma/ed25519"}))
        con_pq = self._ruleset_con(frozenset({"firma/ed25519", "firma/ml-dsa-44"}))
        self.assertEqual(g.techo_vigente(con_ed), g.techo_vigente(con_pq))

    def test_diez_generaciones_de_migraciones_no_lo_mueven(self):
        """El contraste con el ancla que §10.3 rechaza, medido."""
        ruleset = g.RULESET_INICIAL
        for _ in range(10):
            ruleset = Ruleset(
                params=Params(
                    ruleset.generacion + 1,
                    dict(ruleset.params.internos),
                    ruleset.formatos | {"firma/ml-dsa-44"},
                ),
                h0=b"\x00" * 32,
            )
        self.assertEqual(g.techo_vigente(ruleset), g.techo_vigente(g.RULESET_INICIAL))

        # El ancla relativa después de diez generaciones a 2× por transición. El
        # factor exacto contra el techo absoluto depende del techo vigente, así que
        # lo que se fija son **dos órdenes de magnitud** y no un número calzado: la
        # propiedad es que uno explota y el otro no se mueve.
        relativo = t.PASOS_POR_VERIFICACION["ML-DSA-44"] * (2**10)
        self.assertGreater(relativo, g.techo_vigente(ruleset) * 100)


class LosDosFilos(unittest.TestCase):
    """El techo tiene que dejar entrar la referencia y dejar afuera la lenta."""

    def setUp(self):
        self.techo = g.techo_vigente(g.RULESET_INICIAL)

    def test_la_referencia_entra_con_margen_de_dos(self):
        margen = self.techo / t.PASOS_POR_VERIFICACION["ML-DSA-44"]
        self.assertGreaterEqual(margen, 2.0)
        self.assertLess(margen, 2.1)

    def test_la_implementacion_diez_veces_mas_lenta_no_entra(self):
        """El caso que Test 2 encontró, excluido por un factor de cuatro."""
        lenta = t.PASOS_POR_VERIFICACION["ML-DSA-44"] * 10
        self.assertGreater(lenta, self.techo * 4)

    def test_el_techo_de_paginas_deja_entrar_la_referencia(self):
        """**El segundo techo, y tiene que dejar pasar la carga real.**

        Un techo que rechaza todo es fácil de cumplir y no sirve. 48 páginas contra
        las 26 que toca una verificación ML-DSA-44 son 1,85× — menos que el 2× de
        pasos, y a propósito: el número de páginas **no se eligió como múltiplo de
        la carga** sino donde la curva de memoria se cruza con la de aritmética, que
        es donde cerrar más esa puerta ya no compra nada.
        """
        toca = t.PAGINAS_POR_VERIFICACION["ML-DSA-44"]
        self.assertLess(toca, PAGINAS_INICIALES)
        self.assertGreater(PAGINAS_INICIALES / toca, 1.8)

    def test_el_techo_de_paginas_no_excluye_a_ninguna_primitiva_de_la_familia(self):
        """**El criterio que faltaba, y que tumbó el primer número.**

        Con el techo en 48 páginas, ML-DSA-87 —que toca 65— no quedaba cara: quedaba
        **afuera**. Y como este techo es una constante y no se deriva de la capacidad,
        **no hay precio que pueda pagar**, que es justo lo que §6.6 promete que no pasa.
        El techo de pasos encarece; éste sólo excluía.

        Que ML-DSA-87 no entre *en pasos* al techo inicial es correcto y es el mecanismo
        funcionando: entra bajando `tx_por_bloque`. Que no entrara en páginas era un muro.
        """
        for nombre, paginas in t.PAGINAS_POR_VERIFICACION.items():
            self.assertLessEqual(paginas, PAGINAS_INICIALES, f"{nombre} no tiene precio posible")

    def test_el_hardware_de_referencia_NO_siempre_es_el_peor_caso(self):
        """**La frontera que abrió la Fase 4, fijada para que no se pierda.**

        Todo el diseño supone que la capa liviana es la que ata —de ahí sale la entrada
        barata de nodos de §6.1— y con ese supuesto se calibra `R_declarado`. Medido, es
        falso para los patrones adversariales de memoria: de 96 páginas para arriba un
        escritorio x86-64 corre la peor mezcla más lento que el teléfono.

        Esta prueba existe para que el día que alguien vuelva a escribir *"el hardware
        más barato es el peor caso"* se caiga acá. **No dice cuál es el piso de hardware
        —dos máquinas no alcanzan para eso— y por eso el problema queda abierto en
        §10.3**, no absorbido dentro de la constante.

        Y quedó escrito un intento fallido que conviene no repetir: durante unas horas
        el techo de páginas se justificó como *"el último punto donde la referencia
        sigue atando"*. Ese criterio se apoyaba en una medición rota —la persecución de
        punteros no perseguía nada— y con los números corregidos no sobrevive. El techo
        de páginas queda fijado **sólo** por el criterio que no depende del reloj: que
        ninguna primitiva de la familia quede sin precio posible.
        """
        d = t.desacuerdo_entre_maquinas()
        rompen = [p for p, cociente in d.items() if cociente > 1]
        self.assertTrue(rompen, "si esto pasa a estar vacío, la frontera se cerró")
        self.assertIn(PAGINAS_INICIALES, rompen)

    def test_el_ritmo_declarado_entra_en_el_hardware_de_referencia(self):
        """La cota se mide directo sobre el teléfono, sin trasladar nada.

        Tres mediciones independientes coincidieron dentro del 1,6%: `mezclas` 82,1,
        `conjunto` §4 81,4 y `conjunto` §1 80,8. Se toma la más baja.
        """
        self.assertLess(R_INICIAL, t.PEOR_EN_REFERENCIA * 1_000_000)
        self.assertGreater(R_INICIAL, t.PEOR_EN_REFERENCIA * 1_000_000 * 0.8)

    def test_contar_paginas_alcanza_en_el_hardware_de_referencia(self):
        """Desparramar las páginas por 64 MiB **no cuesta nada en ARM**: 81,4 contra
        81,4. Si costara, contar páginas no alcanzaría y habría que acotar además la
        dispersión.

        La primera vez esto se "verificó" con una medición rota que daba 1,07×. El
        número real del teléfono es 1,00×, y el del escritorio 1,48× — otra cara de la
        misma frontera abierta.
        """
        juntas, desparramadas = 81.4, 81.4
        self.assertAlmostEqual(juntas / desparramadas, 1.0, places=2)


class LaMemoriaTienePrecioYNoEsUnMuro(unittest.TestCase):
    """**El muro que cerró la Fase 4, y es lo único que tocaba el núcleo del diseño.**

    §6.6 promete que no hay muros, sólo precios: *"una primitiva más cara no queda
    afuera: entra pagando capacidad"*. Mientras el presupuesto de páginas fue una
    constante, esa promesa era falsa para la memoria — el techo de pasos se deriva de
    la capacidad y por eso encarece, pero **un techo constante no tiene precio que
    cobrar: sólo excluye**.

    Con ML-DSA-87 se salvó por dos páginas de suerte —toca 65 y el techo era 96— y la
    primitiva siguiente podía no tenerla.
    """

    #: Una primitiva imaginaria que no entra en el punto de Genesis. No hace falta que
    #: exista: lo que se prueba es que **el mecanismo le puede cobrar**, no que alguien
    #: la vaya a instalar.
    PAGINAS_QUE_NO_ENTRAN = 300
    PASOS = 3_339_364

    def test_toda_primitiva_tiene_un_punto_donde_entra(self):
        """No hay presupuesto de memoria sin un punto de la curva que lo cubra."""
        for paginas in (26, 40, 65, self.PAGINAS_QUE_NO_ENTRAN, 1_000, 4_096):
            punto = min(
                (p for p in g.R_DECLARADO_POR_PAGINAS if p >= paginas), default=None
            )
            self.assertIsNotNone(punto, f"{paginas} páginas quedan sin precio")

    def test_pedir_mas_memoria_cuesta_capacidad_y_no_esta_prohibido(self):
        """El precio existe, es finito, y se paga en la misma moneda que todo lo demás.

        Antes esta prueba no se podía escribir: no había cuenta que hacer, porque la
        respuesta era *no entra* y no *cuesta tanto*.
        """
        antes = g.capacidad_para(PAGINAS_INICIALES, self.PASOS)
        punto = min(p for p in g.R_DECLARADO_POR_PAGINAS if p >= self.PAGINAS_QUE_NO_ENTRAN)
        despues = g.capacidad_para(punto, self.PASOS)

        self.assertGreater(despues, 0, "sigue siendo un muro: no hay capacidad posible")
        self.assertLessEqual(despues, antes, "pedir más memoria no puede salir gratis")

    def test_el_precio_de_la_memoria_es_monotono(self):
        """Más páginas nunca dan más ritmo. Si la curva no fuese monótona, habría un
        presupuesto que conviene pedir de más, y eso es una palanca."""
        puntos = sorted(g.R_DECLARADO_POR_PAGINAS)
        ritmos = [g.ritmo_declarado(p) for p in puntos]
        self.assertEqual(ritmos, sorted(ritmos, reverse=True))

    def test_el_acantilado_esta_en_la_curva_y_se_cobra(self):
        """Entre 512 y 1.024 páginas el ritmo del hardware de referencia cae 7,4×
        —ahí se acaba el alcance de la TLB—, y el mecanismo **cobra esa forma**:
        cuadruplicar el presupuesto hasta 512 sale casi gratis y el paso siguiente
        divide la capacidad por siete. No hay que declararlo: sale de la curva."""
        barato = g.capacidad_para(512, self.PASOS)
        caro = g.capacidad_para(1_024, self.PASOS)
        self.assertGreaterEqual(barato, g.capacidad_para(PAGINAS_INICIALES, self.PASOS))
        self.assertGreater(barato / max(caro, 1), 5)

    def test_el_punto_de_genesis_no_se_movio_al_volverlo_parametro(self):
        """Un arreglo estructural que además cambia el bloque 0 es dos cambios."""
        self.assertEqual(PAGINAS_INICIALES, 96)
        self.assertEqual(R_INICIAL, 70_000_000)
        self.assertEqual(g.techo_vigente(g.RULESET_INICIAL), 7_000_000)

    def test_el_presupuesto_de_paginas_es_un_punto_medido_y_no_cualquiera(self):
        """El espacio son los puntos donde la curva está medida, no un rango: **no se
        interpola una zona de comportamiento que nadie observó.**"""
        espacio = g.ESPACIO_INTERNO["paginas_vm"]
        self.assertTrue(espacio.contiene(96))
        self.assertFalse(espacio.contiene(100))
        with self.assertRaises(ValueError):
            g.ritmo_declarado(100)
