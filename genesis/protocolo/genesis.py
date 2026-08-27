"""El bloque 0: lo que se congela y no vuelve a cambiar nunca (I1).

Todo lo de este archivo es una decisión que Genesis toma una sola vez. Si algo de
acá tiene que cambiar, no es una transición: es un fork común y corriente.

Lo que se fija:

- **la máquina**, no la lista de reglas posibles. El espacio de descendientes es
  todo lo que esa máquina puede ejecutar (§6.6), y por eso el espacio se declara
  como dominios de parámetros y no como una enumeración de rulesets;
- **`Δ` por clase de transición** (§3). No es global a propósito: una transición
  de circulación tolera un aviso largo y una migración criptográfica bajo ataque
  necesita lo contrario. El intercambio está declarado en §10.1;
- **la ventana de finalidad** (§6.3), que es lo que separa el disparo del lock-in;
- los números de estado con costo —`θ*` y `L_max`— que **esta fase no usa**.
  Están acá porque son de Genesis, y los usa la Fase 5.

> **Los valores son de juguete y son desechables por declaración.** El roadmap lo
> dice en su sección 4: todavía no se sabe qué espacio de parámetros tiene que
> anticipar Genesis, así que estos números existen para que el mecanismo corra,
> no para que alguien los herede.
"""

from __future__ import annotations

from dataclasses import dataclass

from protocolo.generacion import Params, Ruleset
from protocolo.serializacion import huella

# --------------------------------------------------------------------------- #
# I1 · la máquina
# --------------------------------------------------------------------------- #

#: Identidad del intérprete. Una transición **nunca** la mueve: selecciona un
#: punto del espacio que esta máquina ya sabe ejecutar. Si cambia, I1 falla, y
#: esa falla es correcta.
INTERPRETE = "genesis-vm/0"

HUELLA_INTERPRETE = huella(INTERPRETE, dominio="interprete")


@dataclass(frozen=True)
class RangoEntero:
    """Dominio de un parámetro interno: un intervalo con paso."""

    minimo: int
    maximo: int
    paso: int = 1

    def contiene(self, valor: object) -> bool:
        if not isinstance(valor, int) or isinstance(valor, bool):
            return False
        if not (self.minimo <= valor <= self.maximo):
            return False
        return (valor - self.minimo) % self.paso == 0

    def __str__(self) -> str:
        return f"[{self.minimo}..{self.maximo}] paso {self.paso}"


@dataclass(frozen=True)
class ConjuntoEntero:
    """Dominio enumerado, para parámetros donde el valor intermedio no existe."""

    valores: frozenset[int]

    def contiene(self, valor: object) -> bool:
        return (
            isinstance(valor, int)
            and not isinstance(valor, bool)
            and valor in self.valores
        )

    def __str__(self) -> str:
        return "{" + ", ".join(str(v) for v in sorted(self.valores)) + "}"


#: El espacio de descendientes, mitad interna (§4, I1). Una transición puede
#: mover cualquiera de estos en cualquier momento, dentro de su dominio.
# --------------------------------------------------------------------------- #
# El presupuesto de la VM — la curva que congela Genesis (§6.6)
#
# Vive acá arriba, y no junto a las funciones del techo, porque `ESPACIO_INTERNO` la
# necesita: el presupuesto de páginas es un punto de esta tabla y de ningún otro lado.
# --------------------------------------------------------------------------- #

