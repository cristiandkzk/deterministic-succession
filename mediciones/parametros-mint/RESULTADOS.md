# Los parámetros de §8.5 — cálculo

**Corrido el 18/8/2026.** Reproducir con `python parametros.py`. Sin datos externos.

**La pregunta.** §8.5 quedó escrita con tres parámetros sin fijar: el **piso `F`**,
la **tasa `r0`** y la **duración de la época**. De cada uno se pregunta lo mismo:
¿es una decisión, o es una consecuencia de algo ya medido?

**La respuesta corta: ninguno de los tres es lo que parecía.** La época casi se
disuelve, `F` se deriva, y `r0` no es un número — es una ley de control. Lo que
queda por decidir es **un solo número de política**, y aparece **una colisión
nueva** que no estaba vista.

---

## Supuestos, todos declarados

Los mismos de `expiracion-estado/` y `amortizacion-mint/`, más tres de hardware:

| supuesto | valor | por qué |
|---|---|---|
| entrada de estado | 128 B; presupuesto 4 GB → **33.554.432 slots** | los de las mediciones anteriores |
| verificación de firma | 391 µs, contra un cuarto de núcleo | Test 2, ARM64 con JIT |
| hash en el teléfono | 100 MB/s | conservador para la capa liviana |
| escritura secuencial | 200 MB/s | idem |
| divisibilidad / supply | 1e8 / ~1e6 tokens | la de Bitcoin; el supply del orden de los pools de C7.6 |

**Lo que a propósito no se supone: ningún precio del token en moneda externa.**
Todo lo que dependa de eso queda marcado como *no calculable por el protocolo*, y
esa marca es la mitad del resultado.

---

## A · La época: qué la ata, y qué no

**No la ata el cobro.** Descontar el saldo de cada entrada barriendo el estado
cuesta reescribirlo y rehashearlo entero:

| operación | costo por época |
|---|---|
| escribir 4 GB a 200 MB/s | 21,5 s |
| rehashear 4 GB a 100 MB/s | 42,9 s |
| **total** | **64,4 s** |

Con época de diez minutos eso es el 10,7% del tiempo del nodo — y peor: **vence
todas las pruebas de reactivación en cada época**. No hace falta: guardando
depósito y bloque de creación, el saldo se computa **al leer**, en O(1), sin
escrituras y sin invalidar nada.

**No la ata la cola de desalojo.** En régimen estacionario se desaloja al ritmo
que se crea: 9.193/día = **0,11 por segundo**, con `pop` en 25 comparaciones. No
es una carga.

**La ata una sola cosa: el piso de precio representable.** La tasa por época tiene
que ser un entero de unidades mínimas, o hay que definir redondeo — superficie de
determinismo que no conviene abrir. Ese entero mínimo fija cuán barato puede ser
el guardado:

| época | `r0` mínimo (token/año) | estado lleno, % del supply/año |
|---|---|---|
| 10 minutos | 0,00052560 | **1,76%** |
| 1 hora | 0,00008760 | 0,29% |
| **1 día** | **0,00000365** | **0,0122%** |
| 30 días | 0,00000012 | 0,0004% |

Con época de diez minutos el piso ya cuesta 1,8% del supply por año, que es
demasiado para ser un piso. **Con época de un día quedan tres órdenes de margen.**

> **La época sigue siendo una elección, y es la única de las tres — pero es
> barata: un día la resuelve.**

---

## B · Por qué `r0` no puede ser un número fijo

`r0` es un precio **nominal**; el recurso que raciona —disco por tiempo— es
**real y constante**. Con el token flotando, el precio real del guardado se va en
la dirección equivocada las dos veces. Precio real de una entrada-año con `r0`
congelado:

| año | +50%/año | +20%/año | −20%/año | −50%/año |
|---|---|---|---|---|
| 3 | 3,38× | 1,73× | 0,51× | 0,12× |
| 5 | 7,59× | 2,49× | 0,33× | 0,03× |
| 10 | **57,67×** | 6,19× | 0,11× | **~0** |

Si el token se aprecia, guardar se vuelve prohibitivo y el estado se vacía; si se
deprecia, guardar es gratis y se llena. En los dos casos el protocolo perdió el
control de la única variable que le importa, que es la **ocupación**.

Es el mismo defecto que ya mató al piso nominal de la subasta en C7.10 —*nominal
en una moneda que se aprecia*— y es por lo que toda cadena con fee fijo terminó en
un mercado de fees.

> **Un precio nominal fijo no puede racionar un recurso real bajo una moneda que
> flota.** `r0` tiene que moverse, y sólo hay una variable a la que puede indexarse
> sin romper I2: **la ocupación del estado**, que es un hecho del estado y no una
> lectura de mercado. Es la doctrina de §7.6 aplicada al disco — apuntar a la
> cantidad, dejar flotar el precio.

---

## C · `r0` como ley de control

