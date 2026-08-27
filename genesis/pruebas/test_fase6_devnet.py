"""Fase 6 — los criterios de `devnet/CRITERIOS.md`, escritos antes del devnet.

**Lo que esta fase agrega es que las piezas corren juntas.** Cada fase suelta probó su
mecanismo contra un mundo quieto; acá el mundo se mueve mientras el mecanismo corre. El
hallazgo de la fase —B3— es exactamente de esa clase: ninguna prueba de módulo podía verlo,
porque hace falta que una conmutación pase mientras hay depósitos vivos.
"""

from __future__ import annotations

import unittest

from devnet.cadena import Devnet, Registro
from estado import permanencia as perm
from nodo.pod import NodoPoD
from protocolo import genesis as g
from protocolo.generacion import Params, Ruleset
from pruebas.comun import correr_hasta_activar, nodo_emision


def ruleset_con(**cambios) -> Ruleset:
    internos = dict(g.PARAMS_INICIALES.internos)
    internos.update(cambios)
    return Ruleset(
        params=Params(2, internos, g.RULESET_INICIAL.formatos), h0=bytes(32)
    )


def devnet_con_entradas(cuantas: int = 50, epocas: int = 3) -> Devnet:
    d = Devnet(nodo=nodo_emision())
    for k in range(cuantas):
        d.registro.crear(f"obj-{k}".encode(), b"alice", epocas, d.ruleset)
    return d


class B1LaConmutacionBajoCargaNoRompeElEstado(unittest.TestCase):
    """La Fase 1 conmutó sobre un estado quieto. Acá la cadena está haciendo cosas."""

    def test_el_estado_cruza_identico_con_carga_corriendo(self):
        d = devnet_con_entradas()
        correr_hasta_activar(d.nodo)
        self.assertTrue(d.nodo.conmutaciones, "no llegó a conmutar")

        # El conmutador ya verifica I3 por huella e identidad de objeto al conmutar
        # (levanta si el estado se movió), así que llegar hasta acá con la carga
        # corriendo **es** el criterio. Lo que se fija es que la huella quedó registrada
        # y que la generación avanzó.
        conmutacion = d.nodo.conmutaciones[0]
        self.assertEqual(len(conmutacion.huella_estado), 32)
        self.assertEqual(conmutacion.generacion, g.RULESET_INICIAL.generacion + 1)
        self.assertEqual(d.nodo.generacion, conmutacion.generacion)

    def test_ninguna_entrada_cambia_de_estado_por_la_conmutacion(self):
        """Ni se desaloja ni se revive **porque cambió el ruleset**. Lo único que puede
        desalojar es que se agote el depósito."""
        d = devnet_con_entradas(epocas=20)
        vivas_antes = set(d.registro.entradas)
        correr_hasta_activar(d.nodo)
        self.assertEqual(set(d.registro.entradas), vivas_antes)
        self.assertEqual(d.registro.desalojos, 0)


class B2ElCicloDeDesalojoAEscala(unittest.TestCase):
    """La Fase 5 probó el ciclo entrada por entrada. Acá corre con miles."""

    def test_el_ciclo_cierra_para_todas_y_ninguna_se_pierde(self):
        d = devnet_con_entradas(cuantas=500, epocas=2)
        creadas = set(d.registro.entradas)

        for epoca in (1, 2, 3):
            d.registro.cobrar_epoca(epoca, d.ruleset)

        self.assertFalse(d.registro.entradas, "alguna sobrevivió sin depósito")
        self.assertEqual(set(d.registro.desalojados), creadas, "se perdió alguna")
        self.assertEqual(d.registro.acumulador.tamano, len(creadas))

    def test_ninguna_se_desaloja_antes_de_agotarse(self):
        d = devnet_con_entradas(cuantas=100, epocas=5)
        for epoca in (1, 2, 3, 4):
            d.registro.cobrar_epoca(epoca, d.ruleset)
            self.assertEqual(d.registro.desalojos, 0, f"desalojó en la época {epoca}")
        d.registro.cobrar_epoca(5, d.ruleset)
        self.assertEqual(d.registro.desalojos, 100)

    def test_el_orden_de_desalojo_es_el_de_insercion(self):
        """**Dos nodos tienen que meter los desalojados en el mismo orden**, o sus
        acumuladores quedan distintos y las raíces no coinciden — o sea, bifurcan.

        Lo encontró el arnés de mutaciones: se podía recorrer el conjunto por orden de
        hash y ningún criterio se caía. Un recorrido de diccionario por hash **parece
        determinístico dentro de un proceso** y no lo es entre dos.
        """
        d = devnet_con_entradas(cuantas=20, epocas=1)
        creadas = list(d.registro.entradas)
        d.registro.cobrar_epoca(1, d.ruleset)

        posiciones = [d.registro.desalojados[k] for k in creadas]
        self.assertEqual(posiciones, list(range(len(creadas))), "no entraron en orden")

    def test_el_acumulador_sigue_en_cientos_de_bytes(self):
        d = devnet_con_entradas(cuantas=500, epocas=1)
        d.registro.cobrar_epoca(1, d.ruleset)
        self.assertLessEqual(d.registro.acumulador.bytes_en_estado(), 1024)

    def test_y_se_revive_despues_de_la_conmutacion(self):
        """El ciclo entero, con la conmutación en el medio."""
        d = devnet_con_entradas(cuantas=10, epocas=1)
        d.registro.cobrar_epoca(1, d.ruleset)
        self.assertEqual(d.registro.desalojos, 10)

        correr_hasta_activar(d.nodo)
        revivida = d.registro.revivir(b"obj-3", 2, d.ruleset)
        self.assertEqual(revivida.identificador, b"obj-3")
        self.assertEqual(revivida.dueno, b"alice")

    def test_la_doble_reactivacion_falla_contra_el_conjunto_activo(self):
        d = devnet_con_entradas(cuantas=5, epocas=1)
        d.registro.cobrar_epoca(1, d.ruleset)
        d.registro.revivir(b"obj-1", 2, d.ruleset)
        with self.assertRaises(ValueError):
            d.registro.revivir(b"obj-1", 2, d.ruleset)


