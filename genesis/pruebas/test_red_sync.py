"""Los criterios de `red/CRITERIOS.md` — el primer nodo que no produce.

**Hasta acá el proyecto nunca validó nada.** `NodoPoD` sólo producía, así que cada transición
de estado ocurrió por construcción y ningún bloque podía ser inválido jamás.
"""

from __future__ import annotations

import unittest

from nodo.pod import Bloque, NodoPoD
from protocolo import genesis as g
from protocolo.linaje import verificar_linaje
from pruebas.comun import correr_hasta_activar, nodo_emision
from red.sync import BloqueInvalido, mismo_estado, sincronizar, validar_bloque


def cadena_con_conmutacion() -> NodoPoD:
    """Un productor que llegó a conmutar, más unos bloques después."""
    productor = nodo_emision()
    correr_hasta_activar(productor)
    productor.producir(5)
    return productor


def validador() -> NodoPoD:
    """Un nodo vacío, con las mismas reglas y nada más."""
    return nodo_emision()


class R1ProducirYValidarSonCaminosDistintos(unittest.TestCase):
    """Un validador que no puede decir que no, no está validando."""

    def test_existe_un_camino_que_rechaza(self):
        productor = nodo_emision()
        productor.producir(3)
        v = validador()

        # El primero entra.
        validar_bloque(v, productor.cadena[1])
        self.assertEqual(v.altura, 1)

        # Y uno fuera de orden se rechaza en vez de aplicarse.
        with self.assertRaises(BloqueInvalido) as caso:
            validar_bloque(v, productor.cadena[3])
        self.assertIn("altura", caso.exception.motivo)
        self.assertEqual(v.altura, 1, "el rechazo no puede dejar el nodo movido")

    def test_un_bloque_rechazado_deja_el_nodo_intacto(self):
        """Si no, bastaría con mandar basura para envenenar al validador."""
        productor = nodo_emision()
        productor.producir(4)
        v = validador()
        sincronizar(v, productor.cadena[1:3])

        antes = (v.estado.huella(), v.altura, v.generacion, len(v.cadena))
        roto = Bloque(
            altura=3,
            padre=v.cadena[-1].hash(),
            transacciones=(),
            raiz_estado=b"\x00" * 32,
        )
        with self.assertRaises(BloqueInvalido):
            validar_bloque(v, roto)
        self.assertEqual((v.estado.huella(), v.altura, v.generacion, len(v.cadena)), antes)

    def test_no_encadenar_con_la_cabeza_se_rechaza(self):
        productor = nodo_emision()
        productor.producir(2)
        v = validador()
        huerfano = Bloque(altura=1, padre=b"\xff" * 32, transacciones=(), raiz_estado=b"\x00" * 32)
        with self.assertRaises(BloqueInvalido) as caso:
            validar_bloque(v, huerfano)
        self.assertIn("encadena", caso.exception.motivo)


class R2SincronizarLlegaAlMismoEstado(unittest.TestCase):
    """Bit a bit, y cruzando una conmutación sin que nadie se la anuncie."""

    def test_un_nodo_vacio_reconstruye_la_cadena_entera(self):
        productor = cadena_con_conmutacion()
        v = validador()

        veredicto = sincronizar(v, productor.cadena)
        self.assertTrue(veredicto.entera, veredicto.rechazado)
        self.assertEqual(veredicto.aceptados, len(productor.cadena) - 1)
        self.assertTrue(mismo_estado(v, productor))

    def test_el_que_sincroniza_conmuta_solo_en_la_misma_altura(self):
        """**Nadie le dice cuándo.** Lo deriva del estado que él mismo calculó."""
        productor = cadena_con_conmutacion()
        self.assertTrue(productor.conmutaciones)

        v = validador()
        sincronizar(v, productor.cadena)

        self.assertEqual(
            [(c.altura, c.generacion) for c in v.conmutaciones],
            [(c.altura, c.generacion) for c in productor.conmutaciones],
        )
        self.assertEqual(v.generacion, productor.generacion)


