#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test 4 · variante: subsidio bloqueado hasta el fin del ciclo de emision.

Extension al test principal (`simulacion.py`), NO parte de el. El test se corrio
y cerro sobre el modelo del paper tal como estaba escrito; esto evalua una
modificacion propuesta despues.

La propuesta: el subsidio no se cobra liquido en el momento de la liquidacion.
Se acumula bloqueado y se libera al cerrar el ciclo de emision (el equivalente
al halving de Bitcoin, que el paper ya toma prestado como `curva_temporal`).

Por que es admisible: el desbloqueo es funcion de la altura del bloque, asi que
se computa desde el estado (I2) y no juzga si el trabajo fue real (regla 1 de
§7.1). Es una condicion sobre CUANDO se cobra, no sobre QUE se hizo.

--------------------------------------------------------------------------------
La pregunta que decide todo

Bloquear multiplica el valor presente del subsidio por un factor de descuento
`delta = 1/(1+rho)^L`. Si el autotratante y el operador honesto descuentan
IGUAL, las dos condiciones del test se escalan por el mismo numero y la ventana
no se mueve ni un punto:

    no farmear   <=>  delta_f * k <= phi_ef      ->  k <= phi_ef / delta_f
    ser goloso   <=>  delta_h * k >= piso        ->  k >= piso  / delta_h

    ventana no vacia  <=>  piso <= phi_ef * (delta_h / delta_f)

O sea: **todo el poder de la idea esta en el cociente delta_h/delta_f**, que es
cuanto mas caro le sale al autotratante esperar que al operador honesto.

Y hay una razon estructural para que ese cociente sea > 1, que es la parte buena
de la propuesta: el operador honesto cobra del cliente real y esa plata NO esta
bloqueada, asi que el subsidio es un extra marginal sobre un negocio con caja.
El autotratante no tiene ingreso externo: su unica entrada es el subsidio
bloqueado, y mientras tanto tiene que financiar de su bolsillo la quema de fees
durante todo el ciclo. Esta 100% expuesto, sin diversificar y sin liquidez.

Eso es una asimetria real, y es la primera que aparece que no necesita que el
protocolo juzgue el trabajo.
"""

# --------------------------------------------------------------- primitivas


def delta(rho, L):
    """Factor de descuento por bloquear L anios a tasa rho."""
    return 1.0 / (1.0 + rho) ** L


def piso(sigma):
    return sigma / (1.0 - sigma)


def apalancamiento(rho_f, rho_h, L):
    """delta_h / delta_f: cuantas veces se ensancha el techo de k."""
    return delta(rho_h, L) / delta(rho_f, L)


# --------------------------------------------------------------- tabla A


def tabla_a():
    print("=" * 78)
    print("TABLA A - Cuanto ensancha la ventana, segun ciclo y spread de tasas")
    print("=" * 78)
    print()
    print("apalancamiento = ((1+rho_f)/(1+rho_h))^L")
    print("rho_h = 15% (operador con negocio real y caja)")
    print()
    print(f"{'rho_f':>8} " + "".join(f"{f'L={L}a':>10}" for L in [1, 2, 4, 8]))
    print("-" * 78)
    rho_h = 0.15
    for rho_f in [0.25, 0.40, 0.60, 0.85, 1.20]:
        fila = "".join(f"{apalancamiento(rho_f, rho_h, L):>9.1f}x"
                       for L in [1, 2, 4, 8])
        print(f"{rho_f:>7.0%} " + fila)
    print()


# --------------------------------------------------------------- tabla B


def tabla_b():
    print("=" * 78)
    print("TABLA B - Apalancamiento NECESARIO para abrir la ventana")
    print("=" * 78)
    print()
    print("necesario = piso(sigma) / phi_efectivo")
    print()
    print(f"{'sigma':>7} " + "".join(f"{f'phi_ef={p}':>16}"
                                     for p in ["0,15%", "0,30%", "1,0%"]))
    print("-" * 78)
    for sg in [0.01, 0.05, 0.10]:
        fila = "".join(f"{piso(sg)/pe:>15.0f}x" for pe in [0.0015, 0.003, 0.010])
        print(f"{sg:>7.0%} " + fila)
    print()
    print("Comparar contra la tabla A: 4 anios con spread 15%/85% da ~6,4x.")
    print()


# --------------------------------------------------------------- tabla C


def tabla_c():
    print("=" * 78)
    print("TABLA C - Veredicto por celda (ciclo de 4 anios, rho_h=15%)")
    print("=" * 78)
    print()
    L, rho_h = 4, 0.15
    print(f"{'phi_ef':>8} {'rho_f':>7} {'apal.':>7} {'techo k':>10} "
          f"{'subsidio/ingreso':>18} {'sigma=1%':>9} {'sigma=5%':>9}")
    print("-" * 78)
    for phi_ef in [0.0015, 0.003, 0.010]:
        for rho_f in [0.40, 0.85, 1.20]:
            ap = apalancamiento(rho_f, rho_h, L)
            techo = phi_ef * ap
            # lo que el operador honesto percibe en valor presente
            percibido = delta(rho_h, L) * techo
            sig = percibido / (1 + percibido)
            m1 = "SI" if piso(0.01) <= techo else "."
            m5 = "SI" if piso(0.05) <= techo else "."
            print(f"{phi_ef:>8.4f} {rho_f:>7.0%} {ap:>6.1f}x {techo:>10.5f} "
                  f"{sig:>17.2%} {m1:>9} {m5:>9}")
    print()
    print("'subsidio/ingreso' ya esta descontado: es lo que el operador honesto")
    print("percibe hoy por un subsidio que cobra recien al cierre del ciclo.")
    print()


# --------------------------------------------------------------- tabla D


def tabla_d():
    """El efecto que la propuesta introduce y que no estaba antes."""
    print("=" * 78)
    print("TABLA D - El diente de sierra: el lockup no dura lo mismo todo el ciclo")
    print("=" * 78)
    print()
    print("El desbloqueo es en una fecha fija (fin de ciclo), asi que el que")
    print("liquida trabajo al principio del ciclo espera 4 anios y el que")
    print("liquida al final espera semanas. El descuento del autotratante")
    print("colapsa cerca del cierre.")
    print()
    L_ciclo, rho_f, rho_h = 4.0, 0.85, 0.15
    phi_ef = 0.0015
    print(f"ciclo = {L_ciclo:.0f} anios · rho_f = {rho_f:.0%} · phi_ef = {phi_ef}")
    print()
    print(f"{'momento del ciclo':>20} {'espera':>9} {'apal.':>8} {'techo k':>10}")
    print("-" * 78)
    for frac in [0.0, 0.25, 0.50, 0.75, 0.90, 0.98]:
        espera = L_ciclo * (1 - frac)
        ap = apalancamiento(rho_f, rho_h, espera)
        print(f"{frac:>19.0%} {espera:>8.2f}a {ap:>7.1f}x {phi_ef*ap:>10.5f}")
    print()
    print("El techo cae ~6x entre el inicio y el cierre del ciclo. O sea que")
    print("el farmeo no desaparece: se CONCENTRA al final de cada ciclo,")
    print("cuando la espera es corta. Y esa fecha es publica y determinista.")
    print()


if __name__ == "__main__":
    tabla_a()
    tabla_b()
    tabla_c()
    tabla_d()
