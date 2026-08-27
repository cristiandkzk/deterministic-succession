"""El cobro de permanencia — §8.5, y la sospecha de C18.5 corrida contra él.

**Toda entrada de estado paga por seguir existiendo.** Al crear se quema un *piso*; después se
consume un *depósito*, época a época, lineal en tamaño × tiempo. Mientras hay saldo la entrada
está en el conjunto activo; cuando se agota, se desaloja.

La propiedad que compra todo esto: **en la cadena no existe ningún objeto cuyo costo futuro no
tenga a alguien pagándolo. Nadie puede comprar espacio perpetuo con un pago finito.**

## Los dos números, y por qué no son la misma clase de cosa

La Fase 4 cerró dos veces el mismo techo con la misma jugada —*el número no se elige, se deriva*—
y de ahí salió la sospecha de C18.5: **un parámetro que hay que elegir a ojo suele ser una cuenta
que falta escribir.** Corrida contra esta fase, separa los dos números limpiamente:

- **el piso SÍ es una cuenta.** §8.5 ya lo declara —*"no es una perilla: es el costo fijo del
  ciclo crear + desalojar"*— y acá se escribe: se mide el ciclo contra el presupuesto del nodo y
  sale en **épocas de guardado**, que es una cantidad física;
- **la tasa NO puede serlo, y se puede decir exactamente por qué.** El techo de pasos se pudo
  cerrar porque sus dos lados eran físicos: pasos de un lado, segundos del otro. La tasa tiene un
  lado físico —bytes × épocas— y uno monetario —cuántos tokens vale eso—, y **ninguna cuenta
  cruza esos dos lados sin leer un precio**, que es justo lo que I2 prohíbe.

De ahí sale una decisión de forma que no estaba en el paper: **el piso se denomina en épocas de
guardado, no en tokens.** Así hereda la tasa que rija, sea cual sea, y deja de ser un segundo
parámetro libre al lado del primero.
"""

from __future__ import annotations

from dataclasses import dataclass

from protocolo import genesis as g

# --------------------------------------------------------------------------- #
# La época
# --------------------------------------------------------------------------- #

#: Duración de una época, en bloques. **Se declara en bloques y no en tiempo** para que
#: no dependa de un reloj (I2). Con el tiempo de bloque inicial son 24 horas.
EPOCA_BLOQUES = 14_400

#: Bytes que ocupa una entrada activa, contando el objeto, su parte del árbol y el
#: índice de desalojo (§10.1). Un saldo de tenedor pesa la mitad.
ENTRADA_BYTES = 120


def epoca_segundos(tiempo_de_bloque_ms: int) -> int:
    """Cuánto dura una época en la generación vigente."""
    return EPOCA_BLOQUES * tiempo_de_bloque_ms // 1_000


def entradas_que_entran(tamano_bytes: int = ENTRADA_BYTES) -> int:
    """Cuántas entradas caben en el presupuesto de disco declarado (§10.1)."""
    return g.PRESUPUESTO_ESTADO_BYTES // tamano_bytes


# --------------------------------------------------------------------------- #
# El piso — la cuenta que §8.5 declara y nunca escribió
# --------------------------------------------------------------------------- #

def hashes_por_actualizacion(tamano_bytes: int = ENTRADA_BYTES) -> int:
    """Hashes que cuesta actualizar el árbol del conjunto activo una vez.

    **Sale del árbol, no de su altura**, y la diferencia costó un factor de tres. La Fase 5
    usó la altura —26— cuando el árbol todavía no existía; construido, resultó que 26 es el
    costo de `d = 1`, o sea **guardar todos los nodos internos**, que es la opción que el
    diseño descartó por costar 32 B por entrada. Con el corte que el diseño sí eligió son
    **83**: recomputar el subárbol de `2^d` hojas más subir por los niveles guardados.

    Se cuenta en hashes y no en pasos a propósito: es una cantidad exacta e independiente de
    la arquitectura, igual que `steps_per_verify`.
    """
    from estado.arbol import Arbol

    altura = max(entradas_que_entran(tamano_bytes).bit_length(), g.CORTE_ARBOL)
    return Arbol(altura=altura, corte=g.CORTE_ARBOL).hashes_por_actualizacion()


#: Pasos de VM por compresión SHA-256. **MEDIDO** el 21/8/2026, no estimado.
#:
#: Es el número que le faltaba al piso, y el que hizo falta ir a buscar: la primera
#: versión de este archivo lo estimó en 10.000 y lo declaró inofensivo *"porque la
#: verificación de firma lo domina"*. Era circular —sacar la firma del ciclo es
#: justamente la corrección— y con la firma afuera **este término es el único que queda**.
#:
#: Se midió como `steps_per_verify` en Test 2: un SHA-256 escrito a mano, compilado a
#: RV32IM (`predicado/vm/guest-sha/`) y corrido en la máquina de §6.6, restando dos
#: tandas para que el marco de la llamada no entre. El conteo es **exacto e independiente
#: de la arquitectura**: es una propiedad del programa, no del reloj.
#:
#: El estimado estaba 2× arriba, o sea en la dirección conservadora.
PASOS_POR_HASH = 4_898

