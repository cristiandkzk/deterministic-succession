#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
El ataque de Alice, contra el esquema de fees redisenado.

    python ataque-alice.py

Escenario, tal como se planteo: Alice controla nodos, se manda dinero entre sus
propias cuentas, y trata de reciclar la fee para crear emision neta a su favor.

Se prueba contra las dos mitades del diseno nuevo, porque no se comportan igual:

  A. el CIRCUITO DE FEES        demanda -> fee -> proveedores / quema / reserva
  B. la BANDA DE SUPPLY         S < piso -> emision gradual

--------------------------------------------------------------------------------
Contabilidad de un ciclo de Alice, moviendo V entre cuentas propias

    paga            phi * V
    recupera        rho_prov * phi * V      (ella es la proveedora del trabajo)
    recupera        sigma_A * rho_res * phi * V   (su tajada de lo que reparte
                                                   la reserva; sigma_A es su
                                                   participacion en los nodos)
    pierde          rho_burn * phi * V      (la quema no vuelve NUNCA)

    neto = -phi * V * (1 - rho_prov - sigma_A * rho_res)

sigma_A es lo unico que depende de cuantos nodos tenga. Y solo multiplica a
rho_res. La quema queda afuera de su alcance pase lo que pase.
"""

# ------------------------------------------------------------ parametros base

PHI = 0.003                 # fee como fraccion del valor movido
PROV, BURN, RES = 0.70, 0.20, 0.10
assert abs(PROV + BURN + RES - 1.0) < 1e-12


def neto_por_ciclo(sigma_A, phi=PHI, prov=PROV, res=RES):
    """Resultado de Alice por unidad de valor ciclado. Negativo = pierde."""
    return -phi * (1.0 - prov - sigma_A * res)


# ------------------------------------------------------------ tabla A


def tabla_a():
    print("=" * 78)
    print("TABLA A - Alice cicla dinero entre sus propias cuentas")
    print("=" * 78)
    print()
    print(f"fee {PHI:.1%} · reparto {PROV:.0%} proveedores / {BURN:.0%} quema / "
          f"{RES:.0%} reserva")
    print()
    print("Alice arranca con 1.000.000 y cicla el 100% de su saldo cada periodo.")
    print()
    print(f"{'nodos de Alice':>18} {'sigma_A':>9} {'neto/ciclo':>12} "
          f"{'saldo t=100':>14} {'saldo t=1000':>14}")
    print("-" * 78)

    casos = [("2 de 3.000", 2/3000), ("1.000 de 4.000", 0.25),
             ("2.000 de 3.000", 2/3), ("99% de la red", 0.99),
             ("el 100%", 1.00)]
    for etiqueta, sA in casos:
        r = neto_por_ciclo(sA)
        saldos = {}
        S = 1_000_000.0
        for t in range(1, 1001):
            S += r * S                      # cicla todo su saldo
            if t in (100, 1000):
                saldos[t] = S
        print(f"{etiqueta:>18} {sA:>9.4f} {r:>12.6f} "
              f"{saldos[100]:>14,.0f} {saldos[1000]:>14,.0f}")
    print()
    print("El neto es negativo INCLUSO con el 100% de los nodos. El piso de")
    print(f"perdida es la quema: {BURN:.0%} de la fee, o sea {BURN*PHI:.4%} del valor")
    print("ciclado, y no hay cantidad de nodos que lo toque.")
    print()


# ------------------------------------------------------------ tabla B


def tabla_b():
    print("=" * 78)
    print("TABLA B - Cuanto tendria que ser el reparto para que Alice gane")
    print("=" * 78)
    print()
    print("Alice gana si  rho_prov + sigma_A * rho_res >= 1, o sea si la quema es")
    print("cero y ella se queda con todo el resto.")
    print()
    print(f"{'rho_prov':>10} {'quema':>8} {'reserva':>9} "
          f"{'neto sigma_A=0':>16} {'neto sigma_A=1':>16}")
    print("-" * 78)
    for prov, burn, res in [(0.70, 0.20, 0.10), (0.85, 0.10, 0.05),
                            (0.95, 0.02, 0.03), (0.99, 0.00, 0.01),
                            (1.00, 0.00, 0.00)]:
        n0 = -PHI * (1 - prov - 0.0 * res)
        n1 = -PHI * (1 - prov - 1.0 * res)
        m = "  <-- Alice queda a mano" if abs(n1) < 1e-15 else ""
        print(f"{prov:>10.0%} {burn:>8.0%} {res:>9.0%} "
              f"{n0:>16.6f} {n1:>16.6f}{m}")
    print()
    print("Conclusion: mientras la quema sea > 0, Alice pierde SIEMPRE.")
    print("La quema es la unica pieza irreemplazable del esquema.")
    print()


# ------------------------------------------------------------ tabla C


def tabla_c():
    print("=" * 78)
    print("TABLA C - El canal que si filtra: quemar para disparar la banda")
    print("=" * 78)
    print()
    print("Alice quema X tokens (via fees) para empujar el circulante debajo del")
    print("piso. La banda dispara emision gradual hasta restaurarlo: emite X.")
    print("Alice captura sigma_A de esa emision.")
    print()
    print("   costo   = X          (la quema sale de su propio saldo)")
    print("   ingreso = sigma_A * X")
    print("   neto    = (sigma_A - 1) * X")
    print()
    print(f"{'sigma_A':>10} {'neto por token quemado':>26} {'veredicto':>22}")
    print("-" * 78)
    for sA in [0.10, 0.50, 0.90, 0.99, 0.999, 1.00]:
        neto = (sA - 1.0)
        if neto < -1e-12:
            v = "pierde"
        elif abs(neto) <= 1e-12:
            v = "QUEDA A MANO"
        else:
            v = "GANA"
        print(f"{sA:>10.3f} {neto:>26.4f} {v:>22}")
    print()
    print("No llega a ser rentable, pero converge a cero por arriba: en el limite")
    print("de Sybil el ataque es gratis. Y si el reparto de la emision se hace por")
    print("cantidad de nodos, sigma_A -> 1 es exactamente lo que Alice puede")
    print("comprar barato, porque un nodo PoD cuesta un telefono.")
    print()
    print("El circuito de fees aguanta a cualquier Alice. La banda de supply")
    print("aguanta solo si su reparto NO es Sybil-eable.")
    print()


# ------------------------------------------------------------ tabla D


def tabla_d():
    print("=" * 78)
    print("TABLA D - Y si Alice quema esperando que suba el precio de lo suyo")
    print("=" * 78)
    print()
    print("Alice tiene la fraccion h del circulante y quema B de su propio saldo.")
    print("Capitalizacion de mercado M constante.")
    print()
    print(f"{'h':>8} {'B/S':>8} {'part. antes':>13} {'part. despues':>15} "
          f"{'valor antes':>13} {'valor despues':>15}")
    print("-" * 78)
    S, M = 1_000_000.0, 1_000_000.0
    for h in [0.10, 0.50, 0.90]:
        for frac in [0.01, 0.05]:
            B = frac * S
            antes, despues = h, (h * S - B) / (S - B)
            v_antes = h * M
            v_desp = despues * M
            print(f"{h:>8.0%} {frac:>8.0%} {antes:>13.4%} {despues:>15.4%} "
                  f"{v_antes:>13,.0f} {v_desp:>15,.0f}")
    print()
    print("Quemar plata propia SIEMPRE baja su participacion y su valor, para")
    print("cualquier h < 100%. El canal 'quemo para valorizar lo mio' no existe.")
    print()


if __name__ == "__main__":
    tabla_a()
    tabla_b()
    tabla_c()
    tabla_d()
