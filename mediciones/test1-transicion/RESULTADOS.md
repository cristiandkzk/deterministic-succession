# Test 1 · La transición concreta

> Estado: **cerrado. Pasa, con una corrección al alcance.**
> Hay transiciones reales que cumplen las tres condiciones. La principal está viva
> y documentada por los EIPs de la cadena que la necesita. Pero ninguna de las
> encontradas necesita el intérprete ni las generaciones encadenables. Ver §5.

Lo que pide §12: *"nombrar **una** transición real que cumpla las tres condiciones a la
vez"*. Las condiciones, textuales:

1. que su **trigger se compute desde el estado** de la cadena — y, por I2, que sea
   monótono en su aproximación y exponga cuántos bloques faltan al ritmo actual;
2. que se exprese como **selección dentro de un espacio de parámetros definible hoy**
   — por I1, sin código de nodo nuevo;
3. que **alguna cadena real la haya necesitado y no haya podido tenerla**.

No hace falta escribir protocolo: es una búsqueda, como Test 3, y se corrió con el mismo
método de dos vocabularios.

> **Nota del 19/8/2026 — I2 se reformuló después de correr este test, y la condición 1
> quedó escrita con su letra vieja.** No se reescribe: un criterio de un test cerrado se
> anota, no se acomoda. **El resultado no cambia**, y por un motivo que conviene decir:
> los tres clientes encontrados son recalibraciones de parámetros agregados —blobs, gas
> limit, bomba de dificultad— y los tres disparan por **aproximación observable**, que es
> la forma de I2 que la condición 1 ya exigía. La forma que se agregó —*capacidad
> demostrada*— habilita triggers que este test no buscó, así que si algo hace, es ampliar
> el universo de clientes posibles, nunca invalidar los encontrados.

---

## 1. Método

Dos vocabularios, que es la precaución que `patron-construir-antes-de-medir` dejó escrita
y que en Test 3 fue la diferencia entre encontrar a Drake y no encontrarlo:

- **gobernanza / hard fork** — quién decide un cambio de reglas y qué cuesta coordinarlo;
- **recalibración de parámetros** — *protocol constants*, *parameter-only upgrade*,
  *scheduled parameter growth*, ajuste automático sin fork.

El segundo vocabulario es el que trajo los tres casos que califican. El primero solo
devolvió lo que Test 3 ya había cerrado. **La búsqueda por "gobernanza" sistemáticamente
encuentra competidores; la búsqueda por "parámetros" es la que encuentra clientes.** Vale
anotarlo para la próxima.

Cada candidato se evaluó contra las tres condiciones por separado, y se escribieron
también los que fallan (§6), que es donde está la mitad del valor del test.

---

## 2. Caso primario · Capacidad de datos de Ethereum (blobs)

**El único de los tres cuya necesidad está viva hoy.** Por eso es el primario, aunque no
sea el que mejor ajusta a I2.

### Condición 2 — el espacio: no hay que definirlo, ya está definido

EIP-7892 (*Blob Parameter Only Hardforks*) introdujo un objeto `blobSchedule` con tres
enteros:

| parámetro | qué es |
|---|---|
| *blob target* | blobs esperados por bloque |
| *blob limit* | máximo por bloque |
| *blob base fee update fraction* | la velocidad de ajuste del precio |

Eso es, literalmente, *"un punto de un espacio que el nodo ya sabe ejecutar"* (I1). No hay
que argumentar que el espacio sea definible: **Ethereum ya lo escribió, con nombre, en un
archivo de configuración, en producción**. Y son parámetros internos —capacidad, no
formato— así que no tocan I5.

### Condición 3 — la necesitó, y la evidencia es preferencia revelada

Ethereum no solo necesitó estos cambios: **construyó maquinaria dedicada para abaratarlos**.
La motivación de EIP-7892, textual:

> *"Large, infrequent blob parameter changes create high costs and inefficiencies."*
>
> *"Full Ethereum hard forks require significant coordination, testing, and implementation
> changes beyond parameter adjustments."*

Y aun así el disparo quedó humano: los BPO se activan **por timestamp hardcodeado en la
configuración del cliente**. En mainnet corrieron dos, con fecha elegida por personas y
embarcada en releases:

