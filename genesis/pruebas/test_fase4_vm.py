"""Fase 4 — los criterios que se pueden fijar desde Python.

**La máquina está en Rust y sus pruebas también** (`predicado/vm/tests/criterios.rs`,
`cargo test --release`). Este archivo cubre lo que queda de este lado, y que es
justamente lo que ningún test de Rust puede ver: **que los dos lenguajes digan lo
mismo**.

Que una constante de Genesis viva en dos archivos es exactamente el riesgo que I1
señala, y ya cobró una vez en este proyecto: `herramientas/techo.py` tenía su propia
copia de `R_DECLARADO`, la Fase 4 bajó el valor en `protocolo/genesis.py`, y la copia
quedó atrás diciendo que ML-DSA-87 entraba cuando no entra. Se detectó porque una
prueba falló. Estas comprobaciones son para que se siga detectando así.

No hace falta tener Rust instalado: los archivos `.rs` se leen como texto.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from predicado.aceptacion import Corrida, Predicado, Presupuesto, Veredicto, acepta
from protocolo import genesis as g

VM = Path(__file__).resolve().parent.parent / "predicado" / "vm"


def fuente(*partes: str) -> str:
    return (VM.joinpath(*partes)).read_text(encoding="utf-8")


def constante_rust(texto: str, nombre: str) -> int:
    """Lee `pub const NOMBRE: tipo = valor;` de un archivo Rust."""
    m = re.search(rf"pub const {nombre}\s*:\s*\w+\s*=\s*([0-9_]+)", texto)
    if not m:
        raise AssertionError(f"no se encontró la constante {nombre}")
    return int(m.group(1).replace("_", ""))


class LosDosLenguajesDicenLoMismo(unittest.TestCase):
    """**El único lugar donde una constante de Genesis puede desincronizarse.**"""

    def test_el_techo_de_pasos_coincide_con_el_de_python(self):
        rust = constante_rust(fuente("src", "lib.rs"), "TECHO_INICIAL")
        self.assertEqual(rust, g.techo_vigente(g.RULESET_INICIAL))

    def test_el_techo_de_paginas_coincide(self):
        rust = constante_rust(fuente("src", "lib.rs"), "PAGINAS_INICIALES")
        self.assertEqual(rust, g.paginas_vigentes(g.RULESET_INICIAL))

    def test_el_tamano_de_pagina_coincide(self):
        rust = constante_rust(fuente("src", "maquina.rs"), "PAGINA")
        self.assertEqual(rust, g.PAGINA_BYTES)

    def test_la_capacidad_del_bloque_coincide(self):
        rust = constante_rust(fuente("src", "lib.rs"), "TX_INICIAL")
        self.assertEqual(rust, g.RULESET_INICIAL.interno("tx_por_bloque"))

    def test_los_codigos_de_veredicto_coinciden(self):
        """El veredicto entra al hash del bloque: si los dos lados lo codifican
        distinto, dos nodos leen resultados distintos de la misma corrida."""
        rs = fuente("src", "maquina.rs")
        canonico = rs[rs.index("pub fn canonico") : rs.index("pub fn canonico") + 900]
        esperados = {
            "Retorno": Veredicto.RETORNO,
            "Ecall": Veredicto.ECALL,
            "TechoExcedido": Veredicto.TECHO_EXCEDIDO,
            "PaginasExcedidas": Veredicto.PAGINAS_EXCEDIDAS,
        }
        for nombre, veredicto in esperados.items():
            m = re.search(rf"Veredicto::{nombre}[^=]*=>\s*\((\d+)", canonico)
            self.assertIsNotNone(m, nombre)
            self.assertEqual(int(m.group(1)), veredicto.value, nombre)
        # Y la trampa, que lleva la causa en el dato y no en la clase.
        self.assertIn("Trampa(Causa::MemoriaFueraDeRango) => (3", canonico)


class LaMaquinaNoTienePalancas(unittest.TestCase):
    """I1: lo que Genesis congela, no se mueve por generación."""

    def test_el_tamano_de_memoria_es_constante_y_no_parametro(self):
        """El arnés de Test 2 hacía `dirección & MASK`, y con eso el resultado de un
        programa dependía del tamaño de memoria. Si el tamaño fuese un parámetro del
        espacio, el mismo programa daría distinto en dos generaciones."""
        self.assertNotIn("memoria_vm", g.ESPACIO_INTERNO)
        self.assertIn("pub const MEM", fuente("src", "maquina.rs"))

    def test_el_espacio_de_opcodes_reservados_esta_cerrado(self):
        """Los ocho opcodes mayores que RISC-V le asignó a F, D y A. **Cerrarlos es
        más fuerte que no implementarlos**: el día que alguien quiera agregar punto
        flotante, tiene que romper una constante declarada en Genesis."""
        rs = fuente("src", "admision.rs")
        m = re.search(r"const RESERVADOS: \[u8; 8\] = \[([^\]]+)\]", rs)
        self.assertIsNotNone(m)
        leidos = {int(x.strip(), 16) for x in m.group(1).split(",")}
        self.assertEqual(leidos, {0x07, 0x27, 0x2F, 0x43, 0x47, 0x4B, 0x4F, 0x53})

    def test_la_maquina_no_usa_un_solo_flotante(self):
        """C2 de un vistazo: ni un `f32`, ni un `f64`, ni un literal con punto.

        Con límite de palabra, porque `NoEsElf32` contiene `f32` y no es un flotante
        — la primera versión de esta prueba falló por eso y volcó el archivo entero
        en la salida.
        """
        for archivo in ("maquina.rs", "admision.rs", "lib.rs"):
            # Se mira el codigo y no los comentarios: un comentario puede nombrar
            # lo que prohibe, y de hecho el de `lib.rs` lo nombra.
            codigo = "\n".join(
                l for l in fuente("src", archivo).splitlines()
                if not l.lstrip().startswith("//")
            )
            for patron in (r"\bf32\b", r"\bf64\b", r"\b\d+\.\d+\b"):
                halla = re.search(patron, codigo)
                self.assertIsNone(
                    halla,
                    f"{archivo}: {halla.group(0) if halla else patron}",
                )


class LosVectoresDeC3EstanListosParaElTelefono(unittest.TestCase):
    """C3 se cierra corriendo `vectores verificar` en aarch64. Lo que se fija acá es
    que el instrumento esté completo, para que esa corrida sea un solo comando."""

    def setUp(self):
        self.filas = [
            l.split(",")
            for l in (VM / "vectores.csv").read_text(encoding="utf-8").splitlines()
            if l and not l.startswith("#") and not l.startswith("vector,")
        ]

    def test_hay_vectores_de_las_cuatro_clases_de_final(self):
        nombres = {f[0] for f in self.filas}
        for esperado in ("isa-revuelto-200k", "techo-pasos", "techo-paginas", "trampa-pc"):
            self.assertIn(esperado, nombres)

    def test_cada_vector_lleva_veredicto_pasos_paginas_y_huella(self):
        for fila in self.filas:
            self.assertEqual(len(fila), 5, fila)
            self.assertEqual(len(fila[1]), 10, "el veredicto son 5 bytes en hex")
            int(fila[2])
            int(fila[3])
            int(fila[4], 16)

    def test_el_vector_de_la_carga_real_reproduce_el_dato_de_test2(self):
        """`steps_per_verify` es el número del que sale todo el techo de §6.6. Si la
        máquina endurecida lo hubiera movido, el techo estaría mal calibrado."""
        fila = next(f for f in self.filas if f[0] == "mldsa44-una-verificacion")
        self.assertEqual(int(fila[2]), 3_339_442)  # una verificación + el marco
        self.assertEqual(int(fila[3]), 26)


class ElPredicadoCobraLosDosFiltros(unittest.TestCase):
    """§6.2: pasar los vectores **y** entrar bajo los techos. Las dos, no una."""

    def setUp(self):
        self.presupuesto = Presupuesto.de(g.RULESET_INICIAL)
        self.predicado = Predicado(
            programa=b"\x11" * 32,
            vectores=((b"entrada-a", b"salida-a"), (b"entrada-b", b"salida-b")),
        )

    def _corrida(self, salida: bytes, pasos: int = 1000, paginas: int = 4) -> Corrida:
        return Corrida(Veredicto.RETORNO, 0, pasos, paginas, salida)

    def _todas_bien(self) -> dict[bytes, Corrida]:
        return {e: self._corrida(s) for e, s in self.predicado.vectores}

    def test_pasa_cuando_dan_los_dos(self):
        self.assertTrue(acepta(self.predicado, self._todas_bien(), self.presupuesto))

    def test_una_salida_equivocada_rechaza(self):
        corridas = self._todas_bien()
        corridas[b"entrada-b"] = self._corrida(b"otra-cosa")
        self.assertFalse(acepta(self.predicado, corridas, self.presupuesto))

    def test_pasarse_de_pasos_rechaza_aunque_la_salida_sea_correcta(self):
        """**Es una condición de seguridad, no de rendimiento.** Dar bien pero caro
        es exactamente la impugnación más cara de verificar que de crear."""
        corridas = self._todas_bien()
        corridas[b"entrada-a"] = self._corrida(b"salida-a", pasos=self.presupuesto.pasos + 1)
        self.assertFalse(acepta(self.predicado, corridas, self.presupuesto))

    def test_pasarse_de_paginas_rechaza_aunque_los_pasos_entren(self):
        """El segundo techo tiene que cobrar solo. Con pocos pasos y mucha memoria
        el techo de pasos no ve nada, y es el caso que la Fase 4 midió a 23×."""
        corridas = self._todas_bien()
        corridas[b"entrada-a"] = self._corrida(
            b"salida-a", pasos=10, paginas=self.presupuesto.paginas + 1
        )
        self.assertFalse(acepta(self.predicado, corridas, self.presupuesto))

    def test_faltar_un_vector_rechaza(self):
        """Evaluarse sobre los vectores que a uno le convienen no es un predicado."""
        corridas = self._todas_bien()
        del corridas[b"entrada-b"]
        self.assertFalse(acepta(self.predicado, corridas, self.presupuesto))

    def test_un_techo_excedido_no_acepta_pero_tampoco_es_un_error(self):
        """Rechazar es un resultado: entra al bloque como cualquier otro."""
        corte = Corrida(Veredicto.TECHO_EXCEDIDO, 0, self.presupuesto.pasos, 3, b"")
        self.assertFalse(corte.veredicto.acepta)
        self.assertEqual(len(corte.canonico()), 5 + 8 + 4 + 32)

    def test_un_predicado_sin_vectores_no_se_puede_construir(self):
        with self.assertRaises(ValueError):
            Predicado(programa=b"\x11" * 32, vectores=())


class LaCorreccionDeLaFase4NoSePuedeDeshacerSinQueSeNote(unittest.TestCase):
    """Los números viejos, fijados como regresión. La Fase 4 los movió con una
    medición; volver atrás tiene que costar romper una prueba y no un descuido."""

    def test_el_ritmo_declarado_ya_no_es_el_de_una_sola_mezcla(self):
        """300 M era el ritmo de la mezcla de ML-DSA; 120 M salía de un escritorio y de
        mezclar dos intérpretes. 70 M está medido en el hardware de referencia."""
        self.assertNotEqual(g.ritmo_declarado(g.paginas_vigentes(g.RULESET_INICIAL)), 300_000_000)
        self.assertNotEqual(g.ritmo_declarado(g.paginas_vigentes(g.RULESET_INICIAL)), 120_000_000)
        self.assertEqual(g.ritmo_declarado(g.paginas_vigentes(g.RULESET_INICIAL)), 70_000_000)

    def test_el_techo_de_paginas_ya_no_excluye_a_ml_dsa_87(self):
        """48 páginas dejaban afuera a la primitiva de 65 sin precio posible."""
        self.assertNotEqual(g.paginas_vigentes(g.RULESET_INICIAL), 48)
        self.assertEqual(g.paginas_vigentes(g.RULESET_INICIAL), 96)

    def test_la_capacidad_pago_la_correccion(self):
        """67 → 26 → 15 en un día, y las tres veces por el mismo motivo: **no cambió el
        techo, cambió cuántos pasos garantizados compra un segundo de reloj.**"""
        self.assertEqual(g.RULESET_INICIAL.interno("tx_por_bloque"), 15)
        self.assertEqual(g.techo_vigente(g.RULESET_INICIAL), 7_000_000)
