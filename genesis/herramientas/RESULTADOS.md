# Fase 2 · replay contra el historial real de Ethereum

**La bomba de dificultad y sus seis retrasos.** Corrido el 19/8/2026.

```
cd genesis
python herramientas/replay.py        # el informe completo
python verificar.py replay           # los criterios de aprobado
```

> **DATOS VERIFICADOS el 19/8/2026, número por número.** La primera versión de este
> informe corrió con los datos transcriptos de memoria y lo decía arriba de todo:
> *un dato recordado no es un dato de terceros*, y esta fase existe justamente para
> no confundirlos. La pasada de verificación se hizo y **los doce números dieron
> bien**:
>
> | qué | contra qué | resultado |
> |---|---|---|
> | los seis **offsets** de la bomba | el texto de cada EIP en `eips.ethereum.org` | 6/6 |
> | las seis **alturas de activación** | `MainnetChainConfig` en `ethereum/go-ethereum`, `params/config.go` | 6/6 |
> | el bloque de la **fusión** | 15.537.394, 15/9/2022 06:42:42 UTC | ok |
>
> **Y apareció una trampa que conviene dejar anotada: los EIPs no traen la altura de
> activación.** Usan un placeholder (`BYZANTIUM_FORK_BLKNUM`, `FORK_BLOCK_NUMBER`),
> así que quien transcriba sólo del EIP se queda con la mitad del dato. Hacen falta
> **dos** fuentes por fork, y la segunda es la configuración que corren los nodos.

---

# Caso 1 · la bomba de dificultad

## Por qué este caso primero

El roadmap nombra tres —blobs, gas limit, bomba— y se implementó el último de la
lista a propósito. Los otros dos necesitan una **serie**: cuántos blobs por bloque,
cuánto gas usado sobre el límite. Eso no se puede escribir de memoria.

La bomba no necesita ninguna: su efecto es una función determinista de la altura,
escrita en los EIPs, y las seis decisiones humanas son seis alturas. **Todo el caso
se contesta con hechos discretos y citables.**

---

## Medición 1 · el umbral revelado — cero parámetros libres

Cuánto valía el término de la bomba —`2 ** (piso((altura − offset) / 100.000) − 2)`—
en el momento exacto en que los humanos decidieron correrla.

| fork | EIP | altura | fecha | exponente | ¿fork sólo por la bomba? |
|---|---|---|---|---|---|
| Byzantium | EIP-649 | 4.370.000 | 2017-10-16 | **41** | no (bajó la recompensa) |
| Constantinople | EIP-1234 | 7.280.000 | 2019-02-28 | **40** | no (bajó la recompensa) |
| Muir Glacier | EIP-2384 | 9.200.000 | 2020-01-02 | **40** | sí |
| London | EIP-3554 | 12.965.000 | 2021-08-05 | **37** | no (EIP-1559) |
| Arrow Glacier | EIP-4345 | 13.773.000 | 2021-12-09 | **38** | sí |
| Gray Glacier | EIP-5133 | 15.050.000 | 2022-06-30 | **41** | sí |

**Rango 2^37 – 2^41: el término de la bomba varió 16× entre la decisión más
temprana y la más tardía.** No hubo un umbral humano consistente.

Y la hipótesis obvia no explica la dispersión: los forks que existían igual por otro
motivo deberían haber podido correr la bomba antes —les salía gratis— y los
exclusivos deberían haber esperado. Medido: exclusivos `[38, 40, 41]`, mezclados
`[37, 40, 41]`. **No se separan.** Con seis puntos no hay con qué sostener esa
explicación, y se anota como descartada en vez de repetirla.

---

## Medición 2 · el contrafáctico por decisión — un parámetro libre

La comparación correcta, y separarla importa: los humanos tomaron **dos** decisiones
distintas cada vez —*cuándo* correr la bomba y *cuánto* correrla— y una simulación
encadenada las mezcla, porque el error del paso se acumula y contamina la medición
del disparo. Acá el offset lo pone el historial real y lo único que se mide es el
momento.

Regla candidata: *cuando el término de la bomba llegue a `2^40`, correrla.*

| fork | humano | la regla | diferencia | días |
|---|---|---|---|---|
| Byzantium | 4.370.000 | 4.200.000 | −170.000 | 27 |
| Constantinople | 7.280.000 | 7.200.000 | −80.000 | 12 |
| Muir Glacier | 9.200.000 | 9.200.000 | **±0** | **0** |
| London | 12.965.000 | 13.200.000 | +235.000 | 37 |
| Arrow Glacier | 13.773.000 | 13.900.000 | +127.000 | 20 |
| Gray Glacier | 15.050.000 | 14.900.000 | −150.000 | 23 |

