# Sucesión determinista de reglas

**Una cadena que trae escrita desde el bloque 0 cómo cambian sus propias reglas, y que
ejecuta ese cambio sin voto, sin fork político y sin intervención humana en la decisión.**

> **Qué es esto y qué te pido.** Es el diseño completo (~19.500 palabras) comprimido a un
> tercio: **unos 25 minutos**. Saqué el registro de decisiones, la historia de lo que se cayó
> en el camino y las justificaciones largas — quedó el mecanismo, los números medidos y las
> fronteras.
>
> **Si tenés poco tiempo:** §2 y §3 son el mecanismo, §7 dice qué está medido y qué no, y §10
> es el pedido concreto. Lo demás es referencia para cuando quieras pegarle a algo puntual.
>
> **No es un pitch. Es un pedido de que lo rompas.** El diseño sobrevivió a todos los ataques
> que se le corrieron, y todos los corrió quien lo escribió, que es exactamente el tipo de
> evidencia que no vale. Al final hay una lista de **dónde pegar primero**; si sólo tenés
> tiempo para una cosa, andá directo ahí.
>
> Todo lo que figura como *medido* por un test computacional tiene script reproducible y
> datos crudos en [`mediciones/`](../mediciones/). Las **dos excepciones**, declaradas para
> que no las busques: Test 1 es un relevamiento documental y trae fuentes, no datos; y el
> replay contra el historial de Ethereum corrió en la implementación de referencia, que no
> está en este repositorio — esos tres números vienen con su derivación escrita en el paper.

*Volver a la [portada](../README.md).*

**Dónde está el resto, si querés ir al fondo de algo.** Este archivo es el resumen. La fuente
de verdad es **[el paper](paper.md)** —~20.000 palabras, con las fronteras desarrolladas y el
registro de qué se descartó en el camino—. Y la historia de cómo se llegó a esto, con lo que se
cayó en el camino, está en **[la bitácora](bitacora.md)**.

⚠️ **Ojo con los números de sección: este resumen tiene numeración propia.** Fusionó secciones,
así que tiene 10 y el paper tiene 12, y **no coinciden** — la cola de impugnaciones es §5.3 acá y
§6.3 allá; la creación de activos es §6.4 acá y §8.5 allá. Cuando saltes al paper largo, buscá
por título y no por número.

**Y si venís a escribir código:** [`ROADMAP.md`](roadmap.md) tiene el glosario de los conceptos,
la estructura de módulos y las fases con sus criterios de aprobado.

Y cada número de acá tiene su medición, con `RESULTADOS.md` y scripts:

| directorio | qué contesta |
|---|---|
| [`test1-transicion/`](../mediciones/test1-transicion/RESULTADOS.md) | si el mecanismo tiene cliente afuera — los casos de §7 |
| [`test2-interprete/`](../mediciones/test2-interprete/RESULTADOS.md) | el presupuesto del intérprete en hardware real, con el paquete del benchmark |
| [`test4-ventana-k/`](../mediciones/test4-ventana-k/RESULTADOS.md) | el ataque de auto-pago, y la ventana que resultó vacía |
| [`cola-impugnaciones/`](../mediciones/cola-impugnaciones/RESULTADOS.md) | si la cola de §5.3 satura — de dónde salen los diez nodos PoD |
| [`expiracion-estado/`](../mediciones/expiracion-estado/RESULTADOS.md) | cuánto estado se genera y qué cuesta poder revivirlo |
| [`amortizacion-mint/`](../mediciones/amortizacion-mint/RESULTADOS.md) | por qué la tasa no puede bajar por depositar más |
| [`parametros-mint/`](../mediciones/parametros-mint/RESULTADOS.md) | los parámetros de §6.4, y cuál de ellos es realmente una decisión |
| [`presupuesto-nodo/`](../mediciones/presupuesto-nodo/RESULTADOS.md) | cuánto ocupa una entrada, y de dónde salen `θ*` y `L_max` |

---

## 1. El problema

Todo protocolo desplegado enfrenta tarde o temprano una condición que sus reglas originales
no manejan bien. Las tres respuestas que existen hoy ponen un humano en el lazo justo en el
momento del cambio:

| mecanismo | ejemplo | quién decide |
|---|---|---|
| fork disputado | Bitcoin / BCH | una facción escribe software nuevo; el mercado arbitra después |
| voto on-chain | Tezos, Polkadot | los tenedores, con toda la política que eso arrastra |
| obsolescencia forzada | bomba de dificultad de Ethereum | el protocolo fuerza el cambio, pero el sucesor lo escriben humanos |

Las tres funcionan. Ninguna es determinista: en las tres, **qué viene después** es una decisión
tomada en el momento, por gente, bajo presión. Y esa decisión es donde un protocolo se vuelve
político.

La propuesta: que la regla de sucesión viva dentro de Genesis y se ejecute sola cuando el
estado de la cadena cumple una condición verificable. El resultado no es una familia de
cadenas — es **una sola cadena que conmuta su ruleset por generaciones**, conservando el
estado íntegro y encadenando cada generación a su ancestro por hash.

**Cómo conviene leer lo que sigue.** El diseño tiene dos mitades con respaldo muy distinto, y
decirlo temprano es más honesto que dejarlo para el final. La **sucesión de parámetros
internos** —capacidad, emisión, tiempos de bloque— salió a buscar destinatarios afuera y los
encontró (§7). El **intérprete** y las **generaciones encadenables** —que son lo que hace
posible la evolución criptográfica de §5.6 y lo que separa esto de sus precedentes— pagan las
fronteras más caras y **todavía no tienen un caso encontrado afuera**. La primera es una
aplicación; la segunda es una apuesta.

---

## 2. El mecanismo: conmutación

La pieza que hace que esto no sea un fork disfrazado es que **el nodo no se reemplaza, se
conmuta**: el mismo proceso, con el mismo estado en memoria, ejecutando reglas distintas a
partir de un bloque determinado.

