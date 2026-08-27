"""Punto de entrada único: `python verificar.py`.

Corre las invariantes ejecutables y los criterios de aprobado de cada fase. No
hay dependencias fuera de la biblioteca estándar, a propósito: el día que haya
que correr esto en una máquina prestada, tiene que andar sin instalar nada.

    python verificar.py            # todo
    python verificar.py -v         # con el nombre de cada criterio
    python verificar.py fase1      # sólo un archivo de pruebas
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent


def main(argumentos: list[str]) -> int:
    # La consola de Windows viene en cp1252 y los mensajes de fallo tienen
    # acentos: sin esto, un fallo real se ve como un error de codificación.
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:  # pragma: no cover
            pass

    sys.path.insert(0, str(RAIZ))

    verboso = "-v" in argumentos or "--verbose" in argumentos
    filtros = [a for a in argumentos if not a.startswith("-")]

    patron = f"test*{filtros[0]}*.py" if filtros else "test*.py"
    suite = unittest.defaultTestLoader.discover(
        start_dir=str(RAIZ / "pruebas"), top_level_dir=str(RAIZ), pattern=patron
    )

    resultado = unittest.TextTestRunner(verbosity=2 if verboso else 1).run(suite)

    print()
    if resultado.wasSuccessful():
        print(
            f"OK · {resultado.testsRun} criterios. Las cinco invariantes se "
            "cumplen sobre todo lo construido."
        )
        return 0
    print(
        f"NO PASA · {len(resultado.failures)} criterios caídos y "
        f"{len(resultado.errors)} errores.\n"
        "Una invariante que falla no se marca como excepción: se para y se "
        "discute el diseño (ROADMAP, Fase 0)."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
