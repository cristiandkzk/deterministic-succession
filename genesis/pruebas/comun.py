"""Andamios compartidos por las pruebas. Nada de esto es protocolo."""

from __future__ import annotations

from nodo.pod import NodoPoD
from protocolo import genesis as g
from sucesion.regla import ReglaCanarioCriptografico, ReglaEmisionAcumulada

#: La transacción que gasta el canario de §6.6.
GASTAR_CANARIO = ("gastar_canario",)


def nodo_canario(**opciones) -> NodoPoD:
    """Un nodo con la regla criptográfica: `Δ` corto, disparo por un hecho puntual."""
    return NodoPoD(reglas=[ReglaCanarioCriptografico()], **opciones)


def nodo_emision(paso: int = 100_000, **opciones) -> NodoPoD:
    """Un nodo con la regla de circulación: `Δ` largo, disparo por acumulación."""
    return NodoPoD(reglas=[ReglaEmisionAcumulada(paso=paso)], **opciones)


def alturas_de(nodo: NodoPoD) -> list[tuple[int, int, int]]:
    """(disparo, lock-in, activación) de cada checkpoint, para comparar cronogramas."""
    return [
        (c.altura_disparo, c.altura_lockin, c.altura_activacion)
        for c in nodo.cronograma.checkpoints
    ]


def correr_hasta_activar(nodo: NodoPoD, transaccion_en: dict[int, tuple] = {}) -> None:
    """Produce bloques hasta que la primera transición activa.

    `transaccion_en` mapea altura → transacción, para gatillar el canario en un
    bloque elegido. Se corta cuando ya conmutó, así ninguna prueba depende de un
    número de bloques puesto a ojo.
    """
    limite = 4 * (g.VENTANA_FINALIDAD + max(g.DELTA_POR_CLASE.values()) + 8)
    while not nodo.conmutaciones and nodo.altura < limite:
        altura = nodo.altura + 1
        txs = [transaccion_en[altura]] if altura in transaccion_en else []
        nodo.producir_bloque(txs)
    if not nodo.conmutaciones:
        raise AssertionError(f"no conmutó en {limite} bloques: {nodo.resumen()}")
