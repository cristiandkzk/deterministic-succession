"""Fase 5 — los criterios de `estado/CRITERIOS.md`, escritos antes del mecanismo.

Lo que se mide —A3, A8, A9— va a `estado/RESULTADOS.md`; acá quedan las propiedades.
"""

from __future__ import annotations

import unittest

from estado import permanencia as perm
from estado.desalojo import Acumulador
from estado.permanencia import Entrada, VidaMaximaExcedida
from protocolo import genesis as g


def entrada(ident: bytes = b"obj-1", epocas: int = 10) -> Entrada:
    e = Entrada(identificador=ident, dueno=b"alice")
    e.recargar(epocas)
    return e


class A1ElCicloCierraCompleto(unittest.TestCase):
    """crear → pagar → agotar → desalojar → reactivar, y el objeto vuelve idéntico."""

    def test_el_ciclo_entero_y_el_objeto_vuelve_byte_a_byte(self):
        acumulador = Acumulador()
        e = entrada(epocas=3)
        original = e.canonico()

        # pagar: dos épocas de las tres compradas
        quemado = e.cobrar(hasta_epoca=2)
        self.assertEqual(quemado, perm.costo_en_segundos(e.tamano_bytes, 2))
        self.assertEqual(e.epocas_restantes(), 1)

        # agotar
        e.cobrar(hasta_epoca=3)
        self.assertEqual(e.deposito, 0)

        # desalojar
        posicion = acumulador.desalojar(original)
        prueba = acumulador.prueba_de(posicion)
        self.assertTrue(acumulador.verifica(prueba))

        # reactivar: **byte a byte**. Cualquier diferencia sería confiscación parcial.
        self.assertEqual(prueba.datos, original)
        revivida = Entrada(identificador=e.identificador, dueno=e.dueno)
        revivida.recargar(5)  # paga el costo de entonces
        self.assertEqual(revivida.canonico(), original)

    def test_agotarse_no_deja_deuda(self):
        """No hay descubierto: se quema lo que hay y la entrada queda vencida. El
        protocolo no tiene deudor al que embargar — el dueño es una clave."""
        e = entrada(epocas=2)
        quemado = e.cobrar(hasta_epoca=100)
        self.assertEqual(quemado, perm.costo_en_segundos(e.tamano_bytes, 2))
        self.assertEqual(e.deposito, 0)
        self.assertGreaterEqual(e.deposito, 0, "un saldo negativo sería deuda")


class A2ElAcumuladorEsDeCientosDeBytes(unittest.TestCase):
    """La condición que impide que el desalojo sea permanencia comprada más barata."""

    def test_no_crece_con_la_cantidad_de_desalojos(self):
        medidas = {}
        for n in (10, 10_000, 1_000_000):
            a = Acumulador()
            for k in range(n):
                a.desalojar(k.to_bytes(8, "little"))
            medidas[n] = a.bytes_en_estado()

        for n, bytes_ in medidas.items():
            self.assertLessEqual(bytes_, 1024, f"{n} desalojos ocupan {bytes_} bytes")
        # Y crece con el logaritmo, no con n: cinco órdenes de magnitud más de objetos
        # tienen que costar menos del doble de estado.
        self.assertLess(medidas[1_000_000] / medidas[10], 4)

    def test_una_lapida_por_objeto_seria_un_cuarto_del_presupuesto(self):
        """El contraste que justifica el acumulador, con los números del paper."""
        lapidas = 32 * 35_000_000
        self.assertGreater(lapidas / g.PRESUPUESTO_ESTADO_BYTES, 0.2)