**Desvío máximo 235.000 bloques (37 días). Medio, 127.000 (20 días). Una
coincidencia exacta.** Con un único número elegido en Genesis, y sin leer nada más
que la altura y el offset vigente.

**El umbral `2^40` no se eligió a mano: es el que minimiza el desvío máximo en un
barrido de 2^35 a 2^45.** Un grado de libertad contra seis puntos.

### Las dos lecturas de la medición 1 — RESUELTO, y en contra de la optimista

El término varió 16× y aun así un umbral fijo reproduce las seis fechas dentro de
cinco semanas. Las dos cosas son ciertas porque **la bomba es exponencial**: 16× de
dispersión son cuatro pasos de exponente, o sea unos dos meses de calendario.

La primera versión de este informe dejó abierto cuál de las dos lecturas importaba y
dijo qué dato lo cerraría: la **serie de dificultad**. Se bajó el 19/8/2026
(`traer_datos.py dificultad`, 1.154 muestras) y **contestó en contra de la lectura
optimista** — ver la Medición 1b.

---

## Medición 1b · la presión real — con la serie de dificultad

El denominador obvio es el equivocado. Contra la dificultad a secas, el término de la
bomba es 0,00%–0,07% en los seis forks: parece nada. Pero la dificultad **se ajusta**,
y lo que decide si la bomba se siente es cuánto de esa capacidad de ajuste consume:

```
presión = bomba × 2048 / dificultad     ← escalones del ajuste por bloque
```

Por debajo de 1, el ajuste la absorbe dentro de su banda normal y **nadie la nota**.
Por encima, ya no puede: los bloques se hacen más lentos.

| fork | exponente | presión | piso s/bloque | ¿se sentía? |
|---|---|---|---|---|
| Byzantium | 41 | **1,504** | 22,5 | **SÍ** |
| Constantinople | 40 | 0,761 | 15,9 | no |
| Muir Glacier | 40 | 0,916 | 17,2 | no (al borde) |
| London | 37 | 0,037 | 9,3 | no |
| Arrow Glacier | 38 | 0,047 | 9,4 | no |
| Gray Glacier | 41 | 0,315 | 11,8 | no |

**Uno de los seis forks ocurrió con la bomba forzando bloques más lentos. Los otros
cinco fueron preventivos.**

**Y el cálculo tiene validación externa que no se buscó.** Muir Glacier fue un fork de
emergencia, en enero de 2020, porque los bloques treparon a ~17 s. El modelo —que no
sabe nada de esa historia y no se ajustó para nada— da **17,2 s**. Es la única
comprobación independiente que tiene esta medición y la pasa.

**La dispersión, medida en la unidad que importa, es peor: 41×, no 16×.** De 0,037 a
1,504. Y no es ruido: hay una tendencia temporal. Los tres primeros forks (2017-2020)
van de 0,76 a 1,50; los tres últimos (2021-2022), de 0,04 a 0,32. **Los humanos
aprendieron a actuar cada vez más temprano**, y eso es exactamente lo que una regla
escrita en Genesis no puede hacer.

> **Esto refuerza el problema, no la solución.** Un umbral fijo elegido en 2015 habría
> sido el equivocado en los dos extremos: demasiado tardío para el criterio de 2017,
> demasiado temprano para el de 2022. La Medición 2 muestra que **un** número reproduce
> las seis fechas dentro de cinco semanas; la 1b muestra que ese número no corresponde
> a un criterio estable, sino al promedio de un criterio que se estaba moviendo. Es la
> primera frontera de §10.1 con un caso medido: *escribir la regla por adelantado no
> elimina el fork, lo mueve al caso en que la regla escrita es la equivocada* — y acá
> se ve además **cómo** se vuelve equivocada: no porque el mundo cambie, sino porque
> los que la escribieron aprenden.

## Medición 3 · la cota — dónde la diferencia sí se puede llamar *mejor*

| | pico del término de la bomba |
|---|---|
| bajo el proceso humano | **2^41** |
| bajo la regla (umbral 2^40) | **2^40** |

La regla acota **por construcción**: dispara en cuanto se alcanza el umbral, así que
el término no puede pasarlo. El proceso humano llegó al doble de esa cota, y podría
haber llegado a cualquier cosa — nada lo impedía, sólo la atención de un grupo de
personas.

