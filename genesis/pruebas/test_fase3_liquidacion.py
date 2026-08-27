"""Fase 3 · el criterio de aprobado, escrito antes de correrlo.

Los tres puntos que el `ROADMAP.md` fijó, uno por clase:

1. **doble gasto imposible por el lock, sin orden global**;
2. **la doble firma publica la clave privada** — verificado con dos firmas y una
   resta;
3. **bajo carga adversarial con `N` nodos, la cola drena más rápido de lo que se
   llena**, y el margen medido se compara contra los diez nodos PoD que predice
   §6.3. *Si hacen falta cien, la predicción del paper está mal y hay que decirlo.*

El tercero no da cien: da **once** sin coordinación de ninguna clase, **diez** con
partición perfecta —que exige saber cuántos nodos hay— e **infinito** con la regla que
cualquiera escribiría. Está medido acá y en `herramientas/cola.py`.
"""

from __future__ import annotations

import unittest

from estado.cuentas import Libro, SaldoInsuficiente
from liquidacion import doble_firma as df
from liquidacion.impugnacion import (
    AZAR,
    MAS_VIEJA,
    POR_HASH,
    crece_sin_techo,
    espera_media,
    simular,
)
from liquidacion.oferta import Mercado, OfertaInvalida

CLAVE = 0x5EC1E7A_C0FFEE_123456789ABCDEF


def libro_con(**saldos: int) -> Libro:
    libro = Libro()
    for nombre, monto in saldos.items():
        libro.acreditar(nombre, monto)
    return libro


class ElDobleGastoLoImpideElLock(unittest.TestCase):
    """*"Doble gasto imposible por el lock, sin orden global."*"""

    def setUp(self):
        self.libro = libro_con(alice=100)
        self.mercado = Mercado(self.libro)

    def test_los_mismos_fondos_no_se_comprometen_dos_veces(self):
        self.mercado.publicar("o1", "alice", 100, vence_en=50)
        with self.assertRaises(SaldoInsuficiente):
            self.mercado.publicar("o2", "alice", 100, vence_en=50)

        self.assertEqual(self.libro.disponible("alice"), 0)
        self.assertEqual(self.libro.cuenta("alice").saldo, 100)  # sigue siendo suyo
        self.assertIsNone(self.libro.motivo_inconsistente())

    def test_no_hace_falta_decidir_cual_va_primero(self):
        """Nadie arbitra: al segundo no le alcanza, y eso es todo el mecanismo."""
        self.mercado.publicar("o1", "alice", 60, vence_en=50)
        self.mercado.publicar("o2", "alice", 40, vence_en=50)
        with self.assertRaises(SaldoInsuficiente):
            self.mercado.publicar("o3", "alice", 1, vence_en=50)

    def test_una_oferta_abierta_la_toma_uno_solo(self):
        """El lock es lo que la vuelve exclusiva, no un turno ni un candado."""
        self.mercado.publicar("trabajo", "alice", 100, vence_en=50)
        self.mercado.aceptar("trabajo", "nodo-1", altura=1)
        with self.assertRaises(OfertaInvalida):
            self.mercado.aceptar("trabajo", "nodo-2", altura=1)

    def test_lo_que_vence_vuelve_al_disponible(self):
        self.mercado.publicar("o1", "alice", 100, vence_en=10)
        self.assertEqual(self.libro.disponible("alice"), 0)
        self.mercado.vencer(altura=10)
        self.assertEqual(self.libro.disponible("alice"), 100)
        self.assertIsNone(self.libro.motivo_inconsistente())


