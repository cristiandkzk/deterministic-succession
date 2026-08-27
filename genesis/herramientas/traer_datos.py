"""Trae las series que le faltan a la Fase 2. **Es lo único que toca la red.**

```
python herramientas/traer_datos.py blobs        # caso 2
python herramientas/traer_datos.py gas          # caso 3
python herramientas/traer_datos.py dificultad   # cierra la lectura de la Medición 1
```

Cada uno deja un CSV en `herramientas/datos/`, con procedencia adentro. Después el
replay lo lee y corre **offline**: la red se toca una vez, no en cada corrida.

## Qué API hace falta, en una línea

Un endpoint **JSON-RPC de Ethereum**, y nada más. Las tres series salen del mismo
método —`eth_getBlockByNumber`—, que devuelve en una sola respuesta `blobGasUsed`
(caso 2), `gasUsed` y `gasLimit` (caso 3) y `difficulty` (pre-fusión). No hace falta
un explorador, ni un índice, ni una cuenta.

**Probablemente no necesites clave.** El script trae una lista de endpoints públicos
abiertos y los prueba en orden hasta que uno conteste. Si todos fallan o te limitan,
pasás el tuyo:

```
python herramientas/traer_datos.py blobs --rpc https://TU-ENDPOINT
```

## Tres decisiones que no son de comodidad

- **Muestreo, no barrido.** Se pide un bloque cada `paso` y no todos: el trigger lee
  una media móvil de días, así que bajar 6 millones de bloques para promediarlos
  sería pagar mil veces por el mismo número. El paso queda **escrito en el CSV**,
  porque es parte del dato.
- **Se puede cortar y seguir.** Si el CSV existe, arranca donde quedó. Una bajada de
  veinte minutos que se corta por un límite de tasa no se rehace desde cero.
- **Sólo biblioteca estándar.** El repositorio no tiene dependencias y este script
  no las va a introducir: `urllib` alcanza.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
DATOS = RAIZ / "datos"

#: Endpoints públicos sin clave. Se prueban en orden. Si cambian o cierran, se
#: agrega otro acá o se pasa `--rpc`: el resto del script no se entera.
ENDPOINTS = (
    "https://ethereum-rpc.publicnode.com",
    "https://eth.llamarpc.com",
    "https://cloudflare-eth.com",
    "https://eth.drpc.org",
)

#: `GAS_PER_BLOB` de EIP-4844: `blobGasUsed / 131072` = blobs en ese bloque.
GAS_POR_BLOB = 131_072

#: Dencun, primer bloque con blobs. La fecha está en `historial.BLOB_SCHEDULE`.
BLOQUE_DENCUN = 19_426_587
#: Primer bloque PoS, verificado en `historial.ALTURA_FUSION`.
BLOQUE_FUSION = 15_537_394


@dataclass(frozen=True)
class Caso:
    nombre: str
    desde: int
    hasta: int | None  # None = la cabeza de la cadena
    paso: int
    columnas: tuple[str, ...]
    para_que: str


CASOS = {
    "blobs": Caso(
        nombre="blobs",
        desde=BLOQUE_DENCUN,
        hasta=None,
        paso=5_000,
        columnas=("bloque", "marca", "blobs", "blob_gas_usado", "exceso_blob_gas"),
        para_que="caso 2 · ocupación de blobs contra el target del blobSchedule",
    ),
    "gas": Caso(
        nombre="gas",
        desde=BLOQUE_FUSION,
        hasta=None,
        paso=10_000,
        columnas=("bloque", "marca", "gas_usado", "gas_limite", "base_fee"),
        para_que="caso 3 · ocupación contra el límite que votan los validadores",
    ),
    "dificultad": Caso(
        nombre="dificultad",
        desde=4_000_000,
        hasta=BLOQUE_FUSION,
        paso=10_000,
        columnas=("bloque", "marca", "dificultad"),
        para_que="Medición 1 · cuánto pesaba la bomba contra la dificultad real",
    ),
}


class SinRespuesta(RuntimeError):
    """Ningún endpoint contestó. No es un error del dato: es de la red."""


# --------------------------------------------------------------------------- #
# JSON-RPC, a mano
# --------------------------------------------------------------------------- #


def _pedir(url: str, metodo: str, parametros: list, tiempo_limite: int = 20) -> dict:
    cuerpo = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": metodo, "params": parametros}
    ).encode("utf-8")
    pedido = urllib.request.Request(
        url,
        data=cuerpo,
        headers={"Content-Type": "application/json", "User-Agent": "genesis-replay/1"},
    )
    with urllib.request.urlopen(pedido, timeout=tiempo_limite) as respuesta:
        payload = json.loads(respuesta.read())
    if "error" in payload:
        raise SinRespuesta(f"{url} devolvió error: {payload['error']}")
    return payload["result"]


def elegir_endpoint(candidatos: tuple[str, ...] = ENDPOINTS) -> str:
    """El primero que conteste la altura de la cabeza. Falla ruidoso si ninguno."""
    fallas = []
    for url in candidatos:
        try:
            cabeza = int(_pedir(url, "eth_blockNumber", []), 16)
        except (urllib.error.URLError, SinRespuesta, TimeoutError, OSError, ValueError) as falla:
            fallas.append(f"  {url} → {type(falla).__name__}: {falla}")
            continue
        print(f"endpoint: {url} (cabeza {cabeza:,})")
        return url
    raise SinRespuesta(
        "ningún endpoint contestó:\n"
        + "\n".join(fallas)
        + "\n\nPasá el tuyo con --rpc https://…"
    )


def traer_bloque(url: str, altura: int, reintentos: int = 4) -> dict:
    """Un bloque, sin transacciones. Reintenta con espera creciente."""
    for intento in range(reintentos):
        try:
            bloque = _pedir(url, "eth_getBlockByNumber", [hex(altura), False])
            if bloque is None:
                raise SinRespuesta(f"el bloque {altura} volvió vacío")
            return bloque
        except (urllib.error.URLError, SinRespuesta, TimeoutError, OSError) as falla:
            if intento == reintentos - 1:
                raise
            espera = 2**intento
            print(f"  reintento {intento + 1} en {espera}s ({falla})", file=sys.stderr)
            time.sleep(espera)
    raise SinRespuesta("inalcanzable")  # pragma: no cover


# --------------------------------------------------------------------------- #
# Extracción por caso
# --------------------------------------------------------------------------- #


def _entero(bloque: dict, campo: str) -> int:
    valor = bloque.get(campo)
    return 0 if valor is None else int(valor, 16)


def fila(caso: Caso, bloque: dict) -> dict:
    altura = _entero(bloque, "number")
    marca = _entero(bloque, "timestamp")
    if caso.nombre == "blobs":
        gas_blob = _entero(bloque, "blobGasUsed")
        return {
            "bloque": altura,
            "marca": marca,
            "blobs": gas_blob // GAS_POR_BLOB,
            "blob_gas_usado": gas_blob,
            # `excessBlobGas` es el acumulador que Ethereum ya lleva para el fee
            # de blobs, y resuelve un problema de método: un bloque suelto dice
            # 0 o 6 blobs y no dice nada de la tendencia, mientras que el exceso
            # resume la historia reciente en un número. Es, además, exactamente
            # la forma de observable que una TRANSITION_RULE querría leer.
            "exceso_blob_gas": _entero(bloque, "excessBlobGas"),
        }
    if caso.nombre == "gas":
        return {
            "bloque": altura,
            "marca": marca,
            "gas_usado": _entero(bloque, "gasUsed"),
            "gas_limite": _entero(bloque, "gasLimit"),
            "base_fee": _entero(bloque, "baseFeePerGas"),
        }
    return {
        "bloque": altura,
        "marca": marca,
        "dificultad": _entero(bloque, "difficulty"),
    }


# --------------------------------------------------------------------------- #
# CSV con procedencia
# --------------------------------------------------------------------------- #


def ruta_de(caso: Caso) -> Path:
    return DATOS / f"{caso.nombre}.csv"


def cabecera(caso: Caso, url: str, hasta: int) -> list[str]:
    """La procedencia va **adentro del archivo**, no en un README que se separa."""
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return [
        f"# serie: {caso.nombre} — {caso.para_que}",
        f"# origen: {url} · eth_getBlockByNumber",
        f"# bajado: {ahora}",
        f"# rango: bloques {caso.desde}..{hasta} cada {caso.paso}",
        "# el paso es parte del dato: la serie está muestreada, no es continua",
    ]


def leer_serie(ruta: Path) -> tuple[list[str], list[dict]]:
    """Devuelve (comentarios de procedencia, filas). Sin red: esto corre siempre."""
    if not ruta.exists():
        return [], []
    comentarios, lineas = [], []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        (comentarios if linea.startswith("#") else lineas).append(linea)
    if not lineas:
        return comentarios, []
    lector = csv.DictReader(lineas)
    return comentarios, [
        {clave: int(valor) for clave, valor in registro.items()} for registro in lector
    ]


def escribir_serie(ruta: Path, caso: Caso, comentarios: list[str], filas: list[dict]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8", newline="") as salida:
        for comentario in comentarios:
            salida.write(comentario + "\n")
        escritor = csv.DictWriter(salida, fieldnames=list(caso.columnas))
        escritor.writeheader()
        escritor.writerows(filas)


# --------------------------------------------------------------------------- #
# La bajada
# --------------------------------------------------------------------------- #


def bajar(caso: Caso, url: str, tope: int | None = None) -> Path:
    ruta = ruta_de(caso)
    comentarios, ya_estan = leer_serie(ruta)
    conocidos = {f["bloque"] for f in ya_estan}

    hasta = caso.hasta or int(_pedir(url, "eth_blockNumber", []), 16)
    alturas = list(range(caso.desde, hasta + 1, caso.paso))
    faltan = [a for a in alturas if a not in conocidos]
    if tope:
        faltan = faltan[:tope]

    if not faltan:
        print(f"{caso.nombre}: ya está completo ({len(ya_estan)} filas) → {ruta}")
        return ruta

    print(
        f"{caso.nombre}: {len(faltan):,} bloques por bajar de {len(alturas):,} "
        f"(ya había {len(ya_estan):,}). Ctrl-C corta y se puede retomar."
    )

    filas = list(ya_estan)
    comienzo = time.time()
    try:
        for indice, altura in enumerate(faltan, start=1):
            filas.append(fila(caso, traer_bloque(url, altura)))
            if indice % 25 == 0 or indice == len(faltan):
                ritmo = indice / max(time.time() - comienzo, 0.001)
                restante = (len(faltan) - indice) / max(ritmo, 0.001)
                print(
                    f"  {indice:,}/{len(faltan):,} · {ritmo:.1f} bloques/s · "
                    f"faltan ~{restante / 60:.1f} min",
                    end="\r",
                    flush=True,
                )
    except KeyboardInterrupt:
        print("\ncortado a mano: se guarda lo que hay y se puede retomar")
    finally:
        filas.sort(key=lambda f: f["bloque"])
        escribir_serie(ruta, caso, cabecera(caso, url, hasta), filas)

    print(f"\n{caso.nombre}: {len(filas):,} filas → {ruta}")
    return ruta


def main(argumentos: list[str]) -> int:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:  # pragma: no cover
            pass

    analizador = argparse.ArgumentParser(
        description="Trae las series que le faltan a la Fase 2.",
        epilog="Las tres salen de eth_getBlockByNumber. No hace falta clave en general.",
    )
    analizador.add_argument("caso", choices=sorted(CASOS), help="qué serie bajar")
    analizador.add_argument("--rpc", help="endpoint JSON-RPC propio")
    analizador.add_argument("--paso", type=int, help="cada cuántos bloques muestrear")
    analizador.add_argument("--desde", type=int, help="bloque inicial")
    analizador.add_argument("--hasta", type=int, help="bloque final")
    analizador.add_argument(
        "--tope", type=int, help="cortar después de N bloques (para probar)"
    )
    opciones = analizador.parse_args(argumentos)

    caso = CASOS[opciones.caso]
    if opciones.paso or opciones.desde or opciones.hasta:
        caso = Caso(
            nombre=caso.nombre,
            desde=opciones.desde or caso.desde,
            hasta=opciones.hasta if opciones.hasta is not None else caso.hasta,
            paso=opciones.paso or caso.paso,
            columnas=caso.columnas,
            para_que=caso.para_que,
        )

    try:
        url = opciones.rpc or elegir_endpoint()
        bajar(caso, url, tope=opciones.tope)
    except SinRespuesta as falla:
        print(f"\nNo se pudo bajar: {falla}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