#: **La curva de ritmo declarado contra presupuesto de páginas.** Lo que Genesis
#: congela ya no es un ritmo sino esta tabla, y ahí se cierra el último muro del
#: diseño.
#:
#: Hasta el 21/8/2026 el presupuesto de páginas era una constante, y eso tenía una
#: consecuencia que contradecía a §6.6 de frente: **un techo constante no encarece,
#: sólo excluye.** El de pasos se deriva de la capacidad, así que una primitiva más
#: cara entra bajando `tx_por_bloque`; el de páginas no tenía ningún precio que la
#: primitiva pudiera pagar. Con ML-DSA-87 se salvó por dos páginas de suerte —toca
#: 65 y el techo era 96— y la que viniera después podía no tenerla.
#:
#: **La salida es la misma jugada que ya funcionó con el techo de pasos:** dejar de
#: congelar un punto y congelar la cuenta. Acá la cuenta es una curva medida, y el
#: presupuesto de páginas pasa a ser un parámetro interno como cualquier otro. Una
#: primitiva que necesita más memoria **entra resignando capacidad**, que es
#: exactamente lo que §6.6 promete.
#:
#: Los valores salen de `predicado/vm/src/bin/conjunto.rs` corrido en el hardware de
#: referencia, con una sola disciplina aplicada a toda la tabla: **declarado =
#: medido × 0,866, truncado**. El 0,866 es el margen que ya tenía el punto de
#: Genesis (70 declarados sobre 80,8 medidos) y se extiende igual a los demás para
#: que ninguna fila esté elegida con más cariño que otra.
#:
#: | páginas | KiB | medido | declarado |
#: |---:|---:|---:|---:|
#: | 4 | 16 | 163,6 | 140 |
#: | 16 | 64 | 125,5 | 108 |
#: | 32 | 128 | 101,1 | 87 |
#: | 48 | 192 | 86,2 | 74 |
#: | 64 | 256 | 84,3 | 72 |
#: | **96** | **384** | **80,8** | **70** ← el punto de Genesis |
#: | 128 | 512 | 79,8 | 69 |
#: | 256 | 1.024 | 79,3 | 68 |
#: | 512 | 2.048 | 77,6 | 67 |
#: | 1.024 | 4.096 | 10,9 | 9 |
#: | 4.096 | 16.384 | 4,4 | 3 |
#:
#: **La forma de la curva es el hallazgo, y no se podía anticipar sin medir:** de 96
#: a 512 páginas la memoria es casi gratis —el ritmo cae 4%— y entre 512 y 1.024 se
#: derrumba por 7,4×, que es donde se acaba el alcance de la TLB del núcleo de
#: referencia. El mecanismo ahora **cobra esa forma**: cuadruplicar el presupuesto
#: cuesta un 4% de capacidad, y volver a duplicarlo la divide por siete.
#:
#: El espacio no se corta por decreto sino por precio: 4.096 páginas están
#: declaradas, y a 3 M pasos/s la cadena que las elija hace una transacción por
#: bloque. Es una opción legítima y ruinosa, y el protocolo no necesita prohibirla.
R_DECLARADO_POR_PAGINAS: dict[int, int] = {
    4: 140_000_000,
    16: 108_000_000,
    32: 87_000_000,
    48: 74_000_000,
    64: 72_000_000,
    96: 70_000_000,
    128: 69_000_000,
    256: 68_000_000,
    512: 67_000_000,
    1_024: 9_000_000,
    4_096: 3_000_000,
}

#: Tamaño de página. **Ésta sí es constante y no puede ser otra cosa**, y la
#: diferencia con el presupuesto es la que costó entender: cambiar el tamaño de
#: página cambiaría *qué computa* un programa; cambiar el presupuesto sólo cambia
#: *si entra*. Lo primero es semántica y rompe I1; lo segundo es un presupuesto, y
#: el techo de pasos ya funcionaba así desde el principio.
PAGINA_BYTES = 4_096



ESPACIO_INTERNO: dict[str, RangoEntero | ConjuntoEntero] = {
    "emision_por_bloque": RangoEntero(0, 10_000),
    "tamano_bloque_kib": ConjuntoEntero(frozenset({256, 512, 1_024, 2_048, 4_096})),
    "tiempo_bloque_ms": RangoEntero(1_000, 60_000, paso=500),
    "fee_quema_ppm": RangoEntero(0, 1_000_000, paso=1_000),
    #: Entra al espacio porque **el techo de pasos se deriva de él** (§10.3): bajar
    #: capacidad es lo que le hace lugar a una primitiva más cara.
    "tx_por_bloque": RangoEntero(1, 10_000),
    #: **El presupuesto de páginas de la VM, y entra al espacio desde el 21/8/2026.**
    #:
    #: Era una constante, y por eso **excluía en vez de encarecer**: una primitiva que
    #: necesitara más memoria no tenía precio que pagar. Ahora pedir más páginas baja el
    #: ritmo declarado —`R_DECLARADO_POR_PAGINAS`— y bajar el ritmo baja el techo de
    #: pasos, así que la memoria se paga en capacidad como todo lo demás.
    #:
    #: Es un **conjunto y no un rango**: sólo los puntos donde la curva está medida. No
    #: se interpola una zona de comportamiento que nadie observó.
    "paginas_vm": ConjuntoEntero(frozenset(R_DECLARADO_POR_PAGINAS)),
}