```
   ┌──────── ruleset A ────────┐ ┌─ F ─┐ ┌──── Δ ────┐ ┌─── ruleset B ───┐
                                                     ║
   ───▣───▣───▣───▣───▣───▣───▣───▣───▣───▣───▣───▣──╫──▣───▣───▣───▣───▶
                              ▲       ▲              ║
                          bloque N   N final    activación
                       TRANSITION_    LOCK-IN   conmutación efectiva
                        RULE → TRUE  irrevocable
                        (advisorio)  params on-chain

   el MISMO nodo · el MISMO estado · sin migración, sin bridge, sin snapshot
```

**Son tres tiempos, no dos**, y la separación es lo que evita que cada transición sea una
sorpresa:

1. **Disparo.** En el bloque `N`, `TRANSITION_RULE` da TRUE. No conmuta nada y no compromete
   nada: es advisorio, y una reorganización lo puede deshacer.
2. **Lock-in.** Cuando `N` es final, el disparo se vuelve irrevocable. No es ceremonia:
   `H0_B` compromete `state_trigger`, y comprometerlo antes dejaría el checkpoint apuntando a
   un estado que una reorganización puede sacar de la cadena. El lock-in emite on-chain los
   parámetros completos y la altura de activación — todo lo que un integrador necesita está
   en la cadena, `Δ` bloques antes, sin que nadie tenga que anunciarlo.
3. **Activación.** `Δ` bloques después del lock-in —no después del disparo, así el aviso es
   exactamente `Δ`— el nodo conmuta.

`Δ` está fijado en Genesis **por clase de transición**: una transición de circulación tolera
ventana larga, una migración criptográfica bajo ataque necesita lo contrario.

El linaje se encadena por hash:

```
H0_B = H( H0_A ‖ state_trigger ‖ params_nuevos )
Verify( H0_B, H0_A, state_trigger, params_nuevos ) → TRUE
```

Genesis A **no conoce** el hash de B —no puede, B incorpora información que todavía no
existe— pero conoce determinísticamente cómo se calculará. `H0_B` no es el génesis de una
cadena nueva: es un marcador de checkpoint generacional dentro de la misma cadena.

---

## 3. Las cinco invariantes

Cada una elimina una forma de reintroducir al humano en el lazo. **Son el marco duro: un
ataque que las respeta es un ataque contra el diseño; uno que las viola es otro diseño.**

**I1 · El intérprete vive en Genesis y no cambia nunca.** Una transición no introduce código
de nodo: selecciona un punto de un espacio que el nodo **ya sabe ejecutar**. Lo que Genesis
fija de forma permanente no es una lista de reglas posibles sino la **máquina que las corre**.
El espacio está partido: los parámetros **internos** —emisión, fees, tamaño de bloque,
tiempos— cambian en cualquier transición; los **visibles en la interfaz** —primitiva de firma,
formato de dirección, serialización— sólo por la vía de I5.

**I2 · El trigger se computa sólo desde el estado, y nadie elige el momento.** Sin oráculos, sin
firmas, sin votos. Pero computable no alcanza: *"la dirección X recibió 1 wei"* se computa sólo
desde el estado y es una compuerta con dueño. Hay dos formas de cumplirlo y toda regla declara en
cuál está. Por **aproximación observable**: la cantidad que dispara es monótona, la cadena publica
*cuántos bloques faltan al ritmo actual*, y la regla **no puede disparar desde el reposo** — si el
bloque anterior no publicó distancia, era un escalón. Por **capacidad demostrada**: no hay
aproximación ni puede haberla —la rotura de una primitiva ocurre, no se aproxima— y es admisible
sólo si producir el hecho exige **exactamente la capacidad ante la que la transición reacciona**,
declarada on-chain. Es el canario de §6.6, y su condición es que la instancia debilitada se
**derive** de una semilla pública: si alguien la genera, retiene la trampa y el canario es suyo.

*Ningún nodo puede verificar que la capacidad declarada sea la verdadera; eso se audita en
Genesis, y por eso la declaración es obligatoria y explícita. Y la distancia es una proyección al
ritmo actual, no una promesa: la promesa es `Δ`.*

**I3 · El estado se conserva íntegro a través de la transición.** No hay migración de saldos,
no hay snapshot — y por lo tanto no hay bridge, que es el componente más atacado de la
industria.

**I4 · Cada generación commitea a su ancestro.** El linaje es verificable por hash y no
depende de que nadie lo atestigüe.

**I5 · Las transiciones son aditivas en la interfaz.** Toda dirección y toda transacción
llevan etiqueta de generación desde el bloque 0. Una transición puede **agregar** formatos; no
puede quitarlos.

Es la invariante que decide el modo de falla de todo **integrador externo** — un exchange, una
wallet: software que lee la cadena desde afuera, no un nodo. No significa que se quede en una
cadena vieja: **los objetos de la generación anterior nunca dejan de ser válidos**, así que el
integrador que no se actualizó los sigue procesando igual que siempre. Lo que no puede es
entender los nuevos — y ahí, como toda transacción lleva etiqueta de generación desde el bloque
0, **falla cerrado y ruidoso** (*"versión que no conozco"*) en vez de parsearlos bajo las reglas
viejas y sacar un resultado plausible y equivocado, que es la falla que pierde fondos. Eso es
degradar: funciona para lo viejo, se planta ante lo nuevo.

---

## 4. Lo que sale gratis: canonicidad

Es probablemente la propiedad más valiosa del diseño y no fue buscada: **invierte la asimetría
de legitimidad de un fork.**

En Bitcoin la posición conservadora —no cambiar nada— es el default: quien quiere cambiar las
reglas escribe software nuevo, y la cadena que sigue igual reclama ser la original. Acá es al
revés: el cliente estándar conmuta solo, así que **para no conmutar hay que modificar
activamente el software** y desactivar la regla. El que se queda en las reglas viejas no
preserva la cadena original: se desvía de Genesis, y no puede invocar a Genesis para
justificarlo.

