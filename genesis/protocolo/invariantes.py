"""I1–I5 como predicados ejecutables. **No son comentarios.**

Esta es la Fase 0 entera: que las cinco invariantes dejen de ser prosa antes de
la primera línea de mecanismo. Toda fase posterior las sigue pasando sin
excepciones ni *skips* — y el día que haya que marcar una como excepción, se para
y se discute el diseño, no el test.

Cada predicado **levanta `ViolacionInvariante` con el motivo** en vez de devolver
`False`. Un booleano en rojo manda a leer código; el motivo dice qué parámetro,
qué generación y qué altura.

Cómo se reparte el trabajo, que no es obvio:

- **I1, I3, I5 se verifican en la transición.** Son propiedades de la conmutación
  y ahí es donde pueden romperse.
- **I2 se verifica en cada bloque**: la monotonía de la aproximación es una
  propiedad de la serie, no de un punto, así que hay que mirarla mientras corre.
- **I4 se verifica en cualquier momento**, y sobre todo al sincronizar: es la
  única que un tercero puede correr sin confiar en nadie (§5).
"""

from __future__ import annotations

import copy
import inspect
from typing import Any, Protocol, Sequence, runtime_checkable

from protocolo import genesis as g
from protocolo.generacion import Objeto, Params, Ruleset, es_aditivo, formatos_retirados
from protocolo.linaje import Checkpoint, motivo_linaje_invalido
from protocolo.serializacion import corto, huella


class ViolacionInvariante(AssertionError):
    """Una invariante de §4 no se cumple. El mensaje dice cuál y por qué."""

    def __init__(self, invariante: str, motivo: str) -> None:
        super().__init__(f"{invariante}: {motivo}")
        self.invariante = invariante
        self.motivo = motivo


@runtime_checkable
class TieneHuella(Protocol):
    def huella(self) -> bytes: ...


# --------------------------------------------------------------------------- #
# I1 · el intérprete vive en Genesis y no cambia nunca
# --------------------------------------------------------------------------- #


def i1_interprete_congelado(huella_actual: bytes) -> None:
    """El nodo sigue corriendo la máquina de Genesis.

    Se chequea contra la constante y no contra "la de antes": comparar con el
    valor anterior deja pasar una deriva lenta, que es exactamente la forma en
    que un intérprete cambia sin que nadie decida cambiarlo.
    """
    if huella_actual != g.HUELLA_INTERPRETE:
        raise ViolacionInvariante(
            "I1",
            f"el intérprete es {corto(huella_actual)}... y Genesis congeló "
            f"{corto(g.HUELLA_INTERPRETE)}... — eso no es una transición, es un fork",
        )


def i1_sucesor_en_el_espacio(params: Params) -> None:
    """La transición selecciona un punto que la máquina ya sabe ejecutar."""
    motivo = g.motivo_fuera_del_espacio(params)
    if motivo is not None:
        raise ViolacionInvariante(
            "I1", f"el sucesor no es un punto del espacio de Genesis — {motivo}"
        )


# --------------------------------------------------------------------------- #
# I2 · el trigger se computa sólo desde el estado, y nadie elige el momento
# --------------------------------------------------------------------------- #

#: Las dos formas admisibles de cumplir la segunda mitad de I2 (§4).
#:
#: - **aproximación observable**: la cantidad que dispara es monótona y la cadena
#:   publica cuántos bloques faltan al ritmo actual. Nadie elige el momento porque
#:   la aproximación es pública y agregada: ningún actor la mueve solo.
#: - **capacidad demostrada**: no hay aproximación y no puede haberla. Admisible
#:   sólo si producir el hecho exige **exactamente la capacidad a la que la
#:   transición responde** — el canario de §6.6: gastarlo pide haber roto la
#:   primitiva.
#:
#: Lo que las dos excluyen es lo mismo: un hecho que una parte identificable puede
#: producir a voluntad y barato. *"El estado dice que Alice mandó 1 wei a la
#: dirección X"* se computa desde el estado y es la gobernanza de vuelta.
MODO_APROXIMACION = "aproximacion"
MODO_CAPACIDAD = "capacidad"
MODOS = frozenset({MODO_APROXIMACION, MODO_CAPACIDAD})


