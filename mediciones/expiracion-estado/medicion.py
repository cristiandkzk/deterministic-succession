#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Expiracion de estado: cuanto estado se genera, y cuanto cuesta poder revivirlo.

    python medicion.py

Contesta tres preguntas, en orden de dependencia:

  A. LA EXPIRACION, ?hace falta?   -> a que ritmo de minteo se llena un telefono
  B. LA PRUEBA, ?se puede mantener? -> cada cuanto se vuelve obsoleta
  C. EL ARCHIVO, ?cuanto pesa?      -> que guarda el que sirve las reactivaciones

Supuestos declarados, todos conservadores a favor del diseno:

  - una entrada de estado (NFT o cuenta) pesa 128 bytes: clave del duenio,
    identificador, puntero a metadata, saldo prepago y contadores. Se barre
    64/128/256 para que el resultado no dependa del numero elegido.
  - el presupuesto de disco de un nodo es el de un telefono de gama media con
    la app instalada: se barre 2/4/8 GB. Es lo que sostiene el argumento de
    entrada barata de 6.1 ("el precio de un telefono").
  - el compromiso del estado es un arbol de Merkle binario, hash de 32 bytes.
  - la red replica el estado en N nodos. Se usa 3.000, la cifra que el propio
    paper usa al discutir concentracion.