Es la única de las cuatro mediciones donde *mejor* significa algo verificable: no es
que la regla haya acertado más, es que **tiene una garantía y el proceso humano tenía
un resultado.**

---

## Medición 4 · el replay encadenado — dos parámetros libres

Acá la regla elige también **cuánto** retrasar, con un paso fijo, y ahí se separa del
historial: la mejor combinación del barrido deja errores de hasta 2,2 millones de
bloques (unos 354 días).

El motivo está a la vista en los incrementos que los humanos eligieron:

```
3.000k · 2.000k · 4.000k · 700k · 1.000k · 700k
```

**Ningún paso fijo los reproduce.** Y tiene una explicación mecánica: cada retraso lo
dimensionaron para llegar *hasta el próximo fork ya planificado*, que es una variable
que una `TRANSITION_RULE` no lee y no debería leer.

> **Una advertencia sobre cómo leer esta tabla.** El barrido penaliza que la regla
> dispare más veces que los humanos, y esa penalización supone que una transición
> cuesta lo que cuesta un hard fork. **No es así, y ésa es toda la tesis del diseño.**
> Disparar más seguido mantiene la bomba más chica y no le cuesta a nadie una
> coordinación. La medición está igual, con el sesgo declarado, porque quitarla
> sería elegir la métrica que favorece la conclusión.

---

## Lo que el replay **no** demuestra

- **No demuestra que la regla hubiera sido mejor.** En timing es un empate con
  ventaja de cinco semanas para cualquiera de los dos, según el fork.
- **No demuestra que Ethereum debería haberla escrito.** En 2015, el número `2^40`
  no estaba disponible: se lo conoce ahora, mirando hacia atrás. La medición 1 dice
  precisamente eso — **los humanos nunca convergieron a ese número**, y una cadena
  que hubiera escrito la regla en Genesis habría tenido que elegirlo a ciegas. Es la
  primera frontera de §10.1 instanciada por segunda vez, después de la EDA de
  Bitcoin Cash: *escribir la regla por adelantado no elimina el fork, lo mueve al
  caso en que la regla escrita es la equivocada.*
- **Lo de los cero forks no es un hallazgo, es una definición.** La regla no necesita
  fork porque una transición no es un fork; contarlo como resultado del replay sería
  hacer pasar una tautología por medición.

## Lo que sí queda demostrado

- **La regla candidata es una `TRANSITION_RULE` de verdad**: pasa los mismos
  predicados de I2 que las reglas del protocolo, se computa desde dos números que
  están en la cadena —altura y offset— y no lee ni precios, ni relojes, ni votos.
- **La aproximación de I2 no es una figura retórica.** Como el progreso avanza un
  bloque por bloque, la distancia al disparo es **exacta y no una proyección**:
  Ethereum podría haber publicado una cuenta regresiva perfecta al próximo retraso
  de la bomba, con años de anticipación. En el bloque 10.000.000 —mayo de 2020— la
  cadena podía decir *faltan 3.200.000 bloques*, y el fork de London llegó 235.000
  bloques antes de esa fecha.
- **Una decisión de implementación quedó validada contra un caso real.** C9.3 decidió
  que el umbral se mueve y el progreso no se resetea. Acá se ve por qué no era un
  capricho: el exponente de la bomba **baja** en cada retraso, así que usarlo como
  progreso habría violado I2 seis veces.

---

---

# Caso 2 · el `blobSchedule` de Ethereum

**Corrido el 19/8/2026** con la serie bajada el mismo día. `python herramientas/replay_blobs.py`.

Es el caso que el roadmap nombra primero y el que tiene el cliente más cerca del
diseño. Cuatro decisiones verificadas: target **3 → 6 → 10 → 14** en 22 meses.

## Dos avisos sobre el dato, y los dos cambian la medición

**`excessBlobGas` no compara a través de Fusaka.** Era el observable natural —el
acumulador que la propia cadena lleva para cobrar el fee de blobs— y el traedor lo
baja por eso. Pero **EIP-7918** cambió su regla de actualización: cuando el fee de
blobs cae bajo un piso atado al costo de ejecución, el exceso deja de decaer y pasa a
crecer por `blob_gas_used × (max − target) / max`. Se ve en la serie: bajo target 14,
con la demanda al 31%, **el exceso sube igual**. La medición usa entonces
**ocupación** (blobs contra target), que significa lo mismo antes y después.