def i2_trigger_solo_estado(regla: Any, estado: TieneHuella) -> None:
    """Tres chequeos sobre el trigger, y ninguno es redundante.

    1. **Firma.** `progreso` y `dispara` reciben el estado y nada más. Un
       parámetro extra es la puerta por donde entra un oráculo, un reloj o un
       voto.
    2. **Pureza.** Dos evaluaciones sobre estados equivalentes dan lo mismo. Una
       regla que lee la hora del sistema pasa el chequeo de firma y falla acá.
    3. **Sin efecto.** Evaluar el trigger no toca el estado. Un trigger que
       escribe lo que mide se dispara a sí mismo.
    """
    for metodo in ("progreso", "umbral", "dispara"):
        parametros = list(inspect.signature(getattr(regla, metodo)).parameters)
        if parametros != ["estado"]:
            raise ViolacionInvariante(
                "I2",
                f"{type(regla).__name__}.{metodo} recibe {parametros} — el trigger "
                "se computa sólo desde el estado, cualquier otro insumo es externo",
            )

    antes = estado.huella()
    primera = regla.progreso(estado)
    copia = copy.deepcopy(estado)
    segunda = regla.progreso(copia)
    despues = estado.huella()

    if primera != segunda:
        raise ViolacionInvariante(
            "I2",
            f"{regla.nombre}: dos evaluaciones sobre el mismo estado dieron "
            f"{primera} y {segunda} — el trigger depende de algo que no es estado",
        )
    if antes != despues:
        raise ViolacionInvariante(
            "I2", f"{regla.nombre}: evaluar el trigger modificó el estado"
        )


def i2_aproximacion_monotona(nombre: str, progresos: Sequence[int]) -> None:
    """La aproximación al disparo no retrocede.

    Ojo con lo que **no** dice: no exige que la *distancia* sea monótona. La
    distancia se mide al ritmo actual y el ritmo puede bajar, así que puede
    alejarse legítimamente. Lo que no puede pasar es que el progreso vuelva
    atrás, porque entonces el disparo dejaría de verse venir (§4, I2).
    """
    for anterior, actual in zip(progresos, progresos[1:]):
        if actual < anterior:
            raise ViolacionInvariante(
                "I2",
                f"{nombre}: el progreso hacia el disparo retrocedió de {anterior} "
                f"a {actual} — un trigger que no se puede ver venir no es admisible",
            )


def i2_modo_declarado(regla: Any) -> None:
    """Toda regla declara **cómo** cumple I2, y la declaración va on-chain.

    No hay default: una regla sin modo es una regla sobre la que nadie puede
    decidir si es admisible, y el lugar donde eso se decide es la auditoría de
    Genesis, no el runtime.
    """
    modo = getattr(regla, "modo", None)
    if modo not in MODOS:
        raise ViolacionInvariante(
            "I2",
            f"{regla.nombre} declara modo {modo!r} y los admisibles son "
            f"{sorted(MODOS)}",
        )
    if modo == MODO_CAPACIDAD and not getattr(regla, "capacidad", None):
        raise ViolacionInvariante(
            "I2",
            f"{regla.nombre} dispara por capacidad demostrada y no declara cuál — "
            "sin eso no se puede auditar si el que puede producir el hecho es el "
            "único ante quien la transición existe para reaccionar",
        )


def i2_se_vio_venir(regla: Any, distancia_previa: Any) -> None:
    """Una regla de aproximación **no puede disparar desde el reposo**.

    Es el chequeo con filo de I2, y lo que caza es una puerta trasera disfrazada:
    *"cuando la dirección X reciba 1 wei"* tiene progreso monótono y distancia
    publicable, así que pasa la letra vieja de la invariante — pero salta de 0 al
    umbral en un bloque, sin que la cadena haya anunciado nada. Si el bloque
    anterior no publicó una distancia observable, esto no es una aproximación: es
    un escalón, y como escalón hay que declararlo y justificarlo.
    """
    if distancia_previa is None or not distancia_previa.observable:
        raise ViolacionInvariante(
            "I2",
            f"{regla.nombre} se declara por aproximación observable y disparó sin "
            "que el bloque anterior publicara una distancia: es un escalón, no una "
            "aproximación",
        )