*"Cuál es la verdadera"* deja de ser una pregunta social. Un exchange o un light client corren
la verificación de linaje, y la cadena que no conmutó no tiene checkpoint generacional válido.
Es un criterio de canonicidad objetivo, y ningún fork disputado de la historia tuvo uno.

---

## 5. La arquitectura

### 5.1 Dos clases de nodo

**Nodos de cómputo.** GPU y RAM, hostean los modelos que hacen el trabajo pedido. Hardware
caro, mercado competitivo, y **no participan del consenso**: su ingreso es el pago del pedido
que ejecutaron.

**Nodos PoD.** Verifican y liquidan, y cobran fee cada vez que dos contratos interactúan.
Corren en cualquier hardware — la verificación reproduce bit a bit en x86-64, ARM64 y un
teléfono.

**El fee es ad valorem.** Un fee fijo es regresivo en las dos direcciones: vuelve impagable el
pedido chico —que es el que una economía de agentes hace en volumen— y gratis el pedido
grande, que es donde la quema tiene que morder.

La portabilidad tiene consecuencia de gobernanza: **lo que le permite a un validador tomar de
rehén una cadena no es su convicción, es el foso de capital.** Un nodo que entra en un teléfono
no tiene foso. Pero hay un argumento mejor y no depende del costo de entrada:

> **Podés tener 3.000 nodos o 3 millones. Si no hay demanda externa, todos compiten por una
> torta que no existe.** Como la emisión no depende del trabajo (§6.1), sumar nodos no crea
> ingreso: reparte el mismo fee entre más manos. **Fabricar identidades es gratis y da
> exactamente lo mismo**, que es más robusto que hacerlo caro.

**Medido.** En un Motorola Edge 40 Neo bajo Termux, una verificación ML-DSA-44 desde bytes
corre en **391 µs** como bytecode con JIT —3,51× el nativo— y da **~640 tx/s** con un cuarto
de núcleo. Es el mismo tiempo absoluto que en un i5-9400 de escritorio. Con una salvedad: iOS
no permite JIT a terceros y el bytecode llega en tiempo de ejecución, así que un nodo en
iPhone queda forzado al intérprete, **~15× más lento**. Es política de plataforma, no
propiedad del diseño.

### 5.2 PoD verifica el predicado, no la inferencia

Un modelo no puede pasar el gate de determinismo. Ni a temperatura cero: el no determinismo de
punto flotante entre hardware distinto rompe la reproducción bit a bit.

La separación en dos capas lo vuelve irrelevante. **La GPU produce; el nodo liviano
comprueba.** El pedido no dice *"generá buen código"* — dice *"entregá algo que compile y pase
estos tests"*. La inferencia no se verifica: se verifica que **la salida satisface el
predicado**.

De ahí sale una restricción dura:

> **Todo pedido lleva un predicado de aceptación determinístico y lo bastante barato como para
> correr en la capa liviana.** Lo que no se pueda expresar así no es trabajo que la red pueda
> liquidar.

Eso convierte una advertencia difusa en una frontera nítida — y **que ese subconjunto sea lo
bastante grande como para sostener una economía es una hipótesis, no un resultado.**

Corolario que parece limitación y es lo contrario: **el cliente no elige qué nodo ejecuta su
pedido, y no lo necesita.** La calidad no se asegura seleccionando de antemano sino en la
aceptación: si la salida no satisface el predicado, no hay pago.

### 5.3 Orden sin consenso global

Verificar y ordenar no son la misma operación. Si Alice firma dos transacciones que gastan los
mismos 100 tokens, **las dos son individualmente válidas**; sólo el orden decide cuál gana.

Pero el orden **global** no hace falta: cada cuenta lleva su propia secuencia y su dueño es el
único que puede agregarle; comprometer fondos en un contrato los saca del saldo disponible, así
que no se pueden comprometer dos veces; y una interacción queda firme cuando pasa una **ventana
de impugnación** sin que nadie presente prueba de conflicto.

**La ventana no se puede tapar, y el motivo no es el precio:**

> **Llenar es serial; drenar es paralelo.** Una impugnación no existe hasta que entra en un
> bloque, así que el techo para llenar es la capacidad de la cadena — un solo caño. Drenar lo
> hacen todos los nodos PoD **a la vez**.

El margen es `N · h / γ`. Con `γ ≈ 1` —que es lo que garantiza el techo de pasos de VM— y 10%
de headroom por nodo, la fórmula da **diez nodos PoD**; corrida con una cola de verdad hacen
falta **once**. Tres condiciones lo sostienen y ninguna es automática: **cualquier nodo PoD
resuelve cualquier impugnación**; la cola es **por orden de llegada con bono plano** —si se
ordenara por tamaño de bono, el capital compraría prioridad—; y **cada nodo elige en su propio
orden y no en el de la cola**. Esta última apareció al correrla: si todos toman de la cabeza,
los `N` nodos verifican la misma impugnación, el paralelismo se evapora —con cincuenta nodos el
margen es el de uno— y la espera de una impugnación legítima no es un plazo fijo sino una rampa
de `9·T`. Se arregla sin coordinación: cada nodo recorre la cola en un orden pseudoaleatorio
derivado de su identidad, y ése es el costo de diez a once. Al azar el atraso **se estabiliza**
—con once nodos, ~400 impugnaciones y cuatro bloques de espera media— en vez de crecer.

El bono no tiene que ser grande, sólo distinto de cero: **el del impugnador honesto vuelve** y
**el del atacante se quema**.

### 5.4 La equivocación no se prohíbe: se vuelve suicida

Que una firma sea infalsificable no impide que su dueño firme **dos mensajes distintos**.
Ningún esquema lo evita. Pero en Schnorr y ECDSA, firmar dos mensajes con el **mismo nonce**
permite despejar la clave privada de las dos firmas — así se perdió la clave de la PS3.