class R3ElLinajeSeVerificaContraUnaCadenaAjena(unittest.TestCase):
    """I4 corrió siempre sobre checkpoints que el mismo proceso había creado."""

    def test_el_linaje_del_que_sincroniza_verifica(self):
        productor = cadena_con_conmutacion()
        v = validador()
        sincronizar(v, productor.cadena)

        self.assertTrue(v.cronograma.checkpoints, "no hubo checkpoints que verificar")
        self.assertTrue(verificar_linaje(v.cronograma.checkpoints, g.H0_GENESIS))

    def test_alterar_cualquiera_de_los_tres_insumos_lo_rompe(self):
        """`H0_B = H(H0_A ‖ state_trigger ‖ params)`. **Los tres tienen que pesar**, y se
        prueba uno por uno: si sólo se verificara el encadenado, alterar `state_trigger`
        pasaría y el checkpoint dejaría de comprometer el estado que lo disparó.
        """
        import dataclasses

        productor = cadena_con_conmutacion()
        v = validador()
        sincronizar(v, productor.cadena)
        original = v.cronograma.checkpoints
        self.assertTrue(verificar_linaje(original, g.H0_GENESIS))

        for campo in ("h0", "h0_ancestro", "state_trigger"):
            alterado = dataclasses.replace(original[0], **{campo: bytes(32)})
            checkpoints = [alterado] + list(original[1:])
            self.assertFalse(
                verificar_linaje(checkpoints, g.H0_GENESIS),
                f"alterar {campo} no rompió el linaje",
            )

    def test_y_cambiar_los_parametros_tambien(self):
        """El tercer insumo: el checkpoint compromete **qué ruleset** se activó."""
        import dataclasses

        productor = cadena_con_conmutacion()
        v = validador()
        sincronizar(v, productor.cadena)
        original = v.cronograma.checkpoints

        otros = dataclasses.replace(
            original[0].params,
            internos={**dict(original[0].params.internos), "tx_por_bloque": 99},
        )
        checkpoints = [dataclasses.replace(original[0], params=otros)] + list(original[1:])
        self.assertFalse(verificar_linaje(checkpoints, g.H0_GENESIS))


class R4UnaRaizMentidaSeRechaza(unittest.TestCase):
    """El caso más simple, y por eso el que más importa."""

    def test_un_byte_cambiado_en_la_raiz_alcanza(self):
        productor = nodo_emision()
        productor.producir(3)
        v = validador()

        bueno = productor.cadena[1]
        mentido = Bloque(
            altura=bueno.altura,
            padre=bueno.padre,
            transacciones=bueno.transacciones,
            raiz_estado=bytes([bueno.raiz_estado[0] ^ 1]) + bueno.raiz_estado[1:],
        )
        with self.assertRaises(BloqueInvalido) as caso:
            validar_bloque(v, mentido)
        self.assertIn("raíz", caso.exception.motivo)

    def test_y_una_transaccion_agregada_tambien(self):
        """Cambiar las transacciones cambia el estado, y con él la raíz."""
        productor = nodo_emision()
        productor.producir(2)
        v = validador()

        bueno = productor.cadena[1]
        con_extra = Bloque(
            altura=bueno.altura,
            padre=bueno.padre,
            transacciones=(("gastar_canario",),),
            raiz_estado=bueno.raiz_estado,
        )
        with self.assertRaises(BloqueInvalido):
            validar_bloque(v, con_extra)


class R5LaConmutacionNoSeLeeDelBloque(unittest.TestCase):
    """**El criterio con riesgo real.**

    Un productor malicioso puede activar el ruleset nuevo antes de tiempo. El validador no
    puede obedecerle: tiene que derivar la altura de activación del estado que él mismo
    calculó. Si no, §3 entero descansa en la buena fe del que produce — que es exactamente
    lo que todo el diseño existe para no hacer.
    """

    def test_una_cadena_a_la_que_le_falta_un_bloque_antes_de_conmutar_se_rechaza(self):
        """Sacar un bloque corre la conmutación de altura. El validador, que la deriva,
        computa otro estado y la raíz deja de cerrar."""
        productor = cadena_con_conmutacion()
        altura_conmutacion = productor.conmutaciones[0].altura

        recortada = [b for b in productor.cadena if b.altura != altura_conmutacion - 2]
        v = validador()
        veredicto = sincronizar(v, recortada)
        self.assertFalse(veredicto.entera, "aceptó una cadena con un bloque de menos")

    def test_el_validador_no_conmuta_si_el_disparo_no_ocurrio(self):
        """Un nodo que sólo vio bloques vacíos no puede llegar a la generación 2 por más
        que alguien le mande un bloque que dice que sí."""
        v = validador()
        v.producir(3)
        self.assertEqual(v.generacion, g.RULESET_INICIAL.generacion)
        self.assertFalse(v.conmutaciones)


class R6DosNodosIndependientesProducenLaMismaCadena(unittest.TestCase):
    """Determinismo **entre nodos**, no dentro de uno — que es lo único probado hasta hoy.

    El paralelo es C3 en la Fase 4: la máquina reprodujo bit a bit entre arquitecturas, y
    eso valió porque se corrió en dos lados de verdad.
    """

    def test_hash_por_hash_en_cada_altura(self):
        a, b = nodo_emision(), nodo_emision()
        correr_hasta_activar(a)
        correr_hasta_activar(b)
        a.producir(4)
        b.producir(4)

        self.assertEqual(len(a.cadena), len(b.cadena))
        for x, y in zip(a.cadena, b.cadena):
            self.assertEqual(x.hash(), y.hash(), f"difieren en la altura {x.altura}")
        self.assertTrue(mismo_estado(a, b))

    def test_y_cada_uno_valida_la_cadena_del_otro(self):
        a = cadena_con_conmutacion()
        b = validador()
        self.assertTrue(sincronizar(b, a.cadena).entera)
        c = validador()
        self.assertTrue(sincronizar(c, b.cadena).entera)
