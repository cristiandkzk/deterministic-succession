#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test 4 · La ventana de `k`.

Lo que pide §11 del paper: simular si existe algun `k > 0` donde auto-pagarse no
sea rentable y el subsidio todavia sea significativo para un operador honesto.

    python simulacion.py

Modelo, tomado literal de §7.1 y §9:

    E(t) = min( curva_temporal(t),  k * W(t) )

`W(t)` es el trabajo liquidado y verificado en el periodo, medido en tokens
pagados (es lo unico que el protocolo puede contar sin juzgar utilidad, §7.1
regla 1). Entonces `k` es adimensional: subsidio por token de trabajo pagado.

El subsidio se reparte a prorrata del trabajo aportado, asi que la tasa efectiva
por token es

    r = E / W = min( curva / W,  k )

--------------------------------------------------------------------------------
El autotratante (§9: "un agente que se paga a si mismo")

Cicla W tokens: los deposita en escrow y los cobra el mismo. El pago neto es
cero. Sus costos por ciclo:

  - fee del protocolo, `phi` * W, del cual se quema una fraccion `beta` y el
    resto va a los nodos PoD (§6.1);
  - si ademas corre nodos PoD, recupera una fraccion `s` de esa parte no
    quemada. Vertical completo = s=1;
  - el trabajo en si: elige el predicado mas barato que §6.2 admita, y su costo
    es fijo por liquidacion, no proporcional a W. Escalando W lo diluye a cero.

    costo_ciclo = phi * (1 - s*(1-beta)) * W  +  epsilon
    ganancia    = r * W

Como los dos lados escalan con W, la rentabilidad es invariante de escala: no
depende de cuanto capital tenga, solo de comparar tasas.

--------------------------------------------------------------------------------
El operador honesto

Cobra W de un cliente real, gasta c*W en computo real, paga el mismo fee, y
recibe el mismo subsidio r*W. Recibe `r` exactamente igual que el autotratante:
el protocolo no puede distinguirlos, por diseno (§7.1 regla 1).

"Significativo" se mide como fraccion del ingreso bruto del operador:

    significancia = r / (1 + r)