Convertido en regla de diseño: **el nonce es función determinística del índice de la cuenta.**
Firmar dos veces en el mismo índice no es una infracción que haya que probar y sancionar — **es
publicar la propia clave privada.**

El castigo no necesita regla de protocolo ni árbitro, se verifica en un teléfono, y **el
vigilante se financia solo**: la recompensa por pescar la infracción es el saldo del infractor.

### 5.5 Toda transferencia es bilateral

No existe el envío unilateral: Alice ofrece, Bob acepta, y recién ahí la transferencia existe.
Hay dos clases de oferta. Una transferencia común es **dirigida**. Un pedido de trabajo es
**abierto**: no nombra a nadie, y ahí está todo el mecanismo de asignación del sistema:

> **Nadie asigna pedidos.** El cliente publica predicado, precio y plazo con los fondos ya
> comprometidos; el nodo que puede cumplirlo lo acepta. Es *pull*, no *push* — el nodo se
> autoselecciona porque conoce su propio hardware, y se autofiltra solo, porque aceptar un
> pedido que no puede cumplir es fallar el predicado y no cobrar.

De ahí salen tres cosas gratis: **no hay cómputo duplicado**, **un nodo saturado simplemente no
acepta**, y **el cliente no puede dirigir trabajo a un nodo elegido**.

El costo está declarado: no se le puede pagar a alguien que está offline, y la finalidad se
mide en minutos u horas, no en segundos.

### 5.6 Evolución criptográfica sin fondo de escalera

Toda primitiva termina cediendo. El problema es que *"la primitiva se rompió"* no está en el
estado, así que no puede ser trigger (I2); y una **lista** de reemplazos se agota y exige un
fork humano.

**El canario convierte la rotura en un hecho del estado.** Genesis publica una versión
deliberadamente debilitada con recompensa on-chain. Si alguien la rompe y la reclama, eso sí es
estado. El trigger no lee *"la criptografía se rompió"* — lee *"el canario fue reclamado"*. Una
**escalera** de canarios gradúa la respuesta: el débil cede años antes y dispara una migración
con `Δ` largo.

**El intérprete quita el fondo de la escalera.** Como Genesis fija la máquina y no la lista, una
primitiva nueva es **bytecode**, no código de nodo.

**Quién lo escribe: es un pedido de trabajo.** Cuando el canario cae, el protocolo publica el
pedido y los agentes compiten. **Quién dice que es segura: nadie puede**, así que se prueba a
los golpes:

> **El guante.** Toda candidata entra con una instancia debilitada y una recompensa on-chain
> durante una ventana fija. Si alguien la rompe, queda descartada y pasa la siguiente. La que
> sobrevive se instala. Es el mismo canario usado como examen de ingreso.

**El guante mide seguridad; el costo lo mide otra cláusula.** Una implementación correcta e
irrompible pero diez veces más cara sobrevive la ventana y queda instalada para siempre — y ahí
el presupuesto de §5.1 se rompe *desde adentro del protocolo*. Por eso el predicado lleva **tres**
cláusulas: pasar los vectores, verificar por debajo de un **techo de pasos de VM**, y hacerlo
tocando menos de un **techo de páginas**. Las dos cotas son cantidades ejecutadas, no tiempo de
reloj: el conteo es idéntico entre arquitecturas (medido) y el reloj sería un oráculo.

**La tercera cláusula la agregó construir la máquina, y no estaba en el diseño.** Un techo de pasos
supone que un paso vale un paso, y no: la peor mezcla de instrucciones corre **23× más lento** que
la carga real, así que el techo prometía 22 ms por transacción y la mezcla tardaba 596. No se
arregla pesando instrucciones —lo que hace el gas— porque la mezcla que abre el hueco es una
lectura de memoria, y una lectura cuesta lo mismo que una suma cuando el dato está en caché: **es
el mismo opcode**, y lo que cambia es dónde cae el dato. Lo único que se puede contar mientras
corre son las páginas distintas que toca.

**Convergencia previa.** Justin Drake propuso *cryptographic canaries* en Ethereum Research en
febrero de 2018: bounty, prueba de amenaza, conmutación automática a un respaldo. Este diseño se
concibió independientemente. La diferencia es la profundidad: el respaldo de Drake es precableado
y de **un solo escalón**; acá el sucesor se deriva dentro de un espacio definido en Genesis y el
intérprete permite **encadenar generaciones**. Eso contesta la objeción que dejó aquella idea sin
avanzar —que calibrar el canario obliga a estimaciones tan conservadoras que la automatización se
vuelve redundante con la supervisión manual—: con un solo escalón, una transición prematura
consume el único recurso de recuperación y el trigger tiene que ser casi perfecto; encadenable,
sólo consume una generación que puede generar la siguiente.

---

## 6. La moneda

### 6.1 Tres mecanismos que no hay que fundir

| mecanismo | qué hace |
|---|---|
| **fees** | remuneran trabajo — demanda → fee → nodos |
| **emisión** | regula el estado monetario, **independiente del trabajo** |
| **PoD** | valida qué trabajo y qué transición son válidos |

> **Ninguna unidad nueva se crea porque un nodo decidió hacer más trabajo.**

Reparto de la fee, con porcentajes de ejemplo y no de diseño: 70% proveedores / 20% quema / 10%
reserva. **La quema es la única pieza irreemplazable.**

### 6.2 La distribución del día 1

Sacar la emisión de la ecuación del trabajo deja una pregunta sin la cual el resto no arranca:
**quién tiene tokens antes de que exista el primer fee.** Las tres respuestas clásicas la
contestan mal, y el motivo es un teorema:

> **Una distribución de tokens nuevos indexada a una acción rinde a lo sumo lo que cuesta esa
> acción, o es farmeable.** Si paga menos que el costo, nadie la reclama; si paga más, se
> farmea. Bitcoin pudo porque hashear tiene costo externo, físico e imposible de fingir.

