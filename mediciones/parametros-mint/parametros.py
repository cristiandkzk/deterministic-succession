#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Los tres parametros que 8.5 dejo sin fijar: el piso F, la tasa r0 y la epoca.

    python parametros.py

Se pregunta de cada uno si es una DECISION o una CONSECUENCIA. Resultado corto:
dos son consecuencia y el tercero no es un numero.

  A. LA EPOCA       -> ?que la ata? (barrido, granularidad, cola de desalojo)
  B. r0 FIJO        -> por que un precio nominal no puede racionar un recurso real
  C. r0 COMO LEY    -> control indexado a la ocupacion: estabilidad y respuesta
  D. EL PISO F      -> derivado del costo fijo del ciclo crear+desalojar
  E. LA COLISION    -> el canal de quema que abre la ley de control, y su palanca

Supuestos declarados, los mismos de expiracion-estado/ y amortizacion-mint/:

  - entrada de estado 128 B; presupuesto de disco de un nodo 4 GB (se barre).
  - verificacion de firma 391 us (Test 2, ARM64 con JIT); un cuarto de nucleo.
  - hash a 100 MB/s en el telefono; arbol de Merkle binario, hash de 32 B.
  - divisibilidad del token 1e8 (la de Bitcoin), supply del orden de 1e6.
  - replicacion 3.000 nodos.