class B3ElDepositoValeLoMismoDespuesDeConmutar(unittest.TestCase):
    """**El hallazgo de la fase, y sólo se ve integrando.**

    El depósito se compra en una unidad; la época se cuenta en bloques; y
    `tiempo_bloque_ms` es un parámetro interno que una transición puede mover. Con el
    depósito en byte-épocas, una conmutación que cambiara el tiempo de bloque hacía que
    **un depósito ya pagado comprara el doble de guardado**, sin que nadie lo tocara.

    I3 se cumplía y sigue cumpliéndose: los bytes cruzan idénticos. Lo que cambiaba era lo
    que valían — y ninguna invariante mira eso.
    """

    def test_el_guardado_real_no_cambia_al_cambiar_el_tiempo_de_bloque(self):
        d = devnet_con_entradas(cuantas=3, epocas=10)
        antes = {k: e.segundos_restantes() for k, e in d.registro.entradas.items()}

        lento = ruleset_con(tiempo_bloque_ms=12_000)
        despues = {k: e.segundos_restantes() for k, e in d.registro.entradas.items()}

        self.assertEqual(antes, despues)
        # Y en épocas de la generación nueva son la mitad, porque duran el doble.
        for k, e in d.registro.entradas.items():
            self.assertEqual(e.epocas_restantes(lento), e.epocas_restantes() // 2)

    def test_tampoco_al_cambiarlo_para_el_otro_lado(self):
        d = devnet_con_entradas(cuantas=3, epocas=8)
        antes = [e.segundos_restantes() for e in d.registro.entradas.values()]
        rapido = ruleset_con(tiempo_bloque_ms=3_000)
        despues = [e.segundos_restantes() for e in d.registro.entradas.values()]
        self.assertEqual(antes, despues)
        for e in d.registro.entradas.values():
            self.assertEqual(e.epocas_restantes(rapido), e.epocas_restantes() * 2)

    def test_el_tope_de_vida_tambien_esta_en_tiempo_real(self):
        """Por lo mismo: si `L_max` estuviera en épocas, cambiar el tiempo de bloque
        cambiaría cuánto se puede prepagar — y el tope existe para que no se pueda apostar
        contra la tasa."""
        self.assertEqual(perm.L_MAX_SEGUNDOS, g.L_MAX_EPOCAS * perm.EPOCA_BLOQUES * 6)


class B4ElDesalojoYLaColaCompartenPresupuesto(unittest.TestCase):
    """La Fase 3 midió la cola sin permanencia; la Fase 5 midió la permanencia sin cola."""

    def test_el_numero_queda_escrito(self):
        d = Devnet(nodo=nodo_emision())
        m = d.costo_del_desalojo_por_bloque()

        self.assertGreater(m["desalojos_por_bloque"], 0)
        self.assertLess(m["fraccion"], 0.5, "el desalojo se come medio bloque")
        # Sin umbral que pasar: lo que importa es que el número exista y sea chequeable.
        self.assertAlmostEqual(
            m["fraccion"], m["pasos_por_bloque"] / m["presupuesto_del_bloque"]
        )

    def test_sobra_headroom_para_que_la_cola_drene(self):
        """§6.3 mide su margen con `h` de headroom; la Fase 3 lo midió en 10% con once
        nodos. El desalojo tiene que dejar más que eso."""
        d = Devnet(nodo=nodo_emision())
        self.assertLess(d.costo_del_desalojo_por_bloque()["fraccion"], 0.10)


class B5LaConmutacionNoDesalojaPorSorpresa(unittest.TestCase):
    """*Un desalojo anunciado no genera presión por un arreglo coordinado a mano, y una
    sorpresa sí.*"""

    def test_la_cuenta_regresiva_publicada_antes_se_cumple_despues(self):
        d = devnet_con_entradas(cuantas=20, epocas=6)
        prometido = {k: e.segundos_restantes() for k, e in d.registro.entradas.items()}

        correr_hasta_activar(d.nodo)

        for k, e in d.registro.entradas.items():
            self.assertEqual(
                e.segundos_restantes(),
                prometido[k],
                "la conmutación le acortó la vida a una entrada ya pagada",
            )

    def test_conmutar_no_puede_vencer_a_nadie_de_golpe(self):
        d = devnet_con_entradas(cuantas=20, epocas=6)
        correr_hasta_activar(d.nodo)
        self.assertFalse(d.historia_desalojos, "alguien se desalojó en la conmutación")