#: Pasos de una verificación de firma en la máquina de §6.6. **Medido** (Test 2, Fase 4).
PASOS_POR_FIRMA = 3_339_364


def costo_del_ciclo_en_pasos(
    tamano_bytes: int = ENTRADA_BYTES, incluir_firma: bool = False
) -> int:
    """Lo que cuesta el ciclo crear + desalojar, en pasos de la máquina de §6.6.

    **`incluir_firma` está en `False` y ésa es una decisión, no un default.** §8.5 dice
    que el piso es *"el costo fijo del ciclo crear + desalojar"* y nombra *"verificar la
    firma más las dos actualizaciones del árbol"*. Pero **la firma ya la paga el fee ad
    valorem de §6.1**, como en cualquier transacción: cobrarla otra vez en el piso es
    cobrarla dos veces. Lo que la creación agrega por encima de una transacción común son
    las dos actualizaciones del árbol, y eso es lo que el piso tiene que cubrir.

    Se deja el otro camino computable porque es el que el paper describe, y la diferencia
    entre los dos es de un factor siete — lo bastante como para que convenga que se vea.
    """
    arbol = 2 * hashes_por_actualizacion(tamano_bytes) * PASOS_POR_HASH
    return arbol + (PASOS_POR_FIRMA if incluir_firma else 0)


def piso_en_epocas(
    tamano_bytes: int = ENTRADA_BYTES, ruleset=None, incluir_firma: bool = False
) -> float:
    """**El piso, derivado: cuántas épocas de guardado cuesta el ciclo crear + desalojar.**

    La cuenta iguala dos fracciones del mismo nodo, y las dos las declara Genesis:

    - **la del cómputo** — el ciclo consume `C` pasos, y el nodo dedica `f*` de su ritmo
      a verificar, así que gasta `C / (f* × R × duración_de_época)` del cómputo de una época;
    - **la del disco** — guardar la entrada una época ocupa `tamaño / presupuesto_de_estado`
      del disco durante esa época.

    El piso es el cociente: cuántas épocas de disco valen lo que el ciclo gasta de cómputo.

    > **La equivalencia entre cómputo y disco no agrega un número nuevo, pero sí un supuesto
    > que conviene decir en voz alta:** que las dos fracciones que Genesis declara —`f*` del
    > cómputo y el presupuesto de estado— están **igualmente ajustadas**, o sea que el nodo
    > satura las dos. Es lo que §6.1 construye a propósito al fijar las dos contra lo que
    > tiene un teléfono. Si una sobrara, la cuenta se corre hacia la otra.
    """
    ruleset = ruleset or g.RULESET_INICIAL
    ritmo = g.ritmo_declarado(ruleset.interno("paginas_vm"))
    pasos_por_epoca = (
        g.F_VERIFICACION_PPM
        * ritmo
        * epoca_segundos(ruleset.interno("tiempo_bloque_ms"))
        // 1_000_000
    )
    fraccion_computo = costo_del_ciclo_en_pasos(tamano_bytes, incluir_firma) / pasos_por_epoca
    fraccion_disco = tamano_bytes / g.PRESUPUESTO_ESTADO_BYTES
    return fraccion_computo / fraccion_disco


# --------------------------------------------------------------------------- #
# El depósito — lineal, y sin descuento por volumen
# --------------------------------------------------------------------------- #


def costo_en_segundos(tamano_bytes: int, epocas: int, ruleset=None) -> int:
    """Lo tasado es **tamaño × tiempo**: costo, no utilidad.

    Estrictamente lineal, y ésa es una condición y no una simplificación. **La tasa no baja
    por depositar más**: con una regla de potencia la vida crece más rápido que el depósito
    y el precio por año tiende a cero —cien pisos comprarían diez mil años—. Eso no abarata
    cualquier cosa: abarata **la única operación que compra permanencia en volumen**, que es
    llenar el estado de todos los nodos y no soltarlo nunca.

    Devuelve el costo en **byte-segundos declarados**, no en tokens. La conversión a tokens
    la hace la tasa, que es el problema abierto de §10.3.

    ## Por qué segundos y no épocas

    **Lo encontró integrar, y ninguna prueba de módulo podía verlo** (Fase 6, B3). El
    depósito se llevaba en byte-**épocas**, la época se cuenta en bloques, y
    `tiempo_bloque_ms` es un parámetro interno que una transición puede mover. Con eso, una
    conmutación que cambiara el tiempo de bloque hacía que **un depósito ya pagado comprara
    más o menos guardado del que compró**, sin que nadie lo tocara: I3 se cumplía —los bytes
    cruzaban idénticos— y lo que cambiaba era lo que valían.

    La salida es la de siempre en este diseño: **usar la cantidad declarada en vez de la
    derivada.** `tiempo_bloque_ms` no es una lectura de reloj —eso violaría I2— sino un
    parámetro que el ruleset declara, así que la cadena lo puede usar como factor de
    conversión igual que usa `R_declarado`. El depósito queda en byte-segundos y **lo que
    compró no depende de la generación en la que se lo gastó.**
    """
    if tamano_bytes <= 0 or epocas < 0:
        raise ValueError("tamaño positivo y épocas no negativas")
    ruleset = ruleset or g.RULESET_INICIAL
    return tamano_bytes * epocas * epoca_segundos(ruleset.interno("tiempo_bloque_ms"))