| fork | fecha | target / max |
|---|---|---|
| Fusaka | 3/12/2025 | 6 / 9 |
| BPO1 | 9/12/2025 | 10 / 15 |
| BPO2 | 7/1/2026 | 14 / 21 |

**El mismo patrón se repitió en otro parámetro cuatro meses después.** EIP-8261
(*Gas Limit Schedule*, 11/5/2026) propone un cronograma de gas limit por época, en un
archivo legible por máquina, porque los defaults actuales son —textual— *"release-scoped
rather than epoch-based: a new default activates whenever an operator happens to update
their node, not at a network-coordinated epoch."*

Y entonces se detiene justo antes del borde:

> *"Validators retain sovereignty; the schedule serves as a coordinated default and
> recommendation, **not a consensus rule**."*

**Ese es el hallazgo más nítido del test.** En mayo de 2026, la cadena de contratos más
grande escribe un cronograma de parámetros y decide explícitamente no hacerlo vinculante.
La necesidad está documentada por sus propios EIPs; lo que falta es exactamente la pieza
que este diseño pone en Genesis.

### Condición 1 — el trigger, que es lo que hay que construir

Los insumos ya son estado: `excess_blob_gas` viaja **en el header del bloque** y el blob
base fee se deriva de él. Lo que no cumple I2 es el fee, que no es monótono.

La forma que sí cumple I2 no necesita inventar nada: **un contador de bloques en o por
encima del target desde la última transición**. Es monótono por construcción, y la
distancia consultable —*cuántos bloques faltan al ritmo actual*— sale de la tasa de
llenado reciente.

Una propiedad que aparece sola y conviene anotar: **avanzar ese contador cuesta plata.**
Estar por encima del target sube el blob base fee exponencialmente, así que forzar el
trigger con demanda inducida se paga al precio que el propio mecanismo impone. Es el
patrón de §6.4 —el vigilante financiado por el botín, visto del otro lado— y acá sale
gratis, sin diseñar nada. *Acotar la afirmación:* es una **cota de costo**, no una prueba
de resistencia. Nadie corrió el número.

---

## 3. Caso corroborante · La bomba de dificultad (Ethereum, seis veces)

**El mejor ajuste a I2 de todo lo encontrado, y el registro más caro de lo que cuesta que
falte la otra mitad.**

### Las tres condiciones

1. **Trigger:** perfecto. La bomba es una función pura de la altura —`2^((block−offset)/100000)`—
   así que la distancia a cualquier umbral de tiempo de bloque es exactamente computable y
   monótona. La cadena podía publicar *"faltan N bloques para bloques de 20 s"* con
   precisión. De hecho **el propio EIP-2384 hace esa cuenta a mano**, en prosa.
2. **Espacio:** un entero. Literalmente uno:
   `fake_block_number = max(0, block.number − 9_000_000)`.
3. **Necesitada y no disponible:** seis veces en cinco años.

| EIP | fork | fecha | delay |
|---|---|---|---|
| 649 | Byzantium | 2017 | ~3 M bloques |
| 1234 | Constantinople | 2019 | ~5 M bloques |
| 2384 | Muir Glacier | ene 2020 | ~9 M bloques (4 M más) |
| 3554 | London | 2021 | a dic 2021 |
| 4345 | Arrow Glacier | dic 2021 | a jun 2022 |
| 5133 | Gray Glacier | jun 2022 | 700 k bloques |

### Muir Glacier es el caso más filoso del test

La bomba se adelantó respecto de lo estimado. Los tiempos de bloque pasaron de ~13,1 s a
~14,3 s, y el EIP proyectaba 20 s para fin de diciembre y 30 s+ desde febrero. Se anunció
el **23 de diciembre de 2019** como precaución de emergencia; los desarrolladores tuvieron
**menos de tres semanas**, sobre las fiestas, para coordinar un hard fork de mainnet cuyo
contenido era **un número**. Activó en el bloque 9 200 000.

La cita de Tim Beiko es el test entero en una línea:

> *"We thought we had months until it kicked in, but those numbers were wrong."*

