"""El techo de pasos de VM: `python herramientas/techo.py`

**§10.3, primer problema abierto.** Bloquea el cierre de la Fase 4 y también el bloque
0, porque el claim de clase PoD de §7.2 lo necesita. El paper lo declara como *"un
número y dónde vive"*, con dos filos:

- **muy apretado** → la cadena no puede adoptar una primitiva futura legítimamente más
  cara, y el fondo de escalera vuelve por falta de presupuesto;
- **muy holgado** → vuelve el caso que el techo existe para bloquear: la implementación
  correcta pero diez veces más lenta, que pasa el guante porque es correcta y queda
  instalada para siempre.

Y con un acople que el paper señala y no resuelve: un techo congelado en la máquina hay
que elegirlo generoso —tiene que sobrevivir primitivas que no existen— y generoso es
justamente lo que deja pasar la implementación lenta.

## La salida: el techo no es un número, es una cuenta

§10.3 ya dice dónde tiene que estar anclado —*"lo único que no deriva es el presupuesto
de la capa liviana de §6.1"*— y §6.6 dice cómo se mide. Juntando las dos:

```
techo_pasos = f* × tiempo_de_bloque × R_declarado / tx_por_bloque
```

- **`f*`** — qué fracción del nodo liviano puede ocupar la verificación de firmas.
  **Se congela en Genesis.** Es la única constante realmente libre de todo esto;
- **`R_declarado`** — pasos por segundo del hardware de entrada. **Se congela en
  Genesis**, y tiene que ser un número declarado y no medido: la cadena no puede leer
  la velocidad del hardware sin convertirse en un oráculo (I2);
- **`tiempo_de_bloque`** y **`tx_por_bloque`** — ya son parámetros internos del espacio.

**Eso contesta las dos preguntas de una vez.** Lo que se congela en la máquina (I1) es
**la fórmula**; el valor lo determina cada generación con sus propios parámetros. Y no
es una palanca suelta, porque **nadie puede moverlo sin mover capacidad o tiempo de
bloque**, que tienen sus propias consecuencias y sus propios disparos.

## Y el filo de las primitivas futuras se disuelve

El techo no tiene que ser generoso para sobrevivir veinte años de primitivas que no
existen. **Una primitiva más cara no queda afuera: entra pagando capacidad**, y esa
cuenta la hace el mismo mecanismo de §3 —bajar `tx_por_bloque` es una transición—. Deja
de ser una decisión gratis e invisible y pasa a ser una decisión con precio y con aviso.

> **Lo que NO puede ser, y el paper ya lo rechaza:** un techo relativo a la primitiva
> vigente —*el mejor candidato por un múltiplo*— se rebasa en cada generación: 2× por
> transición son 1.024× a las diez. La fórmula de arriba es absoluta: no depende de qué
> primitiva esté instalada, así que no compone.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from protocolo import genesis as g  # noqa: E402

# --------------------------------------------------------------------------- #
# El dato, medido por Test 2 — no se estima acá
# --------------------------------------------------------------------------- #

#: `steps_per_verify` de `test2-interprete/`, intérprete RV32IM, `decode+verify`.
#:
#: **Es el único número de todo el Test 2 que ninguna contaminación puede tocar**:
#: coincide byte a byte entre x86 y ARM en todas las corridas, porque no depende del
#: reloj. Ésa es la propiedad que vuelve admisible un techo en pasos bajo I2 — y la
#: razón por la que el techo no puede ser en tiempo, que sería un oráculo.
PASOS_POR_VERIFICACION = {
    "ML-DSA-44": 3_339_364,
    "ML-DSA-65": 5_379_218,
    "ML-DSA-87": 9_111_691,
}

#: El mismo dato en `verify_only` (clave ya expandida). Está para la comparación de
#: §7.2 —el claim verifica un lote— y no para el techo, que usa el número honesto.
PASOS_VERIFY_ONLY = {
    "ML-DSA-44": 1_126_796,
    "ML-DSA-65": 1_472_591,
    "ML-DSA-87": 2_219_176,
}

#: Tiempos medidos en el teléfono (Motorola Edge 40 Neo, Cortex-A78) con RV32IM,
#: `decode+verify`, en milisegundos. Cruzados con los pasos dan el ritmo real.
MS_EN_TELEFONO = {"ML-DSA-44": 10.57, "ML-DSA-65": 16.75, "ML-DSA-87": 28.49}

# --------------------------------------------------------------------------- #
# Las constantes viven en `protocolo/genesis.py` y acá se importan
#
# Hasta el 20/8/2026 este módulo tenía **su propia copia** de `R_DECLARADO` y de
# `F_VERIFICACION_PPM`. Cuando la Fase 4 bajó el ritmo declarado, esta copia quedó
# atrás y una prueba pasó a decir que ML-DSA-87 entraba cuando no entra. Una
# constante de Genesis en dos archivos no es duplicación: es una bifurcación
# esperando a que alguien edite uno solo.
# --------------------------------------------------------------------------- #

R_DECLARADO = g.ritmo_declarado(g.paginas_vigentes(g.RULESET_INICIAL))
F_VERIFICACION_PPM = g.F_VERIFICACION_PPM

#: El presupuesto de páginas **del ruleset inicial** — desde el 21/8/2026 no es una
#: constante sino un punto de la curva. Ver `protocolo/genesis.py`.
TECHO_PAGINAS = g.paginas_vigentes(g.RULESET_INICIAL)

#: Ritmos por mezcla **medidos en el hardware de referencia** (el teléfono de Test 2,
#: aarch64), en M pasos/s: peor de tres pasadas, con el techo de páginas en 96 y con la
#: verificación de páginas tocadas puesta. Ya no se traslada nada por cociente — el
#: teléfono corre el mismo binario.
#:
#: La fila que cambió el diseño es `aritmetica-revuelta`: en x86 corría a 145 —0,55 de
#: ML-DSA— y en ARM corre a 325 —1,22—. **El castigo por romper el predictor de saltos
#: indirectos del intérprete no existe en ese núcleo**, y sobre ese cruce estaba elegido
#: el techo de páginas viejo.
RITMO_POR_MEZCLA = {
    "addi-uniforme": 322.7,
    "aritmetica-revuelta": 325.4,
    "mul": 326.6,
    "divu": 197.7,
    "lw-secuencial": 186.3,
    "lw-persecucion-96pg": 82.1,
    "ML-DSA-44": 266.0,
}

#: La curva de conjunto de trabajo: páginas → M pasos/s con la peor mezcla de memoria.
#: **Sólo la primera columna decide**, porque el hardware de referencia es el teléfono.
#: La segunda está para la frontera que dejó abierta esta fase — ver
#: `desacuerdo_entre_maquinas`.
CURVA_MEMORIA = {
    #  páginas: (aarch64, x86-64)
    4: (163.6, 186.5),
    16: (125.5, 143.4),
    32: (101.1, 124.0),
    48: (86.2, 122.2),
    64: (84.3, 110.4),
    96: (80.8, 78.9),
    128: (79.8, 71.5),
    256: (79.3, 58.4),
    512: (77.6, 40.6),
    1024: (10.9, 23.4),
}

#: Páginas de 4 KiB que toca una verificación de cada nivel. **Es independiente de la
#: arquitectura** —x86-64 y aarch64 dieron 26 para el nivel 44, exacto— y es el dato que
#: mostró que un techo de 48 páginas no encarecía ML-DSA-87 sino que la dejaba afuera sin
#: precio posible.
#:
#: **Es el único criterio que fija el techo de páginas, y el único que sobrevivió.** No
#: depende de ninguna medición de tiempo, así que ninguna corrida lo puede mover.
PAGINAS_POR_VERIFICACION = {"ML-DSA-44": 26, "ML-DSA-65": 40, "ML-DSA-87": 65}

#: Ritmo de la peor mezcla en el hardware de referencia, en M pasos/s. Tres mediciones
#: independientes —`mezclas` 82,1, `conjunto` §4 81,4, `conjunto` §1 80,8— dentro del
#: 1,6% entre sí. Se toma la más baja.
PEOR_EN_REFERENCIA = 80.8


def desacuerdo_entre_maquinas() -> dict[int, float]:
    """**La frontera que esta fase dejó abierta: cuál hardware es el peor caso.**

    Todo el diseño supone que la capa liviana es la que ata —de ahí sale la entrada
    barata de nodos de §6.1— y con ella se calibra `R_declarado`. Medido, eso **no es
    cierto para los patrones adversariales de memoria**: de 96 páginas para arriba un
    escritorio x86-64 corre la peor mezcla más lento que el teléfono, y a 512 páginas
    la corre a la mitad.

    Devuelve, por techo de páginas, el cociente teléfono/escritorio. Arriba de 1 el
    escritorio es el peor y la premisa se rompe.

    **Dos máquinas no alcanzan para fijar un piso de hardware**, y menos con la
    dispersión que tiene el escritorio: la misma medición dio entre 44 y 79 M pasos/s
    según cuándo se corriera, contra 1,6% de dispersión en el teléfono. Por eso queda
    declarado como frontera y no absorbido dentro de `R_DECLARADO`, que se calibra
    sobre el hardware que el protocolo declara como referencia.
    """
    return {p: arm / x86 for p, (arm, x86) in CURVA_MEMORIA.items()}


def cociente_del_peor_caso() -> float:
    """Cuánto más lenta corre la peor mezcla admisible que la carga real.

    **Es el número que la Fase 4 le agregó al techo.** Antes se suponía 1,0 —que un
    paso vale un paso— y eso es falso por 23× sin el techo de páginas y por 2,3×
    con él.
    """
    peor = min(v for k, v in RITMO_POR_MEZCLA.items() if k != "ML-DSA-44")
    return peor / RITMO_POR_MEZCLA["ML-DSA-44"]


@dataclass(frozen=True)
class Presupuesto:
    """El presupuesto de verificación de un bloque, y lo que implica."""

    tiempo_de_bloque_ms: int
    tx_por_bloque: int
    f_ppm: int = F_VERIFICACION_PPM
    ritmo: int = R_DECLARADO

    @property
    def pasos_por_bloque(self) -> int:
        """Los pasos que el nodo liviano puede gastar verificando, por bloque."""
        return self.f_ppm * self.tiempo_de_bloque_ms * self.ritmo // (1_000_000 * 1_000)

    @property
    def techo(self) -> int:
        """**El número.** Pasos que puede costar verificar una firma."""
        return self.pasos_por_bloque // self.tx_por_bloque

    def entra(self, primitiva: str) -> bool:
        return PASOS_POR_VERIFICACION[primitiva] <= self.techo

    def margen(self, primitiva: str) -> float:
        """Cuántas veces la implementación de referencia entra bajo el techo.

        **Es el número que decide los dos filos.** Por debajo de 1 la referencia no
        entra; en 1 sólo entra la referencia exacta y el protocolo termina eligiendo
        la implementación en vez de la interfaz; en 10 vuelve el caso que Test 2
        encontró.
        """
        return self.techo / PASOS_POR_VERIFICACION[primitiva]

    def capacidad_para(self, primitiva: str) -> int:
        """Cuántas tx por bloque entran con esta primitiva, al techo actual."""
        return self.pasos_por_bloque // PASOS_POR_VERIFICACION[primitiva]


def ritmo_medido() -> dict[str, float]:
    """Pasos por segundo del teléfono, cruzando pasos contra tiempos de Test 2."""
    return {
        nombre: PASOS_POR_VERIFICACION[nombre] / (MS_EN_TELEFONO[nombre] / 1_000)
        for nombre in MS_EN_TELEFONO
    }


def capacidad_al_margen(primitiva: str, margen: float, tiempo_ms: int = 6_000) -> int:
    """Cuántas tx por bloque tolera un margen dado sobre la referencia.

    Es la misma cuenta dada vuelta, y es la que muestra que **el margen sobre la
    implementación de referencia es exactamente la capacidad que se resigna**.
    """
    pasos = F_VERIFICACION_PPM * tiempo_ms * R_DECLARADO // (1_000_000 * 1_000)
    return int(pasos / (PASOS_POR_VERIFICACION[primitiva] * margen))


def informe() -> str:
    lineas: list[str] = []
    ancho = 78
    linea = "-" * ancho

    lineas.append("=" * ancho)
    lineas.append("EL TECHO DE PASOS DE VM · §10.3, primer problema abierto")
    lineas.append("=" * ancho)

    lineas.append("")
    lineas.append("EL INSTRUMENTO · Test 2, y es lo único que ninguna contaminación toca")
    lineas.append("")
    lineas.append(f"{'primitiva':<12}{'pasos/verify':>16}{'ms en teléfono':>16}{'M pasos/s':>12}")
    lineas.append(linea)
    ritmos = ritmo_medido()
    for nombre in PASOS_POR_VERIFICACION:
        lineas.append(
            f"{nombre:<12}{PASOS_POR_VERIFICACION[nombre]:>16,}"
            f"{MS_EN_TELEFONO[nombre]:>16.2f}{ritmos[nombre] / 1e6:>12.0f}"
        )
    lineas.append(linea)
    lineas.append(
        f"ritmo declarado en Genesis: {R_DECLARADO / 1e6:.0f} M pasos/s "
        f"(por debajo del medido, a propósito)"
    )

    lineas.append("")
    lineas.append("EL TECHO, DERIVADO · f* = 25% · bloque de 6 s")
    lineas.append("")
    lineas.append(
        f"{'tx/bloque':>10}{'techo (pasos)':>16}{'margen 44':>11}"
        f"{'margen 65':>11}{'margen 87':>11}"
    )
    lineas.append(linea)
    for tx in (50, 100, 135, 200, 400):
        presupuesto = Presupuesto(6_000, tx)
        lineas.append(
            f"{tx:>10}{presupuesto.techo:>16,}"
            + "".join(f"{presupuesto.margen(p):>11.2f}" for p in PASOS_POR_VERIFICACION)
        )
    lineas.append(linea)
    lineas.append("margen = cuántas veces la implementación de referencia entra bajo el techo")
    lineas.append("por debajo de 1,00 la referencia no entra; en 10 vuelve el caso de Test 2")

    lineas.append("")
    lineas.append("LA MISMA CUENTA DADA VUELTA · el margen es capacidad que se resigna")
    lineas.append("")
    lineas.append(f"{'margen':>8}" + "".join(f"{p:>14}" for p in PASOS_POR_VERIFICACION))
    lineas.append(linea)
    for margen in (1.0, 1.5, 2.0, 3.0, 10.0):
        lineas.append(
            f"{margen:>7.1f}×"
            + "".join(
                f"{capacidad_al_margen(p, margen):>11} tx" for p in PASOS_POR_VERIFICACION
            )
        )
    lineas.append(linea)

    lineas.append("")
    lineas.append("LA DECISIÓN QUE QUEDA · el margen, y se toma UNA vez")
    lineas.append("")
    lineas.append(
        "  El margen sobre la implementación de referencia es lo único que hay que"
    )
    lineas.append("  elegir, y tiene cota de los dos lados:")
    lineas.append("")
    lineas.append(
        "   · por abajo, 1,0× significa que sólo entra la referencia exacta y el"
    )
    lineas.append(
        "     protocolo termina eligiendo la implementación en vez de la interfaz,"
    )
    lineas.append("     que es lo contrario de lo que §6.6 quiere;")
    lineas.append(
        "   · por arriba, Test 2 encontró el caso a excluir: la implementación"
    )
    lineas.append("     correcta pero 10× más lenta. Un margen de 10× lo deja pasar.")
    lineas.append("")
    lineas.append("  **2× es la elección: cubre el rango razonable de calidad de")
    lineas.append("  implementación y excluye el caso de Test 2 por un factor de cinco.**")
    lineas.append("")
    elegido = Presupuesto(6_000, 67)
    lineas.append(
        f"  Con ML-DSA-44 como referencia, bloque de 6 s y margen 2×:"
    )
    lineas.append(f"    tx_por_bloque = 67   →   techo = {elegido.techo:,} pasos")
    lineas.append(
        f"    margen real {elegido.margen('ML-DSA-44'):.2f}× · "
        f"capacidad {elegido.capacidad_para('ML-DSA-44') } tx/bloque a margen 1"
    )
    for nombre in ("ML-DSA-65", "ML-DSA-87"):
        estado = "entra" if elegido.entra(nombre) else "NO entra"
        lineas.append(
            f"    {nombre}: margen {elegido.margen(nombre):.2f}× · {estado}"
        )
    lineas.append("")
    lineas.append(
        "  **El margen se usa una sola vez, en Genesis, para elegir la capacidad.**"
    )
    lineas.append("  No es una regla que el protocolo reaplique en cada transición: si lo")
    lineas.append("  fuera, el techo subiría con cada primitiva nueva y compondría — 2× por")
    lineas.append("  transición son 1.024× a las diez, que es lo que §10.3 rechaza.")
    lineas.append("")
    lineas.append("  ML-DSA-87 no entra, y eso NO es un rechazo: es un precio. Adoptarla")
    lineas.append(
        f"  exige bajar la capacidad a {elegido.capacidad_para('ML-DSA-87')} tx/bloque"
        " o subir el tiempo de bloque, y eso"
    )
    lineas.append("  es una transición de §3, con su Δ y su aviso — no una sorpresa.")

    lineas.append("")
    lineas.append("LO QUE ESTO CIERRA Y LO QUE NO")
    lineas.append("")
    lineas.append("  cierra · dónde vive: **la fórmula se congela (I1), el valor lo deriva**")
    lineas.append("           cada generación de sus propios parámetros. No es una palanca:")
    lineas.append("           moverlo exige mover capacidad o tiempo de bloque.")
    lineas.append("  cierra · el filo de las primitivas futuras: no quedan afuera, entran")
    lineas.append("           pagando capacidad, y el precio se ve.")
    lineas.append("  queda  · **f\\* y R_declarado son dos constantes que alguien elige.**")
    lineas.append("           f\\* tiene piso medido (§6.3 necesita 10% de headroom) y R")
    lineas.append("           tiene que estar por debajo del hardware real. Ninguna de las")
    lineas.append("           dos sale de una medición: son decisiones, y están declaradas.")
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
