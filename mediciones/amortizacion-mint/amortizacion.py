#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Piso de creacion y tasa de amortizacion: ?cuanto descuento se puede dar por
depositar mas, sin regalar el disco?

    python amortizacion.py

La propuesta que se mide: mintear no es gratis (hay un piso), el creador puede
depositar por encima del piso, y CUANTO MAS DEPOSITA, MAS LENTO SE AMORTIZA.

La forma natural de escribir eso es una regla de potencia:

    r(D) = r0 * (D0/D)^alpha        tokens quemados por epoca
    L(D) = D / r(D)                 vida del activo

con D0 el piso, alpha el descuento (alpha=0 es sin descuento, alpha=1 la
version fuerte de la intuicion). De ahi sale, con k = D/D0:

    L(k) = L0 * k^(1+alpha)         la vida crece MAS que el deposito
    precio por entrada-anio = D/L = D0/L0 * k^(-alpha)

Se contesta en cinco bloques:

  A. LA REGLA DE POTENCIA        -> que vida y que precio compra cada deposito
  B. EL ATAQUE QUE ABARATA       -> cuanto cuesta ocupar el disco para siempre
  C. EL COSTO FIJO REAL          -> cuanto vale crear, medido en horas de disco
  D. LA VERSION ACOTADA          -> tarifa en dos partes: el descuento con piso
  E. EL RECIBO DEL GENESIS       -> si el tope duro de 7.2 necesita deposito

Supuestos declarados:

  - todo se expresa en MULTIPLOS DEL PISO, para no inventar un precio del token.
    El piso D0 es la unidad de cuenta y L0 (vida al piso) la unidad de tiempo;
    L0 = 1 anio es normalizacion, no afirmacion.
  - entrada de estado 64/128/256 B y presupuesto de nodo 2/4/8 GB: los mismos
    de expiracion-estado/medicion.py, barridos por el mismo motivo.
  - costo de crear: una verificacion de firma. 391 us en un Motorola Edge 40
    Neo con JIT (Test 2), contra un presupuesto de un cuarto de nucleo -- que
    es el mismo par de numeros que da los ~640 tx/s de 6.1.
  - tope duro del recibo de 7.2: 3.000 PoD + 500 computo = 3.500 entradas.