Lo valioso no es que faltara tiempo. Es que **el humano en el lazo no aportó juicio y sí
aportó error**: el número mal estimado era una cantidad que la cadena mide exactamente. Un
`TRANSITION_RULE` escrito sobre la misma fórmula no podía equivocarse, porque la fórmula
*es* la fuente del número.

### La objeción que hay que escribir

La necesidad era **autoinfligida**. La bomba existía para forzar una transición, y lo que
se recalibró seis veces fue la bomba misma. Un lector puede decir con razón que eso no es
una transición que la cadena necesitó, sino un parche a un dispositivo instalado a
propósito.

La respuesta no debilita el caso: lo enfoca. **La bomba es la fila 3 de la tabla de §1** —
*obsolescencia forzada*— y es el ancestro más cercano en producción de `TRANSITION_RULE`.
Su modo de falla, repetido seis veces, es exactamente el que este diseño ataca: *disparo
determinista, sucesor humano*. El test no encontró un cliente hipotético; encontró **la
mitad del mecanismo ya desplegada**, y la factura de lo que costó que le faltara la otra.

Segunda objeción, y es la razón por la que este caso no es el primario: post-Merge la
bomba es irrelevante. **Ese cliente es histórico.**

---

## 4. Caso corroborante · La emisión terminal (el A/B más limpio)

Dos cadenas, la misma transición, resultados opuestos según se haya escrito antes o no.

**Monero la escribió por adelantado y la obtuvo gratis.** El piso
—`FINAL_SUBSIDY_PER_MINUTE`, 0,6 XMR por bloque— estaba en el código años antes. La curva
de emisión bajó hasta tocarlo en 2022 y la emisión terminal quedó activa **sin fork y sin
que nadie decidiera nada en ese momento**. Es la condición 1 en su forma degenerada
—trigger = la altura, que es estado— y la condición 2 en la suya: un espacio de un punto.

*(Las fuentes discrepan en el bloque exacto —2 628 888, fin de mayo, contra 2 641 623,
9 de junio— y la discrepancia no afecta nada de lo que se afirma acá.)*

**Bitcoin no la escribió y hoy no puede tenerla.** El presupuesto de seguridad es la
necesidad no resuelta más discutida de la industria, y la propuesta de emisión terminal de
Peter Todd chocó contra que 21 millones es la única regla que ningún desarrollador puede
revisar; Adam Back la llamó una trampa disfrazada de lógica técnica. El propio Todd admite
que la ventana es *"en 10-20 años"*.

Ese es **el "no pudo tenerla" más fuerte que apareció**, y no por la razón esperable: no
falta ingeniería —la ingeniería es una constante en una función de reward, y Monero la
tiene corriendo— y aun así la transición es imposible. Lo que falta es **legitimidad**, y
la legitimidad se compra en el bloque 0 o no se compra.

Es exactamente lo que sostiene §5, y es el argumento comercial del diseño en una frase: la
ventana para escribir la regla de sucesión es Genesis.

**Debilidad honesta:** la emisión terminal de Monero es una **constante**, no una selección
en función del estado. Ejercita el disparo, no el sucesor.

---

## 5. Veredicto, y la corrección al alcance

**Test 1 pasa.** Existen transiciones reales que cumplen las tres condiciones a la vez, y
la principal está viva, en producción, y documentada por los EIPs de la cadena que la
necesita. El mecanismo tiene cliente: el riesgo dominante de §12 no se materializó.

Pero —igual que en Test 3— **el cliente es más chico que la vidriera**. Contra las piezas
del diseño:

| pieza | ¿la piden los clientes encontrados? |
|---|---|
| §3 disparo/lock-in/activación con `Δ` | **sí**, los tres |
| I2 trigger desde el estado, monótono, con aviso | **sí**, los tres |
| I5 aditividad en la interfaz | no aplica — los tres son parámetros internos |
| selección del sucesor en función del estado | **A y B sí**; C es una constante |
| intérprete (I1 fuerte, espacio infinito) | **ninguno** |
| generaciones encadenables | **ninguno** |
| §6.6 evolución criptográfica | **ninguno** |

