"""Arma el paquete de la máquina para correrla en el teléfono: `python herramientas/empaquetar_vm.py`

**Para qué.** Lo único que le falta a la Fase 4 es C3 —que el conteo de pasos reproduzca
bit a bit entre x86-64 y ARM64— y eso se cierra corriendo `vectores verificar` en aarch64.
Pero el crate **no es autocontenido**: `lib.rs` hace `include_bytes!` del ELF del guest de
Test 2, que vive cuatro niveles más arriba. Copiar sólo `predicado/vm/` al teléfono no
compila.

Esto arma un `.tar.gz` con los archivos mínimos y **con las rutas relativas intactas**, así
que del otro lado es descomprimir y compilar. Son ~300 KB.

    python herramientas/empaquetar_vm.py            # deja vm-telefono.tar.gz
    python herramientas/empaquetar_vm.py --probar   # además lo extrae y compila

**Por qué no se copia el ELF adentro del crate y listo.** Porque serían dos copias del mismo
artefacto publicado, y dos copias de un binario que fija un número de consenso es la misma
clase de problema que tenía `R_DECLARADO` viviendo en dos archivos. El paquete es una vista,
no una segunda fuente.
"""

from __future__ import annotations

import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
SALIDA = RAIZ / "genesis" / "vm-telefono.tar.gz"

#: Todo lo que hace falta, con la ruta tal como tiene que quedar del otro lado.
#: El ELF del guest **no se toca**: es el artefacto de Test 2, y que sea el mismo byte
#: por byte es justamente lo que hace comparable la medición entre las dos arquitecturas.
ARCHIVOS = [
    "genesis/predicado/vm/Cargo.toml",
    "genesis/predicado/vm/Cargo.lock",
    "genesis/predicado/vm/vectores.csv",
    "genesis/predicado/vm/LEEME.md",
    "genesis/predicado/vm/src/lib.rs",
    "genesis/predicado/vm/src/maquina.rs",
    "genesis/predicado/vm/src/admision.rs",
    "genesis/predicado/vm/src/bin/vectores.rs",
    "genesis/predicado/vm/src/bin/bloque.rs",
    "genesis/predicado/vm/src/bin/mezclas.rs",
    "genesis/predicado/vm/src/bin/conjunto.rs",
    "genesis/predicado/vm/src/bin/paginas.rs",
    "genesis/predicado/vm/tests/criterios.rs",
    "genesis/predicado/CRITERIOS.md",
    "genesis/predicado/RESULTADOS.md",
    "test2-interprete/telefono/guest-rv/guest.elf",
]

INSTRUCCIONES = """\
# Correr la máquina en el teléfono — cierra C3 de la Fase 4

En Termux:

    pkg install -y rust tar
    tar xzf vm-telefono.tar.gz
    cd genesis/predicado/vm

    cargo run --release --bin mezclas               # C7 — la cota, medida directo
    cargo run --release --bin conjunto              # la curva de conjunto de trabajo
    cargo run --release --bin vectores verificar    # C3
    cargo run --release --bin bloque                # C1 sobre el hardware que decide

Sin dependencias: compila un solo crate, no los veinte minutos del arnés de Test 2.

**Qué tiene que dar.** Los siete vectores idénticos a los de x86-64. No hay tolerancia: si
dos nodos cuentan distinto, la impugnación no tiene resultado. Si alguno difiere, la salida
dice cuál y con qué valores, y **eso es un hallazgo, no un error de la corrida** — pegar la
salida entera.

**Y ya que está el teléfono prendido**, `--bin bloque` mide C1 sobre el hardware de
referencia del protocolo. El margen que hay medido es el de un escritorio x86-64, y el
número que decide es éste.
"""


def main(argumentos: list[str]) -> int:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:  # pragma: no cover
            pass

    faltan = [a for a in ARCHIVOS if not (RAIZ / a).is_file()]
    if faltan:
        print("faltan archivos, el paquete quedaria incompleto:")
        for a in faltan:
            print(f"  {a}")
        return 1

    with tarfile.open(SALIDA, "w:gz") as tar:
        for a in ARCHIVOS:
            tar.add(RAIZ / a, arcname=a)
        info = tarfile.TarInfo("LEEME-TELEFONO.md")
        datos = INSTRUCCIONES.encode("utf-8")
        info.size = len(datos)
        import io

        tar.addfile(info, io.BytesIO(datos))

    kb = SALIDA.stat().st_size / 1024
    print(f"{SALIDA.relative_to(RAIZ)}: {kb:.0f} KB, {len(ARCHIVOS) + 1} archivos")

    if "--probar" not in argumentos:
        print("\ncorrer con --probar para verificar que el paquete compila solo")
        return 0

    # Extraer en un directorio limpio y compilar: es la unica forma de saber que no
    # falta nada. Un paquete que compila "porque el resto del repo estaba al lado"
    # no sirve para lo que se hizo.
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(SALIDA) as tar:
            tar.extractall(tmp)
        vm = Path(tmp) / "genesis" / "predicado" / "vm"
        print(f"\nprobando en {vm} ...")
        r = subprocess.run(
            ["cargo", "run", "--release", "--bin", "vectores", "verificar"],
            cwd=vm,
            capture_output=True,
            text=True,
        )
        print(r.stdout[-600:] or r.stderr[-600:])
        if r.returncode != 0:
            print("EL PAQUETE NO SE BASTA A SI MISMO")
            return 1
    print("el paquete compila y verifica desde un directorio limpio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