"""

import math

# ------------------------------------------------------------------ parametros

ENTRADA_BYTES = [64, 128, 256]
PRESUPUESTO_GB = [2, 4, 8]
HORIZONTE_ANIOS = 10
HASH_BYTES = 32
NODOS = 3000

GB = 1024 ** 3


def sep(titulo):
    print()
    print("=" * 78)
    print(titulo)
    print("=" * 78)
    print()


# ------------------------------------------------------- A: hace falta expirar

def bloque_a():
    sep("A - A que ritmo de creacion se agota el disco de un nodo")

    print("Se pregunta al reves de lo intuitivo: en vez de adivinar cuantos NFT")
    print("va a haber, se calcula cuantos ALCANZAN para llenar el presupuesto.")
    print("Si ese numero es chico, la expiracion no es opcional.")
    print()
    print("%14s %12s %16s %16s" % ("presupuesto", "entrada", "entradas tope",
                                   "creaciones/dia"))
    print("-" * 78)

    for gb in PRESUPUESTO_GB:
        for eb in ENTRADA_BYTES:
            tope = (gb * GB) // eb
            por_dia = tope / (HORIZONTE_ANIOS * 365.0)
            print("%11d GB %10d B %16s %16s"
                  % (gb, eb, "{:,}".format(tope), "{:,.0f}".format(por_dia)))
    print()
    print("Lectura: con 4 GB y entradas de 128 B, ~9.200 creaciones por dia")
    print("agotan el presupuesto en %d anios. Eso es 0,1 por segundo."
          % HORIZONTE_ANIOS)
    print("Cualquier adopcion real cruza ese umbral sin esfuerzo.")


# --------------------------------------------------- B: la prueba se mantiene?

def bloque_b():
    sep("B - Cada cuanto se vuelve obsoleta una prueba de reactivacion")

    print("Una prueba es el camino de hermanos de la hoja hasta la raiz.")
    print("El hermano de nivel k cubre un subarbol; la union de TODOS los")
    print("hermanos de mi camino es el arbol entero menos mi propia hoja.")
    print()
    print("Consecuencia: mi prueba sobrevive un bloque solo si NINGUN cambio")
    print("de ese bloque toco otra hoja. Con un solo cambio ajeno ya es")
    print("obsoleta.")
    print()
    print("%14s %12s %12s %14s %18s" % ("presupuesto", "entrada", "hojas",
                                        "profundidad", "prueba"))
    print("-" * 78)

    for gb in PRESUPUESTO_GB:
        for eb in ENTRADA_BYTES:
            hojas = (gb * GB) // eb
            prof = int(math.ceil(math.log(hojas, 2)))
            prueba = prof * HASH_BYTES
            print("%11d GB %10d B %12s %14d %14d B"
                  % (gb, eb, "{:,}".format(hojas), prof, prueba))

    hojas = (4 * GB) // 128
    p_sobrevive = 1.0 / hojas
    print()
    print("Con 4 GB / 128 B: %s hojas." % "{:,}".format(hojas))
    print("Probabilidad de que una prueba sobreviva un bloque que cambia UNA")
    print("hoja al azar: 1/%s = %.9f" % ("{:,}".format(hojas), p_sobrevive))
    print()
    print("O sea: la prueba se vence en el PRIMER bloque que toque cualquier")
    print("otra cosa. No se degrada con los anios: se degrada de inmediato.")
    print()
    print("La prueba en si es chica (%d bytes) y guardarla es gratis." %
          (int(math.ceil(math.log(hojas, 2))) * HASH_BYTES))
    print("Lo caro no es guardarla: es MANTENERLA AL DIA, que exige seguir")
    print("todos los bloques sin cortar nunca.")


# ------------------------------------------------------------- C: el archivo

def bloque_c():
    sep("C - Que pasa cuando el duenio SI se fue offline")

    print("Para rearmar una prueba vieja hacen falta los valores actuales de")
    print("los hermanos del camino. Eso lo puede dar solamente quien tenga el")
    print("arbol del estado DESALOJADO — que es, por construccion, lo que")
    print("ningun nodo esta obligado a guardar.")
    print()
    print("Asi que o el duenio nunca se desconecto, o alguien archiva.")
    print()
    print("%16s %18s %20s %18s" % ("estado desalojado", "si lo guardan todos",
                                   "si lo guarda 1 archivo", "factor"))
    print("-" * 78)

    for gb in PRESUPUESTO_GB:
        desalojado = gb * GB          # peor caso: se desaloja tanto como se carga
        replicado = desalojado * NODOS
        print("%13d GB %15.0f TB %17d GB %15dx"
              % (gb, replicado / float(1024 ** 4), gb, NODOS))

    print()
    print("Y aca esta el resultado que importa, y no es el que se esperaba:")
    print()
    print("  La expiracion NO elimina el costo de guardar. Lo DESREPLICA.")
    print("  Pasa de %d copias obligatorias a unas pocas voluntarias." % NODOS)
    print()
    print("Eso sigue siendo una ganancia de %dx y justifica el mecanismo." % NODOS)
    print("Pero el dato tiene que existir en algun lado para que la")
    print("reactivacion sea real, y nadie esta obligado a tenerlo.")


def veredicto():
    sep("VEREDICTO")

    print("1. La expiracion hace falta. El umbral que llena un telefono son")
    print("   miles de creaciones por dia, no millones: se cruza enseguida.")
    print()
    print("2. 'Que el duenio se guarde la prueba' NO alcanza como respuesta.")
    print("   La prueba vence en el bloque siguiente, asi que 'guardarla'")
    print("   significa en realidad 'seguir la cadena sin cortar nunca'.")
    print("   Sirve para un agente que esta siempre online — que es el publico")
    print("   declarado del diseno — y no sirve para una persona.")
    print()
    print("3. El problema es GRANDE, pero no es el que parecia. No es que la")
    print("   prueba pese: pesa menos de un kilobyte. Es que la reactivacion")
    print("   depende de que ALGUIEN guarde el estado desalojado, y eso es una")
    print("   dependencia nueva que hoy el paper no declara en ninguna parte.")
    print()
    print("4. La forma honesta de escribirlo es como frontera de 10.1, no como")
    print("   mecanismo resuelto: la expiracion desreplica el costo de 3.000")
    print("   copias a unas pocas, y a cambio la reactivacion deja de estar")
    print("   garantizada por el protocolo y pasa a depender de que exista")
    print("   archivo. Es exactamente la misma forma que 'la regla no invoca")
    print("   hardware': el protocolo puede prometer que se PUEDE revivir, no")
    print("   que alguien vaya a tener con que.")


if __name__ == "__main__":
    bloque_a()
    bloque_b()
    bloque_c()
    veredicto()