**La forma elegida toma la tercera, acotada al bloque 0.** Genesis publica pools con tope por
clase, y **reclamar se paga demostrando la capacidad que se reclama**: la clase de cómputo
resuelve una tarea de referencia con predicado determinista; la clase PoD verifica un lote de
referencia dentro del techo de pasos de VM.

No necesita identidad —el costo es externo y físico—, hace **verificable la separación por
clase** —decir *"soy un nodo de cómputo"* es gratis, resolver su tarea no—, y **el trabajo no se
tira**: reclamar es un ensayo del producto real. **Lo no reclamado se quema**, y de ahí sale la
mejor propiedad:

> **La oferta inicial no la fija el creador — la fija cuánta capacidad real apareció.**

**Sin adornos: sigue siendo una subasta pagada en cómputo**, y el que tiene más hardware se
lleva más. No es reparto igualitario y no hay que venderlo como tal. Es **abierto**, que es otra
cosa, y es la propiedad que tuvo el lanzamiento de Bitcoin.

Cada claim emite además un **certificado transferible** de haber participado. **No es dinero y
no es licencia**: si diera derecho a tokens sería concentrar la base monetaria inicial; si hiciera
falta para cobrar fees, la cantidad de nodos se volvería artificialmente escasa.

**Sin decidir: el costo exacto del claim, la duración de la ventana y los topes por clase.**

### 6.3 Por qué el circuito cerrado pierde

El ataque a descartar no depende de que nadie se disfrace: Alice tiene nodos propios, se manda
trabajo a sí misma y cobra sus propias fees. La pregunta correcta no es si el protocolo puede
detectarla —no puede— sino si le conviene.

| nodos de Alice | neto por ciclo | saldo tras 1.000 ciclos, desde 1.000.000 |
|---|---|---|
| 2 de 3.000 | −0,000900 | 406.486 |
| 99% de la red | −0,000603 | 547.068 |
| **el 100%** | **−0,000600** | **548.713** |

**Pierde incluso siendo toda la red.** La cantidad de nodos sólo mueve su tajada de la reserva;
la quema queda fuera de su alcance siempre. Con quema en cero, el ataque pasa a ser gratis.

> **El protocolo no distingue a Alice de un cliente real. No lo intenta.** Hace que el circuito
> cerrado **pierda plata**, y la aritmética no necesita saber quién es nadie.

**Una oferta acotada banca actividad ilimitada.** Con supuestos hostiles —finalidad de 6 horas y
sólo 20% del circulante en vuelo— el techo de velocidad da **292 vueltas al año**, contra 1,2 de
M2 de EE.UU. y ~12 de Bitcoin on-chain. Entre 25× y 250× de aire.

**La concentración de tokens no da poder de protocolo.** I2 prohíbe que el trigger lea cualquier
cosa que no sea `emitido − quemado` del token nativo, y señalizar preparación es información,
nunca compuerta. Un actor con el 90% de los tokens tiene el 90% del dinero y cero poder sobre
las reglas.

### 6.4 Crear activos: el cargo va en la permanencia

Se admite **una primitiva de creación de forma fija**, no una máquina abierta al estado de
terceros. La cadena ya ejecuta código ajeno —el predicado de §5.2— pero un predicado corre,
contesta y muere; acá se admite que un objeto **persista**. Con forma libre, el tamaño de una
entrada lo elige el usuario y el estado deja de tener unidad de medida. Una sola primitiva cubre
fungible y no fungible: **un no fungible es `supply = 1`, indivisible**.

**El cargo no va en la creación, y es lo menos obvio del arreglo:**

> **Un cargo a la creación no reduce la creación — reduce la registración de la creación.**

Si crear adentro lleva cargo propio, se mintea **afuera**, y ahí se pierde todo lo que el
mercado nativo argumenta. La asimetría es de aplicabilidad, no sólo de incentivos: **el cargo a
la creación se evade minteando afuera; el de permanencia no, porque el estado que existe lo ven
todos los nodos.**

Entonces la tarifa tiene dos partes. Un **piso** que se quema, y no es una perilla: es el costo
fijo del ciclo crear + desalojar, medido contra el presupuesto de un nodo, unas **dieciséis horas
de guardado** (0,2% de lo que cuesta tener el objeto un año). Y un **depósito de permanencia**
que se consume quemándose época a época, lineal en **tamaño × tiempo**. Es el depósito, no el
piso, lo que hace de antispam.

**La vida comprable de una vez tiene tope, `L_max`, y es condición de estabilidad y no
recomendación.** Sin tope, un pago finito grande compra siglos. Y como la tasa no puede quedar
congelada —es un precio nominal sobre un recurso real—, prepagar sin límite es apostar contra la
regla que la mueva: cuando la tasa baja, comprar largo captura slots a precio de saldo que no se
recuperan sin confiscar. **Medido: con `L_max` = 25 épocas el lazo aterriza en el objetivo; con
50 es marginal; con 100 se rompe.**

**El cargo es por entrada, no por objeto.** Un fungible es una entrada más un saldo por cada
tenedor, y esa cuenta crece con la adopción: un token con un millón de tenedores ocupa el **3%**
del disco de un nodo — **treinta y tres tokens exitosos llenan la cadena**. Así que **toda
entrada de estado paga permanencia, y la funda quien la crea**. Eso cierra de paso un agujero que
no era del minteo: **las cuentas del token nativo también son entradas de estado**, y como el fee
es ad valorem, sobre polvo tiende a cero.

> **En la cadena no existe ningún objeto cuyo costo futuro no tenga a alguien pagándolo. Nadie
> puede comprar espacio perpetuo con un pago finito.**

**Cambio de carácter que hay que declarar: tener un saldo deja de ser gratis.** Es demurrage
sobre el estado y no sobre el monto — una billetera chica y quieta termina desalojada,
recuperable con prueba.

