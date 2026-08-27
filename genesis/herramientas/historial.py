"""El historial real de Ethereum. **Datos de terceros, no del autor del diseño.**

Toda la Fase 2 se apoya en este archivo, así que tiene una regla propia: **cada
registro lleva su procedencia**, y ningún número entra sin decir de dónde salió y
contra qué se verificó. Un harness alimentado con números recordados produce
evidencia propia con disfraz de evidencia ajena, que es exactamente lo que §11
dice que al proyecto le sobra.

> **VERIFICADO el 19/8/2026** contra fuente primaria, número por número:
>
> - los **seis offsets** de la bomba, contra el texto de cada EIP en
>   `eips.ethereum.org` — la línea `fake_block_number = max(0, block.number - N)`;
> - las **seis alturas de activación**, contra `MainnetChainConfig` en
>   `ethereum/go-ethereum`, `params/config.go`. Los EIPs **no** las traen: usan un
>   placeholder (`BYZANTIUM_FORK_BLKNUM`, `FORK_BLOCK_NUMBER`), así que hacía falta
>   una segunda fuente y ésta es la que corren los nodos;
> - el **blobSchedule** completo, del mismo `config.go`, más el texto de EIP-4844,
>   EIP-7691 y EIP-7892.
>
> Lo que **sigue faltando** son las **series** (ocupación), y no por descuido: ver
> `SERIES_QUE_FALTAN` al final.

## Por qué la bomba primero, y no los blobs

El roadmap nombra tres casos y el primero que se implementó es el último de la
lista, a propósito. Los otros dos necesitan una **serie**: cuán llenos venían los
bloques, cuántos blobs por bloque. Eso no se puede escribir de memoria.

La bomba no. Su efecto es una **función determinista de la altura**, escrita en
los EIPs, y las seis decisiones humanas son seis alturas. Con eso solo ya se puede
contestar la pregunta de la fase, sin pedirle nada a nadie.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

EIPS = "https://eips.ethereum.org/EIPS/"
GETH_CONFIG = (
    "https://raw.githubusercontent.com/ethereum/go-ethereum/master/params/config.go"
)

#: El bloque de la fusión: de ahí en adelante la bomba dejó de importar, así que
#: es donde termina el replay. La dificultad total terminal está en `config.go`
#: (`MainnetTerminalTotalDifficulty = 58_750_000_000_000_000_000_000`); la altura
#: del primer bloque PoS no es una constante del cliente y se verificó aparte.
ALTURA_FUSION = 15_537_394
FECHA_FUSION = "2022-09-15"

#: Segundos por bloque que se usan **solamente** para traducir bloques a días en
#: los informes. No entra en ninguna cuenta del replay: es una regla de tres para
#: que los números se lean, y está declarada para que se pueda discutir.
SEGUNDOS_POR_BLOQUE = 13.5


def fecha_utc(marca: int) -> str:
    """La fecha de un timestamp de activación. Se deriva, no se transcribe."""
    return datetime.fromtimestamp(marca, timezone.utc).strftime("%Y-%m-%d")


# --------------------------------------------------------------------------- #
# Caso 1 · la bomba de dificultad — COMPLETO
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Retraso:
    """Una vez que los humanos corrieron la bomba, con un fork.

    `offset` es el **total** que el EIP resta a la altura, no el incremento: cada
    EIP reescribe el número entero. Confundirlos da un factor de dos en todo lo
    que sigue.
    """

    fork: str
    eip: str
    altura: int
    fecha: str
    offset: int
    procedencia: str

    @property
    def fuente_offset(self) -> str:
        return f"{EIPS}{self.eip.lower()}"


#: Los seis retrasos de la bomba de dificultad, en orden.
#:
#: La bomba: `dificultad += 2 ** (piso((altura - offset) / 100_000) - 2)`. Con
#: `offset = 0` originalmente, y cada uno de estos EIPs reescribiéndolo.
RETRASOS: tuple[Retraso, ...] = (
    Retraso(
        fork="Byzantium",
        eip="EIP-649",
        altura=4_370_000,
        fecha="2017-10-16",
        offset=3_000_000,
        procedencia="EIP-649 · offset verificado en el texto; altura en MainnetChainConfig",
    ),
    Retraso(
        fork="Constantinople",
        eip="EIP-1234",
        altura=7_280_000,
        fecha="2019-02-28",
        offset=5_000_000,
        procedencia="EIP-1234 · offset verificado en el texto; altura en MainnetChainConfig",
    ),
    Retraso(
        fork="Muir Glacier",
        eip="EIP-2384",
        altura=9_200_000,
        fecha="2020-01-02",
        offset=9_000_000,
        procedencia="EIP-2384 · offset verificado en el texto; altura en MainnetChainConfig",
    ),
    Retraso(
        fork="London",
        eip="EIP-3554",
        altura=12_965_000,
        fecha="2021-08-05",
        offset=9_700_000,
        procedencia="EIP-3554 · offset verificado en el texto; altura en MainnetChainConfig",
    ),
    Retraso(
        fork="Arrow Glacier",
        eip="EIP-4345",
        altura=13_773_000,
        fecha="2021-12-09",
        offset=10_700_000,
        procedencia="EIP-4345 · offset verificado en el texto; altura en MainnetChainConfig",
    ),
    Retraso(
        fork="Gray Glacier",
        eip="EIP-5133",
        altura=15_050_000,
        fecha="2022-06-30",
        offset=11_400_000,
        procedencia="EIP-5133 · offset verificado en el texto; altura en MainnetChainConfig",
    ),
)

#: Contexto que cambia la lectura de tres de los seis, y que no está en los
#: números: si el fork existía igual por otro motivo, retrasar la bomba fue una
#: decisión **de oportunidad** y no de umbral. Al comparar, esto es lo que podría
#: explicar los desvíos — y por eso está acá y no en la conclusión.
FORK_POR_OTRO_MOTIVO = {
    "Byzantium": "Metropolis: además bajó la recompensa de 5 a 3 ETH",
    "Constantinople": "además bajó la recompensa de 3 a 2 ETH",
    "London": "EIP-1559: el fork existía por el mercado de fees, no por la bomba",
    "Muir Glacier": "fork exclusivo de la bomba",
    "Arrow Glacier": "fork exclusivo de la bomba",
    "Gray Glacier": "fork exclusivo de la bomba",
}


# --------------------------------------------------------------------------- #
# Caso 2 · los blobs — LA VERDAD DE BASE ESTÁ; FALTA LA SERIE
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ParametrosBlob:
    """Una recalibración de la capacidad de blobs, con su activación."""

    nombre: str
    marca_activacion: int
    target: int
    maximo: int
    fraccion_actualizacion: int
    eip: str
    procedencia: str

    @property
    def fecha(self) -> str:
        return fecha_utc(self.marca_activacion)


#: El `blobSchedule` real de mainnet. **Son las decisiones humanas del caso 2**, y
#: están completas: cuatro recalibraciones en menos de dos años.
#:
#: Osaka (Fusaka) no tiene entrada propia: hereda la anterior. Está igual en la
#: lista, con `target`/`maximo` heredados, porque es una activación real y omitirla
#: haría ver tres decisiones donde hubo cuatro momentos.
BLOB_SCHEDULE: tuple[ParametrosBlob, ...] = (
    ParametrosBlob(
        nombre="Cancun (Dencun)",
        marca_activacion=1_710_338_135,
        target=3,
        maximo=6,
        fraccion_actualizacion=3_338_477,
        eip="EIP-4844",
        procedencia="config.go DefaultCancunBlobConfig · EIP-4844 (target 3 / máx 6)",
    ),
    ParametrosBlob(
        nombre="Prague (Pectra)",
        marca_activacion=1_746_612_311,
        target=6,
        maximo=9,
        fraccion_actualizacion=5_007_716,
        eip="EIP-7691",
        procedencia="config.go DefaultPragueBlobConfig · EIP-7691 (target 6 / máx 9)",
    ),
    ParametrosBlob(
        nombre="BPO1",
        marca_activacion=1_765_290_071,
        target=10,
        maximo=15,
        fraccion_actualizacion=8_346_193,
        eip="EIP-7892",
        procedencia="config.go DefaultBPO1BlobConfig · fork BPO de EIP-7892",
    ),
    ParametrosBlob(
        nombre="BPO2",
        marca_activacion=1_767_747_671,
        target=14,
        maximo=21,
        fraccion_actualizacion=11_684_671,
        eip="EIP-7892",
        procedencia="config.go DefaultBPO2BlobConfig · fork BPO de EIP-7892",
    ),
)

#: EIP-7892, **Final**, en sus propias palabras. Es el cliente del §12 Test 1
#: describiendo el problema del paper sin conocer el paper — y describiendo también
#: cómo lo resolvió, que **no** es con una regla determinista sino con un fork más
#: barato. Las dos mitades importan y hay que leerlas juntas.
EIP_7892 = {
    "estado": "Final (Informational)",
    "abstract": (
        "This EIP introduces Blob Parameter Only (BPO) Hardforks, a lightweight "
        "mechanism for incrementally scaling Ethereum's blob capacity through "
        "targeted hard forks that modify only blob-related parameters: target, max, "
        "and baseFeeUpdateFraction."
    ),
    "motivacion": (
        "the current approach of only modifying blob parameters in large, infrequent "
        "hard forks is not agile enough to keep up with L2 growth"
    ),
    "fuente": f"{EIPS}eip-7892",
}


# --------------------------------------------------------------------------- #
# Lo que falta, y por qué no se inventa
# --------------------------------------------------------------------------- #

#: Las series que los casos 2 y 3 necesitan y que **no se pueden transcribir**.
#:
#: No es una limitación del harness: es la diferencia entre medir el mundo y medir
#: un modelo propio. Un trigger de ocupación lee una serie; si la serie la genera
#: el harness, el resultado vuelve a ser evidencia propia y la fase pierde su único
#: motivo de existir.
SERIES_QUE_FALTAN = {
    "blobs_por_bloque": (
        "media de blobs por bloque desde Dencun (2024-03-13). Con eso el caso 2 "
        "corre entero: las cuatro decisiones humanas ya están verificadas en "
        "BLOB_SCHEDULE, falta el observable que el trigger leería. "
        "Requiere JSON-RPC o una API con clave: no se puede traer con un GET."
    ),
    "gas_usado_sobre_limite": (
        "media de gas usado sobre gas límite. El caso 3 además es distinto de los "
        "otros dos: el límite ya se vota bloque a bloque, así que la comparación no "
        "es contra un fork sino contra una coordinación off-chain."
    ),
    "dificultad_de_la_red": (
        "serie de dificultad de mainnet 2017-2022. No abre un caso nuevo: es el dato "
        "que decide cuál de las dos lecturas de la Medición 1 es la que importa — si "
        "la dispersión de 16× en el término de la bomba se traducía o no en dolor "
        "para el usuario."
    ),
}