#: Todo formato que la máquina de Genesis sabe ejecutar: la mitad **visible** del
#: espacio. Una transición puede activar cualquiera de estos —de forma aditiva,
#: I5— y ninguno más: activar uno que la máquina no conoce sería cambiar la
#: máquina.
#:
#: Que `firma/ml-dsa-44` esté acá desde el bloque 0 es §6.6 en una línea: el
#: sucesor criptográfico no lo introduce la transición, ya estaba adentro.
FORMATOS_CONOCIDOS = frozenset(
    {
        "direccion/gen0",
        "firma/ed25519",
        "firma/ml-dsa-44",
        "recibo/gen0",
    }
)

# --------------------------------------------------------------------------- #
# El canario de §6.6
# --------------------------------------------------------------------------- #

#: La semilla del canario, **pública y sin nada en la manga**. La instancia
#: debilitada que Genesis publica no se *genera*: se **deriva** de este string.
#:
#: La diferencia no es de estilo y es lo que hace admisible al trigger de §6.6
#: bajo I2. Si Genesis generara la instancia —un módulo, un par de claves—, quien
#: la generó conservaría su trampa y podría gastar el canario cuando quisiera: la
#: *capacidad demostrada* pasaría a ser *un secreto que alguien se guardó*, y el
#: canario dejaría de ser una alarma para ser una compuerta con disfraz
#: criptográfico. Derivada, el único camino a producir el hecho es romper la
#: primitiva, que es la capacidad ante la que la transición existe para reaccionar.
#:
#: En una cadena real la derivación produce la instancia debilitada de verdad
#: (parámetros de curva, módulo, lo que corresponda) y hay que poder auditar que
#: **nadie eligió el resultado**. Acá el hash hace de esa derivación: lo que la
#: Fase 1 puede verificar es lo que un revisor verificaría en Genesis — que la
#: instancia publicada es exactamente la que sale de la semilla.
CANARIO_SEMILLA = (
    "genesis/canario/1 · instancia debilitada de firma/ed25519 · "
    "derivada, no generada · nadie retiene la trampa"
)

CANARIO_INSTANCIA = huella(CANARIO_SEMILLA, dominio="canario")

# --------------------------------------------------------------------------- #
# Los tres tiempos (§3)
# --------------------------------------------------------------------------- #

CIRCULACION = "circulacion"
CRIPTOGRAFICA = "criptografica"

CLASES = frozenset({CIRCULACION, CRIPTOGRAFICA})

#: `Δ` en bloques, por clase. Cuenta desde el **lock-in**, no desde el disparo.
#:
#: > **⚠ Estos dos números están abiertos, y la auditoría de `UNIDADES.md` dice por qué.**
#: > §10.1 afirma que `Δ` *compra seguridad de integración con tiempo de reacción*, y a
#: > estos valores compra **6,4 minutos** (circulación) y **48 segundos** (criptográfica)
#: > con el tiempo de bloque inicial. Ningún integrador reacciona en seis minutos, así que
#: > la tensión que §10.1 describe —urgencia de la cadena contra tiempo del integrador— no
#: > existe a estos números: los dos están del mismo lado.
#: >
#: > Y están **en bloques**, que es una unidad que `tiempo_bloque_ms` redefine: el aviso
#: > real varía 60× a lo largo del espacio. Es el mismo defecto que tenía el depósito de
#: > permanencia (C20), en el mecanismo central en vez de en la permanencia — sólo que
#: > acá la corrección no se aplica igual, porque la altura de activación se anuncia al
#: > hacer lock-in y moverla después contradice §3.
#: >
#: > Los valores nunca aparecieron en el paper: viven acá desde la Fase 1, donde alcanzaban
#: > para que las pruebas corrieran. **No se tocan sin decidir a quién se le promete el
#: > aviso y cuánto tarda ese alguien en actualizar.**
DELTA_POR_CLASE: dict[str, int] = {
    CIRCULACION: 64,
    CRIPTOGRAFICA: 8,
}

