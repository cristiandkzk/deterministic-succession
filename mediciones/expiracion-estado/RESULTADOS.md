# Expiración de estado — medición

**Corrida el 17/8/2026.** Reproducir con `python medicion.py`. Sin datos externos.

**La pregunta:** el desalojo de estado promete que lo evictado *"no se destruye,
se puede revivir con una prueba"*. ¿Eso es real, o es una promesa que nadie puede
cumplir? Y antes: ¿hace falta expirar, o el problema es teórico?

**La respuesta corta: el problema es grande, y no está donde parecía.**

---

## Supuestos, todos declarados

| supuesto | valor | por qué |
|---|---|---|
| entrada de estado | 64 / 128 / 256 B | clave, id, puntero a metadata, saldo prepago, contadores. Se barre para que nada dependa del número elegido |
| presupuesto de disco de un nodo | 2 / 4 / 8 GB | es lo que sostiene el argumento de entrada barata de §6.1 (*"el precio de un teléfono"*) |
| compromiso del estado | Merkle binario, hash de 32 B | |
| replicación | 3.000 nodos | la cifra que el propio paper usa al discutir concentración |
| horizonte | 10 años | |

---

## A · ¿Hace falta expirar? Sí, y el umbral es bajísimo

La pregunta se hizo al revés de lo intuitivo: en vez de adivinar cuántos activos
va a haber, se calculó **cuántos alcanzan para llenar el presupuesto**.

| presupuesto | entrada | entradas tope | creaciones/día que lo agotan en 10 años |
|---|---|---|---|
| 2 GB | 128 B | 16.777.216 | **4.596** |
| 4 GB | 128 B | 33.554.432 | **9.193** |
| 8 GB | 128 B | 67.108.864 | **18.386** |

**~9.200 creaciones por día llenan un teléfono en diez años. Eso es 0,1 por
segundo.** Cualquier adopción real cruza ese umbral sin esfuerzo, así que la
expiración no es una optimización: es lo que mantiene en pie el argumento de
§6.1, y con él la no-saturación de la cola de §6.3.

## B · La prueba no pesa. Mantenerla al día, sí

Una prueba es el camino de hermanos de la hoja hasta la raíz. El hermano de cada
nivel cubre un subárbol, y **la unión de todos los hermanos del camino es el árbol
entero menos la propia hoja**. Así que la prueba sobrevive un bloque sólo si ese
bloque no tocó ninguna otra hoja.

Con 4 GB y entradas de 128 B: 33.554.432 hojas, profundidad 25, **prueba de 800
bytes**.

```
P(la prueba sobrevive un bloque que cambia una hoja) = 1/33.554.432 = 0,00000003
```

> **La prueba no se degrada con los años: se vence en el bloque siguiente.**

Guardarla es gratis —menos de un kilobyte—. Lo caro es **mantenerla al día**, y
eso significa seguir todos los bloques sin cortar nunca.

## C · El resultado que no se esperaba

Para rearmar una prueba vieja hacen falta los valores actuales de los hermanos, y
eso sólo lo puede dar quien tenga el árbol del **estado desalojado** — que es, por
construcción, lo que ningún nodo está obligado a guardar.

| estado desalojado | si lo guardan los 3.000 | si lo guarda un archivo | factor |
|---|---|---|---|
| 2 GB | 6 TB | 2 GB | 3.000× |
| 4 GB | 12 TB | 4 GB | 3.000× |
| 8 GB | 23 TB | 8 GB | 3.000× |

> **La expiración no elimina el costo de guardar: lo desreplica.** Pasa de 3.000
> copias obligatorias a unas pocas voluntarias.

Sigue siendo una ganancia de tres órdenes de magnitud y **justifica el mecanismo**.
Pero el dato tiene que existir en algún lado para que la reactivación sea real, y
**nadie está obligado a tenerlo.**

---

## Veredicto

1. **La expiración hace falta.** El umbral que llena un teléfono son miles de
   creaciones por día, no millones.
2. **"Que el dueño se guarde la prueba" no alcanza como respuesta.** La prueba
   vence en el bloque siguiente, así que *guardarla* significa en realidad
   **seguir la cadena sin cortar nunca**. Sirve para un agente permanentemente
   online —que es el público declarado de este diseño— y no sirve para una
   persona.
3. **El problema es grande, pero no es el que parecía.** No es que la prueba pese:
   pesa menos de un kilobyte. Es que **la reactivación depende de que alguien
   guarde el estado desalojado**, y eso es una dependencia que hoy el paper no
   declara en ninguna parte.
4. **La forma honesta de escribirlo es como frontera de §10.1, no como mecanismo
   resuelto.** Y tiene un precedente exacto en esa misma sección — *"la regla no
   invoca hardware: el protocolo puede determinar la generación siguiente hasta el
   último byte, pero no puede obligar a que existan nodos corriéndola"*:

> **El protocolo puede garantizar que un activo desalojado *se puede* revivir. No
> puede garantizar que alguien vaya a tener con qué.**