class NoHayOrdenGlobal(unittest.TestCase):
    """La otra mitad del criterio, y la que se olvida.

    *Sin orden global* no quiere decir *el orden está indefinido*: quiere decir que
    dos interacciones que no comparten colateral **dan el mismo estado en cualquier
    orden**. Eso es falsable con dos huellas.
    """

    def _correr(self, orden: list[tuple[str, str, int]]) -> bytes:
        libro = libro_con(alice=100, bob=100)
        mercado = Mercado(libro)
        for identidad, quien, monto in orden:
            mercado.publicar(identidad, quien, monto, vence_en=50)
            mercado.aceptar(identidad, "carol", altura=1)
            mercado.liquidar(identidad, altura=1)
        return libro.huella()

    def test_dos_interacciones_disjuntas_conmutan(self):
        primero = self._correr([("a", "alice", 30), ("b", "bob", 40)])
        segundo = self._correr([("b", "bob", 40), ("a", "alice", 30)])
        self.assertEqual(primero, segundo)

    def test_cada_cuenta_lleva_su_propia_secuencia(self):
        libro = libro_con(alice=10, bob=10)
        self.assertEqual(libro.avanzar_indice("alice"), 0)
        self.assertEqual(libro.avanzar_indice("alice"), 1)
        self.assertEqual(libro.avanzar_indice("bob"), 0)  # bob no se enteró
        self.assertEqual(libro.cuenta("alice").indice, 2)


class LaDobleFirmaPublicaLaClave(unittest.TestCase):
    """*"La doble firma publica la clave privada y cualquiera puede barrer el saldo
    — verificado con dos firmas y una resta."*"""

    def setUp(self):
        self.publica = df.clave_publica(CLAVE)

    def test_una_firma_normal_verifica(self):
        firma = df.firmar(CLAVE, b"pagar 10 a bob", indice=7)
        self.assertTrue(df.verificar(self.publica, b"pagar 10 a bob", firma))
        self.assertFalse(df.verificar(self.publica, b"pagar 99 a bob", firma))

    def test_firmar_dos_cosas_en_el_mismo_indice_publica_la_clave(self):
        una = df.firmar(CLAVE, b"pagar 10 a bob", indice=7)
        otra = df.firmar(CLAVE, b"pagar 10 a carol", indice=7)

        self.assertEqual(una.r, otra.r, "el nonce se deriva del índice: tiene que repetirse")

        recuperada = df.recuperar_privada(
            b"pagar 10 a bob", una, b"pagar 10 a carol", otra
        )
        self.assertEqual(recuperada, CLAVE % df.Q)

    def test_cualquiera_puede_hacerlo_con_lo_que_esta_en_la_cadena(self):
        """No hace falta ningún secreto: sólo los dos mensajes y las dos firmas."""
        una = df.firmar(CLAVE, b"m1", indice=3)
        otra = df.firmar(CLAVE, b"m2", indice=3)
        recuperada = df.recuperar_privada(b"m1", una, b"m2", otra)
        self.assertTrue(
            df.verificar(df.clave_publica(recuperada), b"barrido", df.firmar(recuperada, b"barrido", 99))
        )

    def test_indices_distintos_no_filtran_nada(self):
        una = df.firmar(CLAVE, b"m1", indice=3)
        otra = df.firmar(CLAVE, b"m2", indice=4)
        self.assertNotEqual(una.r, otra.r)
        self.assertIsNone(df.recuperar_privada(b"m1", una, b"m2", otra))

    def test_firmar_el_mismo_mensaje_dos_veces_no_es_doble_firma(self):
        una = df.firmar(CLAVE, b"m1", indice=3)
        otra = df.firmar(CLAVE, b"m1", indice=3)
        self.assertEqual(una, otra)
        self.assertIsNone(df.recuperar_privada(b"m1", una, b"m1", otra))

    def test_el_grupo_se_rederiva_y_no_se_cree(self):
        """La misma disciplina que el canario: derivar, no elegir."""
        self.assertEqual(df.derivacion_del_grupo(), (df.J, df.P, df.G))
        self.assertEqual(pow(df.G, df.Q, df.P), 1)