#: Ventana de impugnación (§6.3): cuántos bloques tiene que sobrevivir el bloque
#: del disparo para ser final. Antes de eso, el disparo es advisorio.
VENTANA_FINALIDAD = 12

#: Tope duro de demora al lock-in, por clase (C7.4: *un residuo que compone no es
#: un arreglo, es un préstamo*). Acota cuánto puede estirar la finalidad una
#: inundación de impugnaciones antes de que el lock-in ocurra igual.
#:
#: **Está inerte en esta fase.** Sin impugnaciones (Fase 3) la finalidad llega
#: siempre a `N + VENTANA_FINALIDAD` y el tope nunca muerde. Se escribe ahora
#: para que el cronograma no tenga que aprender a esperar después.
#:
#: Su residuo, declarado: *un fraude descubierto después del tope no detiene la
#: transición*, y esa exposición es igual el día 1 que el año 20.
TOPE_DEMORA_LOCKIN: dict[str, int] = {
    CIRCULACION: 256,
    CRIPTOGRAFICA: 32,
}

# --------------------------------------------------------------------------- #
# El techo de pasos de VM (§6.6, §10.3)
# --------------------------------------------------------------------------- #

#: Fracción del nodo liviano que puede ocupar la verificación de firmas, en ppm.
#:
#: **Es una de las dos constantes libres del techo de pasos, y está declarada como
#: decisión y no como medición.** Test 2 usó un cuarto de núcleo para su veredicto y
#: de ahí sale el 25%. El piso lo pone §6.3: la cola necesita headroom para drenar, y
#: la Fase 3 midió que con el 10% alcanzan once nodos — así que la verificación tiene
#: que dejar libre al menos eso, más lo que se lleven el predicado de §6.2, la red y
#: la liquidación de §6.5.
F_VERIFICACION_PPM = 250_000

def ritmo_declarado(paginas_vm: int) -> int:
    """Pasos por segundo que el hardware de referencia sostiene con ese presupuesto.

    **Declarado y no medido**, que es la parte que importa: la cadena no puede leer
    la velocidad del hardware sin convertirse en un oráculo (I2). Es un requisito
    sobre las implementaciones —la que corra más lento está fuera de spec— y por eso
    la tabla se congela en Genesis en vez de recalcularse.
    """
    ritmo = R_DECLARADO_POR_PAGINAS.get(paginas_vm)
    if ritmo is None:
        raise ValueError(
            f"{paginas_vm} páginas no es un punto declarado de la curva; "
            f"están {sorted(R_DECLARADO_POR_PAGINAS)}"
        )
    return ritmo


def techo_de_pasos(tiempo_de_bloque_ms: int, tx_por_bloque: int, paginas_vm: int) -> int:
    """**El techo de pasos de §6.6, derivado y no elegido.**

    ```
    techo = f* × tiempo_de_bloque × R_declarado(páginas) / tx_por_bloque
    ```

    Lo que Genesis congela es **esta función y la curva** (I1); el valor lo determina
    cada generación con sus propios parámetros. Eso contesta las dos preguntas que
    §10.3 dejó abiertas —el número y dónde vive— y **no crea una palanca suelta**:
    nadie puede mover el techo sin mover capacidad, tiempo de bloque o memoria, y las
    tres tienen sus propias consecuencias y sus propios disparos.

    Y no depende de qué primitiva esté instalada, así que **no compone**: un techo
    relativo al mejor candidato de cada ronda se rebasa en cada generación —2× por
    transición son 1.024× a las diez—, que es lo que §10.3 rechaza.

    > **Los dos techos son uno solo mirado de dos lados.** La Fase 4 midió que el
    > mismo opcode `lw` cuesta 23× más si el dato no está en caché, así que el
    > presupuesto de pasos no significa nada sin el de páginas al lado. Por eso el
    > segundo entra en la fórmula del primero en vez de vivir aparte: **pedir más
    > memoria baja el ritmo declarado, y bajar el ritmo baja el techo.**
    """
    if tiempo_de_bloque_ms <= 0 or tx_por_bloque <= 0:
        raise ValueError("el techo se deriva de parámetros positivos")
    pasos_por_bloque = (
        F_VERIFICACION_PPM
        * tiempo_de_bloque_ms
        * ritmo_declarado(paginas_vm)
        // (1_000_000 * 1_000)
    )
    return pasos_por_bloque // tx_por_bloque