**Desalojar no es destruir, y el residuo tiene que ser O(1).** El objeto sale del conjunto activo
y el tenedor lo revive con una prueba, pagando el costo de entonces. Pero el compromiso contra el
que se prueba no puede ser uno por objeto: una lápida de 32 bytes por objeto son **1 GB por nodo
para siempre**, un cuarto del presupuesto. El desalojo **agrega a un acumulador único de
sólo-append** — unos **800 bytes en total**, no por objeto.

**No hay deuda ni remate.** Rematar obliga a la cadena a saber cuánto vale el activo, o sea a leer
el pool, que es exactamente lo que I2 prohíbe y es manipulable en la dirección obvia. La
liquidación la hace el mercado: quien no puede sostener el saldo vende antes del desalojo.

**Ocupación objetivo `θ* = 50%`** de un presupuesto de disco declarado —del orden de pocos GB—
que sólo una transición puede mover. El techo derivado es `θ* ≤ 67%`, porque el pico de un shock
sostenido llega a **1,48×** antes de que el precio muerda. El sesgo conservador es deliberado:
quedarse corto se corrige subiendo el número; pasarse expulsa a los nodos chicos y **eso no se
revierte**, porque el que se fue no vuelve.

---

## 7. Qué está medido y qué no

Esta sección es la que decide cuánto vale todo lo anterior.

**Medido contra el mundo (evidencia externa):**

- **El mecanismo corre y se midió contra el historial real de Ethereum** (agosto 2026), con las
  alturas y los offsets verificados contra los EIPs y contra la configuración que corren los nodos.
  **Dos de los tres casos fueron en contra**, y por eso va primero: en la **bomba de dificultad**,
  una regla con un solo número elegido de antemano reproduce las seis decisiones humanas dentro de
  37 días —pero ese número es el promedio de un criterio que se movió **41×**, y cinco de los seis
  forks fueron preventivos—; en los **blobs**, la regla habría actuado **383 días antes** donde la
  restricción era la demanda y **nunca** donde era la capacidad; en el **gas limit** directamente
  **no hay trigger admisible**, porque EIP-1559 clava la ocupación (correlación **−0,02** contra un
  precio que se movió 650×), el precio nominal caduca y el relativo se vuelve trinquete.
- **El mecanismo tiene cliente, y se está acercando solo.** Ethereum recalibra los parámetros de
  capacidad de blobs (`blobSchedule`) y construyó un tipo de fork dedicado a abaratar ese cambio
  —EIP-7892, hoy **`Final`**: *"the current approach of only modifying blob parameters in large,
  infrequent hard forks is not agile enough to keep up with L2 growth"*—. Ya lo usó dos veces: el
  target fue de 3 a 6, 10 y 14 en veintidós meses, y las dos últimas subas se anunciaron **juntas y
  por adelantado**. O sea que el cliente llegó solo hasta *escribir el cronograma antes*, que es la
  forma de BIP-103; lo que le falta para llegar acá es I2 — el disparo sigue siendo un timestamp
  escrito a mano. En mayo de 2026 el patrón se repitió sobre el gas limit
  (EIP-8261), con un cronograma que declara explícitamente **no** ser regla de consenso.
  Corroboran la bomba de dificultad —retrasada por hard fork **seis veces en cinco años** para
  instalar un entero que la cadena podía calcular sola— y la emisión terminal, que Monero
  escribió por adelantado y obtuvo sin fork, mientras Bitcoin hoy no puede tenerla a ningún
  precio.
- **Precedentes.** Drake 2018 (canarios criptográficos) y BIP-103 de Pieter Wuille, 2015
  —función determinista para el límite de tamaño de bloque, sin voto de mineros—. Ninguno cierra
  el hueco: en Drake el respaldo es de un solo escalón; en BIP-103 el disparo es tiempo y no
  estado, y no hay encadenamiento. **Trabajo concurrente a vigilar:** *Post-Quantum Blockchains
  with Agility in Mind*, Tectonic Labs, IACR eprint 2026/609, marzo de 2026.
- **El presupuesto del intérprete entra**, medido en hardware real (§5.1). Lo que lo decide es que
  **determinismo e interpretación son separables**: para código entero el JIT es tan determinístico
  como el intérprete y cuesta ~3× en vez de ~29×.

**Y ahora lo que hay que decir sin adornos.** La corrección al alcance del primer punto: **ninguno
de los tres clientes encontrados necesita el intérprete, ni las generaciones encadenables, ni la
evolución criptográfica.** Son parámetros internos sobre espacios de enteros. Lo que tiene demanda
demostrada por terceros es la mitad que **no** paga las fronteras caras. La otra mitad —incluido el
diferenciador declarado frente a Drake— sigue sin destinatario encontrado.

**Medido sólo contra sí mismo (evidencia propia, que es de otra clase):** toda la moneda. El
ataque de auto-pago, la velocidad de circulación, la cola de impugnaciones, los parámetros de la
permanencia, `θ*` y `L_max`. Sobrevivieron a todos los ataques que se les corrieron, y **todos los
corrió quien escribió el diseño**.

Vale una muestra de lo frágil que es esa clase de evidencia, porque pasó acá adentro: la primera
versión de la regla que mueve la tasa de permanencia parecía estable y absorbía un shock de 3×.
Lo que la tumbó no fue un ataque — fue **corregir un detalle del modelo con que se la había
probado**: trataba como acortables unos plazos que el protocolo promete respetar. Con plazos
respetados oscila entre casi cero y más del doble del objetivo, con cualquier ganancia.

**Nada está construido.** El diseño no corrió nunca.

---

## 8. Fronteras declaradas

No son problemas a resolver: son el precio de propiedades que el diseño quiere, y se sostienen a
sabiendas. Las que más pesan:

- **La adaptación está acotada a lo que Genesis anticipó.** Si la condición que dispara la
  transición es algo no previsto, no hay ruleset que cargar. **Y el determinismo saca el freno de
  emergencia**: una transición mal anticipada es exactamente el escenario donde los humanos
  querrían negarse, y la respuesta del diseño es *"entonces sos un fork"*.