```
r0(t+1) = r0(t) · (1 + k · (θ − θ*) / θ*)     acotada a ±clamp por época
```

La forma de EIP-1559 aplicada al disco en vez de al gas. Shock de demanda **×3** en
la época 100, con la elasticidad `ε` declarada y barrida porque no se puede medir
sin una red:

| k | clamp | ε | overshoot | vuelta a ±5% |
|---|---|---|---|---|
| 0,05 | 12,5% | 1,0 | 1,16× | 172 épocas |
| 0,125 | 12,5% | 0,5 | 1,09× | 88 épocas |
| 0,125 | 12,5% | 1,0 | 1,07× | 90 épocas |
| 0,25 | 12,5% | 1,0 | 1,04× | no sale de la banda |

El lazo absorbe el shock **sin oscilar**. La ganancia `k` mueve la velocidad, no la
estabilidad; el clamp es lo que impide que un pico de una época mueva el precio.

> **`r0` no es un número que se calcula una vez: es una variable de control.** Lo
> que hay que elegir es `θ*`, y eso sí es política.

---

## D · El piso `F`, derivado

El costo fijo que un objeto le impone a la red aparte del disco es el ciclo
**crear + desalojar**, medido contra el presupuesto del nodo y expresado en horas
de guardado, que es la unidad en la que `r0` está denominado:

| componente | horas de guardado |
|---|---|
| verificar la firma de la creación | 14,6 |
| actualizar el árbol al crear | 0,6 |
| actualizar el árbol al desalojar | 0,6 |
| **F** | **15,8 h = 0,18% de una entrada-año** |

Y `F` queda clavado **por arriba** también, por el propio argumento de §8.5: todo
lo que se cobre por crear **por encima** del costo de crear es un cargo a la
creación, y un cargo a la creación se evade minteando afuera.

> **`F` no es una perilla: es un número.** Ni más —sería cargo a la creación— ni
> menos —sería churn subsidiado.

**Corrige a C7.11.** Allí el piso quedó descrito como *"parámetro antispam, o sea
política"*. Con §8.5 escrita ya no lo es: **el antispam lo hace el depósito**,
porque crear N objetos cuesta N depósitos. El piso sólo cubre el ciclo.

---

## E · La colisión nueva: el canal de quema

Con `r0` indexado a la ocupación, **un atacante que llena estado le sube el precio
a todos** — y como el depósito se consume quemándose, eso acelera la quema de
terceros. La quema entra en `emitido − quemado`, que es lo que lee el trigger
(§7.6). O sea: **se puede pagar por acelerar**.

La pregunta correcta no es si el canal existe —existe— sino cuánta **palanca** da.
Con `s` la fracción del estado que ocupa el atacante y `ε` la elasticidad de la
demanda honesta, el control tiene que subir `r0` por `R = (1/(1−s))^(1/ε)`:

```
palanca = ((1−s)/s) · ((R−1)/R)
```

| s | ε=0,25 | ε=0,5 | ε=1,0 | ε=2,0 |
|---|---|---|---|---|
| 5% | **3,52** | 1,85 | 0,95 | 0,48 |
| 25% | 2,05 | 1,31 | 0,75 | 0,40 |
| 50% | 0,94 | 0,75 | 0,50 | 0,29 |

> **La palanca es del orden de `1/ε`.** Con demanda elástica el atacante nunca
> quema más ajeno que propio. Con demanda **inelástica** —gente que necesita su
> activo vivo al precio que sea— la palanca crece y el canal se vuelve real.

Y `ε` no se puede conocer antes de tener red. Así que **esto no se cierra con un
número**: o se declara como frontera, o se corta el canal excluyendo la quema por
permanencia de la cuenta del trigger — lo segundo con su propio costo, porque
rompe la definición limpia de §7.8, *circulante es emitido menos quemado, sin
excepciones*.

---

## Veredicto

1. **La época casi se disuelve.** No la ata el cobro (la lectura perezosa es O(1)
   contra 64 s de barrido) ni la cola (0,11 desalojos/s). La ata sólo el piso de
   precio representable, y **un día lo resuelve con tres órdenes de margen**.
2. **`F` se deriva:** ~15,8 horas de guardado, 0,18% de una entrada-año. Clavado
   por abajo por el costo del ciclo y por arriba por el argumento anti-evasión de
   §8.5. **Corrige a C7.11:** el antispam lo hace el depósito, no el piso.
3. **`r0` no es un número.** Un precio nominal fijo no puede racionar un recurso
   real bajo una moneda que flota. Tiene que ser una ley de control sobre la
   ocupación — estable con clamp de 12,5% por época.
4. **Queda una sola decisión de política: `θ*`**, la ocupación objetivo. Cuánto
   disco quiere ocupar la cadena en el hardware de entrada.
5. **Y queda una colisión que no estaba vista**, y es lo único que puede voltear
   la ley de control: el canal de quema, con palanca ~`1/ε`. Hay que decidirlo
   **antes** de adoptar la indexación, no después.