#: El tope de vida comprable, **en segundos y no en épocas**, por lo mismo que el depósito:
#: si estuviera en épocas, cambiar el tiempo de bloque cambiaría cuánto se puede prepagar,
#: y el tope existe justamente para que no se pueda apostar contra la tasa.
L_MAX_SEGUNDOS = g.L_MAX_EPOCAS * EPOCA_BLOQUES * 6_000 // 1_000


class VidaMaximaExcedida(ValueError):
    """Se quiso comprar más de `L_max` de una vez.

    **Es una viga, no una molestia.** Sin tope, un pago finito bastante grande compra
    siglos, que es exactamente lo que §8.5 existe para impedir; y con la tasa moviéndose,
    prepagar largo es apostar contra la regla y dejar el estado tomado mientras tanto.
    """


@dataclass
class Entrada:
    """Una entrada del conjunto activo. Forma fija: la elige el protocolo, no el creador.

    El saldo se lleva en **byte-segundos declarados** y no en tokens, por lo mismo que
    `costo_en_segundos`: lo que la cadena puede contar sin leer un precio es cuánto
    guardado se compró.
    """

    identificador: bytes
    dueno: bytes
    tamano_bytes: int = ENTRADA_BYTES
    #: Saldo prepago, en byte-segundos. Se consume quemándose.
    deposito: int = 0
    #: Última época en la que se cobró.
    epoca_cobrada: int = 0

    def segundos_restantes(self) -> int:
        """Guardado real que queda comprado. **No depende del ruleset**, y ahí está la
        corrección de B3: es lo mismo antes y después de una conmutación."""
        return self.deposito // self.tamano_bytes

    def epocas_restantes(self, ruleset=None) -> int:
        """**La cuenta regresiva de A6.** Pública, determinística y computable con
        anticipación — misma forma que la distancia al disparo de I2, y por la misma razón:
        un desalojo anunciado no genera presión por un arreglo coordinado a mano.

        Se expresa en épocas de la generación vigente, así que **sí cambia con el tiempo
        de bloque** — y tiene que cambiar: si los bloques tardan el doble, la misma vida
        real son la mitad de épocas. Lo que no cambia es la vida real.
        """
        ruleset = ruleset or g.RULESET_INICIAL
        por_epoca = epoca_segundos(ruleset.interno("tiempo_bloque_ms"))
        return self.segundos_restantes() // por_epoca

    def vencida_en(self, epoca: int, ruleset=None) -> bool:
        return epoca - self.epoca_cobrada >= self.epocas_restantes(ruleset)

    def recargar(self, epocas: int, ruleset=None) -> int:
        """Compra vida y devuelve lo que costó, en byte-segundos."""
        if epocas <= 0:
            raise ValueError("recargar compra épocas positivas")
        costo = costo_en_segundos(self.tamano_bytes, epocas, ruleset)
        if self.segundos_restantes() + costo // self.tamano_bytes > L_MAX_SEGUNDOS:
            raise VidaMaximaExcedida(
                f"quedarían {self.segundos_restantes() + costo // self.tamano_bytes} s "
                f"y L_max son {L_MAX_SEGUNDOS}"
            )
        self.deposito += costo
        return costo

    def cobrar(self, hasta_epoca: int, ruleset=None) -> int:
        """Consume el depósito hasta la época dada. Devuelve lo quemado.

        **No hay deuda y no hay descubierto**: si no alcanza, se quema lo que hay y la
        entrada queda vencida. El protocolo no tiene deudor al que embargar —el dueño es
        una clave— y rematar el objeto obligaría a la cadena a saber cuánto vale, que es
        exactamente lo que §7.6 prohíbe.
        """
        epocas = max(hasta_epoca - self.epoca_cobrada, 0)
        quemado = min(costo_en_segundos(self.tamano_bytes, epocas, ruleset), self.deposito)
        self.deposito -= quemado
        self.epoca_cobrada = hasta_epoca
        return quemado

    def canonico(self) -> bytes:
        """Lo que se guarda en el acumulador al desalojar, y lo que tiene que volver
        idéntico al revivir (A1)."""
        return (
            len(self.identificador).to_bytes(2, "little")
            + self.identificador
            + len(self.dueno).to_bytes(2, "little")
            + self.dueno
            + self.tamano_bytes.to_bytes(8, "little")
        )
