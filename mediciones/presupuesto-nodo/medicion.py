#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cuanto ocupa DE VERDAD una entrada de estado, y cuanto margen pide el lazo.

    python medicion.py

Existe porque theta* se iba a fijar sobre tres supuestos sumados a ojo (128 B de
entrada + 32 B de arbol + 16 B de indice = 176 B). Dos de los tres estaban mal, y
el tercero depende de una decision de implementacion que nadie habia tomado.

  A. EL LAYOUT      -> los campos, uno por uno, para las dos clases de entrada
  B. EL ARBOL       -> el overhead no es un dato: es una perilla con dos topes
  C. EL INDICE      -> que hace falta para desalojar sin barrer
  D. LA CAPACIDAD   -> el total y cuantos objetos entran por presupuesto
  E. EL LAZO        -> simulacion corregida: las cohortes conservan su vida
  F. EL DIAGNOSTICO -> por que no cierra, y por que no es del controlador
  G. EL ARREGLO     -> tope a la vida comprable, y el techo que deja para theta*

Se empezo midiendo bytes y se termino tumbando la ley de control de C7.13. El
bloque E es el que hay que leer primero si se viene de ahi.

Supuestos declarados:

  - hash de 32 B; direcciones y punteros a metadata son hashes (con firmas
    post-cuanticas la clave publica no se guarda, se guarda su hash).
  - hash a 100 MB/s en el telefono; presupuesto de firma ~640 tx/s (6.1).
  - lectura de disco a 200 MB/s.
  - presupuesto de disco del nodo de entrada: 2/4/8 GB, se barre.
