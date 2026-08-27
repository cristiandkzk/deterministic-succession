"""El linaje generacional: `H0_B = H( H0_A ‖ state_trigger ‖ params_nuevos )` (I4).

`H0_B` **no es el génesis de una cadena nueva**: es un marcador de checkpoint
generacional dentro de la misma cadena. Genesis A no conoce el hash de B —no
puede, porque B incorpora información que todavía no existe— pero conoce
determinísticamente cómo se calculará, y eso alcanza para que el linaje entero
sea verificable con un hash desde cualquier generación hacia atrás.

Los tres insumos no son decorativos y conviene saber qué aporta cada uno:

- `H0_A` encadena. Sin él, cada generación sería un punto suelto.
- `state_trigger` ata la transición **al estado que la disparó**. Por eso el
  checkpoint se computa en el lock-in y no en el disparo: comprometer un estado
  que una reorganización todavía puede sacar de la cadena dejaría el checkpoint
  apuntando a algo que no pasó (§3).
- `params_nuevos` ata la transición al ruleset que efectivamente se activó. Es lo
  que hace verificable que la cadena que no conmutó *se desvió* (§5): no tiene
  checkpoint válido, y eso no es una opinión.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from protocolo.generacion import Params
from protocolo.serializacion import corto, huella


def calcular_h0(h0_ancestro: bytes, state_trigger: bytes, params: Params) -> bytes:
    """`H( H0_A ‖ state_trigger ‖ params_nuevos )`.

    La concatenación del paper se realiza como un mapa de tres claves fijas: la
    codificación canónica es autodelimitada, así que no hay forma de que un
    corrimiento entre los tres insumos produzca la misma imagen.
    """
    return huella(
        {
            "h0_ancestro": h0_ancestro,
            "state_trigger": state_trigger,
            "params": params.canonico(),
        },
        dominio="linaje/checkpoint",
    )


def verificar(
    h0_b: bytes, h0_a: bytes, state_trigger: bytes, params: Params
) -> bool:
    """`Verify( H0_B, H0_A, state_trigger, params_nuevos )` del §3."""
    return h0_b == calcular_h0(h0_a, state_trigger, params)


@dataclass(frozen=True)
class Checkpoint:
    """Lo que el lock-in emite on-chain, completo.

    Todo lo que un integrador necesita saber está acá, `Δ` bloques antes de la
    activación, sin que nadie tenga que anunciarlo ni pedir permiso para leerlo.
    """

    generacion: int
    h0: bytes
    h0_ancestro: bytes
    state_trigger: bytes
    params: Params
    #: Qué regla disparó. Es metadato del evento y **no entra en `h0`**: el hash
    #: del §3 commitea ancestro, estado y parámetros, y nada más. Está acá porque
    #: el evento on-chain se lee, y *"quién disparó"* es lo primero que se pregunta.
    regla: str
    clase: str
    altura_disparo: int
    altura_lockin: int
    altura_activacion: int

    def canonico(self) -> dict:
        return {
            "generacion": self.generacion,
            "h0": self.h0,
            "h0_ancestro": self.h0_ancestro,
            "state_trigger": self.state_trigger,
            "params": self.params.canonico(),
            "regla": self.regla,
            "clase": self.clase,
            "altura_disparo": self.altura_disparo,
            "altura_lockin": self.altura_lockin,
            "altura_activacion": self.altura_activacion,
        }

    def es_valido(self) -> bool:
        return verificar(self.h0, self.h0_ancestro, self.state_trigger, self.params)


def motivo_linaje_invalido(
    checkpoints: Sequence[Checkpoint], h0_raiz: bytes
) -> str | None:
    """`None` si el linaje completo verifica; si no, dónde y por qué se corta.

    Verifica las tres cosas que hacen al linaje, y no sólo la del hash: que cada
    checkpoint sea el hash correcto de sus insumos, que su ancestro sea el
    checkpoint anterior —no cualquiera— y que las generaciones sean consecutivas
    desde la 0. Un linaje con un salto de generación verifica hash por hash y aun
    así miente sobre su historia.
    """
    esperado_ancestro = h0_raiz
    esperada_generacion = 1

    for indice, punto in enumerate(checkpoints):
        if punto.h0_ancestro != esperado_ancestro:
            return (
                f"checkpoint #{indice} (generación {punto.generacion}) commitea a "
                f"{corto(punto.h0_ancestro)}..., y su ancestro real es "
                f"{corto(esperado_ancestro)}..."
            )
        if punto.generacion != esperada_generacion:
            return (
                f"checkpoint #{indice} dice ser la generación {punto.generacion} "
                f"y le toca la {esperada_generacion}"
            )
        if not punto.es_valido():
            return (
                f"checkpoint #{indice} (generación {punto.generacion}): el hash no "
                "se deriva de (ancestro || state_trigger || params)"
            )
        esperado_ancestro = punto.h0
        esperada_generacion += 1

    return None


def verificar_linaje(checkpoints: Sequence[Checkpoint], h0_raiz: bytes) -> bool:
    return motivo_linaje_invalido(checkpoints, h0_raiz) is None
