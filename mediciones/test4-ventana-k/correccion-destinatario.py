#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test 4 · correccion: la emision va a los nodos PoD, no al nodo de computo.

Por que existe este archivo. `simulacion.py` midio la significancia del subsidio
contra la facturacion del nodo que hace el trabajo. Eso contradice §6.1, que dice
textual que el ingreso del nodo de computo es "el pago del pedido que ejecutaron,
no la emision del protocolo". El paper nunca dice quien SI cobra E(t); por
descarte, los nodos PoD.

Esto rehace el test con el destinatario corregido.

--------------------------------------------------------------------------------
Que cambia y que no

NO cambia el techo. El autotratante corre su propio nodo PoD para capturar la
emision sobre el trabajo que el mismo fabrica — y §6.1 hace esa entrada barata a
proposito ("un nodo que entra en un telefono"). Asi que la integracion vertical
deja de ser el peor caso y pasa a ser el caso normal: s = 1, techo k <= beta*phi.

SI cambia el denominador de la significancia: un nodo PoD cuesta un telefono, no
una granja de GPU.

--------------------------------------------------------------------------------
Contabilidad por unidad de trabajo liquidado W

    fee cobrado          phi * W
      quemado            beta * phi * W
      a nodos PoD        (1 - beta) * phi * W
    emision creada       k * W          -> a nodos PoD

    emision neta       = (k - beta*phi) * W
    ingreso PoD total  = (1 - beta)*phi*W + k*W

El autotratante gana k*W y paga beta*phi*W (recupera el resto via su propio PoD).
"""

# --------------------------------------------------------------- tabla A


def tabla_a():
    print("=" * 78)
    print("TABLA A - Contabilidad por unidad de trabajo, alrededor de k*")
    print("=" * 78)
    print()
    phi, beta = 0.003, 1.0
    k_est = beta * phi
    print(f"phi = {phi:.1%} · beta = {beta:.2f}  ->  k* = beta*phi = {k_est:.5f}")
    print()
    print(f"{'k':>9} {'emision':>10} {'quema':>10} {'neto':>11} "
          f"{'ingreso PoD':>13} {'farmeo':>10}")
    print("-" * 78)
    for k in [0.0, 0.001, 0.002, k_est, 0.004, 0.006, 0.010]:
        emision = k
        quema = beta * phi
        neto = emision - quema
        ing_pod = (1 - beta) * phi + k
        farm = k - beta * phi
        marca = "rentable" if farm > 1e-12 else ("nulo" if abs(farm) < 1e-12 else "no")
        print(f"{k:>9.5f} {emision:>10.5f} {quema:>10.5f} {neto:>+11.5f} "
              f"{ing_pod:>13.5f} {marca:>10}")
    print()
    print("Las columnas 'neto' y 'farmeo' son la MISMA columna:")
    print("   emision neta = (k - beta*phi)*W = ganancia del autotratante")
    print()


# --------------------------------------------------------------- tabla B


def tabla_b():
    print("=" * 78)
    print("TABLA B - El teorema, en varias combinaciones")
    print("=" * 78)
    print()
    print("emision neta > 0   <=>   autotrato rentable")
    print("Es una identidad, no una coincidencia numerica: las dos expresiones")
    print("son (k - beta*phi)*W.")
    print()
    print(f"{'phi':>7} {'beta':>6} {'k':>8} {'emision neta':>14} "
          f"{'autotrato':>12} {'coinciden':>11}")
    print("-" * 78)
    casos = [(0.003, 1.00, 0.001), (0.003, 1.00, 0.003), (0.003, 1.00, 0.008),
             (0.010, 0.50, 0.003), (0.010, 0.50, 0.005), (0.010, 0.50, 0.020),
             (0.001, 0.25, 0.0002), (0.001, 0.25, 0.00025), (0.001, 0.25, 0.002)]
    for phi, beta, k in casos:
        neto = k - beta * phi
        farm = k - beta * phi
        ok = "si" if (neto > 0) == (farm > 0) else "NO"
        print(f"{phi:>7.1%} {beta:>6.2f} {k:>8.5f} {neto:>+14.5f} "
              f"{farm:>+12.5f} {ok:>11}")
    print()


# --------------------------------------------------------------- tabla C


def tabla_c():
    print("=" * 78)
    print("TABLA C - En k*, cuantos nodos PoD banca la red")
    print("=" * 78)
    print()
    print("En k* el ingreso total de los nodos PoD es exactamente phi*W:")
    print("   (1-beta)*phi*W  de fee directo  +  beta*phi*W  de emision")
    print("Con entrada libre eso se reparte hasta beneficio cero, asi que el")
    print("numero de nodos que la red sostiene es  phi*W_$ / costo_por_nodo.")
    print()
    print(f"{'W anual (US$)':>16} " + "".join(f"{f'phi={p:.1%}':>14}"
                                             for p in [0.001, 0.003, 0.010]))
    print(f"{'':>16} " + "".join(f"{'nodos':>14}" for _ in range(3)))
    print("-" * 78)
    c_nodo = 100.0     # telefono amortizado + electricidad + datos, por anio
    for W in [1e6, 1e7, 1e8, 1e9, 1e10]:
        fila = "".join(f"{phi*W/c_nodo:>13,.0f} " for phi in [0.001, 0.003, 0.010])
        print(f"{W:>16,.0f} " + fila)
    print()
    print(f"costo por nodo PoD asumido: US$ {c_nodo:.0f}/anio")
    print("(telefono de US$200 amortizado a 3 anios + electricidad + datos)")
    print()
    print("Referencia: Ethereum tiene del orden de 6.000-10.000 nodos de ejecucion.")
    print()


# --------------------------------------------------------------- tabla D


def tabla_d():
    print("=" * 78)
    print("TABLA D - El arranque en frio")
    print("=" * 78)
    print()
    print("W(t) se mide en tokens pagados. §7.1: 'no hay preminado, ni tesoreria,")
    print("ni asignacion de equipo. Toda unidad que existe nacio contra trabajo")
    print("entregado.'")
    print()
    print(f"{'periodo':>9} {'tokens en circulacion':>24} {'W posible':>12} "
          f"{'E = min(curva, k*W)':>21}")
    print("-" * 78)
    supply = 0.0
    k, curva = 0.003, 100_000.0
    for t in range(1, 6):
        W = supply          # no se puede pagar mas de lo que existe
        E = min(curva, k * W)
        print(f"{t:>9} {supply:>24,.2f} {W:>12,.2f} {E:>21,.2f}")
        supply += E
    print()
    print("El lazo es cerrado y arranca en cero. Sin una emision inicial que NO")
    print("dependa de W, el sistema no puede emitir la primera unidad — y esa")
    print("emision inicial es exactamente lo que §7.1 prohibe.")
    print()


if __name__ == "__main__":
    tabla_a()
    tabla_b()
    tabla_c()
    tabla_d()
