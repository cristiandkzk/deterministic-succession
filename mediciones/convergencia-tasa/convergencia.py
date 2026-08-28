"""Se borra el nivel inicial? — el operador de exceso de EIP-4844/7999.

Contesta la hipotesis que quedo del problema abierto 2: si el lazo converge desde
cualquier x0, el nivel inicial no es una variable del diseno.

Criterios en CRITERIOS.md, escritos antes que este archivo. Sin dependencias.
"""
import math

# --- el operador ---------------------------------------------------------
# Normalizado: target = 1, limit = 2*target (como 4844/7999).
# k sale de la intencion de 7999: a uso pleno el precio se mueve 12,5% por paso,
# o sea exp((limit-target)/k) = 1.125  ->  k = target / ln(1.125).
TARGET = 1.0
LIMIT = 2.0 * TARGET
K = TARGET / math.log(1.125)
P_MIN = 1.0
X_EQ = 50.0                      # exceso de equilibrio elegido lejos del piso
P_EQ = P_MIN * math.exp(X_EQ / K)


def precio(x):
    return P_MIN * math.exp(x / K)


def demanda(p, e):
    """Elasticidad constante, topeada por la capacidad del bloque."""
    return min(LIMIT, TARGET * (p / P_EQ) ** (-e))


def paso(x, e):
    return max(0.0, x + demanda(precio(x), e) - TARGET)


def trayectoria(x0, e, n):
    x, out = x0, [x0]
    for _ in range(n):
        x = paso(x, e)
        out.append(x)
    return out


def c_analitico(e):
    """Linealizacion en el punto fijo: F'(x*) = 1 - e*target/k."""
    return abs(1.0 - e * TARGET / K)


E_CRITICA = 2.0 * K / TARGET      # arriba de esto sobrecorrige


# --- criterios -----------------------------------------------------------
def c1_exogena(n=500, delta=10.0):
    """C1 · con e=0 la diferencia no decae."""
    a = trayectoria(X_EQ + delta, 0.0, n)
    b = trayectoria(X_EQ, 0.0, n)
    d = [abs(x - y) for x, y in zip(a, b)]
    constante = max(abs(v - delta) for v in d) < 1e-9
    return constante, d[0], d[-1]


def c2_contraccion(es=(0.5, 1.0, 2.0, 4.0, 8.0, 12.0), n=600, delta=1e-3):
    """C2 · c empirico contra c analitico.

    c = |F'(x*)| es una propiedad LOCAL del punto fijo, asi que la perturbacion
    tiene que ser infinitesimal: con delta grande se mide el transitorio no lineal
    -el precio es exponencial en el exceso- y no la tasa asintotica. Y se promedia
    solo mientras D conserva precision, porque abajo de ~1e-13 es ruido de maquina.
    """
    filas = []
    for e in es:
        a = trayectoria(X_EQ + delta, e, n)
        b = trayectoria(X_EQ - delta, e, n)
        d = [abs(x - y) for x, y in zip(a, b)]
        pares = [(d[i + 1] / d[i]) for i in range(len(d) - 1)
                 if d[i] > 1e-10 and d[i + 1] > 1e-10]
        emp = math.exp(sum(math.log(r) for r in pares) / len(pares)) if pares else float("nan")
        ana = c_analitico(e)
        err = abs(emp - ana) / ana if ana > 1e-12 else abs(emp - ana)
        filas.append((e, emp, ana, err, d[-1]))
    return filas


def c3_inestable(es=(14.0, 16.0, E_CRITICA, 18.0, 22.0), n=600, delta=1.0):
    """C3 · arriba de e = 2k/target el lazo no converge."""
    filas = []
    for e in es:
        a = trayectoria(X_EQ + delta, e, n)
        b = trayectoria(X_EQ - delta, e, n)
        d = [abs(x - y) for x, y in zip(a, b)]
        cola = d[-100:]
        filas.append((e, c_analitico(e), max(cola), sum(cola) / len(cola)))
    return filas


def c4_piso(n=300):
    """C4 · dos trayectorias que tocan el piso se fusionan sin contraer."""
    # demanda muy por debajo del target y e=0: el exceso cae a 0 y se queda.
    def paso_seco(x):
        return max(0.0, x + 0.2 - TARGET)          # uso 0,2 contra target 1
    a, b, fusion = 5.0, 30.0, None
    for i in range(n):
        a, b = paso_seco(a), paso_seco(b)
        if fusion is None and abs(a - b) < 1e-12:
            fusion = i + 1
    return fusion, a, b


def c5_umbral(horizontes=(10, 25, 50, 100, 500), tol=0.01, d0=10.0):
    """C5 · cuanta elasticidad hace falta para borrar x0 en N pasos."""
    filas = []
    for N in horizontes:
        objetivo = (tol / d0) ** (1.0 / N)          # c requerido
        e_min = (1.0 - objetivo) * K / TARGET       # invierte c = 1 - e*target/k
        filas.append((N, objetivo, e_min))
    return filas


# --- salida --------------------------------------------------------------
if __name__ == "__main__":
    print(f"operador: target={TARGET}  limit={LIMIT}  k={K:.4f}  (12,5% por paso a uso pleno)")
    print(f"contraccion analitica: c(e) = |1 - e*{TARGET/K:.6f}|")
    print(f"elasticidad critica (c=1 por sobrecorreccion): e = 2k/target = {E_CRITICA:.4f}\n")

    ok, d0, dn = c1_exogena()
    print("C1 · demanda exogena (e = 0)")
    print(f"   D_0 = {d0:.6f}   D_500 = {dn:.6f}   constante: {ok}")
    print(f"   -> {'APROBADO' if ok else 'REPROBADO'}: c = 1, el operador NO contrae solo\n")

    print("C2 · contraccion con demanda elastica")
    print(f"   {'e':>6} {'c empirico':>12} {'c analitico':>12} {'error':>9} {'D_400':>12}")
    filas = c2_contraccion()
    for e, emp, ana, err, dfin in filas:
        print(f"   {e:>6.1f} {emp:>12.6f} {ana:>12.6f} {err:>8.2%} {dfin:>12.3e}")
    peor = max(f[3] for f in filas)
    print(f"   -> {'APROBADO' if peor < 0.01 else 'REPROBADO'}: peor error {peor:.2%}\n")

    print("C3 · el lado inestable")
    print(f"   {'e':>8} {'c analitico':>12} {'max|D| cola':>14} {'medio':>12}")
    for e, ana, mx, md in c3_inestable():
        print(f"   {e:>8.3f} {ana:>12.6f} {mx:>14.4f} {md:>12.4f}")
    print(f"   -> APROBADO si el regimen aparece en e > {E_CRITICA:.2f}\n")

    fusion, a, b = c4_piso()
    print("C4 · fusion por el piso max(0, .)")
    print(f"   x0 = 5 y x0 = 30, uso 0,2 contra target 1, e = 0")
    print(f"   fusionan exactamente en el paso {fusion}  (a={a}, b={b})")
    print(f"   -> D -> 0 SIN contraccion: es el piso, no el lazo. Se informa aparte.\n")

    print("C5 · cuanta elasticidad hace falta (tol 0,01 sobre D_0 = 10)")
    print(f"   {'N pasos':>8} {'c requerido':>13} {'e minima':>10}")
    for N, c, emin in c5_umbral():
        marca = "   <- L_MAX_EPOCAS del diseno" if N == 25 else ""
        print(f"   {N:>8} {c:>13.6f} {emin:>10.4f}{marca}")