def i2_trigger_discreto(regla: Any, progresos: Sequence[int], umbral: int) -> None:
    """Un trigger de capacidad **no se aproxima: llega**.

    La formulación exacta importa, y el primer intento estuvo mal. *"Su progreso
    no avanza"* es falso —avanza una vez, cuando el hecho ocurre— y medirlo con
    una ventana de ritmo hace ver ese escalón como rampa durante los bloques
    siguientes. Lo que distingue a un escalón de una rampa es otra cosa: **cada
    vez que el progreso avanza, alcanza el umbral en ese mismo bloque.**

    Una regla que se declara por capacidad y avanza de a poco sí se aproxima, y
    entonces le corresponde el otro modo con sus obligaciones — sobre todo la de
    no poder disparar desde el reposo. Esto es lo que mantiene la declaración
    falsable en vez de decorativa.
    """
    if len(progresos) < 2:
        return
    anterior, actual = progresos[-2], progresos[-1]
    if actual > anterior and actual < umbral:
        raise ViolacionInvariante(
            "I2",
            f"{regla.nombre} se declara por capacidad demostrada y su progreso "
            f"pasó de {anterior} a {actual} sin llegar al umbral {umbral}: eso es "
            "una aproximación, y como tal hay que declararla",
        )


def i2_canario_sin_trampa(semilla: str, instancia: bytes) -> None:
    """El canario de §6.6 no lo generó nadie: se deriva de una semilla pública.

    Es la condición que vuelve admisible al trigger por capacidad, y **no estaba
    escrita**. Si Genesis *generara* la instancia debilitada en vez de derivarla,
    quien la generó conservaría su trampa —los factores, la clave, lo que sea— y
    podría gastar el canario cuando quisiera. Ahí la *capacidad demostrada* pasa a
    ser *un secreto que alguien se guardó*, y el canario deja de ser una alarma
    para ser una compuerta con disfraz criptográfico: exactamente la gobernanza
    que I2 existe para eliminar, sólo que más difícil de ver.
    """
    esperada = huella(semilla, dominio="canario")
    if instancia != esperada:
        raise ViolacionInvariante(
            "I2",
            "la instancia del canario no se deriva de su semilla pública: alguien "
            "la generó, y quien la generó puede tener la trampa",
        )


def i2_distancia_publicada(estado: Any, nombres_de_regla: Sequence[str]) -> None:
    """La distancia está en el estado, no en un log del nodo.

    *Consultable on-chain* es la mitad de I2 que se olvida: si la distancia la
    calcula cada quien por su cuenta, el integrador que la necesita depende de
    correr un nodo completo y de haber implementado bien la regla.
    """
    publicadas = getattr(estado, "distancias", None)
    if publicadas is None:
        raise ViolacionInvariante(
            "I2", "el estado no publica ninguna distancia al disparo"
        )
    faltantes = [n for n in nombres_de_regla if n not in publicadas]
    if faltantes:
        raise ViolacionInvariante(
            "I2", f"reglas sin distancia publicada en el estado: {faltantes}"
        )


# --------------------------------------------------------------------------- #
# I3 · el estado cruza la transición íntegro
# --------------------------------------------------------------------------- #


def i3_estado_intacto(
    huella_antes: bytes,
    huella_despues: bytes,
    identidad_antes: int,
    identidad_despues: int,
) -> None:
    """Bit a bit idéntico **y el mismo objeto**.

    Los dos chequeos miden cosas distintas. La huella dice que no hubo migración
    ni reasignación; la identidad dice que no hubo *snapshot* — que el estado
    nunca salió del proceso que lo tiene. Un nodo que serializa, conmuta y
    vuelve a cargar pasa el primero y falla el segundo, y esa diferencia es toda
    la diferencia entre conmutar y forkear.
    """
    if identidad_antes != identidad_despues:
        raise ViolacionInvariante(
            "I3",
            "el estado de después no es el mismo objeto que el de antes — hubo "
            "snapshot o recarga, y eso es una migración con otro nombre",
        )
    if huella_antes != huella_despues:
        raise ViolacionInvariante(
            "I3",
            f"el estado cambió durante la conmutación: {corto(huella_antes)}... -> "
            f"{corto(huella_despues)}...",
        )