"""

import math

# ------------------------------------------------------------------ parametros

ENTRADA_BYTES = [64, 128, 256]
PRESUPUESTO_GB = [2, 4, 8]
NODOS = 3000

ALPHAS = [0.0, 0.25, 0.5, 1.0]
MULTIPLOS = [1, 2, 5, 10, 100, 1000]

US_POR_VERIFICACION = 391e-6      # Test 2, ARM64 con JIT
FRACCION_NUCLEO = 0.25            # el presupuesto de firma de 6.1
SEG_POR_ANIO = 365 * 24 * 3600.0

HORIZONTE_PARA_SIEMPRE = 100      # anios: mas que cualquier tenedor humano
RECIBOS_GENESIS = 3500

GB = 1024 ** 3


def sep(titulo):
    print()
    print("=" * 78)
    print(titulo)
    print("=" * 78)
    print()


# ------------------------------------------------------ A: la regla de potencia

def vida(k, alpha):
    """Vida en unidades de L0, para un deposito de k pisos."""
    return k ** (1.0 + alpha)


def bloque_a():
    sep("A - Que compra cada deposito, segun cuanto descuento se de")

    print("k = cuantas veces el piso deposita el creador.")
    print()
    print("VIDA COMPRADA, en anios (L0 = 1 anio al piso):")
    print()
    print("%8s" % "k", end="")
    for a in ALPHAS:
        print("%17s" % ("alpha=%.2f" % a), end="")
    print()
    print("-" * 78)
    for k in MULTIPLOS:
        print("%8d" % k, end="")
        for a in ALPHAS:
            print("%17s" % "{:,.0f}".format(vida(k, a)), end="")
        print()

    print()
    print("PRECIO POR ENTRADA-ANIO, en % de lo que paga el que deposita el piso:")
    print()
    print("%8s" % "k", end="")
    for a in ALPHAS:
        print("%17s" % ("alpha=%.2f" % a), end="")
    print()
    print("-" * 78)
    for k in MULTIPLOS:
        print("%8d" % k, end="")
        for a in ALPHAS:
            print("%16.1f%%" % (k ** (-a) * 100.0), end="")
        print()

    print()
    print("Sin descuento (alpha=0) la vida es proporcional: pagas el doble,")
    print("vivis el doble, y el precio por anio no se mueve. Es la version")
    print("'pagas por cuanto tiempo queres que la red te lo guarde'.")
    print()
    print("Con alpha=1, 100 pisos compran %s anios y el precio por anio cae al"
          % "{:,.0f}".format(vida(100, 1.0)))
    print("1%% del que paga el piso. Mil pisos compran %s anios."
          % "{:,.0f}".format(vida(1000, 1.0)))
    print()
    print("Con alpha=0 tambien se puede comprar un siglo -- pero se paga un")
    print("siglo. La diferencia no es que una regla venda perpetuidades y la")
    print("otra no: es el PRECIO POR ANIO.")
    print()
    print("  Con alpha > 0 el precio por anio tiende a cero al crecer el")
    print("  deposito: la permanencia deja de costar lo que cuesta.")
    print()
    print("Y eso es exactamente el defecto que 10.1 ya tiene nombrado: un pago")
    print("que no cubre el costo perpetuo no es un arreglo, es un prestamo.")


# ------------------------------------------------- B: el ataque que se abarata

def k_para_vivir(anios, alpha):
    """Cuantos pisos hay que depositar para vivir 'anios' (con L0 = 1)."""
    return anios ** (1.0 / (1.0 + alpha))


def bloque_b():
    sep("B - Cuanto cuesta ocupar el disco de todos los nodos PARA SIEMPRE")

    print("'Para siempre' = %d anios, mas que cualquier tenedor humano."
          % HORIZONTE_PARA_SIEMPRE)
    print("Se compra una entrada por slot, con el deposito minimo que aguante")
    print("ese horizonte. Capital total en multiplos del piso.")
    print()

    tope = (4 * GB) // 128
    print("Tope de slots (4 GB / 128 B): %s" % "{:,}".format(tope))
    print()
    print("%10s %14s %22s %16s" % ("alpha", "pisos/slot", "capital total (pisos)",
                                   "vs alpha=0"))
    print("-" * 78)

    base = None
    for a in ALPHAS:
        k = k_para_vivir(HORIZONTE_PARA_SIEMPRE, a)
        capital = k * tope
        if base is None:
            base = capital
        print("%10.2f %14.1f %22s %15.1fx"
              % (a, k, "{:,.0f}".format(capital), base / capital))

    print()
    print("Lectura: el descuento no abarata cualquier cosa por igual -- abarata")
    print("PRECISAMENTE la operacion de llenar el estado de todos los nodos y")
    print("no soltarlo nunca, que es la unica que compra vida en volumen.")
    print()
    print("Con alpha=1 sale %.0fx mas barato que sin descuento."
          % (base / (k_para_vivir(HORIZONTE_PARA_SIEMPRE, 1.0) * tope)))
    print()
    print("Es la misma forma del fee fijo que 6.1 rechaza -- 'vuelve gratis el")
    print("pedido grande' -- pero en la dimension del tiempo en vez del valor.")
    print("Y el recurso esta topeado: el descuento no crea disco, solo se lo")
    print("reasigna al que tiene mas capital. Es foso de capital, que es lo")
    print("que 6.1 existe para evitar.")


# ------------------------------------------------------- C: el costo fijo real

def equivalencia_horas(entrada_bytes, presupuesto_gb):
    """Cuantas horas de disco 'vale' una creacion, en el presupuesto del nodo."""
    verificaciones_por_seg = FRACCION_NUCLEO / US_POR_VERIFICACION
    frac_cpu = 1.0 / (verificaciones_por_seg * SEG_POR_ANIO)
    frac_disco_por_anio = entrada_bytes / float(presupuesto_gb * GB)
    return (frac_cpu / frac_disco_por_anio) * 365 * 24


def bloque_c():
    sep("C - Cuanto cuesta CREAR, medido en tiempo de guardado")

    print("La pregunta detras del piso: ?hay un costo fijo real de crear, o el")
    print("piso es politica pura? Se mide crear (una verificacion de firma,")
    print("contra el presupuesto de CPU del nodo) contra guardar (la entrada,")
    print("contra el presupuesto de disco), y se expresa el primero en unidades")
    print("del segundo.")
    print()
    print("Presupuesto de firma: %.0f verificaciones/s (%.2f nucleo a %d us)."
          % (FRACCION_NUCLEO / US_POR_VERIFICACION, FRACCION_NUCLEO,
             US_POR_VERIFICACION * 1e6))
    print()
    print("%14s %12s %28s" % ("presupuesto", "entrada", "crear equivale a guardar"))
    print("-" * 78)

    for gb in PRESUPUESTO_GB:
        for eb in ENTRADA_BYTES:
            h = equivalencia_horas(eb, gb)
            print("%11d GB %10d B %24.1f horas" % (gb, eb, h))

    h_ref = equivalencia_horas(128, 4)
    print()
    print("Con 4 GB / 128 B: crear cuesta lo mismo que guardar %.0f horas."
          % h_ref)
    print()
    print("  El costo fijo de crear es real pero DIMINUTO: menos de un dia de")
    print("  guardado, contra activos que pretenden vivir anios.")
    print()
    print("Consecuencia para el piso: el piso NO es un cargo por costo -- no hay")
    print("costo fijo que cubrir. Es un parametro antispam, y esta bien que lo")
    print("sea, porque la fee ad valorem de 6.1 no muerde en un mint (un activo")
    print("recien creado vale ~0). Pero hay que llamarlo por su nombre: es una")
    print("decision de politica, no una tasacion.")


# ------------------------------------------------------- D: la version acotada

def bloque_d():
    sep("D - La version que conserva la intuicion sin vender perpetuidades")

    print("Tarifa en dos partes, que es como se tasa cualquier recurso con un")
    print("costo fijo de alta y uno lineal de permanencia:")
    print()
    print("    precio(L) = F + r0 * L         F = piso, r0 = costo lineal real")
    print("    tasa media = F/L + r0          <- CAE con L, y nunca baja de r0")
    print()
    print("La intuicion 'mas deposito, menor tasa de amortizacion' SALE SOLA de")
    print("aca, y no hay que postularla: lo que cae es el piso repartido entre")
    print("mas tiempo. Lo que no pasa es que caiga a cero.")
    print()

    for f_anios in [1, 10, 100]:
        print("Con el piso equivalente a %d anio(s) de guardado:" % f_anios)
        print("%10s %18s %20s" % ("vida (a)", "tasa media (r0)", "vs pagar 1 anio"))
        print("-" * 78)
        base = f_anios / 1.0 + 1.0
        for L in [1, 2, 5, 10, 50, 100]:
            media = f_anios / float(L) + 1.0
            print("%10d %18.2f %19.0f%%" % (L, media, 100.0 * media / base))
        print()

    print("Y aca esta lo que decide la pregunta original:")
    print()
    print("  El descuento tiene un piso, y ese piso es el costo real de")
    print("  guardar. La tasa media cae con la vida comprada -- hasta r0,")
    print("  nunca por debajo.")
    print()
    print("Lo unico que el volumen ahorra es pagar el alta UNA sola vez en vez")
    print("de una por periodo. Ese ahorro esta ACOTADO por el piso; el de la")
    print("regla de potencia es k^alpha y no tiene tope.")
    print()
    print("Comparacion directa, en vida comprada por 1.000 pisos de capital:")
    print()
    print("%28s %20s" % ("regla", "anios de vida"))
    print("-" * 78)
    for a in ALPHAS:
        print("%28s %20s" % ("potencia alpha=%.2f" % a,
                             "{:,.0f}".format(vida(1000, a))))
    for f_anios in [1, 10, 100]:
        # capital X compra L = (X - F)/r0, con r0 = F/f_anios y F = 1 piso
        vida_2p = (1000 - 1) * f_anios
        print("%28s %20s" % ("dos partes (piso=%da)" % f_anios,
                             "{:,.0f}".format(vida_2p)))
    print()
    print("La tarifa en dos partes tambien es lineal -- igual que alpha=0 -- pero")
    print("con la ventaja de que el piso queda explicito y separado, asi que se")
    print("puede subir por antispam sin tocar el precio del guardado. Que es")
    print("literalmente lo que se pidio: 'un piso, y que se pueda aumentar'.")


# ---------------------------------------------------- E: el recibo del genesis

def bloque_e():
    sep("E - ?El recibo del bloque 0 tiene que pagar deposito?")

    tope = (4 * GB) // 128
    frac = RECIBOS_GENESIS / float(tope)
    print("Recibos de 7.2 con tope duro: %s (3.000 PoD + 500 computo)."
          % "{:,}".format(RECIBOS_GENESIS))
    print("Tope de slots (4 GB / 128 B): %s" % "{:,}".format(tope))
    print()
    print("Ocupacion: %.6f%% del presupuesto de un nodo." % (100 * frac))
    print("En bytes, sobre los 3.000 nodos: %.1f MB en toda la red."
          % (RECIBOS_GENESIS * 128 * NODOS / float(1024 ** 2)))
    print()
    print("  El recibo puede seguir siendo gratis y perpetuo sin romper nada,")
    print("  y la razon es cuantitativa, no de encuadre: el tope duro lo hace")
    print("  despreciable. Lo que NO puede ser gratis y perpetuo es el mint")
    print("  abierto, que es el mismo objeto SIN tope.")
    print()
    print("O sea que las dos decisiones no se contradicen: C7.6 decidio gratis")
    print("para un conjunto de %s entradas; esto decide piso + deposito para un"
          % "{:,}".format(RECIBOS_GENESIS))
    print("conjunto sin cota. La variable que separa los casos es el tope.")


def veredicto():
    sep("VEREDICTO")

    h_ref = equivalencia_horas(128, 4)
    k1 = k_para_vivir(HORIZONTE_PARA_SIEMPRE, 1.0)
    k0 = k_para_vivir(HORIZONTE_PARA_SIEMPRE, 0.0)

    print("1. El piso es correcto, y hay que llamarlo por su nombre. No cubre")
    print("   un costo: crear cuesta %.0f horas de guardado (4 GB / 128 B). Es"
          % h_ref)
    print("   un parametro ANTISPAM, y tiene que serlo porque la fee ad valorem")
    print("   de 6.1 no muerde en un mint. Que se pueda subir es correcto: es")
    print("   la unica perilla antispam que el mint tiene.")
    print()
    print("2. 'Mas deposito, menor tasa de amortizacion' es correcto como")
    print("   OBSERVACION y peligroso como REGLA. Sale solo de amortizar el")
    print("   piso sobre mas tiempo; postularlo como regla de potencia hace")
    print("   otra cosa distinta.")
    print()
    print("3. Toda regla con alpha > 0 manda el precio por anio a cero cuando")
    print("   el deposito crece. Con alpha=1 alcanzan %.0f pisos para vivir %d"
          % (k1, HORIZONTE_PARA_SIEMPRE))
    print("   anios, contra %.0f sin descuento: %.0fx mas barato ocupar todo el"
          % (k0, k0 / k1))
    print("   disco para siempre. Es el fee fijo que 6.1 rechaza por regresivo")
    print("   ('vuelve gratis el pedido grande'), en la dimension del tiempo.")
    print()
    print("4. La forma que conserva la intuicion es la tarifa en dos partes:")
    print("   piso al mintear (antispam, se quema, subible) + deposito de")
    print("   permanencia que se consume quemandose (lineal). La tasa media")
    print("   cae con la vida comprada -- que es lo que se pedia -- pero con")
    print("   PISO en el costo lineal real, y el descuento total esta acotado")
    print("   por el piso en vez de crecer sin tope.")
    print()
    print("5. El recibo del bloque 0 no entra en conflicto: su tope duro lo")
    print("   deja en %.4f%% del presupuesto." % (100 * RECIBOS_GENESIS / float((4 * GB) // 128)))


if __name__ == "__main__":
    bloque_a()
    bloque_b()
    bloque_c()
    bloque_d()
    bloque_e()
    veredicto()
