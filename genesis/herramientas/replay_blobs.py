"""Fase 2 · caso 2: el `blobSchedule` de Ethereum. `python herramientas/replay_blobs.py`

Es el caso que el roadmap nombra **primero**, y el que tiene el cliente más cerca del
diseño: EIP-7892 existe porque Ethereum quiere recalibrar la capacidad de blobs sin
pagar un fork grande cada vez.

Cuatro decisiones humanas, verificadas en `historial.BLOB_SCHEDULE`: target 3 → 6 →
10 → 14 en 22 meses. La pregunta de la fase: **si eso hubiera sido una
`TRANSITION_RULE`, ¿qué habría pasado?**

## Dos avisos sobre el dato, y los dos cambian la medición

**1 · `excessBlobGas` no sirve para comparar a través de Fusaka.** Era el observable
natural —el acumulador que la propia cadena lleva para el fee de blobs— y por eso el
traedor lo baja. Pero **EIP-7918** cambió su regla de actualización: cuando el fee de
blobs cae por debajo de un piso atado al costo de ejecución, el exceso deja de decaer
y pasa a crecer por `blob_gas_used * (max - target) / max`. Se ve en la serie: bajo
target 14, con la demanda al 31%, el exceso **sube igual**. Así que la medición usa
**ocupación** —blobs contra target—, que significa lo mismo antes y después.

**2 · BPO1 y BPO2 no son dos decisiones: son un cronograma.** Los dos se anunciaron
juntos el 6/11/2025, **antes de que Fusaka activara**. Tratarlos como respuestas
independientes a la demanda sería leer mal el dato, y es lo que explica la mitad del
resultado.

## Qué se mide

- **la ocupación bajo cada target** — cero parámetros libres. Es una medición;
- **el contrafáctico por decisión** — un parámetro: a qué ocupación sostenida
  dispararía la regla, con la ventana fija. Igual que en el caso de la bomba, el
  target vigente lo pone el historial, así que no hay un segundo parámetro
  contaminando el primero.

> **La serie está muestreada**, un bloque cada 5.000 (~16,7 h). Para una media móvil
> de 30 días eso son 43 observaciones, que alcanza para una tasa; no alcanzaría para
> nada que dependa de un bloque en particular.
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

RUTA_BLOBS = Path(__file__).resolve().parent / "datos" / "blobs.csv"

#: Muestras de la media móvil. 43 × 5.000 bloques ≈ 30 días.
VENTANA = 43

#: Ocupación que se considera "saturado" al describir un tramo, en ppm.
SATURADO_PPM = 800_000

SEGUNDOS_POR_DIA = 86_400


def serie() -> list[dict]:
    _, filas = leer_serie(RUTA_BLOBS)
    return filas


def hitos(filas: list[dict]) -> list[tuple]:
    """(parámetros, índice de la primera muestra bajo ese target)."""
    marcados = []
    for parametros in historial.BLOB_SCHEDULE:
        indice = next(
            (i for i, f in enumerate(filas) if f["marca"] >= parametros.marca_activacion),
            None,
        )
        if indice is not None:
            marcados.append((parametros, indice))
    return marcados


def ocupacion_movil(filas: list[dict], indice: int, target: int, ventana: int = VENTANA) -> int:
    """Blobs entregados contra blobs objetivo en la ventana, en ppm.

    Puede pasar de 1.000.000: el target es el promedio buscado, no el techo — el
    máximo por bloque es mayor, así que una demanda sostenida lo supera y ahí es
    donde el fee de blobs empieza a subir.
    """
    tramo = filas[max(0, indice - ventana + 1) : indice + 1]
    return sum(f["blobs"] for f in tramo) * 1_000_000 // (len(tramo) * target)


# --------------------------------------------------------------------------- #
# Medición A · la ocupación bajo cada target (cero parámetros)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Tramo:
    nombre: str
    target: int
    maximo: int
    desde: str
    muestras: int
    ocupacion_ppm: int
    #: `None` cuando el tramo dura menos que la ventana móvil: no hay con qué
    #: calcularlos y un cero se leería como una medición. Le pasa a BPO1, que duró
    #: 29 días contra una ventana de 30 — y eso ya dice algo del caso.
    pico_ppm: int | None
    saturado_ppm: int | None

    @property
    def ocupacion(self) -> float:
        return self.ocupacion_ppm / 10_000


def tramos() -> list[Tramo]:
    filas = serie()
    if not filas:
        return []
    marcados = hitos(filas)
    salida: list[Tramo] = []
    for numero, (parametros, inicio) in enumerate(marcados):
        fin = marcados[numero + 1][1] if numero + 1 < len(marcados) else len(filas)
        muestras = filas[inicio:fin]
        if not muestras:
            continue
        medias = [
            ocupacion_movil(filas, i, parametros.target)
            for i in range(inicio + VENTANA, fin)
        ]
        salida.append(
            Tramo(
                nombre=parametros.nombre,
                target=parametros.target,
                maximo=parametros.maximo,
                desde=parametros.fecha,
                muestras=len(muestras),
                ocupacion_ppm=sum(f["blobs"] for f in muestras)
                * 1_000_000
                // (len(muestras) * parametros.target),
                pico_ppm=max(medias) if medias else None,
                saturado_ppm=(
                    sum(1 for m in medias if m >= SATURADO_PPM) * 1_000_000 // len(medias)
                    if medias
                    else None
                ),
            )
        )
    return salida


# --------------------------------------------------------------------------- #
# La regla candidata
# --------------------------------------------------------------------------- #


@dataclass
class EstadoBlobs:
    """El estado que la regla lee. Todo sale de la cadena.

    `blobs_acumulados` es monótono y `blobs_hace_una_ventana` sale del mismo
    acumulador leído `VENTANA` atrás: es la construcción de C9.3 otra vez —
    **progreso que no retrocede, umbral que se mueve**— y acá es obligatoria,
    porque la ocupación sube y baja y como progreso violaría I2.

    Que la cadena tenga que guardar una ventana no es exótico: Ethereum ya guarda
    un acumulador equivalente (`excessBlobGas`) para cobrar el fee de blobs.
    """

    blobs_acumulados: int = 0
    blobs_hace_una_ventana: int = 0
    target_vigente: int = 3
    distancias: dict | None = None

    def canonico(self) -> dict:
        return {
            "blobs_acumulados": self.blobs_acumulados,
            "blobs_hace_una_ventana": self.blobs_hace_una_ventana,
            "target_vigente": self.target_vigente,
        }

    def huella(self) -> bytes:
        return huella(self.canonico(), dominio="replay/blobs")

    def lockins_de(self, nombre_de_regla: str) -> int:
        return 0


class ReglaTargetBlobs(ReglaTransicion):
    """*Subir el target cuando la ocupación sostenida pase el umbral.*

    Cumple I2 **por aproximación observable**: la ocupación es agregada —la mueven
    todos los rollups juntos, ninguno solo— y la cadena puede publicar cuánto falta.
    """

    nombre = "blobs/target"
    clase = g.CIRCULACION
    modo = inv.MODO_APROXIMACION

    def __init__(self, ocupacion_ppm: int, ventana: int = VENTANA, salto: int = 3) -> None:
        self.ocupacion_ppm = ocupacion_ppm
        self.ventana = ventana
        self.salto = salto

    def progreso(self, estado) -> int:
        return estado.blobs_acumulados

    def umbral(self, estado) -> int:
        entregados = self.ventana * estado.target_vigente * self.ocupacion_ppm
        return estado.blobs_hace_una_ventana + entregados // 1_000_000

    def params_sucesor(self, estado, ruleset: Ruleset) -> Params:
        return Params(
            generacion=ruleset.generacion + 1,
            internos={"target_blobs": estado.target_vigente + self.salto},
            formatos=ruleset.formatos,
        )


# --------------------------------------------------------------------------- #
# Medición B · el contrafáctico por decisión (un parámetro)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Contrafactico:
    decision: str
    fecha_humana: str
    fecha_regla: str | None
    dias: float | None
    target_vigente: int
    ocupacion_al_decidir_ppm: int

    @property
    def disparo(self) -> bool:
        return self.fecha_regla is not None


def contrafactico(ocupacion_ppm: int, ventana: int = VENTANA) -> list[Contrafactico]:
    """Cuándo habría disparado la regla bajo el target que estaba vigente.

    Positivo en `dias` = **los humanos tardaron más** que la regla.
    """
    filas = serie()
    if not filas:
        return []
    marcados = hitos(filas)
    salida: list[Contrafactico] = []

    for numero in range(len(marcados) - 1):
        vigente, inicio = marcados[numero]
        siguiente, fin = marcados[numero + 1]
        disparo = next(
            (
                i
                for i in range(inicio + ventana, fin)
                if ocupacion_movil(filas, i, vigente.target, ventana) >= ocupacion_ppm
            ),
            None,
        )
        salida.append(
            Contrafactico(
                decision=siguiente.nombre,
                fecha_humana=siguiente.fecha,
                fecha_regla=historial.fecha_utc(filas[disparo]["marca"]) if disparo else None,
                dias=(
                    (siguiente.marca_activacion - filas[disparo]["marca"]) / SEGUNDOS_POR_DIA
                    if disparo
                    else None
                ),
                target_vigente=vigente.target,
                ocupacion_al_decidir_ppm=ocupacion_movil(filas, fin - 1, vigente.target, ventana),
            )
        )
    return salida


def revisar_invariantes(ocupacion_ppm: int = 800_000) -> None:
    """La candidata, contra los mismos predicados que las reglas del protocolo."""
    regla = ReglaTargetBlobs(ocupacion_ppm)
    estado = EstadoBlobs(blobs_acumulados=1_000, blobs_hace_una_ventana=800)

    inv.i2_trigger_solo_estado(regla, estado)
    inv.i2_modo_declarado(regla)

    progresos, acumulado = [], 0
    for fila in serie():
        acumulado += fila["blobs"]
        progresos.append(acumulado)
    inv.i2_aproximacion_monotona(regla.nombre, progresos)


# --------------------------------------------------------------------------- #
# Informe
# --------------------------------------------------------------------------- #


def informe() -> str:
    lineas: list[str] = []
    ancho = 78
    linea = "-" * ancho

    lineas.append("=" * ancho)
    lineas.append("FASE 2 · caso 2 — el blobSchedule de Ethereum")
    lineas.append("=" * ancho)

    filas = serie()
    if not filas:
        lineas.append("")
        lineas.append("FALTA LA SERIE: python herramientas/traer_datos.py blobs")
        return chr(10).join(lineas)

    lineas.append(f"serie: {len(filas):,} muestras, un bloque cada 5.000 (~16,7 h)")

    # -- A ------------------------------------------------------------------ #
    lineas.append("")
    lineas.append("MEDICIÓN A · la ocupación bajo cada target — CERO parámetros libres")
    lineas.append("")
    lineas.append(
        f"{'target vigente':<20}{'desde':>12}{'muestras':>10}{'ocupación':>11}"
        f"{'pico':>8}{'saturado':>10}"
    )
    lineas.append(linea)
    for tramo in tramos():
        pico = f"{tramo.pico_ppm / 10_000:.0f}%" if tramo.pico_ppm is not None else "n/d"
        saturado = (
            f"{tramo.saturado_ppm / 10_000:.0f}%" if tramo.saturado_ppm is not None else "n/d"
        )
        lineas.append(
            f"{tramo.nombre + ' (t=' + str(tramo.target) + ')':<20}{tramo.desde:>12}"
            f"{tramo.muestras:>10}{tramo.ocupacion:>10.0f}%{pico:>8}{saturado:>10}"
        )
    lineas.append(linea)
    lineas.append("«saturado» = fracción del tramo con la media móvil de 30 días ≥ 80%")
    lineas.append(
        "«n/d» = el tramo dura menos que la ventana móvil. BPO1 duró 29 días: "
        "no se puede medir sostenido nada, y eso ya dice algo."
    )

    # -- B ------------------------------------------------------------------ #
    lineas.append("")
    lineas.append("MEDICIÓN B · el contrafáctico por decisión — UN parámetro libre")
    lineas.append("")
    for umbral in (700_000, 800_000, 900_000):
        lineas.append(f"  regla: subir el target con ocupación sostenida ≥ {umbral // 10_000}%")
        for fila in contrafactico(umbral):
            if not fila.disparo:
                lineas.append(
                    f"    {fila.decision:<18} humano {fila.fecha_humana}   "
                    f"la regla NO dispara (ocupación final "
                    f"{fila.ocupacion_al_decidir_ppm / 10_000:.0f}% de t={fila.target_vigente})"
                )
                continue
            lineas.append(
                f"    {fila.decision:<18} humano {fila.fecha_humana}   "
                f"regla {fila.fecha_regla}   los humanos tardaron "
                f"{fila.dias:,.0f} días más"
            )
        lineas.append("")

    lineas.append(linea)
    lineas.append("La regla candidata contra los predicados de I2 del protocolo:")
    try:
        revisar_invariantes()
        lineas.append("    OK — progreso monótono (blobs acumulados), umbral móvil")
    except inv.ViolacionInvariante as falla:  # pragma: no cover
        lineas.append(f"    FALLA — {falla}")
    lineas.append("")
    lineas.append("Los dos avisos sobre el dato están en el docstring del módulo:")
    lineas.append("  · excessBlobGas no compara a través de Fusaka (EIP-7918)")
    lineas.append("  · BPO1 y BPO2 se anunciaron juntos el 6/11/2025: es un cronograma")
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