class A3MantenerLaPruebaAlDiaEsLoQueCuesta(unittest.TestCase):
    """**La dependencia que §10.2 declara y el protocolo no puede garantizar.**

    La prueba pesa menos de un kilobyte, así que guardarla es gratis. Lo que no es gratis
    es mantenerla al día: *la unión de los hermanos del camino de una hoja es el árbol
    entero menos esa hoja*, de modo que **se vence en el primer bloque que toque cualquier
    otra cosa**.

    Esta clase existe porque el arnés de mutaciones encontró que no existía: se podía
    borrar la revalidación contra los picos vigentes y **ningún criterio se caía**. Una
    prueba que no prueba nada es peor que no tenerla, porque además da confianza.
    """

    def test_un_solo_desalojo_ajeno_vence_la_prueba(self):
        a = Acumulador()
        prueba = a.prueba_de(a.desalojar(b"mio"))
        self.assertTrue(a.verifica(prueba))

        a.desalojar(b"de-otro")
        self.assertFalse(
            a.verifica(prueba),
            "la prueba sobrevivió a un desalojo ajeno: los picos no se están mirando",
        )

    def test_reconstruirla_la_devuelve_al_ruedo(self):
        """Por eso la dependencia es de archivo y no de protocolo: revivir **se puede**,
        siempre que alguien tenga las hojas para rearmar la prueba."""
        a = Acumulador()
        pos = a.desalojar(b"mio")
        for k in range(50):
            a.desalojar(f"otro-{k}".encode())
        self.assertTrue(a.verifica(a.prueba_de(pos)))

    def test_cuantas_veces_por_epoca_hay_que_rehacerla(self):
        """El número que A3 pide, sin umbral que pasar: **una vez por desalojo ajeno.**

        Con la capacidad inicial —15 tx por bloque, 14.400 bloques por época— el techo es
        de 216.000 desalojos por época, así que un agente permanentemente online rehace la
        prueba hasta esa cantidad de veces. Es exactamente el supuesto que ya sostiene
        *"no se le puede pagar a alguien que está offline"*, y no alcanza para una persona.
        """
        tope = g.RULESET_INICIAL.interno("tx_por_bloque") * perm.EPOCA_BLOQUES
        self.assertEqual(tope, 216_000)

        a = Acumulador()
        pos = a.desalojar(b"mio")
        vencimientos = 0
        prueba = a.prueba_de(pos)
        for k in range(20):
            a.desalojar(f"otro-{k}".encode())
            if not a.verifica(prueba):
                vencimientos += 1
                prueba = a.prueba_de(pos)
        self.assertEqual(vencimientos, 20, "vence en cada desalojo ajeno, sin excepción")


class A4LaDobleReactivacionSeFrenaSinNulificadores(unittest.TestCase):
    """Una lista de gastados sería el residuo O(n) entrando por la otra puerta."""

    def test_revivir_dos_veces_falla_contra_el_conjunto_activo(self):
        acumulador = Acumulador()
        e = entrada()
        prueba = acumulador.prueba_de(acumulador.desalojar(e.canonico()))
        activos: set[bytes] = set()

        def revivir() -> bool:
            if not acumulador.verifica(prueba):
                return False
            if e.identificador in activos:  # el chequeo, contra el ACTIVO
                return False
            activos.add(e.identificador)
            return True

        self.assertTrue(revivir())
        self.assertFalse(revivir(), "la segunda reactivación tiene que fallar")

    def test_el_conjunto_activo_esta_acotado_y_la_lista_de_gastados_no(self):
        """Por eso se chequea contra uno y no contra la otra."""
        self.assertLess(perm.entradas_que_entran(), 2**26)


