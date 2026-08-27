"""Fase 2 · el harness de replay: `python herramientas/replay.py`.

La pregunta de la fase, textual: *si esto hubiera sido una `TRANSITION_RULE`
escrita de antemano, ¿qué habría pasado?* Y su valor: **es la única fase que
produce evidencia que no escribió el autor del diseño.** Todo lo demás que hay en
el repositorio mide un modelo propio contra ataques propios; esto mide contra seis
decisiones que tomaron otros, en otra cadena, sin saber que existía este paper.

## El caso: la bomba de dificultad de Ethereum

Seis veces en cinco años, Ethereum corrió la bomba con un hard fork. Cada uno de
esos forks es una decisión humana con fecha, altura y EIP — y la bomba misma es
una **función determinista de la altura**, así que todo el caso se puede replicar
sin una sola serie de datos. Por eso es el primero de los tres.

## Dos mediciones, y la primera es la que vale

**1 · El umbral revelado.** Sin regla, sin ajuste, sin parámetros libres: en cada
uno de los seis forks, ¿cuánto valía el término de la bomba? Si los seis números
se parecen, entonces los humanos venían aplicando una regla que nunca escribieron
— y una regla que nadie escribió es una regla que se podía haber escrito en
Genesis. Es una medición y no una simulación: no hay nada que calibrar.

**2 · El replay.** Recién después se corre una `TRANSITION_RULE` candidata contra
el historial y se compara. Acá **sí** hay dos parámetros libres (el umbral y el
paso del retraso), así que el resultado hay que leerlo con cuidado y el informe lo
dice: barrer dos parámetros contra seis puntos no demuestra que la regla sea
correcta. Lo que mide es **cuánta libertad hace falta** para reproducir lo que los
humanos hicieron, que es una pregunta distinta y contestable.

## Qué se reutiliza del protocolo, y qué no

La regla candidata es una `ReglaTransicion` de verdad y pasa por los **mismos**
predicados de I2 que las del protocolo: se computa sólo desde el estado, su
aproximación es monótona, publica distancia y declara su modo. Eso es lo que hace
que esto sea un replay del mecanismo y no una planilla.

Lo que **no** se reutiliza es el espacio de Genesis: `offset_bomba` no es un
parámetro del Genesis de juguete de esta implementación. El replay declara el
suyo —`ESPACIO_REPLAY`— porque la pregunta es qué habría pasado en una cadena que
sí lo tuviera. Está separado a propósito para que nadie lea que Genesis lo trae.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from herramientas import historial  # noqa: E402
from protocolo import genesis as g  # noqa: E402
from protocolo import invariantes as inv  # noqa: E402
from protocolo.generacion import Params, Ruleset  # noqa: E402
from protocolo.serializacion import huella  # noqa: E402
from sucesion import distancia as distancia_mod  # noqa: E402
from sucesion.regla import ReglaTransicion  # noqa: E402

#: `dificultad += 2 ** (piso((altura - offset) / EPOCA) - 2)`.
EPOCA = 100_000
AJUSTE = 2

#: El espacio de descendientes **de esta cadena hipotética**, no el de Genesis.
ESPACIO_REPLAY = {"offset_bomba": g.RangoEntero(0, 20_000_000, paso=EPOCA)}

#: Cada cuántos bloques se evalúa la regla en el replay. La altura exacta del
#: disparo no sale del muestreo sino del umbral, que es exacto; el muestreo existe
#: para recorrer el historial de verdad en vez de resolver la ecuación y creerle.
PASO_MUESTREO = 1_000

#: Las series que baja `traer_datos.py`. Si no están, las mediciones que dependen
#: de ellas se saltean y el informe lo dice — no se estiman.
DATOS = Path(__file__).resolve().parent / "datos"
RUTA_DIFICULTAD = DATOS / "dificultad.csv"
RUTA_BLOBS = DATOS / "blobs.csv"
RUTA_GAS = DATOS / "gas.csv"


def exponente(altura: int, offset: int) -> int:
    """El exponente del término de la bomba a esa altura, con ese offset."""
    falsa = max(altura - offset, 0)
    return falsa // EPOCA - AJUSTE


# --------------------------------------------------------------------------- #
# El estado histórico
# --------------------------------------------------------------------------- #


@dataclass
class EstadoBomba:
    """Lo mínimo del estado de Ethereum que la regla necesita leer.

    Son dos números y los dos están en la cadena: la altura y el offset vigente
    de la bomba. **Ningún oráculo, ningún precio, ningún reloj** — que es lo que
    hace admisible el trigger bajo I2 y lo que permite afirmar que esta regla se
    podría haber escrito en el bloque 0 de Ethereum.
    """

    altura: int = 0
    offset_bomba: int = 0
    distancias: dict = field(default_factory=dict)

    def canonico(self) -> dict:
        return {"altura": self.altura, "offset_bomba": self.offset_bomba}

    def huella(self) -> bytes:
        return huella(self.canonico(), dominio="replay/bomba")

    @property
    def exponente(self) -> int:
        return exponente(self.altura, self.offset_bomba)

    def lockins_de(self, nombre_de_regla: str) -> int:  # compat con la interfaz
        return 0


# --------------------------------------------------------------------------- #
# La regla candidata
# --------------------------------------------------------------------------- #


class ReglaRetrasoBomba(ReglaTransicion):
    """*Cuando el término de la bomba llegue a `2**umbral_exp`, correrla `paso`.*

    **El progreso es la altura y el umbral se mueve**, no al revés. Es la misma
    decisión que C9.3 y acá se ve por qué no era un capricho de implementación: el
    exponente de la bomba **baja** cuando se aplica un retraso, así que usarlo como
    progreso violaría I2 en cada transición. La altura no baja nunca.

    Y el subproducto es fuerte: como el progreso avanza exactamente un bloque por
    bloque, la distancia al disparo es **exacta**, no una proyección. Ethereum
    podría haber publicado una cuenta regresiva perfecta al próximo retraso de la
    bomba, con años de anticipación, en vez de discutirlo en cada All Core Devs.
    """

    nombre = "bomba/retraso"
    clase = g.CIRCULACION
    modo = inv.MODO_APROXIMACION

    def __init__(self, umbral_exp: int, paso: int) -> None:
        self.umbral_exp = umbral_exp
        self.paso = paso

    def progreso(self, estado) -> int:
        return estado.altura

    def umbral(self, estado) -> int:
        return (self.umbral_exp + AJUSTE) * EPOCA + estado.offset_bomba

    def params_sucesor(self, estado, ruleset: Ruleset) -> Params:
        return Params(
            generacion=ruleset.generacion + 1,
            internos={"offset_bomba": estado.offset_bomba + self.paso},
            formatos=ruleset.formatos,
        )


def motivo_fuera_del_espacio_replay(params: Params) -> str | None:
    for nombre, dominio in ESPACIO_REPLAY.items():
        if nombre not in params.internos:
            return f"falta {nombre}"
        if not dominio.contiene(params.internos[nombre]):
            return f"{nombre} = {params.internos[nombre]} fuera de {dominio}"
    return None


# --------------------------------------------------------------------------- #
# Medición 1 · el umbral revelado (sin parámetros libres)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Revelado:
    fork: str
    eip: str
    altura: int
    fecha: str
    offset_antes: int
    exponente: int
    solo_bomba: bool


def umbral_revelado() -> list[Revelado]:
    """Cuánto valía la bomba en cada uno de los seis forks. **Es una medición.**"""
    filas: list[Revelado] = []
    offset_antes = 0
    for retraso in historial.RETRASOS:
        motivo = historial.FORK_POR_OTRO_MOTIVO.get(retraso.fork, "")
        filas.append(
            Revelado(
                fork=retraso.fork,
                eip=retraso.eip,
                altura=retraso.altura,
                fecha=retraso.fecha,
                offset_antes=offset_antes,
                exponente=exponente(retraso.altura, offset_antes),
                solo_bomba=motivo.startswith("fork exclusivo"),
            )
        )
        offset_antes = retraso.offset
    return filas


# --------------------------------------------------------------------------- #
# Medición 2 · el replay de la regla
# --------------------------------------------------------------------------- #


def simular(umbral_exp: int, paso: int, hasta: int = historial.ALTURA_FUSION) -> list[int]:
    """Las alturas en que la regla habría disparado, recorriendo el historial."""
    regla = ReglaRetrasoBomba(umbral_exp, paso)
    estado = EstadoBomba()
    disparos: list[int] = []

    altura = 0
    while altura <= hasta:
        estado.altura = altura
        if regla.dispara(estado):
            # El umbral es exacto: el disparo no cae donde muestreamos sino donde
            # la condición se cumple por primera vez.
            exacto = regla.umbral(estado)
            if exacto > hasta:
                break
            disparos.append(exacto)
            estado.offset_bomba += paso
            altura = exacto
        altura += PASO_MUESTREO

    return disparos


@dataclass(frozen=True)
class Contrafactico:
    """Qué habría hecho la regla **en cada decisión, con el offset real de ese
    momento**. Un solo parámetro libre: el umbral.

    Es la comparación correcta, y separarla de la encadenada importa. Los humanos
    tomaron **dos** decisiones distintas cada vez —*cuándo* correr la bomba y
    *cuánto* correrla— y una simulación encadenada las mezcla: el error del paso
    se acumula y contamina la medición del disparo. Acá el offset lo pone el
    historial, así que lo único que se mide es el momento.
    """

    fork: str
    altura_humana: int
    altura_regla: int
    offset_vigente: int

    @property
    def diferencia(self) -> int:
        """Positiva = la regla habría disparado **después** que los humanos."""
        return self.altura_regla - self.altura_humana


def contrafactico(umbral_exp: int) -> list[Contrafactico]:
    filas: list[Contrafactico] = []
    offset = 0
    for retraso in historial.RETRASOS:
        filas.append(
            Contrafactico(
                fork=retraso.fork,
                altura_humana=retraso.altura,
                altura_regla=(umbral_exp + AJUSTE) * EPOCA + offset,
                offset_vigente=offset,
            )
        )
        offset = retraso.offset
    return filas


def mejor_umbral(umbrales: range = range(35, 46)) -> tuple[int, list[Contrafactico]]:
    """El umbral que minimiza el desvío máximo. **Un solo grado de libertad.**"""
    candidatos = [(max(abs(f.diferencia) for f in contrafactico(u)), u) for u in umbrales]
    _, elegido = min(candidatos)
    return elegido, contrafactico(elegido)


def cota_humana() -> int:
    """El exponente más alto al que llegó la bomba bajo el proceso humano."""
    picos = []
    offset = 0
    for retraso in historial.RETRASOS:
        picos.append(exponente(retraso.altura, offset))
        offset = retraso.offset
    picos.append(exponente(historial.ALTURA_FUSION, offset))
    return max(picos)


def cota_regla(umbral_exp: int, paso: int) -> int:
    """El exponente más alto bajo la regla, recorriendo el historial de verdad.

    Tiene que dar `umbral_exp`: la regla dispara **en cuanto** lo alcanza. Que sea
    obvio es el punto — es una cota **por construcción**, no un resultado que salió
    bien. Se mide igual, porque una cota que nadie verificó es una creencia.
    """
    estado = EstadoBomba()
    regla = ReglaRetrasoBomba(umbral_exp, paso)
    pico = exponente(0, 0)
    altura = 0
    while altura <= historial.ALTURA_FUSION:
        estado.altura = altura
        pico = max(pico, estado.exponente)
        if regla.dispara(estado):
            estado.offset_bomba += paso
        altura += PASO_MUESTREO
    return pico


@dataclass(frozen=True)
class Comparacion:
    umbral_exp: int
    paso: int
    disparos: list[int]
    #: (fork, altura humana, altura de la regla o None, diferencia en bloques)
    pares: list[tuple[str, int, int | None, int | None]]

    @property
    def cuenta_coincide(self) -> bool:
        return len(self.disparos) == len(historial.RETRASOS)

    @property
    def error_maximo(self) -> int | None:
        difs = [abs(d) for _, _, _, d in self.pares if d is not None]
        return max(difs) if difs else None

    @property
    def error_medio(self) -> int | None:
        difs = [abs(d) for _, _, _, d in self.pares if d is not None]
        return sum(difs) // len(difs) if difs else None


def comparar(umbral_exp: int, paso: int) -> Comparacion:
    """Empareja por orden: el k-ésimo disparo con la k-ésima decisión humana.

    Emparejar por orden y no por cercanía es deliberado. Una regla que dispara
    cincuenta veces tiene un disparo cerca de cualquier fecha, y por cercanía
    parecería perfecta; por orden, el primer número que salta a la vista es que
    disparó cincuenta veces y ellos seis.

    **Y hay una asimetría que conviene tener presente al leer esta tabla:**
    contar disparos de más como un error supone que una transición cuesta lo que
    cuesta un fork, y no es así — ése es todo el punto del diseño. Disparar más
    seguido mantiene la bomba más chica y no le cuesta a nadie una coordinación.
    """
    disparos = simular(umbral_exp, paso)
    pares: list[tuple[str, int, int | None, int | None]] = []
    for indice, retraso in enumerate(historial.RETRASOS):
        propio = disparos[indice] if indice < len(disparos) else None
        diferencia = propio - retraso.altura if propio is not None else None
        pares.append((retraso.fork, retraso.altura, propio, diferencia))
    return Comparacion(umbral_exp, paso, disparos, pares)


def barrer(
    umbrales: range = range(35, 46),
    pasos: tuple[int, ...] = (500_000, 700_000, 1_000_000, 1_500_000, 2_000_000, 3_000_000),
) -> list[Comparacion]:
    """Todas las combinaciones, ordenadas por cuán bien reproducen el historial.

    **Barrer no demuestra que la regla sea correcta.** Dos parámetros libres
    contra seis puntos reproducen bastante por construcción. Lo que mide es cuánta
    libertad hace falta, y eso sí se puede leer.
    """
    resultados = [comparar(u, p) for u in umbrales for p in pasos]
    resultados.sort(
        key=lambda c: (
            not c.cuenta_coincide,
            c.error_maximo if c.error_maximo is not None else 10**9,
        )
    )
    return resultados


# --------------------------------------------------------------------------- #
# Medición 5 · la presión real de la bomba (necesita la serie de dificultad)
# --------------------------------------------------------------------------- #

#: El ajuste de dificultad de Ethereum mueve `dificultad // 2048` por escalón, y
#: el escalón lo fija el tiempo de bloque: `multiplicador = 1 - tiempo // 9`
#: (post-Byzantium; Homestead usaba 10 en vez de 9). En equilibrio, la bomba tiene
#: que quedar compensada por ese término, así que
#:
#:     presion = bomba * 2048 / dificultad
#:
#: es **cuántos escalones del ajuste consume la bomba**. Es el denominador que
#: importa: contra la dificultad a secas la bomba parece cero siempre, porque el
#: ajuste la absorbe — hasta que no puede.
DIVISOR_AJUSTE = 2048
SEGUNDOS_POR_ESCALON = 9


def _serie_dificultad() -> list[dict]:
    from herramientas.traer_datos import leer_serie

    _, filas = leer_serie(RUTA_DIFICULTAD)
    return filas


def dificultad_en(altura: int) -> int | None:
    """La dificultad muestreada más cercana por debajo de esa altura."""
    elegida = None
    for fila in _serie_dificultad():
        if fila["bloque"] <= altura:
            elegida = fila["dificultad"]
        else:
            break
    return elegida


@dataclass(frozen=True)
class Presion:
    fork: str
    exponente: int
    bomba: int
    dificultad: int

    @property
    def escalones(self) -> float:
        """Escalones del ajuste que consume la bomba. `> 1` = ya no se absorbe."""
        return self.bomba * DIVISOR_AJUSTE / self.dificultad

    @property
    def piso_de_tiempo_de_bloque(self) -> float:
        """Segundos por bloque que la bomba fuerza como mínimo, en equilibrio.

        Con `presion = k`, el ajuste necesita `multiplicador = -k`, o sea
        `tiempo // 9 = 1 + k`. Por debajo de `k = 1` el resultado cae dentro de la
        banda normal (9–18 s) y **no se distingue de un día cualquiera**: la
        medición sólo dice algo cuando la presión pasa 1.
        """
        return SEGUNDOS_POR_ESCALON * (1 + self.escalones)

    @property
    def se_sentia(self) -> bool:
        return self.escalones > 1


def presion_de_la_bomba() -> list[Presion]:
    """Cuánta presión había en cada fork. Vacío si falta la serie de dificultad."""
    if not _serie_dificultad():
        return []
    filas: list[Presion] = []
    offset = 0
    for retraso in historial.RETRASOS:
        exp = exponente(retraso.altura, offset)
        dificultad = dificultad_en(retraso.altura)
        if dificultad:
            filas.append(Presion(retraso.fork, exp, 2**exp, dificultad))
        offset = retraso.offset
    return filas


# --------------------------------------------------------------------------- #
# Las invariantes, sobre la regla candidata
# --------------------------------------------------------------------------- #


def revisar_invariantes(umbral_exp: int = 40, paso: int = 1_000_000) -> None:
    """La candidata pasa por los mismos predicados que las reglas del protocolo.

    Es lo que separa este harness de una planilla: si la regla que reproduce el
    historial de Ethereum no cumpliera I2, el resultado no diría nada sobre este
    diseño.
    """
    regla = ReglaRetrasoBomba(umbral_exp, paso)
    estado = EstadoBomba(altura=1_000_000)

    inv.i2_trigger_solo_estado(regla, estado)
    inv.i2_modo_declarado(regla)

    progresos = []
    for altura in range(0, historial.ALTURA_FUSION, 250_000):
        estado.altura = altura
        progresos.append(regla.progreso(estado))
    inv.i2_aproximacion_monotona(regla.nombre, progresos)

    motivo = motivo_fuera_del_espacio_replay(
        regla.params_sucesor(estado, Ruleset(Params(0, {"offset_bomba": 0}, frozenset()), b""))
    )
    if motivo is not None:
        raise inv.ViolacionInvariante("I1", motivo)


def distancia_en(altura: int, umbral_exp: int = 40, paso: int = 1_000_000):
    """La cuenta regresiva que Ethereum podría haber publicado a esa altura."""
    regla = ReglaRetrasoBomba(umbral_exp, paso)
    estado = EstadoBomba(altura=altura)
    for retraso in historial.RETRASOS:
        if retraso.altura <= altura:
            estado.offset_bomba = retraso.offset
    historial_progreso = [altura - 1]
    return distancia_mod.calcular(regla, estado, historial_progreso, ventana=1)


# --------------------------------------------------------------------------- #
# Informe
# --------------------------------------------------------------------------- #


def _dias(bloques: int) -> float:
    return bloques * historial.SEGUNDOS_POR_BLOQUE / 86_400


def informe() -> str:
    lineas: list[str] = []
    ancho = 78
    linea = "-" * ancho

    lineas.append("=" * ancho)
    lineas.append("FASE 2 · replay contra el historial real de Ethereum")
    lineas.append("caso: la bomba de dificultad y sus seis retrasos")
    lineas.append("=" * ancho)

    # -- 1 ----------------------------------------------------------------- #
    lineas.append("")
    lineas.append("MEDICIÓN 1 · el umbral revelado — CERO parámetros libres")
    lineas.append("cuánto valía el término de la bomba cuando los humanos la corrieron")
    lineas.append("")
    lineas.append(
        f"{'fork':<16}{'EIP':<11}{'altura':>12}{'fecha':>13}"
        f"{'exponente':>11}  sólo bomba"
    )
    lineas.append(linea)
    revelados = umbral_revelado()
    for fila in revelados:
        lineas.append(
            f"{fila.fork:<16}{fila.eip:<11}{fila.altura:>12,}{fila.fecha:>13}"
            f"{fila.exponente:>11}  {'sí' if fila.solo_bomba else 'no'}"
        )
    exponentes = [f.exponente for f in revelados]
    solo = [f.exponente for f in revelados if f.solo_bomba]
    mezclados = [f.exponente for f in revelados if not f.solo_bomba]
    lineas.append(linea)
    lineas.append(
        f"rango {min(exponentes)}–{max(exponentes)}: el término de la bomba varió "
        f"{2 ** (max(exponentes) - min(exponentes))}× entre la primera y la última"
    )
    lineas.append(
        f"forks exclusivos de la bomba {sorted(solo)} · mezclados con otra cosa "
        f"{sorted(mezclados)} — no se separan"
    )

    # -- 1b ---------------------------------------------------------------- #
    presiones = presion_de_la_bomba()
    lineas.append("")
    if not presiones:
        lineas.append("MEDICIÓN 1b · la presión real — FALTA LA SERIE DE DIFICULTAD")
        lineas.append("    corré: python herramientas/traer_datos.py dificultad")
    else:
        lineas.append("MEDICIÓN 1b · la presión real — con la serie de dificultad")
        lineas.append(
            "escalones del ajuste de dificultad que consumía la bomba "
            "(bomba x 2048 / dificultad)"
        )
        lineas.append("")
        lineas.append(
            f"{'fork':<16}{'exponente':>10}{'presión':>10}{'piso s/bloque':>15}"
            f"  ¿se sentía?"
        )
        lineas.append(linea)
        for fila in presiones:
            lineas.append(
                f"{fila.fork:<16}{fila.exponente:>10}{fila.escalones:>10.3f}"
                f"{fila.piso_de_tiempo_de_bloque:>15.1f}"
                f"  {'SÍ' if fila.se_sentia else 'no'}"
            )
        lineas.append(linea)
        sentidos = [f for f in presiones if f.se_sentia]
        escalones = [f.escalones for f in presiones]
        lineas.append(
            f"{len(sentidos)} de {len(presiones)} forks ocurrieron con la bomba "
            f"forzando bloques más lentos; los otros {len(presiones) - len(sentidos)} "
            "fueron preventivos"
        )
        lineas.append(
            f"dispersión medida en presión: {min(escalones):.3f} a {max(escalones):.3f} "
            f"= {max(escalones) / min(escalones):.0f}x — más del doble que los 16x "
            "de la Medición 1"
        )

    # -- 2 ----------------------------------------------------------------- #
    lineas.append("")
    lineas.append("MEDICIÓN 2 · el contrafáctico por decisión — UN parámetro libre")
    lineas.append("con el offset real de cada momento: ¿cuándo habría disparado la regla?")
    lineas.append("")
    elegido, filas = mejor_umbral()
    lineas.append(f"umbral que minimiza el desvío máximo: 2^{elegido}")
    lineas.append("")
    lineas.append(
        f"{'fork':<16}{'humano':>12}{'regla':>12}{'diferencia':>14}{'días':>8}"
    )
    lineas.append(linea)
    for fila in filas:
        signo = "+" if fila.diferencia >= 0 else "−"
        lineas.append(
            f"{fila.fork:<16}{fila.altura_humana:>12,}{fila.altura_regla:>12,}"
            f"{signo + format(abs(fila.diferencia), ',') :>14}"
            f"{_dias(abs(fila.diferencia)):>8.0f}"
        )
    difs = [abs(f.diferencia) for f in filas]
    lineas.append(linea)
    lineas.append(
        f"desvío máximo {max(difs):,} bloques ({_dias(max(difs)):.0f} días) · "
        f"medio {sum(difs) // len(difs):,} ({_dias(sum(difs) / len(difs)):.0f} días)"
    )
    exactos = [f.fork for f in filas if f.diferencia == 0]
    if exactos:
        lineas.append(f"coincidencia exacta: {', '.join(exactos)}")
    lineas.append("(+ = la regla habría disparado después que los humanos)")

    # -- 3 ----------------------------------------------------------------- #
    lineas.append("")
    lineas.append("MEDICIÓN 3 · la cota del término de la bomba")
    lineas.append("")
    humana = cota_humana()
    regla = cota_regla(elegido, 1_000_000)
    lineas.append(f"pico bajo el proceso humano:  2^{humana}")
    lineas.append(f"pico bajo la regla (2^{elegido}):     2^{regla}")
    lineas.append(
        f"la regla acota por construcción; el proceso humano llegó a "
        f"{2 ** (humana - regla)}× esa cota" if humana > regla else
        "la regla acota por construcción y el proceso humano no la excedió"
    )

    # -- 4 ----------------------------------------------------------------- #
    lineas.append("")
    lineas.append("MEDICIÓN 4 · el replay encadenado — DOS parámetros libres")
    lineas.append("acá la regla elige también CUÁNTO retrasar, y ahí se separa del historial")
    lineas.append("")
    mejor = barrer()[0]
    lineas.append(
        f"mejor combinación: umbral 2^{mejor.umbral_exp} · paso {mejor.paso:,} · "
        f"disparos {len(mejor.disparos)} (humanos: {len(historial.RETRASOS)})"
    )
    for fork, humano_altura, propio, diferencia in mejor.pares:
        if propio is None:
            lineas.append(f"    {fork:<16} humano {humano_altura:>12,}   la regla no disparó")
            continue
        signo = "+" if diferencia >= 0 else "−"
        lineas.append(
            f"    {fork:<16} humano {humano_altura:>12,}   regla {propio:>12,}"
            f"   {signo}{abs(diferencia):>9,} ({_dias(abs(diferencia)):.0f} d)"
        )
    lineas.append(
        f"    error medio {mejor.error_medio:,} bloques · máximo {mejor.error_maximo:,}"
    )
    incrementos = []
    previo = 0
    for retraso in historial.RETRASOS:
        incrementos.append(retraso.offset - previo)
        previo = retraso.offset
    lineas.append("")
    lineas.append(
        "los incrementos que los humanos eligieron: "
        + ", ".join(f"{i // 1000:,}k" for i in incrementos)
    )
    lineas.append(
        "ningún paso fijo los reproduce, y por eso la medición 2 los separa: "
        "cuándo correr la bomba y cuánto correrla son dos decisiones distintas."
    )

    # -- cierre ------------------------------------------------------------ #
    lineas.append("")
    lineas.append(linea)
    lineas.append("La regla candidata contra los predicados de I2 del protocolo:")
    try:
        revisar_invariantes(elegido, 1_000_000)
        lineas.append("    OK — se computa sólo desde el estado, monótona, modo declarado")
    except inv.ViolacionInvariante as falla:  # pragma: no cover
        lineas.append(f"    FALLA — {falla}")
    lineas.append("")
    lineas.append("La cuenta regresiva que Ethereum podría haber publicado, exacta:")
    for altura in (5_000_000, 10_000_000, 13_000_000):
        lineas.append(f"    bloque {altura:>12,} → {distancia_en(altura, elegido)}")
    lineas.append("")
    lineas.append("CASO 2 · los blobs — la verdad de base ya está verificada")
    lineas.append("")
    lineas.append(f"{'activación':<18}{'fecha':>12}{'target':>9}{'máximo':>9}   EIP")
    lineas.append(linea)
    for fila in historial.BLOB_SCHEDULE:
        lineas.append(
            f"{fila.nombre:<18}{fila.fecha:>12}{fila.target:>9}{fila.maximo:>9}"
            f"   {fila.eip}"
        )
    lineas.append(linea)
    lineas.append(
        "cuatro recalibraciones en menos de dos años; las dos últimas ya con el "
        "mecanismo liviano de EIP-7892"
    )
    lineas.append("")
    lineas.append(f"EIP-7892, {historial.EIP_7892['estado']}, sobre por qué existe:")
    lineas.append(f'    "{historial.EIP_7892["motivacion"]}"')
    lineas.append("")
    lineas.append("Lo que falta para correr los casos 2 y 3 — series, no código:")
    for nombre, motivo in historial.SERIES_QUE_FALTAN.items():
        lineas.append(f"  · {nombre}: {motivo}")
    lineas.append("")
    lineas.append(
        "DATOS DEL CASO 1 VERIFICADOS el 19/8/2026 contra los EIPs y contra "
        "MainnetChainConfig de go-ethereum — ver herramientas/historial.py."
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
