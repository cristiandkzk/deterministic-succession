# Fase 5 — criterios de aprobado

**Escritos el 21/8/2026, antes de la primera línea de `permanencia.py`.** Es la regla de la
sección 4 del `ROADMAP.md`, y en esta fase pesa más que en ninguna: **la única ley de control de
la tasa que este proyecto escribió se cayó, y no la tumbó un ataque — la tumbó corregir un
detalle del modelo con el que se la había probado.** Un criterio escrito después de ver el
resultado se acomoda al resultado.

Este archivo **no se edita después de correr**. Lo que se mide va a `RESULTADOS.md`, al lado.

---

## Los tres del roadmap

### A1 · El ciclo cierra completo

**Aprobado si** `crear → pagar → agotar → desalojar → reactivar` corre entero y el objeto vuelve
**idéntico byte a byte** al que entró. **Reprobado si** la reactivación devuelve algo distinto,
por poco que sea: eso sería confiscación parcial con otro nombre.

### A2 · El acumulador es de cientos de bytes **totales**, no por objeto

Es la condición que hace que el desalojo no sea permanencia comprada más barata. Una lápida de
32 bytes por objeto son 1 GB por nodo para siempre — un cuarto del presupuesto.

**Aprobado si** el acumulador ocupa **≤ 1 KiB con cualquier cantidad de desalojos**, verificado
en tres órdenes de magnitud (10, 10.000, 1.000.000). **Reprobado si** crece linealmente, aunque
sea con una constante chica.

### A3 · Lo que cuesta mantener la prueba al día, medido

Es la dependencia que §10.2 declara y no puede garantizar: la prueba pesa menos de un kilobyte
y guardarla es gratis, pero **la unión de los hermanos del camino de una hoja es el árbol entero
menos esa hoja**, así que se vence en el primer bloque que toque cualquier otra cosa.

**Aprobado si el número queda escrito, sea cual sea** — cuántas actualizaciones por bloque, y
qué le cuesta a un agente permanentemente online. No hay umbral que pasar: lo que reprueba es no
poder medirlo.

---

## Los que se agregan, y por qué

### A4 · La doble reactivación se frena sin lista de nulificadores

Una lista de nulificadores sería exactamente el residuo O(n) que A2 prohíbe, entrando por otra
puerta. **Aprobado si** revivir dos veces el mismo objeto falla, y falla **chequeando contra el
conjunto activo** —que está acotado por construcción— y no contra una lista de gastados.

### A5 · Nadie compra permanencia perpetua con un pago finito

Es la propiedad que §8.5 declara como justificación de la sección entera.

**Aprobado si** las dos:

- se puede comprar como mucho `L_max` de una vez, y volver a comprar exige otra operación al
  precio de entonces;
- **el precio por época no baja al depositar más.** Con una regla de potencia la vida crece más
  rápido que el depósito y el precio por año tiende a cero — cien pisos comprarían diez mil años.
  Lo único que el volumen puede ahorrar legítimamente es **pagar el alta una vez en vez de una
  por período**.

### A6 · La cuenta regresiva es pública y computable con anticipación

Misma forma que la distancia al disparo de I2, y por la misma razón: **un desalojo anunciado no
genera presión por un arreglo coordinado a mano, y una sorpresa sí.**

**Aprobado si** se puede consultar cuántas épocas le quedan a cualquier entrada, la respuesta es
determinística, y es **monótona** mientras no haya recarga.

### A7 · Desalojar no es confiscar

**Aprobado si** las tres: no hay quema del activo al desalojar; no hay saldo en descubierto —el
protocolo no tiene deudor al que embargar—; y no hay remate, porque rematar obliga a la cadena a
saber cuánto vale el objeto, que es exactamente lo que §7.6 prohíbe.

---

## Los dos que vienen de C18.5, y son los que pueden reprobar

La Fase 4 cerró dos veces el mismo techo con la misma jugada: **el número no se elige, se
deriva; lo que se congela es la cuenta.** De ahí salió una sospecha que conviene correr contra
esta fase antes de dar por libre ningún parámetro.

### A8 · El piso: ¿perilla o cuenta?

§8.5 ya lo declara derivado —*"no es una perilla: es el costo fijo del ciclo crear + desalojar"*—
pero nunca se escribió la cuenta con números medidos. Ahora se puede: la Fase 4 midió lo que
cuesta verificar una firma, y esta fase mide lo que cuestan las dos actualizaciones del árbol.

**Aprobado si** la derivación se escribe y da el orden de magnitud que §8.5 afirma —**unas
dieciséis horas de guardado, 0,2% de un año**—. **Reprobado si** hay que elegir el número a ojo,
o si la cuenta da otro orden: en ese caso el que está mal es el paper, y se corrige el paper.

### A9 · La tasa: ¿por qué esta no se puede cerrar igual?

Es el problema abierto de §10.3, y el roadmap dice que esta fase se construye con la tasa
parametrizada. Bien — pero **queda prohibido dejarlo en *"no sabemos"***.

**Aprobado si** pasa una de las dos:

- se escribe la cuenta, como pasó dos veces con el techo; **o**
- se escribe **por qué esta no es de esa clase**, con un argumento que la distinga del techo de
  pasos de forma verificable, no por sensación.

**Reprobado si** el resultado es que hace falta seguir pensando. Después de dos cierres con la
misma jugada, no saber si la tercera aplica es información que sí se puede producir.

---

## Lo que esta fase NO contesta

- **Cuál es el nivel inicial de la tasa.** Es un precio, y §10.3 ya dice que la cadena no lo
  puede leer sin violar I2. Si A9 aprueba por la segunda vía, esto queda cerrado como frontera.
- **Si alguien va a correr archivo.** §10.2 lo declara: el protocolo garantiza que un desalojado
  *se puede* revivir, no que alguien tenga con qué.
- **Si la ley de control es estable.** No hay con qué calibrarla y ése es el bloqueo declarado.