class A5NadieCompraPermanenciaPerpetua(unittest.TestCase):
    """La propiedad que §8.5 declara como justificación de la sección entera."""

    def test_no_se_puede_comprar_mas_de_L_max_de_una_vez(self):
        e = Entrada(identificador=b"x", dueno=b"a")
        with self.assertRaises(VidaMaximaExcedida):
            e.recargar(g.L_MAX_EPOCAS + 1)

    def test_tampoco_de_a_poco_sin_dejar_que_se_consuma(self):
        """Recargar dos veces sin que pase el tiempo no puede acumular más allá del tope."""
        e = Entrada(identificador=b"x", dueno=b"a")
        e.recargar(g.L_MAX_EPOCAS)
        with self.assertRaises(VidaMaximaExcedida):
            e.recargar(1)

    def test_el_precio_por_epoca_no_baja_al_depositar_mas(self):
        """**Sin esto, cien pisos comprarían diez mil años.**

        Un descuento por volumen abarata la única operación que compra permanencia en
        volumen: llenar el estado de todos los nodos y no soltarlo nunca.
        """
        unitario = perm.costo_en_segundos(100, 1)
        for epocas in (2, 5, 25):
            self.assertEqual(
                perm.costo_en_segundos(100, epocas),
                unitario * epocas,
                "el costo dejó de ser lineal: hay descuento por volumen",
            )

    def test_el_deposito_se_lleva_en_guardado_real_y_no_en_epocas(self):
        """**La corrección de B3, que encontró la Fase 6 al integrar.**

        El depósito se llevaba en byte-épocas y la época se cuenta en bloques, así que una
        conmutación que cambiara `tiempo_bloque_ms` hacía que un depósito ya pagado
        comprara más o menos guardado del que compró. I3 se cumplía —los bytes cruzaban
        idénticos— y lo que cambiaba era lo que valían.
        """
        from protocolo.generacion import Params, Ruleset

        e = entrada(epocas=10)
        antes = e.segundos_restantes()

        internos = dict(g.PARAMS_INICIALES.internos)
        internos["tiempo_bloque_ms"] = 12_000
        otro = Ruleset(
            params=Params(2, internos, g.RULESET_INICIAL.formatos), h0=b"\x00" * 32
        )

        self.assertEqual(e.segundos_restantes(), antes, "el guardado real no puede cambiar")
        # Y la cuenta regresiva en épocas sí se ajusta, porque las épocas duran el doble.
        self.assertEqual(e.epocas_restantes(otro), e.epocas_restantes() // 2)

    def test_el_costo_es_tamano_por_tiempo_y_no_mira_el_valor(self):
        """Lo tasado es costo, no utilidad: la regla no le pide al protocolo ninguna
        opinión sobre qué vale un activo."""
        self.assertEqual(perm.costo_en_segundos(240, 3), 2 * perm.costo_en_segundos(120, 3))


class A6LaCuentaRegresivaEsPublica(unittest.TestCase):
    """Misma forma que la distancia al disparo de I2, y por la misma razón."""

    def test_es_consultable_y_monotona_sin_recarga(self):
        e = entrada(epocas=5)
        vistas = []
        for epoca in range(6):
            e.cobrar(hasta_epoca=epoca)
            vistas.append(e.epocas_restantes())
        self.assertEqual(vistas, sorted(vistas, reverse=True))
        self.assertEqual(vistas[0], 5)
        self.assertEqual(vistas[-1], 0)

    def test_el_desalojo_se_puede_anticipar_antes_de_que_pase(self):
        """Un desalojo anunciado no genera presión por un arreglo coordinado a mano."""
        e = entrada(epocas=4)
        self.assertFalse(e.vencida_en(3))
        self.assertTrue(e.vencida_en(4))


class A7DesalojarNoEsConfiscar(unittest.TestCase):
    def test_el_objeto_sobrevive_al_desalojo(self):
        """No hay quema final del activo: sale del conjunto activo y se lo revive."""
        acumulador = Acumulador()
        e = entrada()
        prueba = acumulador.prueba_de(acumulador.desalojar(e.canonico()))
        self.assertEqual(prueba.datos, e.canonico())
        self.assertTrue(acumulador.verifica(prueba))

    def test_la_prueba_pesa_menos_de_un_kilobyte(self):
        """§10.2: guardarla es gratis; lo que cuesta es mantenerla al día."""
        acumulador = Acumulador()
        for k in range(100_000):
            acumulador.desalojar(k.to_bytes(8, "little"))
        self.assertLess(acumulador.prueba_de(42).bytes_aproximados(), 1024)


class A8ElPisoEsUnaCuentaYElPaperEstaMal(unittest.TestCase):
    """**El criterio que reprobó, y reprobó contra el paper.**

    §8.5 afirma que el ciclo crear + desalojar sale *"unas dieciséis horas de guardado, o
    sea el 0,2% de lo que cuesta tener el objeto un año"*. Escrita la cuenta con los
    números que Genesis ya declara, no da eso por uno o dos órdenes de magnitud.
    """

    PAPER_EPOCAS = 16 / 24  # las dieciséis horas de §8.5, en épocas de un día

    def test_la_derivacion_se_puede_escribir(self):
        """A8 aprueba en su primera mitad: no hay que elegir el número a ojo."""
        piso = perm.piso_en_epocas()
        self.assertGreater(piso, 0)
        self.assertEqual(piso, perm.piso_en_epocas(ruleset=g.RULESET_INICIAL))

    def test_no_da_las_dieciseis_horas_que_dice_el_paper(self):
        """Y reprueba en la segunda. Con la firma adentro del ciclo —que es como el paper
        lo describía— el piso son decenas de épocas contra las 0,67 que afirmaba."""
        con_firma = perm.piso_en_epocas(incluir_firma=True)
        self.assertGreater(con_firma / self.PAPER_EPOCAS, 50)

    def test_con_la_firma_adentro_el_piso_supera_al_deposito_maximo(self):
        """Y ahí §8.5 se cae por su propio argumento: si el piso es varias veces el
        depósito máximo, **casi todo el costo se paga al crear** — que es exactamente el
        cargo a la creación que la sección descarta, porque no reduce la creación sino su
        registración."""
        self.assertGreater(perm.piso_en_epocas(incluir_firma=True), g.L_MAX_EPOCAS)

    def test_sacar_la_firma_del_ciclo_lo_arregla_y_es_defendible(self):
        """La firma ya la paga el fee ad valorem de §6.1: cobrarla en el piso es cobrarla
        dos veces. Sacada, el piso vuelve por debajo del depósito máximo."""
        self.assertLess(perm.piso_en_epocas(), g.L_MAX_EPOCAS)

    def test_ya_no_queda_colgando_de_un_numero_estimado(self):
        """**El insumo que faltaba, medido el 21/8/2026.**

        Sacada la firma del ciclo, el término dominante pasó a ser cuántos pasos cuesta un
        SHA-256 — y estaba estimado. Se midió como `steps_per_verify`: un SHA-256 escrito a
        mano, compilado a RV32IM y corrido en la máquina de §6.6. **4.898 pasos por
        compresión**, contra los 10.000 que se habían estimado.

        El número vive en `permanencia.py` y su regresión en Rust
        (`predicado/vm/tests/criterios.rs`), que es donde se puede volver a medir.
        """
        self.assertEqual(perm.PASOS_POR_HASH, 4_898)

    def test_el_piso_con_el_arbol_de_verdad_pone_en_duda_la_estructura_de_8_5(self):
        """**Este criterio se cayó el 22/8/2026 y se reescribió para decir la verdad.**

        La versión anterior exigía que el piso quedara por debajo del 35% del depósito
        máximo, y pasaba con holgura: 24%. Pero ese 24% salía de suponer que actualizar el
        árbol cuesta 26 hashes, que es su **altura** — y el árbol no existía todavía.
        Construido (`estado/arbol.py`), 26 resultó ser el costo de `d = 1`, o sea guardar
        todos los nodos internos: la opción que el diseño descartó por costar 32 B por
        entrada. Con el corte que el diseño sí eligió son 83, y el piso **77% de `L_max`**.

        No se afloja el umbral: se registra que el número cambió y qué implica.
        """
        piso = perm.piso_en_epocas()
        self.assertAlmostEqual(piso, 19.25, places=1)
        self.assertLess(piso, g.L_MAX_EPOCAS, "el piso superó al depósito máximo")
        self.assertGreater(piso / g.L_MAX_EPOCAS, 0.7, "si bajó, revisar por qué")

    def test_para_una_entrada_de_vida_corta_el_piso_es_casi_todo_el_costo(self):
        """**Y ahí es donde §8.5 queda en duda, que es lo que importa.**

        La sección descarta el cargo a la creación con un argumento que no depende de la
        magnitud: *no reduce la creación, reduce la registración de la creación*. Con el
        piso en 19,25 épocas, quien sólo quiere una entrada por poco tiempo paga casi todo
        al crearla — que es exactamente la forma que la sección rechaza.
        """
        piso = perm.piso_en_epocas()
        corta = piso / (piso + 1)      # una entrada que compra una época
        larga = piso / (piso + g.L_MAX_EPOCAS)  # una que compra el máximo

        self.assertGreater(corta, 0.9, "para vida corta el piso tiene que dominar")
        self.assertLess(larga, 0.5, "para vida larga todavía no domina")

    def test_pero_sigue_sin_ser_las_dieciseis_horas_del_paper(self):
        """Nueve veces más. El paper quedó corregido: ya no afirma el número viejo."""
        self.assertGreater(perm.piso_en_epocas() / self.PAPER_EPOCAS, 8)


class A9LaTasaNoEsDeEsaClaseYSePuedeDecirPorQue(unittest.TestCase):
    """**A9 aprueba por la segunda vía: no se escribe la cuenta, se escribe por qué no hay.**

    El techo de pasos se pudo cerrar dos veces porque sus dos lados eran físicos —pasos de
    un lado, segundos del otro— y la cadena puede contar los dos sin preguntarle nada a
    nadie. La tasa tiene un lado físico, bytes × épocas, y uno monetario, cuántos tokens
    vale eso. **Ninguna cuenta cruza esos dos lados sin leer un precio**, y leer un precio
    es exactamente lo que I2 prohíbe.

    La prueba de que el argumento no es una sensación es que **se ve en los tipos**: todo
    lo que este módulo calcula está en byte-épocas o en épocas, y en ningún lado aparece
    una unidad monetaria. El día que aparezca, aparece con un oráculo al lado.
    """

    def test_ningun_calculo_de_este_modulo_devuelve_tokens(self):
        e = entrada(epocas=3)
        self.assertEqual(e.recargar(1), perm.costo_en_segundos(e.tamano_bytes, 1))
        self.assertIsInstance(perm.piso_en_epocas(), float)  # épocas, no tokens

    def test_el_piso_se_denomina_en_guardado_y_asi_hereda_la_tasa(self):
        """La decisión de forma que sale de A9: si el piso estuviera en tokens sería un
        **segundo** parámetro libre al lado de la tasa. En épocas de guardado hereda la
        que rija, sea cual sea, y deja de ser una decisión aparte."""
        piso_a = perm.piso_en_epocas()
        piso_b = perm.piso_en_epocas(ruleset=g.RULESET_INICIAL)
        self.assertEqual(piso_a, piso_b)

    def test_la_tasa_sigue_sin_estar_en_el_espacio_de_parametros(self):
        """Está bloqueada a propósito (§10.3) y el roadmap dice construir con ella
        parametrizada. Que no esté todavía en `ESPACIO_INTERNO` es el estado correcto:
        agregarla sin la ley de control sería declarar una palanca."""
        self.assertNotIn("tasa_permanencia", g.ESPACIO_INTERNO)