y se compara contra un umbral `sigma`. sigma=0.10 quiere decir "el subsidio es
al menos el 10% de lo que factura".
"""

import itertools

# ---------------------------------------------------------------- primitivas


def costo_autotrato(phi, beta, s):
    """Costo marginal de fabricar un token de trabajo pagandose a uno mismo.

    epsilon queda fuera: es fijo por liquidacion y el atacante lo diluye
    subiendo W. Incluirlo solo haria el resultado mas optimista de lo debido.
    """
    return phi * (1.0 - s * (1.0 - beta))


def equilibrio(k, phi, beta, s, W_h, curva):
    """Equilibrio de entrada libre de autotratantes en un periodo.

    Devuelve (W_f, r, captura) donde `captura` es la fraccion de la emision que
    termina en manos de los autotratantes.
    """
    cf = costo_autotrato(phi, beta, s)

    # sin farmeo: la tasa es k, salvo que la curva ya este mordiendo
    r_sin = min(curva / W_h, k) if W_h > 0 else k

    if k <= cf:
        # fabricar trabajo cuesta mas que lo que paga: nadie entra
        return 0.0, r_sin, 0.0

    # entran hasta que la dilucion lleva la tasa a su costo
    W_total = curva / cf
    W_f = max(0.0, W_total - W_h)
    r = cf if W_f > 0 else r_sin
    captura = W_f / (W_h + W_f) if (W_h + W_f) > 0 else 0.0
    return W_f, r, captura


def significancia(r):
    """Subsidio como fraccion del ingreso bruto del operador honesto."""
    return r / (1.0 + r)


# ---------------------------------------------------------------- tabla A


def tabla_a():
    """La ventana de k, en forma cerrada.

    Sin farmeo hace falta  k <= costo_autotrato.
    Significancia >= sigma hace falta  k >= sigma/(1-sigma).
    La ventana existe si y solo si el techo alcanza al piso.
    """
    print("=" * 78)
    print("TABLA A · La ventana [piso de adopcion, techo de seguridad]")
    print("=" * 78)
    print()
    print("Techo de seguridad = costo marginal de auto-pagarse = phi*(1-s*(1-beta))")
    print("Piso de adopcion   = k tal que el subsidio sea sigma del ingreso bruto")
    print()

    sigmas = [0.01, 0.05, 0.10, 0.20]
    print("piso de adopcion segun cuan goloso tenga que ser el subsidio:")
    for sg in sigmas:
        print(f"   sigma = {sg:>5.0%}  ->  k >= {sg/(1-sg):.4f}")
    print()

    phis = [0.001, 0.003, 0.01, 0.03, 0.10]
    betas = [0.25, 0.50, 1.00]
    ss = [0.0, 1.0]

    print(f"{'phi':>7} {'beta':>6} {'s':>4} {'techo k':>10}   ventana no vacia para sigma =")
    print(f"{'':>7} {'':>6} {'':>4} {'':>10}   " + "  ".join(f"{sg:>5.0%}" for sg in sigmas))
    print("-" * 78)
    for phi, beta, s in itertools.product(phis, betas, ss):
        techo = costo_autotrato(phi, beta, s)
        marcas = []
        for sg in sigmas:
            piso = sg / (1 - sg)
            marcas.append(" SI  " if piso <= techo else "  .  ")
        print(f"{phi:>7.1%} {beta:>6.2f} {s:>4.0f} {techo:>10.5f}   " + " ".join(marcas))
    print()
    print("'.' = ventana vacia: no existe k que cumpla las dos condiciones.")
    print()


# ---------------------------------------------------------------- tabla B


def tabla_b():
    """Que pasa con el subsidio del operador honesto cuando k sube."""
    print("=" * 78)
    print("TABLA B · Barrido de k con fee realista (phi=0,3%, beta=0,5)")
    print("=" * 78)
    print()

    phi, beta = 0.003, 0.5
    W_h, curva = 1_000_000.0, 100_000.0   # cadena joven: la curva no muerde

    print(f"trabajo organico W_h = {W_h:,.0f} tokens/periodo")
    print(f"curva temporal       = {curva:,.0f} tokens/periodo")
    print()
    print(f"{'k':>8} {'s':>4} {'W_f farmeado':>16} {'r efectiva':>12} "
          f"{'captura':>9} {'signif.':>9}")
    print("-" * 78)

    for k in [0.0005, 0.001, 0.0015, 0.003, 0.01, 0.05, 0.10, 0.25]:
        for s in [0.0, 1.0]:
            W_f, r, cap = equilibrio(k, phi, beta, s, W_h, curva)
            print(f"{k:>8.4f} {s:>4.0f} {W_f:>16,.0f} {r:>12.5f} "
                  f"{cap:>8.1%} {significancia(r):>8.2%}")
    print()


# ---------------------------------------------------------------- tabla C


def tabla_c():
    """Dinamica: demanda organica que crece, con y sin autotratantes."""
    print("=" * 78)
    print("TABLA C · Diez periodos, demanda organica creciente")
    print("=" * 78)
    print()

    phi, beta, s = 0.003, 0.5, 1.0
    k = 0.10                     # elegido para que el subsidio sea "goloso"
    curva = 100_000.0
    cf = costo_autotrato(phi, beta, s)

    print(f"k = {k:.2f} (subsidio goloso: {significancia(k):.1%} del ingreso bruto)")
    print(f"costo de auto-pagarse = {cf:.5f}  ->  k lo supera por {k/cf:.0f}x")
    print()
    print(f"{'periodo':>8} {'W_h organico':>14} {'W_f farmeado':>16} "
          f"{'r':>9} {'captura':>9} {'signif.':>9}")
    print("-" * 78)

    W_h = 10_000.0
    for t in range(1, 11):
        W_f, r, cap = equilibrio(k, phi, beta, s, W_h, curva)
        print(f"{t:>8} {W_h:>14,.0f} {W_f:>16,.0f} {r:>9.5f} "
              f"{cap:>8.1%} {significancia(r):>8.2%}")
        W_h *= 1.6

    print()
    print("La tasa efectiva r queda clavada en el costo de auto-pagarse,")
    print("no en k. El valor de k dejo de intervenir en el resultado.")
    print()


# ---------------------------------------------------------------- tabla D


def tabla_d():
    """Cuanto fee haria falta para que la ventana exista."""
    print("=" * 78)
    print("TABLA D · El fee que haria falta para abrir la ventana")
    print("=" * 78)
    print()
    print("Invirtiendo la condicion: para que exista k con significancia sigma,")
    print("el fee tiene que cumplir  phi >= sigma/((1-sigma)*(1-s*(1-beta))).")
    print()
    print(f"{'sigma':>7} {'s=0':>12} {'s=1, beta=1':>14} {'s=1, beta=0,5':>16} "
          f"{'s=1, beta=0,25':>16}")
    print("-" * 78)
    for sg in [0.01, 0.05, 0.10, 0.20]:
        piso = sg / (1 - sg)
        fila = [piso / (1 - 0 * (1 - 1.0))]           # s=0 -> factor 1
        for beta in [1.0, 0.5, 0.25]:
            fila.append(piso / (1 - 1.0 * (1 - beta)))
        print(f"{sg:>7.0%} " + " ".join(f"{v:>13.1%}" for v in fila))
    print()
    print("Referencia: §6.1 pide 'un fee chico'. Stripe cobra 2,9%.")
    print()


# ---------------------------------------------------------------- tabla E


def tabla_e():
    """El piso de costo real que habria que imponerle a fabricar trabajo.

    Unica escapatoria estructural: que producir un token de trabajo cueste algo
    real e irreducible `gamma` (fraccion de W), ademas del fee. El techo pasa a
    ser  phi_eff + gamma.  Pero imponer un piso de costo es exactamente decidir
    que cuenta como trabajo, que es lo que §7.1 regla 1 prohibe.
    """
    print("=" * 78)
    print("TABLA E - Cuanto habria que forzar la regla 1 de §7.1")
    print("=" * 78)
    print()
    print("gamma = costo real irreducible por token de trabajo fabricado,")
    print("        que el protocolo tendria que garantizar de algun modo.")
    print()
    print(f"{'sigma':>7} {'phi':>7} {'beta':>6} {'s':>4} {'techo actual':>14} "
          f"{'gamma necesario':>17}")
    print("-" * 78)
    for sg in [0.01, 0.05, 0.10]:
        piso = sg / (1 - sg)
        for phi, beta, s in [(0.003, 0.5, 1.0), (0.003, 1.0, 0.0),
                             (0.010, 1.0, 0.0)]:
            techo = costo_autotrato(phi, beta, s)
            gamma = max(0.0, piso - techo)
            print(f"{sg:>7.0%} {phi:>7.1%} {beta:>6.2f} {s:>4.0f} "
                  f"{techo:>14.5f} {gamma:>16.2%}")
    print()
    print("Leer asi: para que el subsidio sea el 10% del ingreso del operador,")
    print("el protocolo tiene que garantizar que fabricar trabajo cueste ~11%")
    print("de su valor en recursos reales. Eso es una definicion de trabajo.")
    print()


# ---------------------------------------------------------------- tabla F


def tabla_f():
    """Intensidad del bootstrap, contra el ejemplo que §9 dice seguir."""
    print("=" * 78)
    print("TABLA F - Intensidad del subsidio vs. el bootstrap de Bitcoin")
    print("=" * 78)
    print()
    print("§9: 'el bootstrap previsto es el de Bitcoin'.")
    print()
    print("En Bitcoin 2009-2012 el subsidio fue practicamente el 100% del")
    print("ingreso del minero: los fees eran ruido. Aca el techo del subsidio")
    print("como fraccion del ingreso del operador es el propio fee efectivo.")
    print()
    print(f"{'phi':>7} {'beta':>6} {'s':>4} {'k* optimo':>11} "
          f"{'subsidio/ingreso':>18} {'vs. Bitcoin':>13}")
    print("-" * 78)
    for phi, beta, s in [(0.001, 0.5, 1.0), (0.003, 0.5, 1.0),
                         (0.003, 1.0, 0.0), (0.010, 1.0, 0.0),
                         (0.030, 1.0, 0.0)]:
        k_opt = costo_autotrato(phi, beta, s)
        sig = significancia(k_opt)
        print(f"{phi:>7.1%} {beta:>6.2f} {s:>4.0f} {k_opt:>11.5f} "
              f"{sig:>17.2%} {1.0/sig:>12.0f}x")
    print()
    print("Ultima columna: cuantas veces mas intenso fue el incentivo que")
    print("§9 toma como modelo.")
    print()


if __name__ == "__main__":
    tabla_a()
    tabla_b()
    tabla_c()
    tabla_d()
    tabla_e()
    tabla_f()