**BPO1 y BPO2 no son dos decisiones: son un cronograma.** Los dos se anunciaron
juntos el 6/11/2025, en el anuncio de mainnet de Fusaka, **antes de que Fusaka
activara**. Leerlos como dos respuestas independientes a la demanda sería leer mal el
dato — y explica la mitad del resultado.

## Medición A · la ocupación bajo cada target — cero parámetros libres

| target vigente | desde | muestras | ocupación media | pico (30 d) | % del tramo saturado |
|---|---|---|---|---|---|
| Cancun, t=3 | 2024-03-13 | 601 | **83%** | 129% | 64% |
| Prague, t=6 | 2025-05-07 | 309 | **83%** | 106% | 66% |
| BPO1, t=10 | 2025-12-09 | 41 | **43%** | n/d | n/d |
| BPO2, t=14 | 2026-01-07 | 323 | **31%** | 48% | 0% |

*«saturado» = media móvil de 30 días ≥ 80%. «n/d» = el tramo dura menos que la
ventana: BPO1 duró 29 días y no se puede medir sostenido nada — lo cual ya dice algo.*

**Los dos primeros targets corrieron saturados; los dos últimos, ni cerca.** La
demanda dejó de ser la restricción exactamente cuando llegaron los BPO.

## Medición B · el contrafáctico por decisión — un parámetro libre

Regla candidata: *subir el target cuando la ocupación sostenida (30 días) pase el
umbral*. El target vigente lo pone el historial, así que no hay un segundo parámetro
contaminando al primero.

| decisión | humano | la regla (≥80%) | diferencia |
|---|---|---|---|
| Prague | 2025-05-07 | 2024-04-19 | **los humanos tardaron 383 días más** |
| BPO1 | 2025-12-09 | 2025-06-30 | los humanos tardaron 162 días más |
| BPO2 | 2026-01-07 | **nunca dispara** | la ocupación de t=10 era 43% |

**El resultado no depende de elegir bien el umbral**: entre 70% y 90% la conclusión
no cambia — sólo cuánto tardaron de más (390, 383 y 306 días para Prague).

## La lectura, y tiene dos lados opuestos

**Donde la restricción era la demanda, la regla gana por muchísimo.** La ocupación
llegó al 80% del target **37 días después de Dencun**, se quedó saturada el 64% del
tiempo y llegó a picos del **129% del target** —o sea, demanda sostenida por encima de
lo que el parámetro apuntaba, que es exactamente cuando el fee de blobs castiga a los
rollups—. Ethereum tardó **383 días** en responder. Ésa es la cuenta de la
coordinación, medida, sobre el parámetro cuyo propio EIP dice que el método actual
*"no es lo bastante ágil"*.

**Donde la restricción no era la demanda, la regla es ciega — y habría acertado por
el criterio equivocado.** BPO1 y BPO2 subieron el target a 10 y a 14 con la demanda al
43% y al 31%. No fue una respuesta a la demanda: fue posible porque Fusaka trajo
PeerDAS. Y *"la red ahora puede transportar más sin degradarse"* **no es un hecho del
estado**: I2 dice que el trigger sólo lee estado, así que una regla de demanda no
habría subido nada. Habría tenido razón según su propio criterio y le habría errado a
la red.

> **Y el filo verdadero es anterior a eso.** ¿Podría la regla haber subido el target a
> 6 en abril de 2024? Sólo si el 6 estaba en el espacio declarado en Genesis **y era
> seguro**, y no era seguro hasta que existió PeerDAS. El techo del espacio de
> descendientes está acotado por una tecnología que todavía no existía. Es la primera
> frontera de §10.1 en su forma más dura para este caso: **no es que la regla escrita
> pueda ser la equivocada — es que el espacio declarado puede quedar corto por algo que
> nadie podía anticipar.**

## Lo que se ve mirando las cuatro decisiones juntas

En 22 meses, Ethereum recorrió tres etapas sobre este mismo parámetro:

1. **recalibrar dentro de un fork grande** (Dencun, Pectra);
2. **un mecanismo de fork liviano** para no tener que esperar al próximo fork grande
   (EIP-7892, `Final`);
3. **un cronograma de subas escrito de antemano** y ejecutado por calendario (BPO1 y
   BPO2, anunciados juntos).

**El tercer paso está a una propiedad del diseño de este paper**: el cronograma se
escribe por adelantado, sí, pero el disparo es **el reloj y no el estado**, y ejecutarlo
sigue necesitando un fork. Es exactamente la forma de BIP-103, que §12 ya analiza y
descarta como cierre del hueco por el mismo motivo.

