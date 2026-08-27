"""`TRANSITION_RULE`: la condición de disparo, evaluada contra el estado (I2).

Una regla es tres cosas y ninguna más:

- **`progreso(estado)`** — una cantidad **monótona no decreciente** leída del
  estado. Es lo que hace que el disparo se pueda ver venir;
- **`umbral(estado)`** — el valor de `progreso` que dispara. También sale del
  estado, y por eso una regla puede volver a armarse después de transicionar sin
  que nadie la rearme a mano;
- **`params_sucesor(estado, ruleset)`** — qué punto del espacio se selecciona.

**Por qué el umbral se mueve en vez de resetear el progreso.** Lo natural sería
medir *"cuánto se emitió desde la última transición"*, pero esa cantidad baja a
cero en cada transición y un progreso que retrocede viola I2 —el disparo dejaría
de verse venir justo después de cada conmutación—. Se hace al revés: el progreso
no baja nunca y el umbral sube leyendo los lock-ins que ya están on-chain.

**Y por qué el umbral se lee del estado y no del ruleset vigente.** Porque el
ruleset no es estado: si lo fuera, la conmutación lo cambiaría y I3 dejaría de
poder exigir que el estado cruce bit a bit idéntico. Lo que sí es estado es el
evento de lock-in, que se emite on-chain en su momento (§3). La regla cuenta esos.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from protocolo import genesis as g
from protocolo.generacion import Params, Ruleset
from protocolo.invariantes import MODO_APROXIMACION, MODO_CAPACIDAD


class ReglaTransicion(ABC):
    """Interfaz de un trigger. Las firmas son parte del contrato de I2.

    `progreso`, `umbral` y `dispara` reciben **el estado y nada más**: es el
    chequeo estructural que corre `invariantes.i2_trigger_solo_estado`, y existe
    porque un parámetro de más es la puerta por la que entra un oráculo.

    Y toda regla declara **cómo cumple la segunda mitad de I2** —*nadie elige el
    momento*—, porque hay dos formas y no son intercambiables:

    - `MODO_APROXIMACION`: la cadena publica cuántos bloques faltan al ritmo
      actual, y ningún actor mueve solo esa cuenta. **Obliga**: la regla no puede
      disparar desde el reposo (`i2_se_vio_venir`);
    - `MODO_CAPACIDAD`: no hay aproximación y no puede haberla. **Obliga**:
      declarar qué capacidad hay que ejercer para producir el hecho, y no
      publicar una cuenta regresiva inventada (`i2_trigger_discreto`).

    La declaración no es documentación: va on-chain con la distancia, y es lo
    único que le permite a un tercero auditar en Genesis si el que puede producir
    el hecho es el único ante quien la transición existe para reaccionar.
    """

    nombre: str = "regla"
    clase: str = g.CIRCULACION
    modo: str = MODO_APROXIMACION
    #: Sólo para `MODO_CAPACIDAD`: qué hay que poder hacer para producir el hecho.
    capacidad: str | None = None

    @abstractmethod
    def progreso(self, estado: Any) -> int:
        """Cantidad monótona no decreciente leída del estado."""

    @abstractmethod
    def umbral(self, estado: Any) -> int:
        """Valor de `progreso` a partir del cual la regla dispara."""

    def dispara(self, estado: Any) -> bool:
        return self.progreso(estado) >= self.umbral(estado)

    @abstractmethod
    def params_sucesor(self, estado: Any, ruleset: Ruleset) -> Params:
        """El punto del espacio que selecciona esta transición (I1)."""

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.nombre} clase={self.clase}>"


class ReglaEmisionAcumulada(ReglaTransicion):
    """Cada `paso` unidades emitidas, la emisión por bloque se parte al medio.

    Es el caso **fuerte** de C3.2: el trigger es un hecho del estado —cuánto se
    emitió— y no necesita que nadie delate nada ni que se calibre contra el mundo
    de afuera. Con ritmo constante, la distancia al disparo es exacta.

    Cumple I2 **por aproximación**: la emisión acumulada es agregada y nadie la
    mueve solo, así que nadie elige el momento.
    """

    clase = g.CIRCULACION
    modo = MODO_APROXIMACION

    def __init__(self, paso: int, nombre: str = "emision/mitad") -> None:
        if paso <= 0:
            raise ValueError("el paso de la regla de emisión es positivo")
        self.paso = paso
        self.nombre = nombre

    def progreso(self, estado: Any) -> int:
        return estado.emitido

    def umbral(self, estado: Any) -> int:
        return self.paso * (estado.lockins_de(self.nombre) + 1)

    def params_sucesor(self, estado: Any, ruleset: Ruleset) -> Params:
        internos = dict(ruleset.params.internos)
        internos["emision_por_bloque"] = ruleset.interno("emision_por_bloque") // 2
        return Params(
            generacion=ruleset.generacion + 1,
            internos=internos,
            formatos=ruleset.formatos,
        )


class ReglaCanarioCriptografico(ReglaTransicion):
    """Un canario gastado activa la primitiva de firma sucesora (§6.6).

    Es el caso **débil** de C3.2 y el que obligó a reescribir I2. La rotura de una
    primitiva **no tiene observable en el estado** —una firma forjada se ve igual
    que una válida—, así que no hay aproximación posible: mientras nadie gasta el
    canario el ritmo es cero y la distancia es *sin aproximación observable*.

    Bajo la letra vieja de I2 —*un trigger que no se puede ver venir no es
    admisible*— esta regla, que es la sección de vidriera del paper, no cumplía
    una de las cinco invariantes. Cumple la nueva **por capacidad demostrada**: el
    único camino para gastar el canario es romper la instancia debilitada, que es
    exactamente la capacidad ante la que la transición existe para reaccionar. Y
    esa instancia se **deriva** de una semilla pública (`g.CANARIO_SEMILLA`), así
    que nadie la generó y nadie retuvo su trampa — sin eso, *capacidad demostrada*
    sería *un secreto que alguien se guardó*.

    La transición es **aditiva** (I5): agrega el formato nuevo y no saca el
    viejo. Retirar `firma/ed25519` sería una transición posterior, separada por
    al menos una generación.
    """

    clase = g.CRIPTOGRAFICA
    modo = MODO_CAPACIDAD
    capacidad = (
        "romper la instancia debilitada derivada de la semilla pública del "
        "canario (§6.6); nadie la generó, así que nadie retiene su trampa"
    )

    def __init__(
        self,
        formato_sucesor: str = "firma/ml-dsa-44",
        nombre: str = "cripto/canario",
    ) -> None:
        self.formato_sucesor = formato_sucesor
        self.nombre = nombre

    def progreso(self, estado: Any) -> int:
        return estado.canarios_gastados

    def umbral(self, estado: Any) -> int:
        return estado.lockins_de(self.nombre) + 1

    def params_sucesor(self, estado: Any, ruleset: Ruleset) -> Params:
        return Params(
            generacion=ruleset.generacion + 1,
            internos=dict(ruleset.params.internos),
            formatos=ruleset.formatos | {self.formato_sucesor},
        )
