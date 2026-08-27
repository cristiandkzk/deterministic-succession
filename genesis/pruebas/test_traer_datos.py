"""El traedor de series, probado sin red.

Lo que sí depende de la red —que un endpoint público conteste— no se prueba acá:
una prueba que falla porque se cayó un servidor ajeno no dice nada del código y
enseña a ignorar la suite. Lo que sí se prueba es todo lo demás, que es donde
están los errores que importan:

- **la extracción**, que es donde un campo mal leído mete un cero silencioso;
- **el ida y vuelta del CSV**, que es de donde después sale la medición;
- **la procedencia dentro del archivo**, porque un CSV sin origen es un número
  sin fuente — exactamente lo que la Fase 2 existe para no producir.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from herramientas import traer_datos as traer

#: Un bloque tal como lo devuelve `eth_getBlockByNumber`: todo en hexa.
BLOQUE_CON_BLOBS = {
    "number": "0x1284d1b",
    "timestamp": "0x65f1d5d7",
    "gasUsed": "0xb71b00",
    "gasLimit": "0x1c9c380",
    "baseFeePerGas": "0x3b9aca00",
    "blobGasUsed": "0x60000",  # 393.216 = 3 blobs
    "excessBlobGas": "0x120000",
}

#: Un bloque anterior a Dencun: **no trae los campos de blob**, y eso no es un
#: error sino el caso normal de la mitad del historial.
BLOQUE_PRE_DENCUN = {
    "number": "0xed14e0",
    "timestamp": "0x6321ea00",
    "gasUsed": "0xa4cb80",
    "gasLimit": "0x1c9c380",
    "difficulty": "0x0",
}


class LaExtraccion(unittest.TestCase):
    def test_los_blobs_salen_de_dividir_el_gas_de_blob(self):
        fila = traer.fila(traer.CASOS["blobs"], BLOQUE_CON_BLOBS)
        self.assertEqual(fila["blob_gas_usado"], 393_216)
        self.assertEqual(fila["blobs"], 3)
        self.assertEqual(fila["blobs"], fila["blob_gas_usado"] // traer.GAS_POR_BLOB)

    def test_se_guarda_el_acumulador_y_no_solo_el_bloque_suelto(self):
        """Un bloque dice 0 o 6 blobs; el exceso resume la historia reciente."""
        fila = traer.fila(traer.CASOS["blobs"], BLOQUE_CON_BLOBS)
        self.assertEqual(fila["exceso_blob_gas"], 0x120000)

    def test_un_campo_que_no_existe_da_cero_y_no_rompe(self):
        """La mitad del historial es anterior a los blobs: tiene que pasar igual."""
        fila = traer.fila(traer.CASOS["blobs"], BLOQUE_PRE_DENCUN)
        self.assertEqual((fila["blobs"], fila["exceso_blob_gas"]), (0, 0))

    def test_el_caso_de_gas_trae_uso_limite_y_base_fee(self):
        fila = traer.fila(traer.CASOS["gas"], BLOQUE_CON_BLOBS)
        self.assertEqual(fila["gas_usado"], 12_000_000)
        self.assertEqual(fila["gas_limite"], 30_000_000)
        self.assertEqual(fila["base_fee"], 1_000_000_000)

    def test_toda_fila_trae_bloque_y_marca(self):
        for nombre, caso in traer.CASOS.items():
            fila = traer.fila(caso, BLOQUE_CON_BLOBS)
            self.assertEqual(set(fila), set(caso.columnas), nombre)
            self.assertEqual(fila["bloque"], 0x1284D1B, nombre)


class ElIdaYVuelta(unittest.TestCase):
    def setUp(self):
        self.caso = traer.CASOS["blobs"]
        self.filas = [
            traer.fila(self.caso, BLOQUE_CON_BLOBS),
            traer.fila(self.caso, BLOQUE_PRE_DENCUN),
        ]

    def test_lo_que_se_escribe_es_lo_que_se_lee(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "blobs.csv"
            cabecera = traer.cabecera(self.caso, "https://ejemplo", 25_000_000)
            traer.escribir_serie(ruta, self.caso, cabecera, self.filas)

            comentarios, leidas = traer.leer_serie(ruta)

            self.assertEqual(leidas, self.filas)
            self.assertEqual(comentarios, cabecera)

    def test_los_valores_vuelven_como_enteros_y_no_como_texto(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "blobs.csv"
            traer.escribir_serie(ruta, self.caso, [], self.filas)
            _, leidas = traer.leer_serie(ruta)
            for valor in leidas[0].values():
                self.assertIsInstance(valor, int)

    def test_un_archivo_que_no_existe_no_es_un_error(self):
        """Es la ruta normal de la primera corrida, y la que permite retomar."""
        comentarios, filas = traer.leer_serie(Path("no-existe.csv"))
        self.assertEqual((comentarios, filas), ([], []))


class LaProcedenciaVaAdentroDelArchivo(unittest.TestCase):
    """Un CSV sin origen es un número sin fuente."""

    def test_la_cabecera_dice_origen_metodo_fecha_rango_y_paso(self):
        cabecera = "\n".join(
            traer.cabecera(traer.CASOS["blobs"], "https://ejemplo", 25_000_000)
        )
        self.assertIn("https://ejemplo", cabecera)
        self.assertIn("eth_getBlockByNumber", cabecera)
        self.assertIn("cada 5000", cabecera)
        self.assertIn("muestreada", cabecera)

    def test_cada_caso_dice_para_qué_es(self):
        for caso in traer.CASOS.values():
            self.assertTrue(caso.para_que)
            self.assertLess(caso.desde, caso.hasta or 10**9)


if __name__ == "__main__":
    unittest.main()