## Estado del caso 2

**Aprobado como diferencia explicada, no como empate.** El criterio pedía *o reproduce
la decisión, o queda escrito exactamente dónde difiere y si era mejor o peor*: difiere
en las tres decisiones, la diferencia está medida en días, y el *mejor o peor* tiene
respuesta distinta según qué restringía — velocidad a favor de la regla, capacidad en
contra, y las dos con el número al lado.

---

---

# Caso 3 · el gas limit de Ethereum

**Corrido el 19/8/2026.** `python herramientas/replay_gas.py`.

**Es el único de los tres donde el mecanismo del paper no compite contra un fork.** El
gas limit ya es un parámetro que **cada validador vota bloque a bloque**, con un tope
de 1/1024 de cambio por bloque: una coordinación liviana, descentralizada y sin fork,
que ya funciona. Y el resultado es el más incómodo de la fase: **para este parámetro no
hay trigger admisible**, y no por falta de ingenio.

## Medición A · la trayectoria humana — cero parámetros libres

| desde | hasta | límite | duración |
|---|---|---|---|
| 2022-09-15 | 2025-01-31 | 30,0M → 30,6M | **870 días** |
| 2025-01-31 | 2025-02-05 | 30,6M → 35,8M | 4 días |
| 2025-02-05 | 2025-07-18 | 35,8M → 36,5M | 164 días |
| 2025-07-18 | 2025-07-22 | 36,5M → 44,9M | 4 días |
| 2025-07-22 | 2025-11-25 | 44,9M → 48,8M | 126 días |
| 2025-11-25 | 2025-11-27 | 48,8M → 59,6M | 1 día |
| 2025-11-27 | 2026-08-19 | 59,6M → 60,0M | 265 días |

**28 meses congelado en 30M, y después el doble en 300 días.** La forma de una
coordinación off-chain: nada, nada, nada, y de golpe.

## Medición B · la ocupación no lleva información — cero parámetros libres

| | |
|---|---|
| ocupación media | **50,9%** |
| rango de la media móvil (60 muestras) | 42,8% – 59,3% |
| base fee mediano | 36,43 → 0,056 gwei (**650× de caída**) |
| **correlación ocupación / base fee** | **−0,021** |

EIP-1559 fija el target en la mitad del límite y mueve el base fee hasta que el uso
vuelve ahí. **Con el fee moviéndose 650×, la ocupación no se mueve.**

> **Esto cierra una puerta que el paper tenía abierta.** C7.13 concluyó que `r0` no
> podía ser un número nominal y que la salida era **una ley de control indexada a la
> ocupación**. Acá se ve que esa salida no está disponible cuando el recurso ya lo
> raciona un mercado de fees: la ocupación queda clavada por construcción y **no
> índica nada**. No es que la correlación sea débil — es cero, sobre 1.026 muestras y
> cuatro años.

## Medición C · la única señal es el fee, y ninguna de sus dos formas sirve

**Forma nominal.** El fee mediano cayó **650×**. Cualquier umbral en gwei elegido en
Genesis deja de significar lo que significaba. Es literalmente el hallazgo de C7.13,
confirmado en otro parámetro y con datos de terceros.

**Forma adimensional** —el fee contra su propia mediana anual, que es escalable y sale
del estado—. Con `k = 1,5` dispara **cuatro veces, todas entre diciembre de 2023 y
abril de 2024**, con el límite todavía en 30M y el fee entre 31 y 35 gwei: **catorce
meses antes** de que los humanos lo movieran por primera vez. Ahí acierta.

Pero pierde la noción de *caro*:

```
k = 1,0 · 2026-05-01 · fee 0,261 gwei · límite 60M · ratio 1,06
```

**Dispara otra vez porque el fee se duplicó de 0,08 a 0,26 gwei**, que es
económicamente absurdo: sin referencia absoluta, *caro* es sólo *más que recién*. Con
`k` más alto el trinquete desaparece — y con él desaparecen también los disparos de
2023, que eran los correctos.

## Sobre leer un precio, que es la duda obvia

§7.6 prohíbe que el trigger lea **precios de mercado on-chain** —ratios de pool,
profundidad, volumen— porque permitiría *comprar una transición* moviendo un pool con
capital prestado. **El base fee no es eso:** lo computa el protocolo desde la
ocupación, y empujarlo exige llenar bloques y quemar el fee, así que cae del lado del
canal de quema que §10.2 ya declara como frontera acotada. Lo que lo descalifica no es
de dónde sale — es que es **nominal**.

