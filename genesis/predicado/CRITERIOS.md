# Fase 4 — criterios de aprobado

**Escritos el 20/8/2026, antes de la primera línea de la máquina.** Ésa es la regla de la
sección 4 del `ROADMAP.md` y no es burocracia: en este proyecto ya se pagó una vez el precio
de un criterio escrito después de ver el resultado.

Este archivo **no se edita después de correr**. Lo que se mide va a `RESULTADOS.md`, al lado.
Si un criterio queda reprobado, se escribe que quedó reprobado y qué se hace — no se ablanda.

---

## Los tres del roadmap

Vienen textuales de la Fase 4. Acá se los vuelve operables: cada uno con un número y con la
forma exacta de medirlo, para que no haya lugar donde acomodar.

### C1 · El presupuesto entra bajo carga de bloque real, no en benchmark aislado

`f* = 25%` de un bloque de 6 s son **1.500 ms** para verificar las 67 transacciones del
ruleset inicial. En pasos, eso ya está dicho: `techo = 6.716.417` por transacción.

**Aprobado si** un bloque de 67 verificaciones ML-DSA-44 `decode+verify` corre en ≤ 1.500 ms
de reloj en la máquina de referencia, medido **como un bloque**: 67 pares clave/firma
distintos, uno detrás del otro, en el mismo proceso. **Reprobado si** hace falta medir una
verificación y multiplicar por 67 para que dé.

> **Por qué la distinción importa.** Una verificación sola vive en caché caliente con la clave
> ya en L2. Sesenta y siete claves distintas de 1,3 KB no entran, y ésa es la diferencia entre
> el benchmark y el bloque. Es exactamente el error que el criterio del roadmap nombra.

### C2 · El flotante prohibido antes de que el guante corra por primera vez

Es condición **sobre Genesis**, así que no alcanza con que el flotante falle: tiene que ser
imposible que llegue a correr.

**Aprobado si** las dos cosas:

- la máquina es RV32IM y **no tiene F ni D**: no hay ni un opcode de punto flotante que
  decodificar, verificable leyendo el `match` del decodificador entero;
- un programa que contiene una sola palabra de punto flotante **se rechaza en la admisión**,
  con **cero pasos ejecutados**. No se rechaza al llegar a esa instrucción: se rechaza antes
  de empezar.

**Reprobado si** el flotante se detecta recién en ejecución. Un rechazo en ejecución es un
veredicto tardío: ya se gastó presupuesto de bloque para descubrirlo.

### C3 · El conteo de pasos reproduce bit a bit entre x86-64 y ARM64

**Aprobado si** el mismo ELF con las mismas entradas da **el mismo número de pasos y el mismo
hash de salida** en x86-64 y en aarch64. Igualdad exacta; no hay tolerancia.

---

## Los cuatro que se agregaron al leer el intérprete que se iba a reutilizar

El arnés de `test2-interprete/telefono` mide un ISA con un guest **de confianza**. Una máquina
de consenso corre programas de un adversario, y eso son cuatro propiedades más. **Agregar
criterios está permitido; ablandarlos no.** Se escriben acá antes de correr, igual que los otros.

### C4 · Ninguna entrada hace `panic`

El cargador de ELF del arnés indexa sin chequear. Un ELF truncado lo hace `panic`, y un
`panic` en un nodo es una caída — **una transacción malformada cuesta una transacción y tira
un nodo**.

**Aprobado si** un barrido sobre el ELF real —cada truncamiento y una batería de bytes
alterados en las cabeceras— devuelve siempre `Ok` o `Err`, y **nunca** aborta el proceso.

### C5 · El techo corta, y cortar es un veredicto y no un error

Un programa que no termina tiene que parar en **exactamente** `techo` pasos, y las dos partes
de una impugnación tienen que leer lo mismo.

**Aprobado si** un programa en bucle infinito para en `techo` pasos exactos, con veredicto
`TechoExcedido`, y ese veredicto entra al hash del bloque como cualquier otro resultado.
**Reprobado si** el resultado depende de un reloj, de un timeout o de una señal.

### C6 · Fuera de rango es trampa, no envolver

El arnés hace `dirección & MASK`: toda dirección inválida envuelve dentro de la memoria. Es
determinista —así que no bifurca— pero el comportamiento **depende del tamaño de memoria**, y
el tamaño de memoria es un parámetro. Un mismo programa daría resultados distintos en dos
generaciones, y eso rompe I1 en el único lugar donde no se puede.

**Aprobado si** todo acceso fuera de la región declarada es una trampa determinista, y el
tamaño de memoria es una constante de Genesis y no un parámetro del espacio interno.

### C7 · El paso es una unidad honesta *(el que puede reprobar)*

`R_declarado = 300 M pasos/s` se derivó de **una** mezcla de instrucciones: la de ML-DSA. Si
todos los pasos valen uno y una división cuesta veinte veces una suma, un predicado adversarial
hecho de divisiones y de fallos de caché corre mucho más lento por paso — y entonces el techo
promete un presupuesto que no cumple. La cadena se atrasa, de forma determinista, y ninguna
invariante lo ve.

**Aprobado si** la mezcla más lenta que se pueda construir corre a **≥ 300 M pasos/s**.

**Reprobado si** alguna corre por debajo. En ese caso el techo prometía de más y hay dos
salidas, que se eligen después de ver el número y no antes: bajar `R_declarado` al peor caso
—simple, y le cobra a todos el costo del peor— o **pesar el paso** por clase de instrucción con
pesos congelados en Genesis, que es lo que hace el gas y cuesta un decodificador más caro.

> Este criterio existe porque el techo se cerró ayer con el dato de una sola mezcla. Es el
> lugar más probable donde la cuenta de ayer esté mal, así que se mide primero y se escribe el
> resultado sea cual sea.

---

## Lo que esta fase NO contesta

- **Si el predicado de §6.2 sirve para algo que alguien compre.** Eso es la sección 6 del
  roadmap y no es código.
- **Cuánto cuesta el predicado en un nodo real bajo red.** Acá no hay red.
- **Si la máquina chica es la correcta a veinte años.** Es la decisión de I1 y no se falsa con
  una medición.