# --------------------------------------------------------------------------- #
# I4 · cada generación commitea a su ancestro
# --------------------------------------------------------------------------- #


def i4_linaje(checkpoints: Sequence[Checkpoint], h0_raiz: bytes = g.H0_GENESIS) -> None:
    motivo = motivo_linaje_invalido(checkpoints, h0_raiz)
    if motivo is not None:
        raise ViolacionInvariante("I4", motivo)


# --------------------------------------------------------------------------- #
# I5 · las transiciones son aditivas en la interfaz
# --------------------------------------------------------------------------- #


def i5_aditiva(viejo: Params, nuevo: Params) -> None:
    if not es_aditivo(viejo, nuevo):
        raise ViolacionInvariante(
            "I5",
            "la transición retira formatos de la interfaz: "
            f"{sorted(formatos_retirados(viejo, nuevo))} — retirar es una "
            "transición posterior, separada por al menos una generación",
        )


def i5_objetos_etiquetados(objetos: Sequence[Objeto], generacion_maxima: int) -> None:
    """Todo objeto lleva etiqueta de generación, desde el bloque 0.

    Sin etiqueta, el integrador viejo no puede *fallar cerrado* frente a un
    objeto nuevo: lo interpreta con las reglas que conoce, que es la falla que
    pierde fondos.
    """
    for objeto in objetos:
        if not isinstance(objeto.generacion, int) or objeto.generacion < 0:
            raise ViolacionInvariante(
                "I5", f"objeto sin etiqueta de generación válida: {objeto!r}"
            )
        if objeto.generacion > generacion_maxima:
            raise ViolacionInvariante(
                "I5",
                f"objeto etiquetado en la generación {objeto.generacion} y la "
                f"vigente es la {generacion_maxima}",
            )


# --------------------------------------------------------------------------- #
# Las revisiones compuestas que corre el nodo
# --------------------------------------------------------------------------- #


def revisar_bloque(
    estado: Any,
    ruleset: Ruleset,
    reglas: Sequence[Any],
    historial_progreso: dict[str, list[int]],
    checkpoints: Sequence[Checkpoint],
) -> None:
    """Todo lo que se puede verificar con la cadena quieta, después de un bloque."""
    i1_interprete_congelado(g.HUELLA_INTERPRETE)
    i2_canario_sin_trampa(g.CANARIO_SEMILLA, g.CANARIO_INSTANCIA)
    for regla in reglas:
        i2_trigger_solo_estado(regla, estado)
        i2_modo_declarado(regla)
        i2_aproximacion_monotona(regla.nombre, historial_progreso.get(regla.nombre, []))
        if regla.modo == MODO_CAPACIDAD:
            i2_trigger_discreto(
                regla,
                historial_progreso.get(regla.nombre, []),
                regla.umbral(estado),
            )
    i2_distancia_publicada(estado, [r.nombre for r in reglas])
    i4_linaje(checkpoints)
    i5_objetos_etiquetados(list(estado.objetos.values()), ruleset.generacion)


def revisar_transicion(
    viejo: Ruleset,
    nuevo: Ruleset,
    huella_antes: bytes,
    huella_despues: bytes,
    identidad_antes: int,
    identidad_despues: int,
) -> None:
    """Todo lo que sólo puede romperse en el instante de la conmutación."""
    i1_interprete_congelado(g.HUELLA_INTERPRETE)
    i1_sucesor_en_el_espacio(nuevo.params)
    i5_aditiva(viejo.params, nuevo.params)
    i3_estado_intacto(huella_antes, huella_despues, identidad_antes, identidad_despues)