class LaColaNoSatura(unittest.TestCase):
    """*"Bajo carga adversarial con `N` nodos, la cola drena más rápido de lo que se
    llena, y el margen medido se compara contra los diez nodos PoD que predice §6.3.
    Si hacen falta cien, la predicción del paper está mal y hay que decirlo."*

    **No hacen falta cien: hace falta uno más, y sólo si los nodos no se pisan.** La
    fórmula supone que se reparten la cola, y §6.3 no dice cómo — no puede, porque no
    hay conjunto de validadores y ningún nodo sabe cuántos son.

    > **Y hay una trampa de medición que estas pruebas fijan a propósito.** La primera
    > versión midió el `N` crítico con corridas de 80 bloques y dio 13. Era un
    > artefacto: con selección al azar el backlog **se estabiliza** —a mayor cola menos
    > se pisan los nodos y el desagüe sube hasta igualar la canilla—, así que una
    > corrida corta lo agarra antes del equilibrio. Medido con dos largos, el número
    > real es 11. **Cualquier medición de saturación acá tiene que comparar dos largos.**
    """

    def test_con_particion_perfecta_la_prediccion_da_exacta(self):
        self.assertTrue(crece_sin_techo(9, POR_HASH))
        self.assertFalse(crece_sin_techo(10, POR_HASH))

    def test_sin_coordinacion_hace_falta_un_nodo_mas(self):
        """Once, no trece y no cien: la predicción se corre por uno."""
        self.assertTrue(crece_sin_techo(10, AZAR))
        self.assertFalse(crece_sin_techo(11, AZAR))

    def test_al_azar_el_backlog_se_estabiliza_en_vez_de_crecer(self):
        """Es lo que hace que 11 alcance, y lo que la primera medición no vio."""
        corta, _ = simular(nodos=11, bloques=250, estrategia=AZAR)
        larga, _ = simular(nodos=11, bloques=500, estrategia=AZAR)
        self.assertLess(larga[-1].backlog, corta[-1].backlog * 1.15)
        self.assertLess(espera_media(larga[-1].backlog, 100), 5)

    def test_la_regla_natural_colapsa_el_paralelismo_entero(self):
        """*La más vieja primero* es lo que cualquiera escribiría, y no funciona."""
        self.assertTrue(crece_sin_techo(50, MAS_VIEJA))

        pocos, _ = simular(nodos=1, bloques=60, estrategia=MAS_VIEJA)
        muchos, _ = simular(nodos=50, bloques=60, estrategia=MAS_VIEJA)
        self.assertEqual(
            sum(r.verificadas for r in pocos), sum(r.verificadas for r in muchos)
        )

    def test_y_ahi_la_espera_de_la_legitima_crece_con_la_altura(self):
        """El ataque de censura funcionando: no es una demora fija, es una rampa.

        Con FIFO el backlog crece ~90 por bloque y se drena a 10, así que lo que
        llega en la altura `T` espera del orden de `9·T`. Medido en dos alturas para
        que se vea la pendiente y no un número suelto.
        """
        esperas = []
        for llega_en in (5, 10):
            _, cola = simular(
                nodos=50, bloques=140, estrategia=MAS_VIEJA, legitima_en=llega_en * 100
            )
            esperas.append(cola.espera_de(llega_en * 100))
        self.assertGreater(esperas[0], 40)
        self.assertGreater(esperas[1], esperas[0] * 1.5)

    def test_el_default_no_puede_ser_la_regla_que_colapsa(self):
        """El valor por defecto **es** la decisión de diseño.

        Un implementador que no piense el punto se lleva el default, y con *la más
        vieja primero* la cola satura con cualquier `N`.
        """
        from liquidacion.impugnacion import NodoVerificador

        self.assertEqual(NodoVerificador(0, 0.10).estrategia, AZAR)

    def test_el_trabajo_duplicado_es_lo_que_explica_la_diferencia(self):
        _, natural = simular(nodos=50, bloques=60, estrategia=MAS_VIEJA)
        _, particion = simular(nodos=50, bloques=60, estrategia=POR_HASH)
        self.assertGreater(natural.duplicadas, 20_000)
        self.assertEqual(particion.duplicadas, 0)


if __name__ == "__main__":
    unittest.main()