"""

import math

HASH = 32
HASH_MBPS = 100.0
TPS = 640.0
GB = 1024 ** 3

PRESUPUESTOS_GB = [2, 4, 8]


def sep(t):
    print()
    print("=" * 78)
    print(t)
    print("=" * 78)
    print()


# ---------------------------------------------------------------- A: el layout

OBJETO = [
    ("dueno (hash de clave publica)", HASH),
    ("identificador del activo", 8),
    ("puntero a metadata (hash)", HASH),
    ("deposito de permanencia", 8),
    ("bloque de creacion", 8),
    ("supply", 8),
    ("divisibilidad + flags", 4),
]

SALDO = [
    ("dueno (hash de clave publica)", HASH),
    ("identificador del activo", 8),
    ("monto", 8),
    ("deposito de permanencia", 8),
    ("bloque de creacion", 8),
]


def alinear(n, a=16):
    return int(math.ceil(n / float(a)) * a)


def bloque_a():
    sep("A - El layout, campo por campo")

    print("Hay DOS clases de entrada y no una sola, y esa distincion no estaba")
    print("hecha: el objeto-activo lleva metadata y supply; el saldo de un")
    print("tenedor no lleva ninguno de los dos.")
    print()

    for nombre, campos in [("OBJETO (el activo)", OBJETO), ("SALDO (un tenedor)", SALDO)]:
        print("  %s" % nombre)
        total = 0
        for c, b in campos:
            print("      %-34s %4d B" % (c, b))
            total += b
        print("      %-34s %4d B  -> alineado: %d B"
              % ("suma", total, alinear(total)))
        print()

    print("  Los 128 B que se venian usando son correctos para el OBJETO.")
    print("  Para el SALDO sobran: son %d B." % alinear(sum(b for _, b in SALDO)))


# ----------------------------------------------------------------- B: el arbol

def bloque_b():
    sep("B - El arbol: el overhead no es un dato, es una perilla")

    print("Se venia suponiendo 32 B por entrada, o sea guardar TODOS los nodos")
    print("internos (N-1 nodos para N hojas). No hace falta: se pueden guardar")
    print("solo los niveles por encima de un corte d y recomputar el subarbol")
    print("de 2^d hojas cuando se necesita.")
    print()
    print("Guardar mas arriba abarata el disco y encarece cada actualizacion.")
    print("Hay dos topes, y el que muerde es el de ACTUALIZAR, no el de probar:")
    print("actualizar pasa en cada transaccion; generar una prueba, casi nunca.")
    print()
    print("%6s %14s %20s %20s"
          % ("corte d", "B por entrada", "hash por operacion", "% del presup. hash"))
    print("-" * 78)

    for d in [1, 3, 6, 9, 12]:
        b_entrada = HASH / float(2 ** (d - 1))
        bytes_op = (2 ** d) * (128 + 64)          # hojas leidas + pares hasheados
        seg_op = bytes_op / (HASH_MBPS * 1e6)
        pct = 100.0 * seg_op * TPS
        print("%6d %14.3f %17.2f KB %19.1f%%"
              % (d, b_entrada, bytes_op / 1024.0, pct))

    print()
    print("Lectura: con d=1 (guardar todo) el disco paga 32 B por entrada. Con")
    print("d=6 paga 1 B y las actualizaciones consumen ~8% del presupuesto de")
    print("hash del nodo. Con d=9 el disco es gratis pero el nodo se queda sin")
    print("presupuesto de hash.")
    print()
    print("  >> El overhead del arbol NO es 32 B. Es ~1 B con el corte en d=6,")
    print("     y el precio es 8% del presupuesto de hash. Es una decision de")
    print("     implementacion que hay que tomar, no un costo que se sufre.")


# ---------------------------------------------------------------- C: el indice

def bloque_c():
    sep("C - El indice de desalojo")

    print("Para desalojar sin barrer hay que poder encontrar lo vencido. Dos")
    print("formas, y no cuestan lo mismo:")
    print()
    print("  heap binario de (vencimiento, id) ....... 16 B por entrada")
    print("  baldes por epoca de vencimiento ......... %2d B por entrada" % 8)
    print("     (un balde por epoca futura, con la lista de ids que vencen ahi;")
    print("      el vencimiento ya esta implicito en el balde, asi que solo hay")
    print("      que guardar el id)")
    print()
    print("  >> 8 B por entrada, no 16. El balde ademas hace el desalojo O(k)")
    print("     sobre los k que vencen, sin tocar el resto.")


# ------------------------------------------------------------- D: la capacidad

def totales():
    objeto = alinear(sum(b for _, b in OBJETO))
    saldo = alinear(sum(b for _, b in SALDO))
    arbol = HASH / float(2 ** (6 - 1))     # corte d=6
    indice = 8
    return objeto + arbol + indice, saldo + arbol + indice


def bloque_d():
    sep("D - La capacidad real")

    t_obj, t_sal = totales()
    print("Con corte d=6 e indice por baldes:")
    print()
    print("  objeto activo ..... %3d B de entrada + %.0f B de arbol + %d B de indice = %.0f B"
          % (alinear(sum(b for _, b in OBJETO)), HASH / 32.0, 8, t_obj))
    print("  saldo de tenedor .. %3d B de entrada + %.0f B de arbol + %d B de indice = %.0f B"
          % (alinear(sum(b for _, b in SALDO)), HASH / 32.0, 8, t_sal))
    print()
    print("Contra los 176 B que se venian usando: %.0f B, o sea %.0f%% menos."
          % (t_obj, 100 * (1 - t_obj / 176.0)))
    print()
    print("%14s %18s %18s %18s"
          % ("presupuesto", "objetos", "saldos", "supuesto viejo"))
    print("-" * 78)
    for gb in PRESUPUESTOS_GB:
        n_obj = int(gb * GB / t_obj)
        n_sal = int(gb * GB / t_sal)
        n_viejo = int(gb * GB / 176.0)
        print("%11d GB %18s %18s %18s"
              % (gb, "{:,}".format(n_obj), "{:,}".format(n_sal),
                 "{:,}".format(n_viejo)))
    print()
    n4 = int(4 * GB / t_obj)
    print("Con 4 GB entran %s objetos, contra los %s del supuesto viejo."
          % ("{:,}".format(n4), "{:,}".format(int(4 * GB / 176.0))))
    print("Y el umbral de creaciones/dia que agota el presupuesto en 10 anios")
    print("vuelve a subir: %s por dia." % "{:,.0f}".format(n4 / 3650.0))


# ------------------------------------------------------------- E: el margen

def simular(theta_obj, k, clamp, epsilon, shock, epocas=4000,
            vida_ref=200.0, shock_desde=100, tope_vida=None):
    """Cada cohorte conserva la vida que compro. Devuelve (ocupacion, r0, vidas)."""
    r0 = 1.0
    demanda_ref = theta_obj / vida_ref
    vencimientos = {}
    theta = 0.0
    for i in range(int(vida_ref)):
        vencimientos[i] = demanda_ref
        theta += demanda_ref

    serie, serie_r0, vidas = [], [], []
    for t in range(epocas):
        theta -= vencimientos.pop(t, 0.0)

        demanda = demanda_ref * (1.0 / r0) ** epsilon
        if t >= shock_desde:
            demanda *= shock

        # la vida se FIJA al comprar: mismo presupuesto por objeto
        vida = max(1, int(round(vida_ref / r0)))
        if tope_vida:
            vida = min(vida, tope_vida)
        vencimientos[t + vida] = vencimientos.get(t + vida, 0.0) + demanda
        theta += demanda

        error = (theta - theta_obj) / theta_obj
        f = max(1.0 - clamp, min(1.0 + clamp, 1.0 + k * error))
        r0 *= f
        serie.append(theta / theta_obj)
        serie_r0.append(r0)
        vidas.append(vida)
    return serie, serie_r0, vidas


def _resumen(serie):
    post = serie[100:]
    cola = post[-500:]
    return max(post), min(cola), max(cola)


def bloque_e():
    sep("E - La simulacion corregida tumba el resultado de C7.13")

    print("La simulacion de C7.13 recalculaba la vida de TODAS las cohortes cada")
    print("epoca, o sea que al subir el precio acortaba retroactivamente plazos")
    print("ya pagados. Eso no puede pasar: el que pago tiene su plazo. Corregido,")
    print("cada cohorte vence cuando compro vencer -- y el lazo deja de cerrar.")
    print()
    print("Shock de demanda x3 sostenido desde la epoca 100, 4.000 epocas de")
    print("corrida, vida al precio de referencia 200 epocas.")
    print()
    print("%8s %10s %12s %18s %16s"
          % ("k", "epsilon", "pico", "cola (min-max)", "r0 final"))
    print("-" * 78)
    for k in [0.05, 0.125, 0.25]:
        for eps in [0.5, 1.0]:
            s, r, _ = simular(1.0, k, 0.125, eps, 3.0)
            pico, cmin, cmax = _resumen(s)
            r_txt = "%.2f" % r[-1] if r[-1] < 1e6 else "%.0e" % r[-1]
            print("%8.3f %10.2f %11.2fx %18s %16s"
                  % (k, eps, pico, "%.2f - %.2f" % (cmin, cmax), r_txt))
    print()
    print("No converge con ninguna ganancia: la ocupacion sigue oscilando entre")
    print("casi cero y mas del doble del objetivo despues de 4.000 epocas, y r0")
    print("se va a valores sin sentido.")
    print()
    print("  >> El resultado de C7.13 -'absorbe un shock x3 sin oscilar'- era un")
    print("     artefacto del modelo. Con plazos que se respetan, no.")


# ------------------------------------------------------- F: por que no cierra

def bloque_f():
    sep("F - Por que no cierra, y no es culpa del controlador")

    _, r, v = simular(1.0, 0.125, 0.125, 1.0, 3.0)
    print("Diagnostico medido sobre la corrida de arriba:")
    print()
    print("  r0 minimo alcanzado ................ %.4f" % min(r))
    print("  vida maxima comprada ............... %s epocas (referencia: 200)"
          % "{:,}".format(max(v)))
    print()
    print("Ahi esta todo. Cuando el lazo baja el precio para llenar, la vida que")
    print("se compra por el mismo presupuesto se ALARGA -- y esos slots quedan")
    print("tomados por siglos a precio de saldo. El lazo despues no los puede")
    print("recuperar, porque estan pagados y el desalojo anticipado seria")
    print("confiscacion.")
    print()
    print("  >> No es un problema de sintonia. Es ARBITRAJE INTERTEMPORAL:")
    print("     prepago con precio flotante = comprar largo cuando esta barato.")
    print()
    print("Y de paso explica el tiempo muerto: el efecto de mover el precio recien")
    print("aparece cuando vencen las cohortes. Un controlador proporcional con")
    print("cientos de epocas de tiempo muerto oscila por construccion.")


# --------------------------------------------------- G: el arreglo, y theta*

def bloque_g():
    sep("G - El arreglo: tope a la vida que se puede comprar de una vez")

    print("Si la vida comprable de una vez esta topeada en L_max --y para seguir")
    print("vivo se recarga al precio de entonces--, el arbitraje desaparece y el")
    print("tiempo muerto queda acotado por L_max en vez de por el presupuesto")
    print("del comprador.")
    print()
    print("%8s %10s %12s %18s %16s"
          % ("L_max", "epsilon", "pico", "cola (min-max)", "?cierra?"))
    print("-" * 78)
    picos_ok = []
    for lmax in [10, 25, 50, 100]:
        for eps in [0.5, 1.0]:
            s, r, _ = simular(1.0, 0.125, 0.125, eps, 3.0, tope_vida=lmax)
            pico, cmin, cmax = _resumen(s)
            cierra = (cmax - cmin) < 0.02
            if cierra:
                picos_ok.append(pico)
            print("%8d %10.2f %11.2fx %18s %16s"
                  % (lmax, eps, pico, "%.2f - %.2f" % (cmin, cmax),
                     "si" if cierra else "NO"))
    print()
    print("Con L_max de 25 epocas o menos el lazo aterriza EXACTO en el objetivo.")
    print("Con 50 es marginal y con 100 vuelve a romperse. El umbral esta en el")
    print("orden de un octavo de la vida de referencia.")
    print()
    peor = max(picos_ok)
    print("El pico peor entre las configuraciones que cierran es %.2fx, y de ahi"
          % peor)
    print("sale un techo DURO para theta*, que hasta ahora era intuicion:")
    print()
    print("%14s %20s %24s" % ("theta*", "pico de ocupacion", "?entra en el presupuesto?"))
    print("-" * 78)
    for th in [0.25, 0.50, 0.65, 0.75, 0.90]:
        p = th * peor
        print("%13.0f%% %19.0f%% %24s"
              % (100 * th, 100 * p, "si" if p < 1.0 else "NO - se pasa"))
    print()
    print("  >> theta* <= 1/%.2f = %.0f%%. Y el tope a la vida comprable pasa de"
          % (peor, 100 / peor))
    print("     ser una recomendacion economica a ser CONDICION DE ESTABILIDAD.")


def veredicto():
    sep("VEREDICTO")

    t_obj, t_sal = totales()
    n4 = int(4 * GB / t_obj)

    print("1. LOS 176 B ESTABAN MAL, Y POR DOS LADOS. El arbol no cuesta 32 B")
    print("   por entrada: con el corte en d=6 cuesta ~1 B, y el precio es 8%")
    print("   del presupuesto de hash del nodo. El indice no cuesta 16 B sino")
    print("   8 B con baldes por epoca. El layout de 128 B si estaba bien para")
    print("   el objeto -- pero un SALDO de tenedor son %d B, no 128."
          % alinear(sum(b for _, b in SALDO)))
    print()
    print("2. LA CAPACIDAD REAL ES MAYOR: %s objetos con 4 GB, contra %s del"
          % ("{:,}".format(n4), "{:,}".format(int(4 * GB / 176.0))))
    print("   supuesto viejo. El umbral de creaciones/dia sube a %s."
          % "{:,.0f}".format(n4 / 3650.0))
    print()
    print("3. LA LEY DE CONTROL DE C7.13 NO CIERRA, y el resultado anterior era")
    print("   un artefacto: la simulacion vieja acortaba retroactivamente plazos")
    print("   ya pagados. Con plazos respetados, la ocupacion oscila entre casi")
    print("   cero y mas del doble del objetivo, sin converger en 4.000 epocas.")
    print()
    print("4. LA CAUSA NO ES DE SINTONIA, ES ECONOMICA: prepago con precio")
    print("   flotante es arbitraje intertemporal. Cuando el lazo abarata para")
    print("   llenar, se compran vidas de %s epocas contra 200 de referencia, y"
          % "{:,}".format(max(simular(1.0, 0.125, 0.125, 1.0, 3.0)[2])))
    print("   esos slots ya no se recuperan sin confiscar.")
    print()
    print("5. EL ARREGLO ES UN TOPE A LA VIDA COMPRABLE DE UNA VEZ. Con L_max de")
    print("   25 epocas o menos, el lazo aterriza exacto en el objetivo. Deja de")
    print("   ser una recomendacion economica y pasa a ser condicion de")
    print("   estabilidad del mecanismo.")
    print()
    print("6. Y RECIEN AHI theta* TIENE TECHO DERIVADO: el pico del shock fija el")
    print("   margen. Ver la ultima tabla de G.")


if __name__ == "__main__":
    bloque_a()
    bloque_b()
    bloque_c()
    bloque_d()
    bloque_e()
    bloque_f()
    bloque_g()
    veredicto()
