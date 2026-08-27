"""Los tres tiempos: disparo → lock-in → activación (§3).

El cronograma es la única pieza del sistema donde algo pasa a ser irrevocable, y
toda su razón de ser es la asimetría entre las dos primeras etapas:

- **el disparo es advisorio.** `TRANSITION_RULE` dio TRUE en el bloque `N` y eso
  no compromete nada: una reorganización que saque a `N` de la cadena lo borra
  sin dejar rastro;
- **el lock-in es irrevocable.** Cuando `N` es final, la activación queda fijada
  *aunque el estado vuelva atrás*. No es ceremonia: `H0_B` commitea
  `state_trigger`, y comprometerlo antes dejaría el checkpoint apuntando a un
  estado que una reorganización todavía puede sacar de la cadena. Un cronograma
  que se enciende y se apaga es peor que ninguno, porque nadie moviliza un equipo
  contra una fecha que puede evaporarse;
- **la activación es `Δ` bloques después del lock-in**, no después del disparo.
  Así el aviso al integrador es exactamente `Δ` y no depende de cuánto tardó la
  finalidad.

## Más de una transición en vuelo

Entre el lock-in y la activación pasan `Δ` bloques en los que la cadena **todavía
corre con las reglas viejas** aunque las nuevas ya estén commiteadas. Ahí se abren
dos preguntas que el mecanismo tiene que contestar, y las contesta acá:

**1 · ¿Puede una regla volver a disparar mientras su propia transición está en
vuelo? No.** Se rearma recién en la **activación**, no en el lock-in. Si pudiera
disparar antes, estaría midiendo un estado que no refleja el cambio que ella misma
acaba de comprometer — un lazo de control con tiempo muerto, que es exactamente
cómo falló la EDA de Bitcoin Cash: una regla automática escrita de antemano,
actuando sobre información que su acción anterior todavía no había corregido. El
lazo lo cierra la activación.

**2 · ¿Y las otras reglas? Sí, sin esperar.** La serialización es **por regla, no
global**. Bloquear todos los disparos mientras haya uno en vuelo pondría una
migración criptográfica de urgencia (§6.6, `Δ` corto) a esperar detrás de una
transición de circulación (`Δ` largo). Eso es fondo de escalera por otra puerta: la
urgencia la fija la clase, y una clase no puede quedar rehén de la otra.

**3 · Las activaciones van en orden de lock-in, aunque las `Δ` sean distintas.**
Una transición criptográfica commiteada detrás de una de circulación activa recién
cuando activa la anterior, si su `Δ` corto vencía antes. No es una preferencia:
`params_nuevos` es un **punto completo** del espacio y no un delta, así que activar
la generación 2 antes que la 1 aplicaría también los cambios de la 1 —con el aviso
de la 2, que es más corto— y le rompería la promesa de `Δ` al integrador.

> **El residuo, declarado.** Una migración de urgencia puede esperar hasta el `Δ`
> restante de la transición que tenga adelante. **Es acotado y no compone**: el
> tope es la `Δ` más larga del espacio, no crece con la cantidad de generaciones, y
> cuando vence las dos activan en el mismo bloque. Igual conviene tenerlo a la vista
> al elegir la `Δ` de circulación, porque es el número que fija esa espera. Lo que
> la concurrencia sí gana es el **lock-in**: la urgente se commitea enseguida en vez
> de esperar a que la lenta active para recién ahí disparar.

De ahí sale la cuarta decisión: **`params_nuevos` se computa en el lock-in, no en
el disparo.** Con dos reglas en vuelo, entre el disparo de la segunda y su lock-in
puede haberse commiteado la primera; unos parámetros calculados en el disparo
quedarían colgando de un ancestro que ya no es el último y el linaje no cerraría.
Computados en el lock-in, el sucesor sale siempre del ruleset comprometido **en ese
instante** y las generaciones son consecutivas por construcción. Es también lo que
§3 ya decía de `H0_B`: se computa en el lock-in, con `N` ya final.

**Y por eso el lock-in valida antes de comprometer.** Una vez emitido, el
checkpoint es irrevocable: si commiteara un punto fuera del espacio de Genesis, el
nodo llegaría a la activación sin poder conmutar y la cadena se pararía. Así que
I1 e I5 se verifican **antes** de emitirlo y, si no pasan, no hay checkpoint:
queda un **rechazo**, también on-chain. Un rechazo no recorta el sucesor al borde
del espacio —eso cambiaría la semántica en silencio— ni detiene el consenso.
Simplemente esa transición no ocurre, y se ve.

> **Residuo declarado.** Dos reglas que escriben el mismo parámetro componen por
> orden de lock-in: la última gana sobre ese parámetro. Y una regla que quedó
> pegada al borde del espacio no reintenta contra el mismo ancestro —el rechazo
> registra de qué ruleset salió—, así que no hay bucle de rechazos: espera a que
> otra transición mueva la base.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from protocolo import genesis as g
from protocolo.generacion import Params, Ruleset
from protocolo.invariantes import (
    ViolacionInvariante,
    i1_sucesor_en_el_espacio,
    i5_aditiva,
)
from protocolo.linaje import Checkpoint, calcular_h0


class SucesorInvalido(ValueError):
    """La regla propuso un sucesor que no se puede commitear. No se commitea."""


@dataclass(frozen=True)
class Disparo:
    """`TRANSITION_RULE` dio TRUE en `altura`. Todavía no compromete nada.

    Se lleva **el estado que lo disparó**, congelado, porque `params_nuevos` se
    computa recién en el lock-in y tiene que salir de ese estado y no del que haya
    `F` bloques después. Un nodo real lo rederiva del bloque `N`, que sigue en la
    cadena; acá se guarda una copia porque es más corto y el estado es de juguete.
    """

    regla: Any
    altura: int
    hash_bloque: bytes
    state_trigger: bytes
    estado: Any

    @property
    def nombre(self) -> str:
        return self.regla.nombre

    @property
    def clase(self) -> str:
        return self.regla.clase


@dataclass(frozen=True)
class Rechazo:
    """Un lock-in que no ocurrió, y por qué. Va on-chain como el checkpoint.

    Es irrevocable por la misma razón que el checkpoint: sale de un estado final y
    de un ancestro irrevocable, así que ningún nodo puede llegar a otra conclusión.
    """

    regla: str
    clase: str
    altura_disparo: int
    altura: int
    #: El ruleset comprometido contra el que se calculó. Mientras siga siendo el
    #: último, esta regla no reintenta: el resultado sería idéntico.
    base_h0: bytes
    motivo: str

    def canonico(self) -> dict:
        return {
            "tipo": "rechazo",
            "regla": self.regla,
            "clase": self.clase,
            "altura_disparo": self.altura_disparo,
            "altura": self.altura,
            "base_h0": self.base_h0,
            "motivo": self.motivo,
        }


class Cronograma:
    """Lleva los disparos pendientes, los lock-ins y los rechazos."""

    def __init__(self, ruleset_raiz: Ruleset = g.RULESET_INICIAL) -> None:
        self.ruleset_raiz = ruleset_raiz
        #: Un disparo pendiente por regla: mientras no finalice, no se repite.
        self.pendientes: dict[str, Disparo] = {}
        #: Los lock-ins, en orden. **De acá no se saca nada nunca.**
        self.checkpoints: list[Checkpoint] = []
        #: Los rechazos, en orden. Tampoco se sacan: son igual de irrevocables.
        self.rechazos: list[Rechazo] = []

    # -- lecturas ---------------------------------------------------------- #

    @property
    def h0_raiz(self) -> bytes:
        return self.ruleset_raiz.h0

    @property
    def comprometido(self) -> Ruleset:
        """El último ruleset commiteado, esté activo o esperando su `Δ`.

        Es la base de todo sucesor nuevo. La diferencia con *el vigente* sólo se
        nota con dos transiciones en vuelo, y es la que hace que el linaje cierre.
        """
        if self.checkpoints:
            ultimo = self.checkpoints[-1]
            return Ruleset(params=ultimo.params, h0=ultimo.h0)
        return self.ruleset_raiz

    @property
    def h0_vigente(self) -> bytes:
        return self.comprometido.h0

    @property
    def generacion_comprometida(self) -> int:
        return len(self.checkpoints)

    def activaciones(self, altura: int) -> list[Checkpoint]:
        """Los checkpoints que conmutan exactamente en esta altura.

        Vienen en orden de lock-in, que es el orden de generación: si dos caen en
        el mismo bloque, se aplican una tras otra y el linaje no se saltea nada.
        """
        return [c for c in self.checkpoints if c.altura_activacion == altura]

    @property
    def ultima_activacion(self) -> int:
        """La activación más lejana ya comprometida. Ninguna nueva va antes."""
        return max((c.altura_activacion for c in self.checkpoints), default=0)

    def pendientes_de_activar(self, altura: int) -> list[Checkpoint]:
        return [c for c in self.checkpoints if c.altura_activacion > altura]

    def en_vuelo(self, nombre_de_regla: str, altura: int) -> Checkpoint | None:
        """La transición de esta regla que ya tiene lock-in y todavía no activó."""
        for punto in reversed(self.checkpoints):
            if punto.regla == nombre_de_regla and punto.altura_activacion > altura:
                return punto
        return None

    def rechazo_vigente(self, nombre_de_regla: str) -> Rechazo | None:
        """Un rechazo contra el ancestro que todavía es el último.

        Mientras la base no cambie, reintentar da el mismo rechazo: la regla no
        vuelve a disparar y no hay bucle. Que se vea en la cadena que una regla
        quedó pegada al borde del espacio es información, no un error.
        """
        base = self.h0_vigente
        for rechazo in reversed(self.rechazos):
            if rechazo.regla == nombre_de_regla:
                return rechazo if rechazo.base_h0 == base else None
        return None

    # -- disparo ----------------------------------------------------------- #

    def registrar_disparo(self, disparo: Disparo, altura_cabeza: int) -> bool:
        """Anota un disparo advisorio. `False` si no corresponde anotarlo.

        Las cuatro guardas, y ninguna es cosmética:

        1. **ya hay uno pendiente de esta regla** — sigue evaluando TRUE entre el
           disparo y el lock-in, y sin esto se registraría en cada bloque;
        2. **esta regla tiene una transición en vuelo** — se rearma en la
           activación, no en el lock-in (ver el docstring del módulo);
        3. **el mismo disparo ya es irrevocable** — pasa cuando una
           reorganización deshizo el bloque del lock-in y la regla vuelve a
           evaluar TRUE porque el evento todavía no se reescribió;
        4. **hay un rechazo contra la base vigente** — reintentar daría idéntico.
        """
        if disparo.nombre in self.pendientes:
            return False
        if self.en_vuelo(disparo.nombre, altura_cabeza) is not None:
            return False
        if any(
            c.regla == disparo.nombre and c.altura_disparo == disparo.altura
            for c in self.checkpoints
        ):
            return False
        if self.rechazo_vigente(disparo.nombre) is not None:
            return False
        self.pendientes[disparo.nombre] = disparo
        return True

    # -- lock-in ----------------------------------------------------------- #

    def altura_de_lockin(self, disparo: Disparo, ventana_finalidad: int) -> int:
        """Dónde se vuelve irrevocable: cuando `N` es final, con tope duro.

        El tope (C7.4) acota cuánto puede estirar la finalidad una inundación de
        impugnaciones. **En esta fase está inerte** —la finalidad llega siempre en
        `VENTANA_FINALIDAD` bloques— y se escribe ahora para que el cronograma no
        tenga que aprender a esperar en la Fase 3.
        """
        tope = g.VENTANA_FINALIDAD + g.tope_demora(disparo.clase)
        return disparo.altura + min(ventana_finalidad, tope)

    def _sucesor(self, disparo: Disparo, base: Ruleset) -> Params:
        """Los `params_nuevos`, computados acá y no en el disparo.

        Levanta `SucesorInvalido` o `ViolacionInvariante` si no se puede
        commitear. **Nada de eso detiene la cadena**: el lock-in no ocurre.
        """
        params = disparo.regla.params_sucesor(disparo.estado, base)
        if params.generacion != base.generacion + 1:
            raise SucesorInvalido(
                f"la regla propuso la generación {params.generacion} y sobre el "
                f"ruleset comprometido le toca la {base.generacion + 1}"
            )
        i1_sucesor_en_el_espacio(params)
        i5_aditiva(base.params, params)
        return params

    def promover(
        self, altura_cabeza: int, ventana_finalidad: int
    ) -> tuple[list[Checkpoint], list[Rechazo]]:
        """Resuelve todo disparo cuyo bloque ya es final: lock-in o rechazo.

        El orden es por altura de disparo y, a igualdad, por nombre de regla: dos
        transiciones que maduran en el mismo bloque componen en un orden que
        cualquier nodo deriva de la cadena, no del azar de un diccionario.
        """
        emitidos: list[Checkpoint] = []
        rechazados: list[Rechazo] = []
        maduros = sorted(
            (
                d
                for d in self.pendientes.values()
                if self.altura_de_lockin(d, ventana_finalidad) <= altura_cabeza
            ),
            key=lambda d: (d.altura, d.nombre),
        )

        for disparo in maduros:
            base = self.comprometido
            altura_lockin = self.altura_de_lockin(disparo, ventana_finalidad)
            del self.pendientes[disparo.nombre]

            try:
                params = self._sucesor(disparo, base)
            except (SucesorInvalido, ViolacionInvariante) as falla:
                rechazo = Rechazo(
                    regla=disparo.nombre,
                    clase=disparo.clase,
                    altura_disparo=disparo.altura,
                    altura=altura_lockin,
                    base_h0=base.h0,
                    motivo=str(falla),
                )
                self.rechazos.append(rechazo)
                rechazados.append(rechazo)
                continue

            checkpoint = Checkpoint(
                generacion=params.generacion,
                h0=calcular_h0(base.h0, disparo.state_trigger, params),
                h0_ancestro=base.h0,
                state_trigger=disparo.state_trigger,
                params=params,
                regla=disparo.nombre,
                clase=disparo.clase,
                altura_disparo=disparo.altura,
                altura_lockin=altura_lockin,
                # Nunca antes que una generación anterior: `params_nuevos` es un
                # punto **completo** del espacio y no un delta, así que activar
                # la generación 2 antes que la 1 aplicaría los cambios de la 1
                # con el aviso de la 2. Ver el docstring del módulo.
                altura_activacion=max(
                    altura_lockin + g.delta(disparo.clase), self.ultima_activacion
                ),
            )
            self.checkpoints.append(checkpoint)
            emitidos.append(checkpoint)

        return emitidos, rechazados

    # -- reorganización ---------------------------------------------------- #

    def reorganizar(self, altura_desde: int) -> list[Disparo]:
        """Deshace los disparos advisorios de `altura_desde` en adelante.

        **No toca los checkpoints ni los rechazos, y ésa es toda la idea.** Los
        dos salen de un estado final y de un ancestro irrevocable: si un lock-in
        se pudiera deshacer, la fecha de activación sería una promesa que
        cualquier reorganización rompe.
        """
        descartados = [d for d in self.pendientes.values() if d.altura >= altura_desde]
        for disparo in descartados:
            del self.pendientes[disparo.nombre]
        return descartados

    # -- diagnóstico ------------------------------------------------------- #

    def resumen(self) -> str:
        lineas = [f"generación comprometida: {self.generacion_comprometida}"]
        for disparo in self.pendientes.values():
            lineas.append(f"  disparo advisorio  {disparo.nombre} en {disparo.altura}")
        for punto in self.checkpoints:
            lineas.append(
                f"  lock-in gen {punto.generacion:>2}  {punto.clase}"
                f"  disparo {punto.altura_disparo}"
                f" -> lock-in {punto.altura_lockin}"
                f" -> activación {punto.altura_activacion}"
            )
        for rechazo in self.rechazos:
            lineas.append(
                f"  RECHAZO {rechazo.regla} en {rechazo.altura}: {rechazo.motivo}"
            )
        return "\n".join(lineas)


def avisos(checkpoints: Sequence[Checkpoint]) -> list[int]:
    """El aviso efectivo de cada transición: activación menos lock-in.

    Es `Δ` cuando no hay cola, y **más** cuando la transición tuvo que esperar a
    una anterior. Nunca menos: un aviso más corto que `Δ` sería un incumplimiento;
    uno más largo es sólo más tiempo para prepararse.
    """
    return [c.altura_activacion - c.altura_lockin for c in checkpoints]
