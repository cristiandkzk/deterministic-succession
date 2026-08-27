"""Fase 2 · caso 3: el gas limit de Ethereum. `python herramientas/replay_gas.py`

**Es el más distinto de los tres, y por eso queda para el final.** Los otros dos
comparan una regla contra un fork; acá no hay fork que comparar: el gas limit ya es
un parámetro que **cada validador vota bloque a bloque**, con un tope de 1/1024 de
cambio por bloque. O sea que el mecanismo del paper no compite contra una
coordinación pesada — compite contra una coordinación **liviana, descentralizada y
sin fork, que ya funciona**.

Y el resultado es el más incómodo de la fase: **para este parámetro no hay trigger
admisible**, y no por falta de ingenio sino por una razón estructural que se puede
medir.

## Las tres piezas

**1 · La ocupación no lleva información.** EIP-1559 fija el target en la mitad del
límite y mueve el base fee hasta que el uso vuelve ahí. Medido sobre cuatro años y un
rango de 300× en el fee: la ocupación media se queda entre 48% y 55% **siempre**, y su
correlación con el base fee es **−0,02**. El observable de cantidad, que es el que
§7.6 quiere, está vacío por construcción.

**2 · El base fee es la única señal, y es nominal.** Cayó de ~26 gwei a 0,08 gwei
—unas 300 veces— en cuatro años. Cualquier umbral en gwei elegido en Genesis deja de
significar lo que significaba. Es exactamente lo que C7.13 encontró para `r0`: *un
precio nominal fijo no puede racionar un recurso real bajo una moneda que flota.*

**3 · La forma adimensional arregla eso y trae un trinquete.** Comparar el base fee
contra su propia mediana anual es escalable y computable desde el estado — y funciona
bien donde importa. Pero se queda **sin noción de caro**: cuando el fee ya cayó 300×,
que se duplique de 0,08 a 0,17 gwei vuelve a disparar la regla, que es económicamente
absurdo.

## Sobre leer un precio, que es la duda obvia

§7.6 prohíbe que el trigger lea **precios de mercado on-chain** —ratios de pool,
profundidad, volumen— porque eso permitiría *comprar una transición* moviendo un pool
con capital prestado. El base fee no es eso: **lo computa el protocolo** desde la
ocupación, y empujarlo exige llenar bloques y quemar el fee. Cae del lado del canal de
quema que §10.2 ya declara como frontera acotada, no del lado del oráculo. Lo que lo
descalifica no es de dónde sale: es que es **nominal**.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from herramientas import historial  # noqa: E402
from herramientas.traer_datos import leer_serie  # noqa: E402
from protocolo import genesis as g  # noqa: E402
from protocolo import invariantes as inv  # noqa: E402
from protocolo.generacion import Params, Ruleset  # noqa: E402
from protocolo.serializacion import huella  # noqa: E402
from sucesion.regla import ReglaTransicion  # noqa: E402

RUTA_GAS = Path(__file__).resolve().parent / "datos" / "gas.csv"

#: La muestra es un bloque cada 10.000 (~33 h), así que:
VENTANA_CORTA = 22   # ≈ 30 días
VENTANA_LARGA = 263  # ≈ 365 días

#: EIP-1559: el target es la mitad del límite, en ppm de ocupación.
TARGET_PPM = 500_000

SEGUNDOS_POR_DIA = 86_400


def serie() -> list[dict]:
    _, filas = leer_serie(RUTA_GAS)
    return filas


def mediana(valores: list[int]) -> int:
    ordenados = sorted(valores)
    return ordenados[len(ordenados) // 2]


def ocupacion_ppm(fila: dict) -> int:
    return fila["gas_usado"] * 1_000_000 // fila["gas_limite"]


# --------------------------------------------------------------------------- #
# Medición A · la trayectoria humana (cero parámetros)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Meseta:
    desde: str
    hasta: str
    limite_desde: int
    limite_hasta: int
    dias: float


def mesetas(salto_ppm: int = 20_000) -> list[Meseta]:
    """Los tramos donde el límite se quedó quieto, y los saltos entre ellos."""
    filas = serie()
    if not filas:
        return []
    salida: list[Meseta] = []
    anterior, inicio = filas[0]["gas_limite"], filas[0]
    for fila in filas:
        if abs(fila["gas_limite"] - anterior) * 1_000_000 // anterior > salto_ppm:
            salida.append(
                Meseta(
                    desde=historial.fecha_utc(inicio["marca"]),
                    hasta=historial.fecha_utc(fila["marca"]),
                    limite_desde=anterior,
                    limite_hasta=fila["gas_limite"],
                    dias=(fila["marca"] - inicio["marca"]) / SEGUNDOS_POR_DIA,
                )
            )
            anterior, inicio = fila["gas_limite"], fila
    salida.append(
        Meseta(
            desde=historial.fecha_utc(inicio["marca"]),
            hasta=historial.fecha_utc(filas[-1]["marca"]),
            limite_desde=anterior,
            limite_hasta=filas[-1]["gas_limite"],
            dias=(filas[-1]["marca"] - inicio["marca"]) / SEGUNDOS_POR_DIA,
        )
    )
    return salida


# --------------------------------------------------------------------------- #
# Medición B · la ocupación no lleva información (cero parámetros)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SenalDeOcupacion:
    muestras: int
    ocupacion_media_ppm: int
    ocupacion_minima_ppm: int
    ocupacion_maxima_ppm: int
    correlacion_milesimas: int
    base_fee_maximo: int
    base_fee_minimo: int

    @property
    def caida_del_fee(self) -> float:
        return self.base_fee_maximo / max(self.base_fee_minimo, 1)


def senal_de_ocupacion(ventana: int = 60) -> SenalDeOcupacion | None:
    """¿La ocupación dice algo sobre la demanda? Medido, no argumentado.

    La correlación se calcula contra el base fee, que es la señal que sí existe. Si
    la ocupación tuviera información, tendrían que moverse juntos.
    """
    filas = serie()
    if not filas:
        return None

    ocupaciones = [ocupacion_ppm(f) for f in filas]
    fees = [f["base_fee"] for f in filas]
    cantidad = len(filas)

    media_ocupacion = sum(ocupaciones) / cantidad
    media_fee = sum(fees) / cantidad
    covarianza = sum(
        (o - media_ocupacion) * (b - media_fee) for o, b in zip(ocupaciones, fees)
    ) / cantidad
    desvio_ocupacion = (
        sum((o - media_ocupacion) ** 2 for o in ocupaciones) / cantidad
    ) ** 0.5
    desvio_fee = (sum((b - media_fee) ** 2 for b in fees) / cantidad) ** 0.5
    correlacion = covarianza / (desvio_ocupacion * desvio_fee)

    # medias móviles, para que el ruido de una muestra suelta no confunda
    medias = [
        sum(ocupaciones[i - ventana : i]) // ventana
        for i in range(ventana, cantidad + 1)
    ]
    medianas_fee = [
        mediana(fees[i - ventana : i]) for i in range(ventana, cantidad + 1)
    ]

    return SenalDeOcupacion(
        muestras=cantidad,
        ocupacion_media_ppm=int(media_ocupacion),
        ocupacion_minima_ppm=min(medias),
        ocupacion_maxima_ppm=max(medias),
        correlacion_milesimas=round(correlacion * 1_000),
        base_fee_maximo=max(medianas_fee),
        base_fee_minimo=min(medianas_fee),
    )


# --------------------------------------------------------------------------- #
# La regla candidata: adimensional, y con su defecto medido
# --------------------------------------------------------------------------- #


@dataclass
class EstadoGas:
    """Lo que la regla lee. Un contador monótono y el ruleset vigente."""

    periodos_caros: int = 0
    periodos_caros_al_ultimo_cambio: int = 0
    limite_vigente: int = 30_000_000
    distancias: dict | None = None

    def canonico(self) -> dict:
        return {
            "periodos_caros": self.periodos_caros,
            "periodos_caros_al_ultimo_cambio": self.periodos_caros_al_ultimo_cambio,
            "limite_vigente": self.limite_vigente,
        }

    def huella(self) -> bytes:
        return huella(self.canonico(), dominio="replay/gas")

    def lockins_de(self, nombre_de_regla: str) -> int:
        return 0


class ReglaLimiteGas(ReglaTransicion):
    """*Subir el límite tras N períodos con el fee caro respecto de su propia historia.*

    El progreso es un contador de períodos caros —monótono, C9.3 otra vez— y el
    umbral se corre en cada cambio. Lo que la regla llama *caro* es adimensional: el
    fee contra su mediana anual, no contra un número de gwei.
    """

    nombre = "gas/limite"
    clase = g.CIRCULACION
    modo = inv.MODO_APROXIMACION

    def __init__(self, periodos: int = 3, salto: int = 5_000_000) -> None:
        self.periodos = periodos
        self.salto = salto

    def progreso(self, estado) -> int:
        return estado.periodos_caros

    def umbral(self, estado) -> int:
        return estado.periodos_caros_al_ultimo_cambio + self.periodos

    def params_sucesor(self, estado, ruleset: Ruleset) -> Params:
        return Params(
            generacion=ruleset.generacion + 1,
            internos={"gas_limite": estado.limite_vigente + self.salto},
            formatos=ruleset.formatos,
        )


@dataclass(frozen=True)
class Disparo:
    fecha: str
    base_fee_gwei: float
    limite: int
    ratio_milesimas: int


def contrafactico(k_milesimas: int = 1_500, separacion: int = VENTANA_CORTA) -> list[Disparo]:
    """Cuándo dispararía *el fee sobre su mediana anual ≥ k*.

    `separacion` evita contar el mismo episodio muchas veces: después de un disparo
    hay que esperar una ventana corta para volver a mirar.
    """
    filas = serie()
    if len(filas) <= VENTANA_LARGA:
        return []
    fees = [f["base_fee"] for f in filas]
    salida: list[Disparo] = []
    ultimo = -10**6
    for i in range(VENTANA_LARGA, len(filas)):
        corta = mediana(fees[i - VENTANA_CORTA : i + 1])
        larga = mediana(fees[i - VENTANA_LARGA : i + 1])
        if larga and corta * 1_000 >= k_milesimas * larga and i - ultimo > separacion:
            salida.append(
                Disparo(
                    fecha=historial.fecha_utc(filas[i]["marca"]),
                    base_fee_gwei=corta / 1e9,
                    limite=filas[i]["gas_limite"],
                    ratio_milesimas=corta * 1_000 // larga,
                )
            )
            ultimo = i
    return salida


def revisar_invariantes() -> None:
    regla = ReglaLimiteGas()
    estado = EstadoGas(periodos_caros=5, periodos_caros_al_ultimo_cambio=2)
    inv.i2_trigger_solo_estado(regla, estado)
    inv.i2_modo_declarado(regla)
    inv.i2_aproximacion_monotona(regla.nombre, [0, 1, 1, 2, 5, 9])


# --------------------------------------------------------------------------- #
# Informe
# --------------------------------------------------------------------------- #


def informe() -> str:
    lineas: list[str] = []
    ancho = 78
    linea = "-" * ancho

    lineas.append("=" * ancho)
    lineas.append("FASE 2 · caso 3 — el gas limit de Ethereum")
    lineas.append("el único de los tres donde no hay fork: se vota bloque a bloque")
    lineas.append("=" * ancho)

    filas = serie()
    if not filas:
        lineas.append("")
        lineas.append("FALTA LA SERIE: python herramientas/traer_datos.py gas")
        return chr(10).join(lineas)

    lineas.append(
        f"serie: {len(filas):,} muestras · "
        f"{historial.fecha_utc(filas[0]['marca'])} .. {historial.fecha_utc(filas[-1]['marca'])}"
    )

    lineas.append("")
    lineas.append("MEDICIÓN A · la trayectoria humana — CERO parámetros libres")
    lineas.append("")
    lineas.append(f"{'desde':>12}{'hasta':>12}{'límite':>18}{'duración':>12}")
    lineas.append(linea)
    for meseta in mesetas():
        lineas.append(
            f"{meseta.desde:>12}{meseta.hasta:>12}"
            f"{meseta.limite_desde / 1e6:>9.1f}M →{meseta.limite_hasta / 1e6:>6.1f}M"
            f"{meseta.dias:>10.0f} d"
        )
    lineas.append(linea)

    senal = senal_de_ocupacion()
    lineas.append("")
    lineas.append("MEDICIÓN B · la ocupación no lleva información — CERO parámetros")
    lineas.append("")
    lineas.append(
        f"  ocupación media                {senal.ocupacion_media_ppm / 10_000:>8.1f}%"
    )
    lineas.append(
        f"  rango de la media móvil        "
        f"{senal.ocupacion_minima_ppm / 10_000:>8.1f}% .. "
        f"{senal.ocupacion_maxima_ppm / 10_000:.1f}%"
    )
    lineas.append(
        f"  base fee mediano, rango        "
        f"{senal.base_fee_maximo / 1e9:>8.2f} .. {senal.base_fee_minimo / 1e9:.3f} gwei"
        f"  ({senal.caida_del_fee:,.0f}× de caída)"
    )
    lineas.append(
        f"  correlación ocupación/base fee {senal.correlacion_milesimas / 1_000:>8.3f}"
    )
    lineas.append("")
    lineas.append(
        "  EIP-1559 fija el target en la mitad del límite y mueve el fee hasta que"
    )
    lineas.append(
        "  el uso vuelve ahí. Con el fee moviéndose 300×, la ocupación no se mueve:"
    )
    lineas.append(
        "  **el observable de cantidad que §7.6 quiere está vacío por construcción.**"
    )

    lineas.append("")
    lineas.append("MEDICIÓN C · la única señal es el fee, y ninguna de sus dos formas sirve")
    lineas.append("")
    lineas.append("  forma nominal (umbral en gwei):")
    lineas.append(
        f"    el fee mediano cayó de {senal.base_fee_maximo / 1e9:.2f} a "
        f"{senal.base_fee_minimo / 1e9:.3f} gwei — {senal.caida_del_fee:,.0f}×."
    )
    lineas.append(
        "    Cualquier número elegido en Genesis deja de significar lo que significaba."
    )
    lineas.append("")
    lineas.append("  forma adimensional (fee sobre su mediana anual ≥ k):")
    for k in (1_000, 1_500):
        disparos = contrafactico(k)
        lineas.append(f"    k = {k / 1_000:.1f}: {len(disparos)} disparos")
        for disparo in disparos:
            lineas.append(
                f"      {disparo.fecha}  fee {disparo.base_fee_gwei:>7.3f} gwei"
                f"  límite {disparo.limite / 1e6:>4.0f}M"
                f"  ratio {disparo.ratio_milesimas / 1_000:.2f}"
            )
    lineas.append("")
    lineas.append(linea)
    lineas.append("La regla candidata contra los predicados de I2 del protocolo:")
    try:
        revisar_invariantes()
        lineas.append("    OK — el trigger sale del estado y el progreso no retrocede")
    except inv.ViolacionInvariante as falla:  # pragma: no cover
        lineas.append(f"    FALLA — {falla}")
    lineas.append(
        "    (pasa I2 y aun así no sirve: el problema no es de dónde sale el dato)"
    )
    return chr(10).join(lineas)


def main() -> int:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:  # pragma: no cover
            pass
    print(informe())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
