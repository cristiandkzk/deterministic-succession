# Piso de creación y tasa de amortización — cálculo

**Corrido el 18/8/2026.** Reproducir con `python amortizacion.py`. Sin datos externos.

**La pregunta.** La propuesta a medir: mintear no puede ser gratis —hay un **piso
de creación**, y el piso se tiene que poder **aumentar**— y **cuanto más se
deposita, menor es la tasa de amortización**. ¿Cuánto descuento por volumen se
puede dar sin regalar el disco?

**La respuesta corta: las tres partes de la propuesta son correctas, pero la
tercera sólo en una de sus dos formas posibles.** El piso va; que sea subible va;
y la tasa decreciente **ya sale sola** de una tarifa de dos partes, con un piso
duro en el costo real. Escrita como regla de potencia, no: manda el precio del
guardado a cero y abarata exactamente el ataque que importa.

---

## Supuestos, todos declarados

| supuesto | valor | por qué |
|---|---|---|
| unidad de cuenta | **múltiplos del piso** `D0` | para no inventar un precio del token |
| unidad de tiempo | `L0` = vida al piso, normalizada a 1 año | normalización, no afirmación |
| entrada de estado | 64 / 128 / 256 B | los mismos de `expiracion-estado/`, barridos por el mismo motivo |
| presupuesto de disco de un nodo | 2 / 4 / 8 GB | sostiene el argumento de entrada barata de §6.1 |
| costo de crear | una verificación de firma: **391 µs** (Test 2, ARM64 con JIT) | contra un cuarto de núcleo — el mismo par que da los ~640 tx/s de §6.1 |
| replicación | 3.000 nodos | la cifra que el paper usa al discutir concentración |
| tope del recibo de §7.2 | 3.500 (3.000 PoD + 500 cómputo) | lo decidido en C7.6 |

**La regla que se mide**, que es la forma natural de escribir *"más depósito,
menos amortización"*:

```
r(D) = r0 · (D0/D)^α        quemado por época
L(D) = D / r(D)             vida del activo
```

con `k = D/D0`, sale `L(k) = L0 · k^(1+α)` y `precio por entrada-año = D0/L0 · k^(−α)`.
`α = 0` es sin descuento; `α = 1` es la versión fuerte de la intuición.

---

## A · Lo que compra cada depósito

**Vida comprada, en años:**

| k | α=0 | α=0,25 | α=0,5 | α=1 |
|---|---|---|---|---|
| 1 | 1 | 1 | 1 | 1 |
| 10 | 10 | 18 | 32 | 100 |
| 100 | 100 | 316 | 1.000 | **10.000** |
| 1.000 | 1.000 | 5.623 | 31.623 | **1.000.000** |

**Precio por entrada-año, en % de lo que paga el que deposita el piso:**

| k | α=0 | α=0,25 | α=0,5 | α=1 |
|---|---|---|---|---|
| 10 | 100% | 56,2% | 31,6% | 10,0% |
| 100 | 100% | 31,6% | 10,0% | 1,0% |
| 1.000 | 100% | 17,8% | 3,2% | **0,1%** |

Con `α = 0` también se puede comprar un siglo — pero se paga un siglo. **La
diferencia entre las reglas no es que una venda permanencia y la otra no: es el
precio por año.**

> **Con cualquier α > 0 el precio por año tiende a cero al crecer el depósito: la
> permanencia deja de costar lo que cuesta.**

Y ese es exactamente el defecto que §10.1 ya tiene nombrado con otras palabras —
*un residuo que compone no es un arreglo, es un préstamo*.

---

## B · Qué abarata el descuento, exactamente

Ocupar **todos** los slots de la cadena durante 100 años, comprando una entrada
por slot con el depósito mínimo que aguante ese horizonte (4 GB / 128 B →
33.554.432 slots):

| α | pisos por slot | capital total (pisos) | vs α=0 |
|---|---|---|---|
| 0 | 100,0 | 3.355.443.200 | 1,0× |
| 0,25 | 39,8 | 1.335.825.998 | 2,5× |
| 0,5 | 21,5 | 722.908.323 | 4,6× |
| **1** | **10,0** | **335.544.320** | **10× más barato** |

El descuento no abarata todo por igual: **abarata precisamente la única operación
que compra vida en volumen**, que es llenar el estado de todos los nodos y no
soltarlo nunca.

Es la misma forma del fee fijo que §6.1 rechaza por regresivo —*"vuelve gratis el
pedido grande"*— pero en la dimensión del tiempo en vez de la del valor. Y el
recurso está topeado: **el descuento no crea disco, sólo se lo reasigna al que
tiene más capital.** Eso es foso de capital, que es lo que §6.1 existe para
evitar.

---

## C · Cuánto cuesta crear de verdad, medido en tiempo de guardado

