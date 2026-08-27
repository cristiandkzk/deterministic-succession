# -*- coding: utf-8 -*-
"""
¿Cierra el tope duro de demora al lock-in con "demora acotada" en vez de con
"cola de impugnaciones no saturable"?

Mecanismo (§3, §6.3): disparo → F (ventana de impugnación) → lock-in → Δ → activación.
El tope duro dice F ≤ F_max. El ataque que el tope NO mata por sí solo no es
demorar (eso ya está acotado) sino CENSURAR: llenar la capacidad de verificación
con impugnaciones basura para que una impugnación legítima no se procese dentro
de F_max, y entonces el fraude queda firme — que es el residuo declarado en §7.4.

La pregunta es entonces: ¿puede un atacante sostener la cola llena durante F_max?

Estructura del problema:
  - LLENAR es serial: una impugnación no existe hasta que entra en un bloque.
    Techo = capacidad del bloque, T transacciones/bloque.
  - DRENAR es paralelo: los N nodos PoD verifican, y la verificación PoD reproduce
    bit a bit en cualquier hardware (§6.1), así que cualquiera puede tomar
    cualquier impugnación.

  => saturación posible sólo si   fill > drain.

Parámetros:
  T      transacciones por bloque (capacidad de la cadena)
  N      nodos PoD que procesan impugnaciones
  gamma  costo de verificar una impugnación / costo de verificar una transacción
         (acotado por el techo de pasos de VM de §10.1 — ver nota al pie)
  h      headroom: trabajo extra que un nodo hace por bloque ADEMÁS de verificar
         el bloque entero, en múltiplos del bloque
  b      bono plano por impugnación, se pierde si no verifica
  F_max  tope duro, en bloques

drain = N * h * T / gamma      impugnaciones verificadas por bloque
fill  = T                      impugnaciones inyectadas por bloque (techo duro)

margen = drain / fill = N * h / gamma
"""

# --------------------------------------------------------------------------- datos
# Test 2 (§6.1/§11): 391 µs por verificación ML-DSA-44 en un Motorola Edge 40 Neo,
# ~640 tx/s con un cuarto de núcleo dedicado a firmas.
TX_S_TELEFONO = 640.0
BLOQUE_S = 10.0
T = TX_S_TELEFONO * BLOQUE_S          # 6400 tx/bloque


def margen(N, h, gamma):
    """drain / fill. > 1 significa que la cola no puede acumular backlog."""
    return N * h / gamma


def N_critico(h, gamma):
    """Nodos mínimos para que la cola NO sea saturable."""
    return gamma / h


def costo_censura(F_max, b, T=T):
    """
    Si la saturación es posible, el atacante tiene que sostener fill = T durante
    F_max bloques. Cada impugnación basura pierde el bono (no verifica, y "no
    verifica" es determinístico — §6.3/§6.4, no hace falta juez).
    """
    return b * T * F_max


def sep(t):
    print("\n" + t)
    print("-" * len(t))


# --------------------------------------------------------------------------- A
sep("Tabla A — margen drain/fill = N·h/gamma  (>1 = cola NO saturable)")
print("h = headroom del nodo (múltiplos del bloque, más allá de verificar el bloque)")
print("gamma = costo de una impugnación en transacciones equivalentes\n")

hs = [0.05, 0.10, 0.25, 1.00]
gammas = [1, 2, 10, 100]
Ns = [3, 10, 100, 1000, 10000]

print(f"{'gamma':>6} {'h':>6} | " + " ".join(f"{'N='+str(n):>12}" for n in Ns))
for g in gammas:
    for h in hs:
        fila = " ".join(f"{margen(n, h, g):>12,.1f}" for n in Ns)
        print(f"{g:>6} {h:>6.2f} | {fila}")

# --------------------------------------------------------------------------- B
sep("Tabla B — N crítico: nodos necesarios para que la cola no sature")
print(f"{'gamma':>6} | " + " ".join(f"{'h='+format(h,'.2f'):>10}" for h in hs))
for g in gammas:
    fila = " ".join(f"{N_critico(h, g):>10,.0f}" for h in hs)
    print(f"{g:>6} | {fila}")

# --------------------------------------------------------------------------- C
sep("Tabla C — si la saturación FUERA posible: costo de censurar F_max bloques")
print(f"capacidad de cadena T = {T:,.0f} tx/bloque (Test 2, bloque de {BLOQUE_S:.0f} s)")
print("el atacante tiene que sostener fill = T todo el tope; todo bono se quema\n")

F_maxs = [10, 100, 1000, 10000]
bs = [0.0001, 0.001, 0.01, 0.1]

print(f"{'F_max (bl)':>11} {'~tiempo':>10} | " + " ".join(f"{'b='+str(b):>14}" for b in bs))
for F in F_maxs:
    horas = F * BLOQUE_S / 3600.0
    if horas < 48:
        tiempo = f"{horas:.1f} h"
    else:
        tiempo = f"{horas/24:.1f} d"
    fila = " ".join(f"{costo_censura(F, b):>14,.0f}" for b in bs)
    print(f"{F:>11,} {tiempo:>10} | {fila}")

# --------------------------------------------------------------------------- D
sep("Tabla D — asimetría del bono: honesto vs atacante")
print("El bono es COSTO, no puja (FIFO). Se pierde sólo si la impugnación no verifica.")
print("Una impugnación válida es prueba determinística: el bono vuelve.\n")

print(f"{'impugnaciones':>14} | {'costo honesto':>14} | {'costo atacante':>15} | {'ratio':>8}")
for n in [1, 100, 10_000, 1_000_000]:
    b = 0.01
    honesto = 0.0            # verifica → bono devuelto
    atacante = b * n         # no verifica → bono quemado
    ratio = "∞" if honesto == 0 else f"{atacante/honesto:.0f}×"
    print(f"{n:>14,} | {honesto:>14,.2f} | {atacante:>15,.2f} | {ratio:>8}")

# --------------------------------------------------------------------------- E
sep("Tabla E — el punto de bootstrap: N chico con gamma pesimista")
print("El único régimen donde la cola satura. F_max = 100 bloques (~17 min).\n")

print(f"{'N':>6} {'gamma':>6} {'h':>5} | {'margen':>8} | {'satura?':>8}")
for N in [1, 2, 3, 5, 10, 20, 50, 100]:
    for g, h in [(10, 0.10), (100, 0.05)]:
        m = margen(N, h, g)
        print(f"{N:>6} {g:>6} {h:>5.2f} | {m:>8.2f} | {'SÍ' if m < 1 else 'no':>8}")

print("""
NOTA sobre gamma, que es el parámetro que decide todo.
gamma > 1 significa que una impugnación cuesta más verificar que la transacción
que la origina — la asimetría clásica de DoS al verificador. El techo de pasos de
VM (§10.1) es exactamente lo que la prohíbe: una impugnación que excediera el
techo es inválida de cara, así que verificarla cuesta a lo sumo lo que costó
crear la interacción disputada. Con techo, gamma ≈ 1. Las filas de gamma = 10 y
100 están para ver qué pasaría SIN techo.
""")