def techo_vigente(ruleset) -> int:
    """El techo de pasos que rige bajo este ruleset. Se lee, no se guarda."""
    return techo_de_pasos(
        ruleset.interno("tiempo_bloque_ms"),
        ruleset.interno("tx_por_bloque"),
        ruleset.interno("paginas_vm"),
    )


def paginas_vigentes(ruleset) -> int:
    """El techo de páginas que rige bajo este ruleset."""
    return ruleset.interno("paginas_vm")


def capacidad_para(paginas_vm: int, pasos_por_verificacion: int, margen: float = 2.0,
                   tiempo_de_bloque_ms: int = 6_000) -> int:
    """Cuántas transacciones por bloque tolera una primitiva con ese presupuesto.

    **Es la cuenta que vuelve visible el precio de la memoria**, y la que antes no
    existía: con el techo de páginas constante, una primitiva que necesitaba más
    memoria no tenía capacidad que resignar — no entraba y punto.
    """
    pasos_por_bloque = (
        F_VERIFICACION_PPM
        * tiempo_de_bloque_ms
        * ritmo_declarado(paginas_vm)
        // (1_000_000 * 1_000)
    )
    return int(pasos_por_bloque / (pasos_por_verificacion * margen))


# --------------------------------------------------------------------------- #
# Estado con costo — declarado acá, lo usa la Fase 5
# --------------------------------------------------------------------------- #

#: `θ*` en partes por millón (§10.1): 50% de un presupuesto declarado. El techo
#: derivado es 67%, porque el pico de un shock sostenido llega a 1,48×. El sesgo
#: conservador es deliberado: errar bajo es reversible, errar alto no.
THETA_ESTRELLA_PPM = 500_000

#: El presupuesto de estado que el nodo declara, en bytes (§10.1).
PRESUPUESTO_ESTADO_BYTES = 4 * 2**30

#: **El corte del árbol del conjunto activo (§10.1), y es constante de Genesis.**
#:
#: Guardar todos los nodos internos del árbol cuesta 32 B por entrada. La alternativa es
#: guardar los niveles por encima de un corte `d` y recomputar el subárbol de `2^d` hojas:
#: con `d = 6` el disco baja a **1 B por entrada** y el precio son ocho puntos del
#: presupuesto de hash del nodo. Está medido en `presupuesto-nodo/RESULTADOS.md`.
#:
#: **Y no es una decisión de implementación, aunque así se la anotó el 18/8/2026.** El piso
#: de permanencia de §8.5 se **deriva** del costo de actualizar el árbol, y el piso se
#: quema — o sea que es consenso. Dos nodos con `d` distinto calcularían pisos distintos y
#: no coincidirían sobre cuánto se quemó al crear una entrada. **O `d` es constante de
#: Genesis, o el piso deja de ser derivado.**
#:
#: El precio de `d` es de tres monedas y no de dos, que es lo que faltaba ver:
#:
#: | `d` | B/entrada | hashes por actualización | piso, en % de `L_max` |
#: |---:|---:|---:|---:|
#: | 1 | 32,0 | 26 | 24% |
#: | 4 | 4,0 | 37 | 34% |
#: | **6** | **1,0** | **83** | **77%** |
#: | 7 | 0,5 | 146 | 135% — el piso supera al depósito máximo |
#:
#: Se deja en 6, que es el que el diseño eligió cuando sólo se miraban dos de las tres
#: monedas. **Que a 7 el piso ya supere `L_max` dice que el margen es más fino de lo que
#: parecía**, y elegir de nuevo es una decisión abierta.
CORTE_ARBOL = 6