Para saber si el piso cubre un costo o es política, se mide **crear** (una
verificación de firma contra el presupuesto de CPU del nodo) contra **guardar**
(la entrada contra el presupuesto de disco), y se expresa el primero en unidades
del segundo. Presupuesto de firma: 639 verificaciones/s.

| presupuesto | entrada | crear equivale a guardar |
|---|---|---|
| 2 GB | 256 B | 3,6 horas |
| 4 GB | 128 B | **14,6 horas** |
| 8 GB | 64 B | 58,3 horas |

> **El costo fijo de crear es real pero diminuto: menos de un día de guardado**,
> contra activos que pretenden vivir años.

**Consecuencia para el piso:** el piso **no es una tasación**, porque no hay costo
fijo que cubrir. Es un **parámetro antispam**, y tiene que serlo — el punto 4 de
C7.10 ya lo había anticipado: la fee ad valorem de §6.1 no muerde en un mint,
porque un activo recién creado vale ~0. **Que se pueda subir es correcto: es la
única perilla antispam que el mint tiene.** Pero hay que llamarlo por su nombre.

---

## D · La versión que conserva la intuición sin regalar el guardado

Tarifa en dos partes, que es como se tasa cualquier recurso con un costo fijo de
alta y uno lineal de permanencia:

```
precio(L) = F + r0 · L         F = piso, r0 = costo lineal real
tasa media = F/L + r0          ← cae con L, y nunca baja de r0
```

**La intuición sale sola de acá y no hay que postularla**: lo que cae al comprar
más vida es el piso repartido entre más tiempo. Con el piso equivalente a 10 años
de guardado:

| vida comprada | tasa media | vs pagar 1 año |
|---|---|---|
| 1 año | 11,00 · r0 | 100% |
| 10 años | 2,00 · r0 | 18% |
| 100 años | 1,10 · r0 | 10% |

**La tasa cae 10× — y nunca baja de `r0`.**

> **El descuento tiene un piso, y ese piso es el costo real de guardar.** Lo único
> que el volumen ahorra es pagar el alta una sola vez en vez de una por período.
> Ese ahorro está **acotado por el piso**; el de la regla de potencia es `k^α` y no
> tiene tope.

Vida comprada con un capital de 1.000 pisos, para ver las dos familias juntas:

| regla | años de vida |
|---|---|
| potencia α=0 | 1.000 |
| potencia α=0,5 | 31.623 |
| potencia α=1 | 1.000.000 |
| dos partes (piso = 1 año) | 999 |
| dos partes (piso = 10 años) | 9.990 |

La tarifa de dos partes también es lineal —igual que α=0— pero con la ventaja de
que **el piso queda explícito y separado del precio del guardado**, así que se
puede subir por antispam sin tocar la tasa de permanencia. Que es literalmente lo
que se pidió: *un piso, y que se pueda aumentar*.

---

## E · El recibo del bloque 0 no entra en conflicto

| | |
|---|---|
| recibos de §7.2, tope duro | 3.500 |
| slots del nodo (4 GB / 128 B) | 33.554.432 |
| ocupación | **0,0104%** |
| peso en toda la red (3.000 nodos) | 1,25 GB |

C7.6 decidió que el recibo del claim es **gratis**; esto decide **piso + depósito**
para el mint abierto. No se contradicen, y la razón es cuantitativa y no de
encuadre: **la variable que separa los dos casos es el tope.** Con tope duro el
conjunto es despreciable y puede ser gratis y perpetuo; sin tope, no.

---

## Veredicto

1. **El piso va, y hay que llamarlo por su nombre.** No cubre un costo —crear
   cuesta 14,6 horas de guardado— sino que raciona: es antispam puro, y es la
   única perilla que el mint tiene, porque la fee ad valorem de §6.1 no muerde
   sobre un activo que vale ~0. **Que sea subible es correcto por el mismo
   motivo.**
2. **"Más depósito, menor tasa" es correcto como observación y peligroso como
   regla.** Sale solo de amortizar el piso sobre más tiempo; postularlo como
   regla de potencia hace otra cosa distinta.
3. **Cualquier α > 0 manda el precio por año a cero**, y abarata 10× (con α=1)
   ocupar el disco de todos los nodos para siempre. Es el fee fijo que §6.1
   rechaza por regresivo, en la dimensión del tiempo.
4. **La forma que cierra es la tarifa en dos partes:** piso al mintear (antispam,
   se quema, subible) **+** depósito de permanencia que se consume quemándose, a
   tasa lineal. La tasa media cae con la vida comprada —que es lo que se pedía—
   pero con piso en el costo real, y con el descuento acotado en vez de creciendo
   sin tope.
5. **El recibo del génesis sigue pudiendo ser gratis**, y no por excepción: por
   su tope duro.