- **El conjunto de futuros posibles deja de ser auditable.** Es el precio del intérprete. Con una
  lista finita, cualquiera podía leer Genesis y saber en qué se puede convertir la cadena.
- **El intérprete es un punto único de falla que no se puede parchear nunca.** Si tiene un bug, no
  hay transición que lo arregle, porque toda transición corre sobre él. Es la única pieza donde la
  verificación formal no es opcional.
- **Sobrevivir el guante no es sobrevivir quince años de criptoanálisis.**
- **El protocolo no tiene noción de identidad, así que toda palanca que mueva, la mueve para
  todos.** Explica de una sola vez por qué murieron cuatro arreglos distintos —graduar el subsidio,
  bloquearlo un tiempo, repartir por rol, bono de impugnación superlineal—: cada uno necesitaba
  distinguir al honesto del atacante, y lo único que el protocolo ve son firmas y montos. **Toda
  propuesta de la forma "que el bueno pague menos" es una propuesta de introducir identidad.**
- **El split es ilegítimo, no imposible.** Ethereum Classic existe. La asimetría no mata a la
  cadena disidente — la hace chica.
- **El hash que encadena el linaje no se puede reemplazar**, porque lo que habría que migrar es el
  pasado. Le pasa a cualquier cadena que comprometa su historia con un hash.
- **El protocolo no puede obligar a que exista archivo.** Puede garantizar que un activo
  desalojado *se puede* revivir; no que alguien vaya a tener con qué. Alcanza para un agente
  permanentemente online y no alcanza para una persona, que va a depender de un servicio de
  archivo — o sea de mercado y no de protocolo.
- **Se puede pagar por acercar una transición, aunque no por cambiar cuál.** Al indexar la tasa de
  permanencia a la ocupación, quien ocupa disco acelera la quema ajena, y la quema es lo que lee el
  trigger. Con `s` la fracción de estado que ocupa el atacante y `ε` la elasticidad de la demanda
  honesta, la quema ajena por unidad de quema propia es `((1−s)/s)·((R−1)/R)` con
  `R = (1/(1−s))^(1/ε)`:

  | `s` | `ε` = 0,25 | `ε` = 0,5 | `ε` = 1,0 | `ε` = 2,0 |
  |---|---|---|---|---|
  | 5% | **3,52** | 1,85 | 0,95 | 0,48 |
  | 25% | 2,05 | 1,31 | 0,75 | 0,40 |
  | 50% | 0,94 | 0,75 | 0,50 | 0,29 |

  **La palanca es del orden de `1/ε`**, y `ε` no se conoce sin red corriendo. Se declara en vez de
  cerrarse: lo acota que **se compra la fecha y no el contenido** —el sucesor está escrito de
  antemano y por I3 el estado cruza intacto—. Lo reabre una medición: si la demanda de guardado
  resulta marcadamente inelástica, hay que cerrarlo por definición y pagar la primera excepción a
  *circulante es emitido menos quemado*.
- **El canario paga por delatar, y quien puede romper la primitiva gana más callándose.** El que
  puede falsificar firmas puede tomar la cadena entera, y eso vale más que cualquier bounty. Lo
  acota que el canario no necesita atraer al adversario óptimo sino a **cualquiera** que llegue
  primero — que es lo que históricamente pasó con DES, MD5 y SHA-1. **Es un supuesto empírico sobre
  cómo se difunde el criptoanálisis, no una propiedad del diseño.**
- **No hay incentivo pagado por el protocolo a correr un nodo antes de que exista demanda.** El
  claim compra la cohorte del día 1 y después el ingreso es fee de demanda real o nada. Es una
  elección deliberada entre dos fallas: el diseño viejo arrancaba seguro y se auto-farmeaba; éste
  no se auto-farmea y **puede no arrancar**.

---

## 9. Los problemas abiertos, y el que se cerró

**Cerrado en agosto de 2026 · el techo de pasos de VM.** Estaba declarado como *un número y dónde
vive*, con un acople que parecía obligar a elegir entre dos formas malas: congelado hay que elegirlo
generoso —tiene que sobrevivir primitivas que no existen— y generoso deja pasar la implementación
correcta pero 10× más lenta; apretado obliga a que sea parámetro interno, o sea una palanca.

**La disyuntiva era falsa: el techo no se elige, se deriva.**

```
techo = f* × tiempo_de_bloque × R_declarado(páginas) / tx_por_bloque
```

Lo que se congela en la máquina es **la fórmula**; el valor lo pone cada generación con parámetros
que ya están en el espacio. No es una palanca —moverlo exige mover capacidad o tiempo de bloque— y
**no compone**, porque no depende de qué primitiva esté instalada. Y el filo de las primitivas
futuras se disuelve: una más cara no queda afuera, **entra pagando capacidad**, y eso lo cobra una
transición con su `Δ` y su aviso.

Quedan dos constantes que **son decisiones y se declaran como tales**: `f*` (fracción del nodo
liviano para verificar firmas, con piso medido en el headroom que §5.3 necesita) y `R_declarado`
(ritmo del hardware de entrada, declarado por debajo del real porque el sobrante es headroom). Con
25% y 70 M pasos/s, un bloque de 6 s con 15 tx da **7 millones de pasos** — el doble de la
implementación de referencia de ML-DSA-44 y la quinta parte de la lenta que Test 2 encontró.