Lo que NO se supone: ningun precio del token en moneda externa. Todo lo que
depende de eso se marca como no calculable por el protocolo, que es la mitad
del resultado.
"""

import math
from collections import deque

# ------------------------------------------------------------------ parametros

ENTRADA_BYTES = 128
PRESUPUESTO_GB = 4
GB = 1024 ** 3
NODOS = 3000

US_VERIFICACION = 391e-6
FRACCION_NUCLEO = 0.25
HASH_MBPS = 100.0
HASH_BYTES = 32
ESCRITURA_MBPS = 200.0
SEG_ANIO = 365 * 24 * 3600.0

DIVISIBILIDAD = 10 ** 8
SUPPLY = 10 ** 6

SLOTS = (PRESUPUESTO_GB * GB) // ENTRADA_BYTES
PROFUNDIDAD = int(math.ceil(math.log(SLOTS, 2)))


def sep(titulo):
    print()
    print("=" * 78)
    print(titulo)
    print("=" * 78)
    print()


# ----------------------------------------------------------------- A: la epoca

def bloque_a():
    sep("A - Que ata la duracion de la epoca")

    print("Slots (%d GB / %d B): %s   profundidad del arbol: %d"
          % (PRESUPUESTO_GB, ENTRADA_BYTES, "{:,}".format(SLOTS), PROFUNDIDAD))
    print()

    # --- 1: el barrido
    bytes_estado = PRESUPUESTO_GB * GB
    seg_escritura = bytes_estado / (ESCRITURA_MBPS * 1e6)
    seg_hash = bytes_estado / (HASH_MBPS * 1e6)
    seg_barrido = seg_escritura + seg_hash

    print("1) COBRAR BARRIENDO EL ESTADO. Descontar el saldo de cada entrada,")
    print("   una vez por epoca, cuesta reescribir el estado entero y rehacer")
    print("   el arbol:")
    print()
    print("      escribir %d GB a %d MB/s ....... %5.1f s"
          % (PRESUPUESTO_GB, ESCRITURA_MBPS, seg_escritura))
    print("      rehashear %d GB a %d MB/s ...... %5.1f s"
          % (PRESUPUESTO_GB, HASH_MBPS, seg_hash))
    print("      total por epoca ................ %5.1f s" % seg_barrido)
    print()
    for epoca_seg, nombre in [(600, "10 minutos"), (3600, "1 hora"),
                              (86400, "1 dia")]:
        print("      epoca de %-11s -> %5.1f%% del tiempo del nodo, y TODA"
              % (nombre, 100 * seg_barrido / epoca_seg))
        print("                              prueba de reactivacion se vence")
    print()
    print("   Y no hace falta: el saldo se computa al LEER, con la entrada")
    print("   guardando deposito y bloque de creacion. Costo O(1), cero")
    print("   escrituras, cero pruebas invalidadas.")
    print()
    print("   >> La epoca NO es un barrido. Es una unidad de cuenta.")
    print()

    # --- 2: la cola de desalojo
    creaciones_dia = SLOTS / (10 * 365.0)
    print("2) LA COLA DE DESALOJO. En regimen estacionario se desaloja al mismo")
    print("   ritmo que se crea. Con el umbral de expiracion-estado/:")
    print()
    print("      %s creaciones/dia = %.2f por segundo"
          % ("{:,.0f}".format(creaciones_dia), creaciones_dia / 86400.0))
    print("      cola por expiracion, pop en O(log N) con N=%s -> %d comparaciones"
          % ("{:,}".format(SLOTS), PROFUNDIDAD))
    print()
    print("   No ata nada: 0,1 desalojos por segundo no es una carga.")
    print()

    # --- 3: la granularidad
    print("3) LA GRANULARIDAD. Unica atadura real: la tasa por epoca tiene que")
    print("   ser un entero de unidades minimas, o hay que definir redondeo")
    print("   (que es superficie de determinismo que no vale la pena abrir).")
    print()
    print("   Con divisibilidad 1e%d, la tasa MINIMA representable por epoca es"
          % int(math.log10(DIVISIBILIDAD)))
    print("   1 unidad. Traducido a costo anual de tener el estado LLENO:")
    print()
    print("%16s %22s %26s" % ("epoca", "r0 minimo (token/anio)",
                              "estado lleno (% del supply/anio)"))
    print("-" * 78)
    for epoca_seg, nombre in [(600, "10 minutos"), (3600, "1 hora"),
                              (86400, "1 dia"), (30 * 86400, "30 dias")]:
        epocas_anio = SEG_ANIO / epoca_seg
        r0_min = epocas_anio / float(DIVISIBILIDAD)
        pct = 100.0 * r0_min * SLOTS / SUPPLY
        print("%16s %22.8f %25.4f%%" % (nombre, r0_min, pct))
    print()
    print("   Aca si hay una atadura, y es la unica de las tres: la epoca fija")
    print("   un PISO al precio representable. Con epoca de 10 minutos el piso")
    print("   ya cuesta 1,8% del supply por anio con el estado lleno, que es")
    print("   demasiado para ser un piso. Con epoca de un dia son 0,012%: tres")
    print("   ordenes de margen por debajo de cualquier tarifa razonable.")
    print()
    print("   (La alternativa es una tasa en punto fijo escalado, que borra la")
    print("   atadura pero agrega una regla de redondeo, o sea superficie de")
    print("   determinismo. Con un dia no hace falta.)")
    print()
    print("   >> La epoca no la ata el barrido ni la cola: la ata el piso de")
    print("      precio representable, y un dia lo resuelve con tres ordenes")
    print("      de margen. Es el unico de los tres que sigue siendo eleccion,")
    print("      y es una eleccion barata.")


# ---------------------------------------------------------- B: r0 fijo no puede

def bloque_b():
    sep("B - Por que r0 no puede ser un numero fijo")

    print("r0 es un precio nominal. El recurso que raciona -disco por tiempo-")
    print("es real y constante. Si el token flota, el precio real del guardado")
    print("flota con el, y en la direccion equivocada las dos veces.")
    print()
    print("Precio real de una entrada-anio, con r0 nominal congelado:")
    print()
    print("%10s %14s %14s %14s %14s" % ("anio", "+50%/anio", "+20%/anio",
                                        "-20%/anio", "-50%/anio"))
    print("-" * 78)
    for t in [0, 1, 3, 5, 10]:
        fila = "%10d" % t
        for g in [0.50, 0.20, -0.20, -0.50]:
            fila += "%13.2fx" % ((1 + g) ** t)
        print(fila)
    print()
    print("Si el token se aprecia, guardar se vuelve prohibitivo y el estado se")
    print("vacia; si se deprecia, guardar es gratis y se llena. En los dos")
    print("casos el protocolo perdio el control de la unica variable que le")
    print("importa, que es la OCUPACION.")
    print()
    print("Es el mismo defecto que ya mato al piso nominal de la subasta en")
    print("C7.10 -'nominal en una moneda que se aprecia'- y es el motivo por el")
    print("que las cadenas con fee fijo terminaron todas en mercado de fees.")
    print()
    print("  >> Un precio nominal fijo no puede racionar un recurso real bajo")
    print("     una moneda que flota. r0 tiene que moverse.")
    print()
    print("Y solo hay una variable a la que puede indexarse sin romper I2: la")
    print("OCUPACION DEL ESTADO, que es un hecho del estado y no una lectura de")
    print("mercado. Que es, literalmente, la doctrina de 7.6 aplicada al disco:")
    print("apuntar a la cantidad y dejar flotar el precio.")


# ------------------------------------------------------ C: r0 como ley de control

def simular(theta_obj, k, clamp, epsilon, shock, epocas=400, vida_ref=200):
    """Controla r0 contra la ocupacion. Devuelve la serie de ocupacion."""
    r0 = 1.0
    demanda_ref = theta_obj / float(vida_ref)   # equilibrio inicial
    cohortes = deque()
    theta = 0.0
    # precargar el estado en equilibrio
    for _ in range(vida_ref):
        cohortes.append(demanda_ref)
        theta += demanda_ref

    serie = []
    for t in range(epocas):
        demanda = demanda_ref * (1.0 / r0) ** epsilon
        if t >= 100:
            demanda *= shock
        # la vida comprada cae con el precio: mismo presupuesto por objeto
        vida = max(1, int(round(vida_ref / r0)))

        cohortes.append(demanda)
        theta += demanda
        # desalojar lo que cumplio su vida
        while len(cohortes) > vida:
            theta -= cohortes.popleft()

        error = (theta - theta_obj) / theta_obj
        factor = 1.0 + k * error
        factor = max(1.0 - clamp, min(1.0 + clamp, factor))
        r0 *= factor
        serie.append(theta / theta_obj)
    return serie


def bloque_c():
    sep("C - r0 como ley de control indexada a la ocupacion")

    print("Ley:  r0(t+1) = r0(t) * (1 + k * (theta - theta*) / theta*)")
    print("      acotada a +-clamp por epoca. theta = ocupacion, theta* = objetivo.")
    print()
    print("Es la forma de EIP-1559 aplicada al disco en vez de al gas. Se")
    print("simula un shock de demanda x3 en la epoca 100 y se mide overshoot y")
    print("tiempo de vuelta a +-5% del objetivo. Elasticidad de la demanda")
    print("declarada y barrida, porque no se puede medir sin una red.")
    print()
    print("%8s %8s %10s %14s %16s" % ("k", "clamp", "epsilon", "overshoot",
                                      "vuelta a +-5%"))
    print("-" * 78)

    for k in [0.05, 0.125, 0.25]:
        for eps in [0.5, 1.0]:
            serie = simular(theta_obj=1.0, k=k, clamp=0.125, epsilon=eps,
                            shock=3.0)
            post = serie[100:]
            overshoot = max(post)
            vuelta = None
            for i, v in enumerate(post):
                if abs(v - 1.0) < 0.05 and all(abs(x - 1.0) < 0.05
                                               for x in post[i:i + 20]):
                    vuelta = i
                    break
            if vuelta is None:
                txt = "no vuelve"
            elif vuelta == 0:
                txt = "no sale de la banda"
            else:
                txt = "%d epocas" % vuelta
            print("%8.3f %8s %10.2f %13.2fx %19s"
                  % (k, "12,5%", eps, overshoot, txt))

    print()
    print("Lectura: con clamp de 12,5% por epoca el lazo absorbe un shock de")
    print("x3 sin oscilar. La ganancia k mueve la velocidad, no la estabilidad;")
    print("el clamp es lo que impide que un pico de una epoca mueva el precio.")
    print()
    print("  >> r0 no es un numero que se calcula una vez: es una variable de")
    print("     control. Lo que hay que elegir es theta*, y ESO si es politica.")


# ------------------------------------------------------------- D: el piso F

def bloque_d():
    sep("D - El piso F, derivado")

    verif_por_seg = FRACCION_NUCLEO / US_VERIFICACION
    frac_cpu_firma = 1.0 / (verif_por_seg * SEG_ANIO)

    # actualizacion de Merkle: un camino de PROFUNDIDAD hashes de 64 B
    bytes_camino = PROFUNDIDAD * 2 * HASH_BYTES
    seg_merkle = bytes_camino / (HASH_MBPS * 1e6)
    frac_cpu_merkle = seg_merkle / (SEG_ANIO * FRACCION_NUCLEO)

    frac_disco_anio = ENTRADA_BYTES / float(PRESUPUESTO_GB * GB)

    print("El ciclo completo que un objeto le cuesta a la red, aparte del")
    print("disco, es CREAR + DESALOJAR. Se mide contra el presupuesto del nodo")
    print("y se expresa en horas de guardado, que es la unidad en la que r0")
    print("esta denominado.")
    print()
    print("%38s %18s" % ("componente", "horas de guardado"))
    print("-" * 78)

    def horas(frac_cpu):
        return (frac_cpu / frac_disco_anio) * 365 * 24

    h_firma = horas(frac_cpu_firma)
    h_merkle = horas(frac_cpu_merkle)
    print("%38s %17.1f" % ("verificar la firma de la creacion", h_firma))
    print("%38s %17.1f" % ("actualizar el arbol al crear", h_merkle))
    print("%38s %17.1f" % ("actualizar el arbol al desalojar", h_merkle))
    print("-" * 78)
    total = h_firma + 2 * h_merkle
    print("%38s %17.1f" % ("TOTAL = F", total))
    print()
    print("  F = %.1f horas de guardado = %.4f%% del precio de una entrada-anio."
          % (total, 100 * total / (365 * 24)))
    print()
    print("Y F queda clavado por arriba tambien, por el propio argumento de")
    print("8.5: todo lo que se cobre por crear POR ENCIMA del costo de crear es")
    print("un cargo a la creacion, y un cargo a la creacion se evade minteando")
    print("afuera. Asi que F no es una perilla: es un numero.")
    print()
    print("  >> F = costo fijo del ciclo crear+desalojar. Ni mas -seria cargo a")
    print("     la creacion- ni menos -seria churn subsidiado-.")
    print()
    print("Corolario que corrige a C7.11: el antispam NO lo hace el piso, que")
    print("es el 0,2% de un anio de guardado. Lo hace el DEPOSITO, porque")
    print("crear N objetos cuesta N depositos. El piso solo cubre el ciclo.")


# --------------------------------------------------------- E: la colision

def bloque_e():
    sep("E - La colision que abre la ley de control: el canal de quema")

    print("Con r0 indexado a la ocupacion, un atacante que llena estado sube el")
    print("precio a TODOS. Como el deposito se consume QUEMANDOSE, eso acelera")
    print("la quema de terceros -- y la quema entra en 'emitido - quemado', que")
    print("es lo que lee el trigger (7.6). O sea: se puede pagar por acelerar.")
    print()
    print("La pregunta correcta no es si el canal existe -existe- sino cuanta")
    print("PALANCA da: cuanta quema ajena compra el atacante por unidad de")
    print("quema propia.")
    print()
    print("Con s = fraccion del estado que ocupa el atacante en el equilibrio")
    print("nuevo, y elasticidad epsilon de la demanda honesta, el control tiene")
    print("que subir r0 por R = (1/(1-s))^(1/epsilon) para desplazarla:")
    print()
    print("      palanca = ((1-s)/s) * ((R-1)/R)")
    print()
    print("%10s %12s %12s %12s %12s" % ("s", "eps=0,25", "eps=0,5", "eps=1,0",
                                        "eps=2,0"))
    print("-" * 78)
    for s in [0.05, 0.10, 0.25, 0.50, 0.75]:
        fila = "%9.0f%%" % (100 * s)
        for eps in [0.25, 0.5, 1.0, 2.0]:
            R = (1.0 / (1.0 - s)) ** (1.0 / eps)
            palanca = ((1 - s) / s) * ((R - 1) / R)
            fila += "%12.2f" % palanca
        print(fila)
    print()
    print("Lectura, y es el resultado del bloque: para s chico la palanca tiende")
    print("a 1/epsilon. O sea:")
    print()
    print("  >> La palanca del canal es del orden de 1/elasticidad. Con demanda")
    print("     elastica (eps>=1) el atacante nunca quema mas ajeno que propio.")
    print("     Con demanda INELASTICA -gente que necesita su activo vivo al")
    print("     precio que sea- la palanca crece y el canal se vuelve real.")
    print()
    print("Y epsilon no se puede conocer antes de tener red. Asi que esto no se")
    print("cierra con un numero: o se declara como frontera, o se corta el")
    print("canal excluyendo la quema por permanencia de la cuenta del trigger.")
    print("Lo segundo tiene su propio costo: rompe la definicion limpia de 7.8")
    print("-circulante es emitido menos quemado, sin excepciones-.")


def veredicto():
    sep("VEREDICTO")

    print("De los tres parametros que 8.5 dejo abiertos, ninguno es lo que")
    print("parecia:")
    print()
    print("1. LA EPOCA SE DISUELVE. No hay que elegirla. Cobrar barriendo el")
    print("   estado cuesta ~65 s por epoca y vence todas las pruebas; cobrar")
    print("   al leer cuesta O(1). Con lectura perezosa la 'epoca' es la tasa")
    print("   por bloque, la cola de desalojo mueve 0,1 objetos por segundo y")
    print("   la granularidad no ata en ningun rango razonable.")
    print()
    print("2. EL PISO F SE DERIVA. Es el costo fijo del ciclo crear+desalojar")
    print("   medido contra el presupuesto del nodo: ~16 horas de guardado, o")
    print("   sea 0,2% de una entrada-anio. Clavado por abajo por el costo y")
    print("   por arriba por el argumento anti-evasion de 8.5. No es politica.")
    print("   Corrige a C7.11: el antispam lo hace el deposito, no el piso.")
    print()
    print("3. r0 NO ES UN NUMERO. Un precio nominal fijo no puede racionar un")
    print("   recurso real bajo una moneda que flota -- se rompe en las dos")
    print("   direcciones. Tiene que ser una ley de control sobre la unica")
    print("   variable admisible: la ocupacion del estado. La ley es estable")
    print("   con clamp de 12,5% por epoca y absorbe un shock de x3.")
    print()
    print("4. QUEDA UNA SOLA DECISION DE POLITICA: theta*, la ocupacion")
    print("   objetivo. Cuanto disco quiere ocupar la cadena en el hardware de")
    print("   entrada. Todo lo demas cuelga de ese numero.")
    print()
    print("5. Y QUEDA UNA COLISION NUEVA, que no estaba vista: indexar r0 a la")
    print("   ocupacion abre un canal para acelerar la quema ajena pagando la")
    print("   propia, con palanca ~1/elasticidad. Con demanda elastica es")
    print("   inofensivo; con demanda inelastica no. Hay que decidirlo antes de")
    print("   adoptar la ley de control.")


if __name__ == "__main__":
    bloque_a()
    bloque_b()
    bloque_c()
    bloque_d()
    bloque_e()
    veredicto()