Cuatro consecuencias, en orden de cuánto duelen:

1. **§6.6 sigue sin cliente demostrado.** Los tres casos son parámetros internos
   —capacidad, emisión, tiempos—; ninguno es criptográfico. Y §6.6 ya era la aplicación
   más débil por la tensión de CONTEXTO §3.2. **El orden de exposición del paper está
   invertido respecto de dónde está la demanda:** la sección de vidriera es la única sin
   cliente, y las secciones aburridas son las que tienen tres.
2. **Ninguno necesita el intérprete.** Los tres espacios son enteros: target, max, update
   fraction, offset, tasa de emisión. Se cubren con una lista finita —la I1 débil—, que es
   la que **no** paga el precio declarado en §10.1 (*"el conjunto de futuros posibles deja
   de ser auditable"*) ni el de *"punto único de falla que no se puede parchear nunca"*. El
   intérprete es necesario para §6.6 y, por lo que muestra este test, solo para §6.6.
3. **Ninguno necesita generaciones encadenables** — son recalibraciones repetidas dentro
   del mismo espacio, no una sucesión de espacios. Y encadenable es precisamente el
   diferenciador declarado contra Drake en §6.6. O sea: **el diferenciador contra el
   competidor es la parte que el cliente encontrado no pide.**
4. **La selección con contenido real aparece en un solo caso.** En B el sucesor era un
   entero que un humano calculó mal; en C es una constante. Solo en A la selección tiene
   sustancia —cuánto subir el target depende de salud de propagación medida— y por eso
   Ethereum no lo resolvió con un cronograma fijo al estilo BIP-101.

**El mecanismo mínimo que cubre a los tres clientes es §3 + I2 con espacio finito.** Sin
intérprete, sin encadenamiento, sin §6.6. Es una versión mucho más chica del diseño, mucho
más barata de defender —no paga ninguna de las fronteras caras de §10.1— y es la que tiene
demanda escrita por terceros. La versión grande sigue siendo especulativa; esto no la
refuta, pero deja de sostenerla el mismo argumento.

---

## 6. Revisado y descartado (para que nadie repita el trabajo)

| candidato | falla | por qué |
|---|---|---|
| **Gas limit de Ethereum** (±1/1024 por bloque) | 1 | Se mueve sin fork, pero por **señalización de los proposers**: es un voto, prohibido por I2. Contraejemplo útil — el único parámetro que Ethereum hizo ajustable sin fork, lo hizo ajustable por voto. |
| **Tamaño de bloque dinámico de Monero** | 3 | Cumple 1 y 2 (mediana de los últimos 100 bloques + penalidad al minero) pero **la tuvo**: no le faltó. Es control de lazo cerrado *dentro* de un ruleset, no conmutación de ruleset. Prueba de existencia de que el espacio funciona; no es cliente. |
| **Halving de Bitcoin** | 3 | Automático desde el bloque 0. Mismo caso. |
| **Fondo de desarrollo de Zcash** | 2 | El disparo sí es estado (el halving), pero el sucesor es *quién cobra*. Eso no es un punto de un espacio de parámetros: es una decisión política. |
| **Parámetro `k` de Cardano** | 3 | Recalibración a partir de métricas on-chain, pero Cardano **puede** cambiarlo por gobernanza. Falla el "no pudo tenerla" en sentido fuerte. |
| **Tamaño de bloque de Bitcoin** | 3 (disputada) | La necesidad más famosa, pero **contestada**: la facción conservadora sostiene que el cambio no era necesario. Un caso cuya condición 3 es objeto del propio conflicto no sirve como evidencia. Lo que sí aporta está en §7. |

### El contracaso que hay que declarar: EDA → DAA de Bitcoin Cash

BCH **sí** llevaba una regla automática de ajuste de dificultad escrita de antemano —la
*Emergency Difficulty Adjustment*: −20% si entre el bloque −6 y el −12 pasaban más de 12
horas— y **estaba mal**. Osciló, corrió miles de bloques por delante de Bitcoin y desplazó
el cronograma de emisión. Se reemplazó por **hard fork humano** el 13 de noviembre de 2017.

Es la instancia exacta de la primera frontera de §10.1: *"la adaptación está acotada a lo
que Genesis anticipó"*. Escribir la regla por adelantado **no elimina el fork — lo mueve al
caso en que la regla escrita es la equivocada**, y ahí no hay override por construcción.

También es evidencia a favor de dos exigencias de I2 que podrían parecer decorativas: la
EDA no era monótona y no avisaba. Las dos cosas que I2 pide son las dos que le faltaban.

---

## 7. Prior art que apareció por esta vía (para el registro de Test 3)

**BIP-103** (Pieter Wuille, 2015). Reemplaza el límite de tamaño de bloque por una función
determinista: **+4,4% cada ~97 días** (17,7% anual) hasta 2063, evaluada sobre la mediana de
los timestamps de los 11 bloques anteriores, **sin voto de mineros**. Es sucesión de
parámetros escrita de antemano y sin votación, en Bitcoin, diez años antes.

No cierra el hueco declarado: **el disparo es tiempo, no estado**; el sucesor es una
constante de una curva fija, sin selección; y no hay encadenamiento. Pero hay que citarlo
por la misma razón que a Drake, y es la razón que el autor ya fijó: **para demostrar
dominio del terreno, no para atribuir inspiración.**

El contexto completo importa y es elegante: la guerra del tamaño de bloque produjo las tres
formas posibles a la vez —**BIP-100** (voto de mineros), **BIP-101** (cronograma fijo,
duplicar cada dos años), **BIP-103** (cronograma determinista lento)— y ninguna se activó.
Bitcoin terminó en split. La forma que no se probó nunca es la cuarta: **cronograma
disparado desde el estado**.

---

## 8. Límites de la búsqueda

Una pasada, en inglés, dos vocabularios (gobernanza/hard fork y recalibración de
parámetros), sobre web y literatura indexada.

- **Sesgada a cadenas grandes y bien documentadas.** Si el mejor cliente es una cadena
  chica que sufrió una recalibración sin cobertura, no lo habría visto.
- **No se buscó en actas de reuniones de core devs ni en foros no indexados**, que es
  justamente donde está el costo real de coordinación de cada uno de estos cambios. Todo lo
  que se afirma acá sobre ese costo sale de lo que los EIPs y la prensa dijeron, no de las
  llamadas.
- **No se buscó fuera del mundo blockchain.** Un cliente análogo podría existir en
  protocolos de red con parámetros negociados; no se miró.
- Los tres casos que califican son de **dos cadenas** (Ethereum ×2, Monero/Bitcoin). Es
  poca diversidad para una conclusión de mercado.

---

## 9. Fuentes

- EIP-7892, *Blob Parameter Only Hardforks* — https://eips.ethereum.org/EIPS/eip-7892
- EIP-8261, *Gas Limit Schedule* (11/5/2026) — https://eips.ethereum.org/EIPS/eip-8261
- EIP-2384, *Muir Glacier Difficulty Bomb Delay* — https://eips.ethereum.org/EIPS/eip-2384
- EIP-649 / EIP-1234 — https://eips.ethereum.org/EIPS/eip-649 · https://eips.ethereum.org/EIPS/eip-1234
- Fusaka mainnet announcement (calendario BPO) — https://blog.ethereum.org/2025/11/06/fusaka-mainnet-announcement
- Muir Glacier, contexto y cita de Beiko — https://decrypt.co/15813/ethereum-hard-fork-muir-glacier-goes-live · https://medium.com/ethereum-cat-herders/ethereum-muir-glacier-upgrade-89b8cea5a210
- BIP-103 — https://bips.dev/103/ · BIP-101 — https://github.com/bitcoin/bips/blob/master/bip-0101.mediawiki
- Emisión terminal de Monero — https://www.getmonero.org/resources/moneropedia/tail-emission.html
- Emisión terminal de Bitcoin, debate 2025-26 — https://news.bitcoin.com/featured/peter-todds-tail-emissions-pitch-sparks-bitcoin-inflation-debate/
- DAA de Bitcoin Cash — https://www.bitcoinabc.org/2017-11-01-DAA/