#: `L_max` en épocas (§8.5): tope a la vida comprable de una vez. **Es condición
#: de estabilidad, no una recomendación.**
L_MAX_EPOCAS = 25

# --------------------------------------------------------------------------- #
# El ruleset inicial
# --------------------------------------------------------------------------- #

PARAMS_INICIALES = Params(
    generacion=0,
    internos={
        "emision_por_bloque": 1_000,
        "tamano_bloque_kib": 512,
        "tiempo_bloque_ms": 6_000,
        "fee_quema_ppm": 200_000,
        # 67 → 26 → 15 el 20/8/2026, en tres correcciones del mismo día. **No cambió
        # el techo: cambió lo que un segundo de reloj compra en pasos garantizados.**
        # Con R_declarado en 70 M el bloque tiene 105 M pasos, y darle a ML-DSA-44 el
        # margen de 2× que eligió Genesis deja 15 transacciones. Es exactamente el
        # mecanismo que §6.6 describe —una primitiva más cara entra pagando capacidad—
        # cobrado sobre la que ya estaba, y no sobre una futura.
        "tx_por_bloque": 15,
        #: 96 páginas: donde estaba el techo constante, así que el punto de Genesis no
        #: se movió al volverlo parámetro. ML-DSA-44 toca 26 y entra con 3,7×.
        "paginas_vm": 96,
    },
    formatos=frozenset({"direccion/gen0", "firma/ed25519", "recibo/gen0"}),
)

#: La raíz del linaje (I4). Es el único hash de la cadena que no commitea a nada
#: anterior; todo lo demás cuelga de acá.
H0_GENESIS = huella(
    {"interprete": HUELLA_INTERPRETE, "params": PARAMS_INICIALES.canonico()},
    dominio="linaje/raiz",
)

RULESET_INICIAL = Ruleset(params=PARAMS_INICIALES, h0=H0_GENESIS)


def motivo_fuera_del_espacio(params: Params) -> str | None:
    """`None` si `params` es un punto del espacio; si no, por qué no lo es.

    Devuelve el motivo en vez de un booleano porque el mensaje es la mitad del
    valor: *"la transición quiso poner tamano_bloque_kib = 3000"* se arregla
    solo; *"I1 falló"* manda a leer código.
    """
    faltantes = set(ESPACIO_INTERNO) - set(params.internos)
    if faltantes:
        return f"faltan parámetros internos: {sorted(faltantes)}"

    sobrantes = set(params.internos) - set(ESPACIO_INTERNO)
    if sobrantes:
        return (
            f"parámetros que el espacio de Genesis no define: {sorted(sobrantes)} — "
            "agregar un parámetro es cambiar la máquina, no seleccionar un punto"
        )

    for nombre, dominio in ESPACIO_INTERNO.items():
        valor = params.internos[nombre]
        if not dominio.contiene(valor):
            return f"{nombre} = {valor!r} fuera de {dominio}"

    desconocidos = params.formatos - FORMATOS_CONOCIDOS
    if desconocidos:
        return (
            "formatos que la máquina de Genesis no sabe ejecutar: "
            f"{sorted(desconocidos)}"
        )
    return None


def pertenece_al_espacio(params: Params) -> bool:
    return motivo_fuera_del_espacio(params) is None


def delta(clase: str) -> int:
    if clase not in DELTA_POR_CLASE:
        raise KeyError(f"clase de transición desconocida: {clase!r}")
    return DELTA_POR_CLASE[clase]


def tope_demora(clase: str) -> int:
    if clase not in TOPE_DEMORA_LOCKIN:
        raise KeyError(f"clase de transición desconocida: {clase!r}")
    return TOPE_DEMORA_LOCKIN[clase]