> **Y construir la máquina falsó la primera calibración de esos números.** Decían 300 M pasos/s y
> 67 transacciones. Aquel ritmo era el de **una** mezcla de instrucciones, y el de la máquina
> depende de la mezcla por 23×. **La fórmula sobrevivió sin un cambio** —que es exactamente lo que
> se gana cuando un techo es una cuenta y no un número—, pero la calibración costó tres cuartas
> partes de la capacidad del bloque, y hizo falta un segundo techo, sobre páginas tocadas: **96
> páginas de 4 KiB**.
>
> Y ese segundo techo trajo su propia lección, que terminó siendo la más útil de la fase. Un techo
> derivado de la capacidad **encarece**; uno constante **sólo puede excluir**, porque no hay precio
> que la primitiva pueda pagar — y las tres primitivas de la familia tocan 26, 40 y 65 páginas, así
> que el primer número elegido dejaba a la tercera afuera para siempre sin que ninguna cuenta lo
> señalara. **Se cerró con la misma jugada que había cerrado el primero: congelar la curva en vez
> del punto.** Genesis fija cuánto ritmo sostiene el hardware de referencia para cada presupuesto de
> memoria, el presupuesto pasa a ser un parámetro, y pedir más memoria se paga en capacidad como
> todo lo demás. La medición está en `genesis/predicado/RESULTADOS.md`.

**Abierto · cuál hardware es el peor caso.** Todo el diseño supone que la capa liviana es la que
ata —de ahí sale la entrada barata de nodos— y con ese supuesto se calibra `R_declarado`. **Medido,
es falso para los patrones adversariales de memoria:** un teléfono de gama media corre el peor
programa admisible a 80,8 M pasos/s y un escritorio x86-64 a 78,9, y con más memoria la distancia
se abre al doble a favor del teléfono. Las dos máquinas se rompen por lugares distintos. No
invalida el techo —se calibra contra el hardware declarado como referencia— pero sí la frase de que
el hardware más barato es el peor caso. **Dos máquinas no alcanzan para fijar un piso**, y cerrarlo
necesita más máquinas, no más análisis.

**Abierto · la regla que mueve la tasa de permanencia, y el nivel del que parte.** Que la tasa no puede
quedar congelada ya está dicho. La única variable a la que puede indexarse sin violar I2 es la
**ocupación del estado** — un hecho del estado, no una lectura de mercado. Lo que falta es qué regla
se escribe.

Y falta algo más que la forma: **falta el nivel del que parte.** Una ley de control dice cómo se
mueve la tasa, no dónde empieza, y dónde empieza es un precio —cuánto vale una época de guardado en
unidades del token— que la cadena no puede leer sin violar I2. O se fija a mano en Genesis, y
entonces lo único que el diseño promete es que la regla lo corrija si estaba mal, o hay que anclarlo
a algo que esté en el estado y todavía no aparece qué.

> **Y se puede decir por qué ésta no cede a la jugada que cerró el techo dos veces.** El techo
> tenía sus dos lados en el mundo físico —pasos y segundos— y la cadena puede contar los dos. La
> tasa tiene un lado físico, bytes × épocas, y uno monetario, y **ninguna cuenta cruza esos dos
> lados sin leer un precio**. No es una cuenta que falta escribir: es una frontera. De ahí salió
> denominar el piso en épocas de guardado en vez de en unidades del token — con eso **lo que
> queda abierto es un solo número y no dos**.

---

## 10. Dónde pegar

Lo que más sirve es que ataques acá. Van en orden de cuánto costaría descubrirlo tarde.

**A · ¿El subconjunto de trabajo verificable es una economía o un nicho?** Todo el ingreso de la red
depende de que existan pedidos con predicado determinista barato (§5.2). Hoy la mayor parte del valor
económico de un modelo está en salidas sin predicado barato. **Es la hipótesis más cara del diseño y
es la única que nunca se salió a falsar.** Pregunta concreta: ¿pagarías por esto, contra un proveedor
centralizado que responde en segundos, con finalidad de horas?

**B · ¿El claim recluta operadores o reclutantes?** El reclamante óptimo de §6.2 es una flota de GPU
alquilada durante la ventana, que se devuelve cuando cierra. El diseño demuestra que el hardware
**existió**, no que se **queda** — y como la emisión está desacoplada del trabajo, tener tokens no da
ninguna razón para seguir trabajando. El claim además es **irrepetible**.

**C · ¿La tarea de referencia es replayable?** Si la instancia es fija y publicada en Genesis, el
primero que la resuelve publica la solución y el costo del claim colapsa a cero para todos los demás.
Se arreglaría derivando la instancia de la clave del reclamante — no está escrito.

**D · En `t = 0` todas las defensas están denominadas en una unidad sin precio.** El fee es ad
valorem, el piso y el depósito son nominales, y el nivel inicial de la tasa es el problema abierto 2.
En la ventana en que la cadena es más frágil, el antispam vale aproximadamente nada.

**E · El escenario peligroso es el éxito, no el fracaso.** Si la moneda se aprecia —que es lo que pasa
si se adopta— el guardado se vuelve prohibitivo en términos reales y el estado se vacía. Lo que lo
compensa es la regla que no está escrita, y la primera versión de esa regla ya se cayó.

**F · El guante instala criptografía de consenso escrita por un postor anónimo**, con *"nadie rompió
una instancia debilitada en una ventana fija"* como único filtro. ¿Alcanza?

**G · El intérprete no se puede parchear nunca.** ¿Es realista verificar formalmente una VM
determinista completa, y qué pasa el día que aparezca un bug?

**H · El diseño no puede corregir un error económico del día 1**, por construcción, y un lanzamiento
es exactamente el momento en que se descubre qué no se anticipó. Toda otra cadena arregla eso por
gobernanza. ¿Es sostenible?

Si algo de esto ya está contestado en el documento largo y no se ve acá, **es culpa del resumen y
quiero saberlo** — abrilo como pregunta.

---

**Dónde sigue esto.** La lista de arriba, desarrollada y con qué haría falta para cerrar cada punto,
está en [problemas abiertos](problemas-abiertos.md). Cómo se llegó hasta acá y qué se descartó en el
camino, en [la bitácora](bitacora.md). Y el formato de un ataque útil, en
[CONTRIBUTING](../CONTRIBUTING.md).