Y la regla candidata **pasa los predicados de I2** del protocolo. El problema no está
en la procedencia del dato ni en la forma del trigger: está en que **el único
observable con información sobre este recurso es un precio, y ningún precio nominal
sirve como setpoint de largo plazo.**

## Estado del caso 3

**Aprobado como diferencia explicada, y es la diferencia más dura de la fase.** Donde
la señal existía, la regla habría actuado 14 meses antes que una coordinación
off-chain que ya funcionaba sin forks. Pero **el trigger que haría falta no existe en
el marco del paper**: la cantidad está vacía por diseño de EIP-1559, el precio nominal
caduca, y la forma adimensional ratchetea.

Es §10.3, problema abierto 2 —*el nivel nominal del que parte `r0`*— apareciendo en un
segundo parámetro, independiente, con datos de terceros, y con la salida propuesta en
C7.13 empíricamente descartada.

# Estado de la Fase 2 — CERRADA, tres de tres

Los tres casos corridos y escritos, los tres aprobados por la vía que el criterio
admite cuando no hay empate: **la diferencia está medida y explicada.**

| caso | ¿reproduce? | dónde difiere |
|---|---|---|
| **1 · bomba de dificultad** | **sí**, las seis decisiones dentro de 37 días con un solo parámetro, y una exacta | el umbral que lo logra es el **promedio de un criterio que se estaba moviendo**: 41× de dispersión, cinco de seis forks preventivos |
| **2 · blobSchedule** | **no, y para los dos lados** | **383 días más rápida** donde la restricción era demanda; **ciega** donde era capacidad (PeerDAS) |
| **3 · gas limit** | **no hay regla admisible** | la cantidad está vacía por EIP-1559 (correlación −0,02), el precio nominal cae 650×, y la forma adimensional ratchetea |

## Lo que la fase produjo, que es lo que §11 pedía

**Evidencia que no escribió el autor del diseño.** Cinco cosas, y tres van en contra:

1. **la cuenta de la coordinación es real y tiene número**: 383 días de demora sobre
   blobs saturados al 129% del target; 870 días con el gas limit congelado. No es una
   figura retórica del paper — es lo que le pasó a una cadena que factura miles de
   millones;
2. **el mecanismo es estructuralmente mejor reaccionando y estructuralmente incapaz de
   anticipar.** Los casos 1 y 2 lo muestran desde lados distintos: el criterio humano
   se movía mientras aprendían; y las dos últimas subas de blobs respondieron a una
   capacidad nueva que no es un hecho del estado;
3. **§10.1 tiene ahora casos medidos, y una forma más dura que la escrita**: no sólo la
   regla escrita puede ser la equivocada — **el espacio declarado en Genesis puede
   quedar corto** por una tecnología que no existía al declararlo;
4. **§10.3, problema abierto 2, tiene una segunda instancia independiente**, y la
   salida que C7.13 había propuesto —indexar a la ocupación— queda **empíricamente
   descartada** para cualquier recurso que ya raciona un mercado de fees;
5. **el cliente se está acercando solo.** En 22 meses Ethereum fue de recalibrar dentro
   de un fork grande, a un mecanismo de fork liviano (EIP-7892, `Final`), a un
   cronograma escrito de antemano y ejecutado por calendario. **Lo que le falta para
   llegar es exactamente I2**: disparo desde el estado y no desde el reloj.

## Lo que la fase **no** produjo

**No produjo evidencia de que el diseño sea mejor.** Dos de los tres casos dan
hallazgos en contra, y el tercero da un empate con un asterisco. Lo que produjo es algo
más útil en esta etapa: **los tres lugares exactos donde el mecanismo se rompe contra
el mundo real**, cada uno con su número al lado y su prueba anclada, para que ninguno
se pueda olvidar sin que la suite se caiga.

## Reproducirlo

```
cd genesis
python herramientas/replay.py        # caso 1 · la bomba
python herramientas/replay_blobs.py  # caso 2 · el blobSchedule
python herramientas/replay_gas.py    # caso 3 · el gas limit
python verificar.py replay           # los criterios de aprobado de los tres
```

Las tres series están en `datos/` (144 KB, con procedencia adentro), así que **todo
corre offline**. Para volver a bajarlas: `python herramientas/traer_datos.py
blobs|gas|dificultad` — endpoint público, sin clave.
