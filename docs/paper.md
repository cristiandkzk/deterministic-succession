# Sucesión determinista de reglas

**Una cadena que trae escrita desde el bloque 0 cómo cambian sus propias reglas, y que ejecuta
ese cambio sin voto, sin fork político y sin intervención humana en la decisión.**

---

## Resumen

La evolución de un protocolo es hoy un acto de gobernanza: alguien propone, alguien decide,
alguien se va. Este documento describe una alternativa — que la regla de sucesión viva dentro
de Genesis y se ejecute sola cuando el estado de la cadena cumple una condición verificable.

El resultado no es una familia de cadenas: es **una sola cadena que conmuta su ruleset por
generaciones**, conservando el estado íntegro y encadenando cada generación a su ancestro por
hash. El objetivo no es una blockchain que nunca necesite un fork, sino una blockchain **cuyo
fork ya forma parte del protocolo**.

---

## 1. El problema

Todo protocolo desplegado enfrenta tarde o temprano una condición que sus reglas originales no
manejan bien. Las tres respuestas que existen hoy ponen un humano en el lazo justo en el momento
del cambio:

| Mecanismo | Ejemplo | Quién decide |
|---|---|---|
| Fork disputado | Bitcoin / BCH | Una facción escribe software nuevo; el mercado arbitra después |
| Voto on-chain | Tezos, Polkadot | Los tenedores, con toda la política que eso arrastra |
| Obsolescencia forzada | Bomba de dificultad de Ethereum | El protocolo fuerza el cambio, pero el sucesor lo escriben humanos |

Las tres funcionan. Ninguna es determinista: en las tres, qué viene después es una decisión
tomada en el momento, por gente, bajo presión. Y esa decisión es exactamente donde un protocolo
se vuelve político.

---

## 2. La propuesta

Genesis contiene, además de las reglas de la primera generación, tres cosas más:

- **`TRANSITION_RULE`** — la condición de disparo, computable desde el estado de la cadena.
- **El espacio de parámetros** de todos sus descendientes posibles.
- **El intérprete** capaz de ejecutar cualquier punto de ese espacio.

Cuando la condición se cumple, el nodo lee la regla, selecciona los parámetros de la generación
siguiente y **cambia su propio ruleset**. No hay software nuevo que instalar, no hay estado que
migrar, no hay nadie a quien preguntarle.

**Cómo conviene leer lo que sigue.** Esas tres piezas no tienen el mismo respaldo, y decirlo acá
es más honesto que dejarlo para el final. La sucesión de **parámetros internos** —capacidad,
emisión, tiempos de bloque— es la mitad que salió a buscar destinatarios afuera y los encontró
(§12, Test 1). El **intérprete** y las **generaciones encadenables** —que son lo que hace posible
§6.6 y lo que separa este diseño de sus precedentes— son la mitad que paga las fronteras más caras
de §10.1 y que **todavía no tiene un caso encontrado afuera**. Van juntas porque el mecanismo es
uno solo; pero la primera es una aplicación y la segunda es una apuesta, y el documento no gana
nada escondiendo cuál es cuál.

---

## 3. El mecanismo: conmutación

La pieza que hace que esto no sea un fork disfrazado es que **el nodo no se reemplaza, se
conmuta**. Es el mismo proceso corriendo, con el mismo estado en memoria, ejecutando reglas
distintas a partir de un bloque determinado.

<!-- FIGURA: figura-conmutacion.html -->

```
   ┌──────── ruleset A ────────┐ ┌─ F ─┐ ┌──── Δ ────┐ ┌─── ruleset B ───┐
                                                     ║
   ───▣───▣───▣───▣───▣───▣───▣───▣───▣───▣───▣───▣──╫──▣───▣───▣───▣───▶
                              ▲       ▲              ║
                              │       │              ║
                          bloque N   N final    activación
                       TRANSITION_    LOCK-IN   conmutación efectiva
                        RULE → TRUE  irrevocable
                        (advisorio)  params_nuevos
                                      on-chain

   el MISMO nodo · el MISMO estado · sin migración, sin bridge, sin snapshot

   F = ventana de impugnación (§6.3) · Δ cuenta desde el lock-in, no desde N

   H0_A ─────────────▶ H0_B = H( H0_A ‖ state_trigger ‖ params_nuevos )
                       se computa en el lock-in, con N ya final
```

La pista del nodo no se corta en el bloque de transición: cambia de reglas. El estado cruza
intacto porque nunca sale del proceso que lo tiene.

### El disparo no es la activación

Conmutar en el mismo bloque en que la regla evalúa TRUE convertiría cada transición en una
sorpresa. El mecanismo tiene tres tiempos, no dos:

1. **Disparo.** En el bloque `N`, `TRANSITION_RULE` da TRUE. Eso no conmuta nada y todavía no
   compromete nada: es advisorio, y una reorganización lo puede deshacer. Como I2 exige que el
   trigger publique cuántos bloques faltan al ritmo actual, el disparo es simplemente el momento
   en que esa distancia llega a cero.
2. **Lock-in.** Cuando `N` es final, el disparo se vuelve **irrevocable**: de ahí en adelante,
   aunque el estado vuelva atrás, la activación ya está fijada. Un cronograma que se enciende y
   se apaga es peor que ninguno, porque nadie moviliza un equipo contra una fecha que puede
   evaporarse. Esperar a la finalidad no es ceremonia — `H0_B` compromete `state_trigger`, y
   comprometerlo antes dejaría al checkpoint apuntando a un estado que una reorganización puede
   sacar de la cadena. El lock-in emite el evento on-chain con `params_nuevos` completos y la
   altura de activación: todo lo que un integrador necesita saber está en la cadena, `Δ` bloques
   antes, sin que nadie tenga que anunciarlo ni pedir permiso para leerlo.
3. **Activación.** `Δ` bloques después del lock-in —no después del disparo, así el aviso es
   exactamente `Δ` y no depende de cuánto haya tardado la finalidad— el nodo conmuta.

`Δ` está fijado en Genesis **por clase de transición**, no globalmente: una transición de
circulación tolera una ventana larga —la emisión se pausa unas semanas y no pasa nada—, mientras
que una migración criptográfica bajo ataque necesita lo contrario. El intercambio es real y está
declarado en §10.1.

El hash de cada generación se deriva del de su ancestro, del estado que disparó la transición y
de los parámetros seleccionados. Genesis A **no conoce el hash de B** —no puede, porque B
incorpora información que todavía no existe— pero conoce determinísticamente cómo se calculará:

```
H0_B = H( H0_A ‖ state_trigger ‖ params_nuevos )

Verify( H0_B, H0_A, state_trigger, params_nuevos ) → TRUE
```

`H0_B` no es el génesis de una cadena nueva: es un **marcador de checkpoint generacional** dentro
de la misma cadena. Y hace el linaje completo verificable con un hash, desde cualquier generación
hacia atrás.

### Más de una transición en vuelo

Entre el lock-in y la activación pasan `Δ` bloques en los que la cadena sigue corriendo con las
reglas viejas aunque las nuevas ya estén comprometidas. Esa ventana no es un caso de borde:
aparece sola apenas hay una regla de acumulación, porque el estado que disparó sigue por encima
del umbral mientras el cambio todavía no tuvo efecto.

**Una regla no vuelve a disparar hasta su propia activación** — no hasta su lock-in. Si pudiera
dispararse en el medio estaría midiendo un estado que **todavía no refleja el cambio que ella
misma acaba de comprometer**, que es un lazo de control con tiempo muerto. Bitcoin Cash ya pagó
esa cuenta: su EDA de 2017 era una regla automática escrita de antemano que reaccionaba más rápido
de lo que su propio efecto se hacía visible, osciló, y hubo que reemplazarla por un fork humano a
los tres meses. Lo que cierra el lazo es el efecto, no el compromiso.

**Pero la espera es por regla y no global.** Bloquear todos los disparos mientras haya uno en
vuelo pondría una migración criptográfica de urgencia a esperar detrás de una transición de
circulación, y eso vacía la razón por la que `Δ` es por clase. Dos reglas distintas pueden estar
en vuelo a la vez, y la segunda hace lock-in sin esperar a la primera.

**Lo que sí comparten es el orden de activación.** `params_nuevos` es un punto completo del
espacio y no un incremento, así que activar la generación 2 antes que la 1 aplicaría también los
cambios de la 1, y con el aviso de la 2. Las generaciones activan en el orden en que hicieron
lock-in; si dos coinciden en la misma altura, se aplican en el mismo bloque, una tras otra.

> **Residuo declarado.** Una transición de urgencia puede esperar hasta el `Δ` restante de la que
> tenga adelante. Es **acotado** —el tope es la `Δ` más larga del espacio— y **no compone**: no
> crece con la cantidad de generaciones. Y lo que la concurrencia gana igual es lo irrevocable: la
> urgente queda comprometida y anunciada aunque su activación tenga que hacer cola.

De ahí que **`params_nuevos` se compute en el lock-in y no en el disparo**, que es también donde se
computa `H0_B`. Con dos transiciones en vuelo, unos parámetros calculados en el disparo colgarían
de un ancestro que dejó de ser el último, y el linaje no cerraría.

**Y por eso el lock-in verifica antes de comprometer.** Un checkpoint es irrevocable: si
comprometiera un punto fuera del espacio de Genesis, el nodo llegaría a la activación sin poder
conmutar y la cadena se detendría. El sucesor se verifica contra el espacio y contra la
aditividad de la interfaz **antes** de emitirlo, y si no pasa no hay checkpoint sino un **rechazo**,
también on-chain. Un rechazo no recorta el sucesor al borde del espacio —eso cambiaría la regla en
silencio— ni detiene el consenso: esa transición no ocurre, queda registrado que no ocurrió y
contra qué ancestro, y la regla no reintenta contra ese mismo ancestro. Que se vea que una regla
quedó pegada al techo del espacio es información, no una falla: es el fondo de escalera de §10.1
anunciándose con tiempo.

### El evento de lock-in es estado, no un anuncio

El lock-in emite on-chain el ruleset nuevo completo y la altura de activación, y lo hace en el
bloque en que `N` pasa a ser final — un bloque que, **por ser el último, todavía no es final él
mismo**. Una reorganización legítima puede reemplazarlo.

No hay contradicción, pero hay una regla de consenso que escribir: **el evento se emite en función
de la altura en que `N` se vuelve final, no de que el nodo acabe de enterarse.** Es un hecho
derivado de la cadena y no una notificación: cualquiera que reproduzca los mismos bloques lo
produce idéntico, porque sus dos insumos —el estado que disparó, ya final, y el ancestro
comprometido, ya irrevocable— no dependen de quién estuvo presente. Un nodo que publicara sólo *lo
que acaba de madurar* quedaría, después de una reorganización, con un lock-in vigente y sin
registro en el estado, y su raíz se separaría de la de un nodo que no reorganizó. **Eso no es un
aviso ilegible: es una bifurcación**, y de la peor clase, porque los dos nodos coinciden en todo lo
demás.

Que el registro viva **en el estado** y no en la memoria del nodo se paga por dos cosas distintas.
Un integrador con una cabecera y una prueba tiene que poder leer la activación sin replicar la
cadena entera; si no, el aviso de `Δ` existe sólo para quien ya corre un nodo completo, que es
justamente el que no lo necesita. Y §5 se apoya en lo mismo: *la cadena que no conmutó no tiene
checkpoint generacional válido* es verificable por un tercero únicamente si el checkpoint está en
el estado que la cadena commitea.

Un corolario para tener a mano: cuando la finalidad la decide la ventana de impugnación (§6.3) y
no un número fijo de bloques, la altura del lock-in también la deriva la cadena, y una
reorganización anterior a él puede moverla. Por eso el aviso se cuenta desde el lock-in y no desde
el disparo — y por eso `H0_B` no incluye alturas: mover *cuándo* no cambia *qué*.

---

## 4. Invariantes de diseño

Cinco propiedades no negociables. Cada una elimina una forma de reintroducir al humano en el
lazo.

**I1 · El intérprete vive en Genesis y no cambia nunca.** Una transición no introduce código de
nodo: selecciona un punto de un espacio que el nodo **ya sabe ejecutar**. Lo que Genesis fija de
manera permanente no es una lista de reglas posibles sino la **máquina que las corre**, y el
espacio de descendientes es todo lo que esa máquina puede ejecutar (§6.6). Si hiciera falta
cambiar el intérprete, no sería una transición — sería un fork común y corriente.

El espacio está partido en dos mitades con reglas distintas. Los parámetros **internos**
—emisión, fees, tamaño de bloque, tiempos— pueden cambiar en cualquier transición. Los
**visibles en la interfaz** —primitiva de firma, formato de dirección, serialización— solo por
la vía de I5.

*Esta invariante se debilitó a propósito, y el costo está declarado en §10.1: con un intérprete,
el conjunto de futuros posibles deja de ser auditable desde Genesis.*

**I2 · El trigger se computa solo desde el estado de la cadena, y nadie elige el momento.** Sin
oráculos, sin firmas, sin votos, sin insumos externos: un trigger que necesita que alguien lo
declare ya reintrodujo la gobernanza que el diseño existe para eliminar. Pero computable no
alcanza, y no alcanza por dos motivos distintos: una variable volátil es computable y sorpresiva
a la vez, y *"el estado dice que Alice mandó 1 wei a la dirección X"* también se computa solo
desde el estado — y es una compuerta con dueño.

Hay **dos formas** de que nadie elija el momento, y toda regla tiene que declarar en cuál está.
Por **aproximación observable**: la cantidad que dispara es monótona no decreciente y la cadena
publica *cuántos bloques faltan al ritmo actual*. Nadie elige el momento porque la aproximación es
agregada y pública, y ningún actor la mueve solo. Una regla declarada así **no puede disparar
desde el reposo**: si el bloque anterior no publicó una distancia, lo que hubo no fue una
aproximación sino un escalón.

Por **capacidad demostrada**: no hay aproximación y no puede haberla. Es el caso de §6.6 —la
rotura de una primitiva no se aproxima, ocurre— y es admisible solo si **producir el hecho exige
exactamente la capacidad ante la que la transición existe para reaccionar**. Quien puede elegir el
momento es, por construcción, aquel contra quien el mecanismo se defiende, y elegirlo le cuesta la
ventaja que tenía. La regla declara cuál es esa capacidad, la declaración va on-chain, y la cadena
publica *sin aproximación observable* en lugar de inventar una fecha.

Las dos excluyen lo mismo: un hecho que una parte identificable puede producir a voluntad y
barato. Y las dos tienen su límite escrito. Ningún nodo puede verificar que la capacidad declarada
sea la verdadera: eso se audita en Genesis, que es donde el espacio de reglas está fijo y a la
vista (I1), y por eso la declaración es obligatoria y explícita en vez de implícita. Y la distancia
de la primera forma es una **proyección al ritmo actual**, no una promesa — el ritmo puede cambiar.
La promesa es `Δ`, que se cuenta desde el lock-in y no depende de que nadie haya sabido ver venir
nada.

**I3 · El estado se conserva íntegro a través de la transición.** No hay migración de saldos, no
hay reasignación, no hay snapshot — y por lo tanto no hay bridge, que es el componente más
atacado de la industria.

**I4 · Cada generación commitea a su ancestro.** El linaje es verificable por hash y no depende de
que nadie lo atestigüe.

**I5 · Las transiciones son aditivas en la interfaz.** Toda dirección y toda transacción llevan
etiqueta de generación desde el bloque 0. Una transición puede **agregar** formatos; no puede
quitarlos. Retirar un formato es una transición posterior, separada por al menos una generación
de la que lo deprecó.

Esta es la invariante que decide el modo de falla de todo integrador externo. Con ella, quien no
llegó a soportar la generación nueva **sigue operando en la anterior** —los objetos viejos
siguen siendo válidos— y degrada en vez de detenerse. Y cuando encuentra un objeto de la
generación nueva falla cerrado y ruidoso, *"versión que no conozco"*, en vez de malinterpretarlo,
que es la falla que pierde fondos.

---

## 5. Canonicidad

La conmutación produce una consecuencia que no es obvia y que es, probablemente, la propiedad más
valiosa del diseño: **invierte la asimetría de legitimidad de un fork.**

En Bitcoin la posición conservadora —no cambiar nada— es el default. Quien quiere cambiar las
reglas tiene que escribir software nuevo, y la cadena que sigue igual puede reclamar ser la
original. Acá es al revés: el cliente estándar conmuta solo, así que **para no conmutar hay que
modificar activamente el software** y desactivar la regla de transición. El que se queda en las
reglas viejas no preserva la cadena original — se desvía de Genesis, y no puede invocar a Genesis
para justificarlo.

La consecuencia práctica es que *"cuál es la verdadera"* deja de ser una pregunta social. Un
exchange, una wallet o un light client corren la verificación de linaje, y la cadena que no
conmutó simplemente no tiene checkpoint generacional válido. Es un criterio de canonicidad
objetivo, y ningún fork disputado de la historia tuvo uno.

---

## 6. Arquitectura: nodos, trabajo y orden

### 6.1 Dos clases de nodo, con economías distintas

**Nodos de cómputo.** GPU y RAM. Hostean los modelos que hacen el trabajo pedido. Es hardware
caro y es un mercado competitivo, pero **no participan del consenso**: su ingreso es el pago del
pedido que ejecutaron, no la emisión del protocolo por producir bloques.

**Nodos PoD.** Verifican y liquidan, y cobran un fee cada vez que dos contratos interactúan.
Corren en cualquier hardware — la verificación PoD reproduce bit a bit en x86-64, ARM64 y un
teléfono.

**El fee es ad valorem, no fijo por operación.** Un fee fijo es regresivo en las dos direcciones
que importan: vuelve impagable el pedido chico —que es el que una economía de agentes va a hacer
en volumen— y vuelve gratis el pedido grande, que es justo donde la quema de §7.1 tiene que
morder para que el retiro de circulante siga al valor y no al número de operaciones.
Proporcional al valor, el mismo parámetro sirve para las dos escalas sin que nadie decida cuál
es cuál.

**La regla tiene una excepción y conviene declararla acá:** un activo recién creado vale ~0, así
que un fee ad valorem no muerde sobre su creación. Es la única operación del diseño donde la regla
de §6.1 no alcanza, y por eso el antispam del minteo no viene de la fee sino del piso y del
depósito de permanencia de §8.5.

La portabilidad tiene además una consecuencia de gobernanza. **Lo que le permite a un minero o a
un validador tomar de rehén una cadena no es su convicción: es el foso de capital.** Reemplazar a
quien se niega cuesta ASICs o stake, y mientras tanto la cadena no avanza. Un nodo que entra en un
teléfono no tiene foso: si un grupo se niega a conmutar, el costo marginal de reemplazarlo es un
celular. **Una coalición de bloqueo no puede durar si entrar es gratis.**

**Hay un argumento más fuerte que ese, y no depende del costo de entrada.** El de arriba se apoya
en que entrar sea barato, y Test 2 lo debilitó: el costo es asimétrico por plataforma, hasta 15×
según el sistema operativo (§10.1). El argumento que no se debilita es otro:

> **Podés tener 3.000 nodos o 3 millones. Si no hay demanda externa, todos compiten por una torta
> que no existe.** Como la emisión no depende del trabajo (§7.1), sumar nodos no crea ingreso:
> sólo reparte el mismo fee entre más manos. **Fabricar identidades es gratis y da exactamente lo
> mismo**, que es una propiedad bastante más robusta que hacerlo caro.

**Medido (Test 2, §12).** En un Motorola Edge 40 Neo bajo Termux, una verificación ML-DSA-44 desde
bytes corre en **391 µs** como bytecode con JIT —3,51× el nativo— y da ~640 tx/s con un cuarto de
núcleo dedicado a firmas. Es el mismo tiempo absoluto que en un i5-9400 de escritorio. El
presupuesto entra con margen.

Con una salvedad que el argumento de arriba no anticipaba: **no todos los teléfonos cuestan lo
mismo.** iOS no permite JIT a terceros, y como acá el bytecode llega en tiempo de ejecución desde
la cadena, tampoco se puede precompilar antes de publicar la app. Un nodo en iPhone queda forzado
al intérprete: **~15× más lento** que el mismo aparato en Android. La coalición de bloqueo sigue
sin poder durar —entrar sigue siendo barato en términos absolutos— pero el costo de entrada es
asimétrico según el lado del duopolio, y esa asimetría es del sistema operativo, no del diseño
(§10.1).

### 6.2 PoD verifica el predicado, no la inferencia

Un modelo no puede pasar el gate de determinismo que sostiene a PoD. Ni siquiera a temperatura
cero: el no determinismo de punto flotante entre hardware distinto rompe la reproducción bit a
bit, y sin re-ejecución reproducible una disputa no se puede resolver sin que aparezca un humano
opinando.

La separación en dos capas lo vuelve irrelevante. **La GPU produce; el nodo liviano comprueba.**
El pedido no dice *"generá buen código"* — dice *"entregá algo que compile y pase estos tests"*, y
eso se chequea determinísticamente, barato, en cualquier hardware. La inferencia no se verifica:
se verifica que **la salida satisface el predicado**.

De ahí sale una restricción dura sobre qué puede ser un pedido de trabajo:

> **Todo pedido lleva un predicado de aceptación determinístico y lo bastante barato como para
> correr en la capa liviana.** Lo que no se pueda expresar así no es trabajo que emita moneda.

Eso convierte una advertencia difusa —*"no todo trabajo es demostrable"*— en una frontera nítida:
el subconjunto liquidable es exactamente el de los pedidos con predicado verificable. Código que
compila y pasa tests, una respuesta que satisface un chequeo, una transformación con inversa
comprobable. Que ese subconjunto sea lo bastante grande como para sostener una economía es una
hipótesis, y está en §12.

**Y hay un corolario que parece una limitación y es lo contrario: el cliente no elige qué nodo
ejecuta su pedido, y no lo necesita.** En un mercado de servicios normal, elegir proveedor *es* el
mecanismo de calidad: uno investiga, compara reputaciones y apuesta. Acá la calidad no se asegura
seleccionando de antemano sino **en la aceptación** — si la salida no satisface el predicado, no
hay pago. Es la misma inversión que hace el resto del diseño: no confiar en quién, verificar qué.

De ahí sale también una propiedad que §6.5 usa: como no hay canal por el cual dirigir un pedido a
un nodo en particular, tampoco hay canal por el cual una reputación previa —haber estado en el
bloque 0, por ejemplo— pueda convertirse en ventaja económica.

### 6.3 Orden sin consenso global

Verificar y ordenar no son la misma operación, y conviene decirlo porque se confunden con
facilidad. Si Alice firma dos transacciones que gastan los mismos 100 tokens, **las dos son
individualmente válidas**: cualquier verificador que las mire por separado dice TRUE a las dos.
Solo el orden decide cuál gana. Ese es el problema que el consenso existe para resolver, y la
validez no lo toca.

Pero el orden **global** no hace falta:

- **Cola por cuenta.** Cada cuenta lleva su propia secuencia y su dueño es el único que puede
  agregarle. Dos interacciones que no comparten colateral no necesitan orden relativo — y no lo
  tienen, que es distinto de tenerlo indefinido.
- **El lock elimina la contienda.** Comprometer fondos en un contrato los saca del saldo
  disponible. No se pueden comprometer dos veces, así que el único hecho que cruza entre cuentas
  —*"estos tokens están comprometidos"*— no necesita ordenarse contra nada.
- **Finalidad por ventana de impugnación.** Una interacción queda firme cuando pasa la ventana
  sin que nadie presente prueba de conflicto. No es un mecanismo nuevo: es la verificación
  optimista del escrow, ascendida a capa de finalidad.

Queda un solo conflicto real: que el dueño de una cuenta firme dos cosas en el mismo índice.

**La ventana de impugnación no se puede tapar, y el motivo no es el precio.** La objeción evidente
es que si procesar impugnaciones tiene capacidad finita, un atacante la llena de basura para que
una prueba legítima no entre a tiempo — y con el tope duro de demora al lock-in (§10.1) eso
alcanzaría para que un fraude quede firme. No alcanza, por una asimetría estructural:

> **Llenar es serial; drenar es paralelo.** Una impugnación no existe hasta que entra en un
> bloque, así que el techo para llenar es la capacidad de la cadena — un solo caño. Drenar lo
> hacen todos los nodos PoD **a la vez**, porque la verificación reproduce bit a bit en cualquier
> hardware y cualquiera puede tomar cualquier impugnación.

El margen es `N · h / γ`, con `N` nodos, `h` el trabajo que cada uno hace por bloque además de
verificar el bloque, y `γ` el costo de verificar una impugnación medido en transacciones
equivalentes. Con `γ ≈ 1` —que es lo que garantiza el techo de pasos de VM de §10.1— y un headroom
del 10% por nodo, la fórmula da **diez nodos PoD**; corrida con una cola de verdad en vez de
calculada, hacen falta **once**, y el porqué está en la tercera condición de abajo. El 10% es
conservador en un orden de magnitud: Test 2 midió 640 tx/s usando un cuarto de núcleo en un
teléfono de ocho.

**Tres** condiciones sostienen eso y hay que escribirlas, porque ninguna es automática:

- **cualquier nodo PoD resuelve cualquier impugnación.** Si hiciera falta el nodo que ordenó la
  interacción original, no habría trabajo paralelo que repartir y `N` desaparecería de la fórmula;
- **orden de llegada, y bono plano.** Si la cola se ordenara por tamaño de bono, el capital
  compraría prioridad. Con orden de llegada, el bono deja de ser una **puja** y pasa a ser un
  **costo**: se pierde si la impugnación no verifica, y *"no verifica"* es determinístico, así que
  no hace falta juez;
- **cada nodo elige en su propio orden, y no en el de la cola.** Es la condición que faltaba, y
  apareció al correr la cola en vez de calcularla. El orden de llegada resuelve la **prioridad** —el
  capital no compra turno—, pero si además cada nodo toma **de la cabeza**, los `N` nodos verifican
  exactamente la misma impugnación y el paralelismo se evapora: medido, con cincuenta nodos el
  margen es idéntico al de uno solo, la cola satura con cualquier `N`, y una impugnación legítima
  enterrada en basura no espera un plazo fijo sino una rampa: el atraso crece unos noventa por
  bloque y se drena a diez, así que lo que llega en la altura `T` espera del orden de `9·T` —el
  ataque de censura funcionando, y empeorando con el tiempo—. La regla que lo arregla no necesita
  coordinación ni saber cuántos nodos hay: **cada nodo recorre la cola en un orden pseudoaleatorio
  derivado de su propia identidad.** El costo es de **un nodo**: el `N` necesario pasa de diez a
  once, porque dos nodos a veces coinciden. La alternativa exacta —repartir la cola entre los `N`—
  reproduce el diez clavado y **exige saber cuántos son**, que es justamente lo que un diseño sin
  conjunto de validadores no puede saber.

Y hay una propiedad del caso al azar que conviene tener escrita, porque es la que hace que once
alcancen: **el atraso no crece sin techo, se estabiliza.** Cuanto más larga la cola, menos se pisan
los nodos, así que el desagüe efectivo sube solo hasta igualar a la canilla. Con once nodos el
equilibrio queda en unas cuatrocientas impugnaciones y una espera media de cuatro bloques; con
veinte, en veinte impugnaciones y dos décimas de bloque. *La cola es larga, no infinita, y eso es
otra cosa.*

El bono no tiene que ser grande, sólo distinto de cero, y la razón es una asimetría que juega
entera del lado correcto: **el bono del impugnador honesto vuelve** —su prueba verifica— **y el
del atacante se quema.** Mandar diez mil copias de una prueba válida no le cuesta nada al honesto,
y mandar diez mil impugnaciones falsas es diez mil bonos perdidos.

Debajo de esa decena de nodos la cola sí satura. Es el régimen del arranque, y ahí la cadena tiene
problemas más grandes que éste.

**Qué pasa en el bloque de la transición.** Nada especial, y por dos motivos distintos. Lo que
está en el mempool no es estado de consenso: valen las reglas del bloque que lo incluye, y lo que
queda inválido simplemente no entra — es lo que hace cualquier cadena en cualquier hard fork y no
necesita mecanismo propio. Y lo que sí está a medio comprometer **en el estado** —una oferta
firmada y no aceptada, un escrow con la ventana abierta cruzando la activación— lo resuelve I5:
cada objeto lleva su etiqueta de generación y los rulesets viejos nunca se retiran, así que **un
escrow abierto en la generación A se liquida con las reglas de A**. Las reglas nuevas aplican
solo a lo que se abre después de la activación, que además es lo justo: las partes acordaron bajo
reglas conocidas.

### 6.4 La equivocación no se prohíbe: se vuelve suicida

Que una firma sea infalsificable no impide que su dueño firme **dos mensajes distintos**. Las dos
son genuinamente suyas, ninguna está falsificada, y ningún esquema de firma puede evitarlo. Por
eso la respuesta no es prohibir sino hacer que no convenga — y hay una forma de que el castigo
sea criptográfico en vez de administrativo.

En Schnorr y ECDSA, firmar dos mensajes distintos **con el mismo nonce criptográfico** permite
despejar la clave privada de las dos firmas. Es un accidente conocido: así se perdió la clave de
la PS3, y así se vaciaron wallets con generadores de aleatoriedad malos.

Convertido en regla de diseño: **el nonce de firma es una función determinística del índice de
la cuenta.** Entonces firmar dos veces en el mismo índice no es una infracción que haya que
probar y sancionar — **es publicar la propia clave privada.** Cualquiera que junte las dos firmas
se queda con todo lo que el equivocador tenga.

Tres consecuencias, y la tercera es la que cierra el diseño:

1. El castigo no necesita regla de protocolo, ni bond, ni árbitro que lo ejecute.
2. Se verifica en un teléfono: son dos firmas y una resta.
3. **El vigilante se financia solo.** El problema clásico del challenger —nadie tiene motivo para
   mirar— desaparece cuando la recompensa por pescar la infracción es el saldo del infractor. No
   hay que inventar un incentivo: el incentivo es el botín.

### 6.5 Toda transferencia es bilateral

No existe el envío unilateral. Alice ofrece, Bob acepta, y recién ahí la transferencia existe;
si Bob nunca contesta, un timeout devuelve los fondos.

**Hay dos clases de oferta y la diferencia es de diseño, no de uso.** Una transferencia común es
**dirigida**: nombra al receptor, porque pagarle a alguien puntual es el punto. Un pedido de
trabajo es **abierto**: no nombra a nadie, lo toma el nodo que pueda cumplir el predicado, y el
lock de §6.3 hace que se lo lleve uno solo. Esa segunda forma es todo el mecanismo de asignación
de trabajo del sistema, y conviene decirlo porque no está escrito en ninguna otra parte:

> **Nadie asigna pedidos.** El cliente publica predicado, precio y plazo con los fondos ya
> comprometidos; el nodo que puede cumplirlo lo acepta. Es *pull*, no *push* — el nodo se
> autoselecciona porque conoce su propio hardware, y se autofiltra solo, porque aceptar un pedido
> que no puede cumplir es fallar el predicado y no cobrar.

De ahí salen tres cosas gratis. **No hay cómputo duplicado**, porque se acepta antes de computar y
el que pierde la aceptación no gastó nada. **Un nodo saturado simplemente no acepta**, así que el
pedido queda disponible para otro sin que nada tenga que rutearlo. Y **el cliente no puede dirigir
trabajo a un nodo elegido**, que es la propiedad de la que depende que el certificado de §7.2 no
se convierta en ventaja.

El plazo lo declara el cliente junto con el precio, y ahí está la tensión que hay que fijar: largo,
un nodo puede aceptar y no entregar para bloquear el pedido barato; corto, el nodo con hardware
lento no llega y pierde la electricidad que ya gastó. Declarándolo el cliente, el nodo decide
sobre tres ejes en vez de uno —*¿puedo cumplir el predicado, a este precio, en este plazo?*— y el
parámetro lo fija quien paga las consecuencias. **El que acepta y no entrega no cobra y libera el
pedido**, y como aceptar es un acto on-chain que devenga fee, bloquear pedidos cuesta plata y
compra sólo un plazo de demora.

Esto no previene el doble gasto —eso lo hacen el lock y §6.4— pero hace otras dos cosas:

**Pone al vigilante donde ya estaba mirando.** El que tiene que firmar para aceptar es el que
puede perder. Bob está online, está por comprometerse, y revisar el índice de Alice antes de
firmar no le cuesta nada extra. El observador interesado deja de ser un rol que hay que financiar
y pasa a ser un firmante obligatorio.

**Y convierte la prudencia en estructura.** Como la aceptación es un acto on-chain, *"esperar la
finalidad"* deja de ser una disciplina que el receptor tiene que acordarse de cumplir: no hay
transacción hasta que firmó. En Bitcoin, aceptar con cero confirmaciones es una imprudencia que
el protocolo permite; acá no hay dónde ser imprudente.

Los costos están en §10.1: no se le puede pagar a alguien que está offline, y la finalidad se
mide en minutos u horas.

### 6.6 Evolución criptográfica sin fondo de escalera

Toda primitiva criptográfica termina cediendo, y una cadena que no puede reemplazar las suyas
tiene fecha de vencimiento. El problema es que *"la primitiva se rompió"* no está en el estado de
la cadena, así que no puede ser un trigger (I2); y si Genesis trajera una **lista** de primitivas
de reemplazo, la lista se agotaría y haría falta un fork humano. Ninguna de las dos cosas es
aceptable, y las dos se resuelven con el mismo lazo.

**El canario convierte la rotura en un hecho del estado.** Genesis publica una versión
deliberadamente debilitada de la primitiva, con una recompensa on-chain. Si alguien la rompe y
la reclama, eso **sí** es estado: hay una preimagen o una falsificación escrita en un bloque. El
trigger no lee *"la criptografía se rompió"* — lee *"el canario fue reclamado"*, que es
observable, determinístico y sin oráculo. La recompensa además hace que alguien efectivamente lo
intente: es el mismo patrón de §6.4, el vigilante financiado por el botín.

**La instancia debilitada se deriva; no se genera.** Es la condición que vuelve admisible al
canario bajo I2 —la forma de *capacidad demostrada*— y es fácil pasarla por alto. Si Genesis
**generara** la instancia —un módulo, un par de claves—, quien la generó conservaría su trampa y
podría reclamar el canario cuando se le diera la gana. Lo que I2 admite como capacidad demostrada
sería, en realidad, un secreto que alguien se guardó: el canario dejaría de ser una alarma para
ser una compuerta con disfraz criptográfico, o sea la misma gobernanza que el diseño elimina, pero
mucho más difícil de ver. Por eso la instancia sale de una **semilla pública** por un
procedimiento determinista, sin nada en la manga, y cualquiera la rederiva desde Genesis. Un
canario que no se puede rederivar de su semilla no es un canario: es de alguien.

**La escalera de canarios gradúa la respuesta.** Un canario débil cede años antes que uno
fuerte, así que el débil dispara una migración con `Δ` largo —planificada, sin emergencia— y el
fuerte una con `Δ` corto. Para cuando alguien pueda romper el fuerte, la migración ya se hizo. Es
lo que evita el caso de una sorpresa criptográfica con ventana de gracia corta.

**El intérprete quita el fondo de la escalera.** Como Genesis fija la máquina y no la lista (I1),
una primitiva nueva es **bytecode**, no código de nodo. El nodo no se actualiza nunca porque ya
sabe ejecutar la máquina, y el conjunto de primitivas posibles deja de ser finito.

**Quién escribe ese bytecode: es un pedido de trabajo.** Cuando el canario cae, el protocolo
publica un pedido —*"entregá una implementación que cumpla esta interfaz y estos vectores"*— y los
agentes compiten por entregarlo. El predicado de aceptación es determinístico y barato de correr
en la capa liviana, que es exactamente lo que §6.2 exige de cualquier pedido. No hay comité que
elija: el que entrega cobra como cualquier otro trabajo.

**Quién dice que es segura: nadie puede, así que se prueba a los golpes.** La seguridad
criptográfica no es una propiedad decidible — no existe predicado que la verifique. Lo que sí se
puede es volver mecánico el estándar que usa el mundo real, que es *"muchos lo atacaron y nadie
pudo"*:

> **El guante.** Toda candidata entra con una instancia debilitada y una recompensa on-chain
> durante una ventana fija. Si alguien la rompe, queda descartada y pasa la siguiente. La que
> sobrevive la ventana se instala. Es el mismo canario, usado como examen de ingreso en vez de
> como alarma.

**El guante mide seguridad; el costo lo mide otra cláusula.** Una implementación puede ser correcta
e irrompible y aun así diez veces más cara que la que reemplaza: nadie la puede romper —es
correcta— así que sobrevive la ventana y queda instalada para siempre. En ese momento el
presupuesto de §6.1 se rompe *desde adentro del protocolo*: sin fork, sin atacante y sin que
ninguna regla se haya violado. Por eso el predicado de aceptación lleva **tres** cláusulas y no una:

> **Corrección, techo y localidad.** La candidata tiene que pasar los vectores, verificar por
> debajo de un **techo de pasos de VM**, y hacerlo tocando menos de un **techo de páginas**. Los
> dos techos se miden en cantidades ejecutadas, no en tiempo de reloj: son determinísticas y
> reproducen entre arquitecturas (Test 2 midió el conteo idéntico entre x86-64 y ARM64), así que
> califican como predicado bajo §6.2 y como hecho del estado bajo I2. El tiempo de reloj no
> calificaría: depende del hardware, y eso sería un oráculo.

**El techo no es un número libre, y no es una decisión de rendimiento.** Por un lado lo ata el
presupuesto de §6.1 —la verificación tiene que seguir entrando en la capa liviana, que es de donde
sale la entrada barata de nodos y con ella la respuesta al problema de los validadores—; por el
otro es **una condición de seguridad de §6.3**, porque es lo que impide que exista una impugnación
más cara de verificar que de crear (§10.1). Una candidata correcta que no entra en el techo no se
rechaza por insegura: se rechaza por impagable, que es el mismo criterio que §6.1 aplica a todo lo
demás.

**Y el techo no se elige: se deriva.** Es lo que ata `§6.1` con `§6.6` en una sola cuenta —
`techo = f* × tiempo_de_bloque × R_declarado / tx_por_bloque`, donde `f*` es la fracción del nodo
liviano que puede ocupar la verificación de firmas y `R_declarado` es el ritmo del hardware de
entrada, ambos congelados en Genesis, y los otros dos son parámetros internos de la generación. Lo
que I1 congela es **la fórmula**; el valor lo pone cada generación. El desarrollo, las dos
constantes y lo que queda decidido está en §10.3.

### 6.6.1 · Por qué son dos techos y no uno

Un techo de pasos supone que un paso vale un paso, y **eso es falso**. Construida la máquina y
medida contra mezclas de instrucciones elegidas para ser lentas, la peor corre a **veintitrés veces
menos pasos por segundo** que la carga real de la que salió `R_declarado`. Con ese hueco abierto, un
predicado perfectamente legítimo gasta su techo entero en 596 milisegundos en vez de los 22 que el
techo promete: **la cadena se atrasa de forma determinista, sin fork, sin atacante y sin que ninguna
invariante lo vea**. Es el mismo modo de falla que abre esta sección, una capa más abajo.

**Y no se arregla pesando las instrucciones.** La salida obvia es cobrar cada paso según su clase
—lo que hace el gas—, pero la mezcla que produce el hueco es una lectura de memoria, y una lectura
cuesta lo mismo que una suma cuando el dato está en caché: 207 millones de pasos por segundo contra
11. **Es el mismo opcode.** Lo que los separa no es qué instrucción es sino dónde cae el dato, y eso
no se lee del binario: sólo se sabe corriéndolo. Un peso por clase tendría que cobrarle a toda
lectura el precio de la peor, y entonces la primitiva de referencia —que está llena de accesos que
sí pegan en caché— dejaría de entrar.

Lo que sí se puede contar mientras corre es **cuántas páginas distintas toca el programa**, y ése es
el segundo techo: 96 páginas de cuatro kilobytes. La verificación de referencia toca 26.

**Y el segundo techo estuvo a punto de introducir en el diseño lo único que el diseño no admite: un
muro.** Escrito como constante, el presupuesto de páginas tenía una propiedad que la escritura no
delataba. Un techo derivado de la capacidad puede *encarecer* —una primitiva que cuesta más pasos
entra bajando `tx_por_bloque`— pero **un techo constante sólo puede excluir**, porque no hay precio
que la primitiva pueda pagar. Y las tres primitivas de una misma familia no tocan la misma memoria:
26, 40 y 65 páginas. Un presupuesto elegido con la vista puesta en la primera deja a la tercera
afuera para siempre, y ninguna cuenta lo señala.

**La salida es la misma jugada que ya había cerrado el techo de pasos: dejar de congelar un punto y
congelar la cuenta.** Acá la cuenta es una curva —cuánto ritmo sostiene el hardware de referencia
para cada presupuesto de memoria—, medida una vez y congelada en Genesis. El presupuesto de páginas
pasa a ser un parámetro interno como el tiempo de bloque o la capacidad, y **pedir más memoria baja
el ritmo declarado, que baja el techo de pasos, que se paga en capacidad**. Con eso los dos techos
dejan de ser dos: son la misma cota de tiempo mirada por dos lados.

```
techo = f* × tiempo_de_bloque × R_declarado(páginas) / tx_por_bloque
```

Lo que la curva cobra no se podía anticipar sin medirla, y es lo más útil que dejó: **de 96 a 512
páginas la memoria es casi gratis** —el ritmo cae un 4%— y **entre 512 y 1.024 se derrumba por
7,4×**, que es donde se acaba el alcance de la TLB del núcleo de referencia. El mecanismo cobra esa
forma sin que nadie la declare: cuadruplicar el presupuesto cuesta un 4% de capacidad y el paso
siguiente la divide por siete.

> **Y el espacio deja de necesitar un límite por decreto.** El punto más caro de la curva está
> declarado y es ruinoso: con dieciséis megabytes de conjunto de trabajo la cadena hace una
> transacción por bloque. Es una elección legítima y nadie la va a tomar — que es exactamente cómo
> tiene que verse una frontera en este diseño.

**Lo que esto le costó al bloque 0 se declara.** `R_declarado` se había calibrado sobre el ritmo de
una sola mezcla de instrucciones, y la corrección lo baja de 300 a 70 millones de pasos por segundo
— porque lo que tiene que aguantar no es el promedio sino el peor caso admisible, y el adversario no
corre el promedio. El techo en pasos casi no se mueve; lo que cambia es cuántos pasos garantizados
compra un segundo de reloj, y como el costo en pasos de una verificación lo fija el ISA y no el
ruleset, **la capacidad inicial baja de 67 a 15 transacciones por bloque**. Es el mismo mecanismo que
esta sección describe para las primitivas futuras —entrar cuesta capacidad—, cobrado sobre la que ya
estaba. La medición completa está en §12, Test 5.

```
canario roto  →  pedido de trabajo  →  candidatas entregadas
                                              ↓
                            predicado: vectores + techo de pasos
                                              ↓
                                     guante: instancia débil
                                     + recompensa + ventana fija
                                              ↓
                            la que sobrevive se instala como bytecode
                                              ↓
                                     canario nuevo publicado ──┐
                                              ↑                │
                                              └────────────────┘
```

El lazo se repite indefinidamente, todo on-chain y sin que nadie decida nada. Los cuatro costos
que esto trae están en §10.1, y el que decide si es realizable está en §12.

**Convergencia previa.** La idea de que una cadena lleve precargado desde Genesis el mecanismo de
su propia sucesión criptográfica ya había aparecido: en febrero de 2018, Justin Drake propuso
*cryptographic canaries* en Ethereum Research — un mecanismo con un bounty, redimible mediante una
prueba de amenaza, que al activarse conmuta automáticamente a una primitiva criptográfica de
respaldo.

Este diseño fue concebido independientemente de esa discusión. La coincidencia es, por tanto,
información relevante: la premisa de que la evolución criptográfica pueda anticiparse en el
protocolo, en lugar de decidirse después de que aparezca la amenaza, ya había surgido de forma
natural al abordar un problema distinto. La convergencia no demuestra la validez del diseño, pero
sí constituye evidencia de que la premisa merece consideración independiente.

La diferencia está en la profundidad de la sucesión. El respaldo de Drake es un mecanismo
precableado de un solo escalón: una transición hacia una primitiva alternativa. Aquí, en cambio, el
sucesor se deriva dentro de un espacio de transiciones definido por Genesis, y el intérprete permite
encadenar generaciones sucesivas.

En la discusión original se objetó —y es la objeción que dejó la idea sin avanzar— que calibrar un
canario para que dispare *antes* de que la criptografía en producción esté comprometida obliga a
estimaciones tan conservadoras que la automatización termina siendo redundante con la supervisión
manual.

La objeción es correcta para un mecanismo de un solo escalón. Una transición prematura consume el
único recurso de recuperación disponible, así que el trigger tiene que ser casi perfecto; y un
trigger que tiene que ser casi perfecto necesita a alguien que lo juzgue. Ahí la automatización se
disuelve.

Una sucesión encadenable cambia ese cálculo. Una transición prematura no destruye la capacidad
futura de recuperación: consume una generación que puede, a su vez, generar la siguiente bajo las
reglas de Genesis. El trigger deja de tener que ser perfecto — y con eso desaparece la razón por la
que la automatización recaía en supervisión humana.

La segunda objeción de esa misma discusión —que quien puede romper la primitiva gana más
callándose que cobrando la recompensa— no la resuelve este lazo, y está declarada en §10.2.

---

## 7. Política monetaria

### 7.1 Tres mecanismos que no hay que fundir

Toda regla monetaria tiene que contestar una sola pregunta: **cuánto dinero nuevo puede existir,
y en función de qué.** La primera versión de este diseño contestaba *"en función del trabajo
pagado y verificado"* —emisión indexada al trabajo liquidado, acotada por una curva temporal— y
esa respuesta no sobrevivió a su propio test. Conviene decir cómo murió, porque el cadáver es el
mejor argumento a favor de lo que la reemplaza.

**El teorema que la mató.** Si la emisión se indexa al trabajo liquidado, entonces para quien
ocupa los dos lados de la operación —paga el pedido y ejecuta el pedido— la emisión neta del
sistema y su propia ganancia **son la misma cantidad**:

```
emisión neta  =  (k − β·φ) · W  =  ganancia del autotratante
```

No son dos números que haya que balancear con cuidado: es una identidad. **La red emite si y solo
si auto-pagarse es rentable.** El único punto donde el autotrato deja de rendir es `k = β·φ`, y
ahí la emisión neta es exactamente cero — o sea, el punto seguro es aquel en el que el mecanismo
entero equivale a no emitir ni quemar. Medido en §12, Test 4.

> **La emisión indexada al trabajo no tiene ventana angosta: tiene ventana de medida cero.**

La salida no es calibrar mejor. Es dejar de fundir en un solo mecanismo tres cosas que hacen
trabajos distintos:

| mecanismo | qué hace | de qué depende |
|---|---|---|
| **fees** | remuneran el trabajo entregado | de la demanda real |
| **emisión** | fija el estado monetario | **de nada que un nodo pueda fabricar** |
| **PoD** | valida qué trabajo y qué transición son válidos | del predicado, no de la intención |

> **Ninguna unidad nueva se crea porque un nodo decidió hacer más trabajo.**

La diferencia con la versión anterior no es de grado. Antes, fabricar trabajo producía tokens y
todo el diseño consistía en lograr que produjera pocos; ahora **no produce ninguno**. El farmeo no
se vuelve poco rentable: deja de existir como categoría. Y eso desacopla dos cosas que estaban
atadas y no podían estarlo —la fricción contra el farmer y la fricción contra el usuario real—,
que es exactamente lo que hacía imposible la ventana de Test 4.

Las fees se reparten en tres destinos. Los porcentajes son de ejemplo y no de diseño; lo que
importa es que los tres existan:

```
fee del pedido  ─┬─  70%  proveedores      (paga el trabajo)
                 ├─  20%  quema            (retira circulante)
                 └─  10%  reserva          (se redistribuye entre nodos)
```

**La quema es la única pieza irreemplazable.** Con quema en 0% el circuito cerrado queda a mano y
el autotrato pasa a ser gratis. Todo el resto del reparto es negociable; eso no. El porqué está
en §7.3.

### 7.2 La distribución del día 1

Sacar la emisión de la ecuación del trabajo deja una pregunta sin la cual el resto no arranca:
**quién tiene tokens antes de que exista el primer fee.** Es la misma pregunta que las tres
respuestas clásicas contestan mal.

- **Oferta fija creada de golpe.** Elegante, pero traslada el problema al reparto: quién recibe y
  con qué criterio. Es una decisión humana en el bloque 0.
- **Emisión por calendario.** Distribuye en el tiempo, pero sigue sin decir a quién.
- **Indexada a trabajo.** Funciona sólo si el trabajo tiene costo externo y físico — y entonces es
  prueba de trabajo, que es lo que este diseño evita en el consenso.

No hay una cuarta, y el motivo es el mismo teorema de §7.1 en otra forma: **una distribución de
tokens nuevos indexada a una acción rinde a lo sumo lo que cuesta esa acción, o es farmeable.**
Si paga menos que el costo, nadie la reclama; si paga más, se farmea. Bitcoin pudo porque hashear
tiene costo externo, físico e imposible de fingir.

**La forma elegida toma la tercera, acotada al bloque 0.** Genesis publica pools con tope por
clase de nodo, y **reclamar se paga demostrando la capacidad que se reclama**:

| clase | qué demuestra el claim | maquinaria |
|---|---|---|
| **cómputo** | resolver una tarea de referencia con predicado determinista | §6.2 |
| **PoD** | verificar un lote de referencia dentro del techo de pasos de VM | §10.1 |

Cuatro propiedades, y la última es la que justifica todo el arreglo:

1. **No necesita identidad.** El costo es externo y físico. Genesis no conoce a nadie, no escribe
   ninguna lista de destinatarios y no elige.
2. **Hace verificable la separación por clase.** Declarar *"soy un nodo de cómputo"* es gratis;
   resolver la tarea de referencia de esa clase no lo es.
3. **El trabajo no se tira.** A diferencia del hashing, reclamar es **un ensayo del producto
   real**: hacés exactamente lo que la red te va a pedir después. El costo de entrada selecciona
   por la capacidad que la red necesita.
4. **Lo no reclamado se quema.** Y de ahí sale la propiedad que contesta la crítica que abre esta
   sección:

> **La oferta inicial no la fija el creador — la fija cuánta capacidad real apareció.** El pool
> publicado deja de ser una promesa y pasa a ser un techo. No elimina la decisión, porque alguien
> eligió el techo; pero el número que efectivamente queda circulando lo determina el mundo.

**Lo que hay que declarar sin adornos:** sigue siendo **una subasta pagada en cómputo**, y el que
tiene más hardware se lleva más. No es un reparto igualitario y no hay que venderlo como tal. Es
**abierto**, que es otra cosa, y es la propiedad que tuvo el lanzamiento de Bitcoin.

**El certificado no es dinero.** Cada claim emite además un registro transferible de haber
participado en el bloque 0. No trae asignación de tokens ni derecho a cobrar: si diera derecho a
tokens sería dinero, y concentrarlo sería concentrar la base monetaria inicial — las unidades en
que se denomine no cambiarían nada. **Tampoco es una licencia**, y esa variante hay que descartarla
explícitamente porque es la que primero se le ocurre a cualquiera: si hiciera falta un certificado
para cobrar fees, la cantidad de nodos se volvería artificialmente escasa y aparecería justo el
foso de capital que §6.1 existe para evitar.

Cuatro detalles de forma:

- **se emite como recibo del claim, no se reclama aparte.** Así es gratis y a la vez infarmeable:
  hereda el costo del claim, que sí cuesta;
- **es transferible recién después de un plazo, y el plazo corre desde cada claim**, no contra
  una fecha común — una fecha común es un muro de venta previsible;
- **el protocolo no le confiere ningún derecho, ni ventaja indirecta.** No hay canal por donde una
  ventaja pudiera operar: el cliente no elige qué nodo ejecuta su pedido (§6.5);
- **puede ser gratis y perpetuo porque el conjunto tiene tope duro.** Ocupa estado para siempre
  igual que cualquier objeto, pero los topes de los pools lo acotan al orden del 0,01% del
  presupuesto de disco de un nodo. Lo que no puede ser gratis es la creación **sin tope** de §8.5,
  que paga piso y permanencia: la variable que separa los dos casos es el tope, no la naturaleza
  del objeto.

**Lo que queda por parametrizar y no está decidido:** el costo exacto del claim, la duración de la
ventana y los topes por clase.

### 7.3 Por qué el circuito cerrado pierde

El ataque que hay que descartar es el de siempre, y no depende de que alguien se disfrace: Alice
tiene nodos propios, se manda trabajo a sí misma y cobra sus propias fees. La pregunta correcta
no es si el protocolo puede detectarla —no puede, y §10.2 explica por qué nunca va a poder— sino
si le conviene.

No le conviene, y a ninguna escala. Con el reparto de §7.1, cada ciclo de auto-pago le deja:

```
neto por ciclo  =  −φ · ( 1 − proveedores − σ_A · reserva )
```

donde `σ_A` es su fracción de la red. Medido:

| nodos de Alice | neto por ciclo | saldo tras 1.000 ciclos, desde 1.000.000 |
|---|---|---|
| 2 de 3.000 | −0,000900 | 406.486 |
| 99% de la red | −0,000603 | 547.068 |
| **el 100%** | **−0,000600** | **548.713** |

**Pierde incluso siendo toda la red.** La cantidad de nodos sólo mueve su tajada de la reserva; la
quema queda fuera de su alcance siempre, porque no se le paga a nadie. De ahí que la quema sea la
pieza que no se puede sacar: con quema en cero, la última columna se vuelve plana y el ataque
pasa a ser gratis.

Vale notar qué clase de argumento es este, porque es el hallazgo de método de todo el diseño:

> **El protocolo no distingue a Alice de un cliente real. No lo intenta.** Hace que el circuito
> cerrado **pierda plata**, y la aritmética no necesita saber quién es nadie.

Y el mismo cálculo cierra la puerta de al lado: **quemar plata propia nunca beneficia al que
quema.** Para cualquier tenencia menor al 100%, quemar baja su participación y su valor a la vez,
aun a capitalización constante. El canal *"quemo para valorizar lo mío"* no existe.

### 7.4 Una oferta acotada banca actividad ilimitada

La objeción natural a un techo de circulación es que le pone techo a la economía. No: le pone
techo a la **unidad**, no a la **actividad**. Lo que limita cuánta economía cabe no es la cantidad
de dinero sino la velocidad a la que puede circular, y acá el único límite mecánico es el escrow
de §6.5 durante la ventana de finalidad — dinero comprometido no puede volver a moverse hasta que
la interacción cierre.

Medido con supuestos deliberadamente hostiles —finalidad de 6 horas y sólo 20% del circulante
tolerado en vuelo simultáneo— el techo de velocidad da **292 vueltas al año**, contra 1,2 de M2
de Estados Unidos, 1,5 de M1 y ~12 de Bitcoin on-chain. Entre 25× y 250× de aire.

> **La emisión determina la unidad monetaria; las fees determinan la capacidad económica de la
> red.** Son dos preguntas separadas, y confundirlas es lo que hace pensar que una oferta acotada
> necesita una economía acotada.

### 7.5 La concentración de tokens no da poder de protocolo

Conviene decirlo acá porque es la crítica que este diseño recibe prestada de Bitcoin, y en este
diseño no aplica por construcción.

En las cadenas de gobernanza por voto —Tezos, Polkadot— la tenencia **es** decisión: quien
concentra tokens concentra votos. En Bitcoin la separación entre tenencia y poder existe pero es
costumbre, no invariante. Acá es invariante: **I2 prohíbe que el trigger lea cualquier cosa que
no sea estado**, y §10.1 cierra la puerta de atrás declarando que señalizar preparación es
información y nunca compuerta.

Un actor con el 90% de los tokens tiene el 90% del dinero y cero poder sobre las reglas. Eso no
resuelve la desigualdad de riqueza ni la percepción de afuera —ninguna de las dos es un problema
que un protocolo pueda resolver— pero sí separa las dos cosas que en el resto del ecosistema
vienen pegadas.

### 7.6 Se apunta a la cantidad, no al precio

El sistema fija **circulación** y deja flotar el precio. Es targeting de agregado monetario, y la
distinción con un peg es de fondo, no de grado: un peg tiene el setpoint afuera —una paridad
contra un activo que el protocolo no controla— y cuando el mercado no quiere ese precio, el lazo
corre en reversa y no hay fondo. Un techo de circulación tiene el setpoint **adentro**: el
protocolo mide exactamente la variable que controla.

Esto además es lo único compatible con I2. El precio no existe en el estado de la cadena; y un
trigger que leyera un precio de mercado on-chain sería peor que un oráculo, porque permitiría
**comprar una transición** moviendo un pool con capital prestado.

> **Prohibición explícita, y es condición de seguridad.** El trigger lee `emitido − quemado`
> **del token nativo** y nada más. No lee ratios de pool, no lee profundidad de liquidez, no lee
> volumen, y no lee la contabilidad de ningún otro activo. Esto era una conclusión mientras no
> había mercado nativo; con el mercado de §8 el pool pasa a estar en el estado, a mano, y con la
> creación de activos de §8.5 el atacante puede fabricar **el activo y su pool** desde cero. Un
> trigger que leyera un `emitido − quemado` cualquiera sería disparable a voluntad por quien
> mintee el activo que lo alimenta: deja de ser una conclusión y pasa a ser regla escrita. Es el
> mismo ascenso que hizo el techo de pasos de VM, que entró como presupuesto de performance y
> resultó condición de seguridad de §6.3.

**Una distinción que el replay de §11 obligó a escribir.** Hay precios que no son cotizaciones: el
base fee de EIP-1559 lo **computa el protocolo** a partir de una cantidad —cuán llenos vinieron los
bloques— y no lo publica ningún mercado. Un trigger que lo leyera no estaría leyendo un pool, así
que no cae bajo la prohibición de arriba; lo que sí hay que ver es que empujarlo cuesta llenar
bloques y quemar el fee, o sea que cae dentro del canal de quema que §10.2 declara como frontera
acotada. **Lo que lo descalifica como setpoint no es de dónde sale: es que es nominal** — el base
fee de Ethereum cayó 650 veces en cuatro años (§10.3). La regla se sostiene igual, entonces, pero
por dos motivos distintos que conviene no fundir: un precio de mercado está prohibido porque es
**comprable**; un precio computado por el protocolo está descartado porque **caduca**.

### 7.7 El techo es de la familia, no de la generación

Genesis fija el total y cada generación recibe una porción del mismo cronograma. Una transición
**reubica** la emisión, no la agranda: la generación siguiente no gana poder de compra que la
anterior no tuviera, gana margen de maniobra dentro de un total ya fijado en el bloque 0.

Es lo que mantiene el ancla en pie. La variante donde cada generación trae techo propio que se
suma al anterior es defendible, pero es otro diseño: no tiene ancla, tiene una regla determinista
de expansión.

### 7.8 Circulante es `emitido − quemado`

Es la única definición compatible con I2. Descontar custodia, bloqueos o tesorería exige
clasificar direcciones, y clasificar es juicio humano. Lo único excluible sin romper nada son
direcciones que Genesis mismo define.

**Con más de un activo en el estado (§8.5) hay que precisar de qué circulante se habla: del token
nativo.** Distinguir un activo de otro no es la misma operación que clasificar direcciones y no
cae en la misma prohibición — la identidad de un activo es un hecho del estado, escrito en su
creación; la de una dirección es una interpretación sobre quién está detrás.

**Que no lleve excepciones tiene un costo, y está declarado.** La quema por permanencia de §8.5
cuenta como cualquier otra, así que quien ocupa estado mueve el circulante medido de todos. Es la
frontera de §10.2, y la salida que la cerraría es justamente abrir acá la primera excepción.

Conviene no confundir dos cosas: que no haya preminado significa que Genesis no otorga custodia,
no que la custodia no exista. Bitcoin tampoco premineó y hoy los exchanges tienen millones de
BTC. La custodia aparece cuando un humano entrega sus claves, y ningún protocolo puede verlo ni
impedirlo.

### 7.9 Dormancia, y una tensión que hay que declarar

Un régimen que apunta a la cantidad tiene un problema que uno que emite por calendario puede
ignorar: **los tokens perdidos.** Claves perdidas y contratos muertos quedan como *emitido y no
quemado* para siempre —de Bitcoin se estima un ~20% perdido de forma permanente— y nadie quema
una billetera cuya clave perdió. Con el tiempo el circulante medido queda pegado al techo
mientras la economía viva se drena por abajo.

La salida que respeta I2 es **reclamo por dormancia**: una dirección sin movimiento durante `N`
generaciones se quema. Es determinista, se computa del estado y no clasifica a nadie.

**Y conviene decir qué no es**, porque hay una superposición aparente con §8.5: la dormancia **no
es el freno del crecimiento del estado**. Corre en generaciones, o sea en años, y lo que hace con
un saldo dormido es quemarlo, que es una operación monetaria. Lo que raciona el disco es el
depósito de permanencia, que corre en épocas y desaloja sin destruir. Son dos reglas con el mismo
disparador aparente y trabajos distintos: una mide circulante, la otra cobra almacenamiento.

**Pero la dormancia sirve para dos cosas distintas que piden calibraciones opuestas, y este
diseño no puede tener las dos.**

| propósito | qué cuenta como vida | `N` | efecto sobre el atesoramiento | confisca custodia legítima |
|---|---|---|---|---|
| **medición** — que el circulante medido sea el real | cualquier actividad firmada | por encima del horizonte del cold storage | **ninguno** | no |
| **velocidad** — empujar el dinero a circular | sólo movimiento de saldo | por debajo de ese horizonte | real | **sí** |

**Separar la emisión del trabajo cambió cuál de las dos importa.** Mientras la emisión se
indexaba al trabajo y una banda de circulación podía dispararla, medir mal el circulante producía
emisión espuria: la medición era lo urgente. Con la emisión desacoplada, ese canal se cierra y
queda en pie el segundo problema, que es de comportamiento y no de aritmética — **si la moneda se
aprecia, atesorarla es racional y gastarla es tonto**, y eso ningún techo de circulación lo
arregla. Es el problema de la Etapa 2 de §9, y ahí la dormancia deja de ser un detalle de
medición para ser el mecanismo central.

> **Lo que hay que decir sin adornos: los parámetros escritos arriba están calibrados para la
> justificación que el rediseño degradó.** Contar *"cualquier actividad firmada"* como vida y fijar
> `N` por encima del cold storage legítimo hace que la dormancia **no haga absolutamente nada
> contra el atesoramiento** — una firma barata cada tanto la desactiva por completo. Sirven para
> medir; no sirven para lo que ahora importa.

La calibración de velocidad es la opuesta —sólo cuenta movimiento de saldo, y `N` por debajo del
horizonte del cold storage— y **su costo hay que declararlo, no esconderlo**: un custodio con
almacenamiento en frío y un tenedor de largo plazo se vuelven indistinguibles de una billetera
perdida, porque lo único que los separa es la intención, y la intención no es estado. Ese es el
muro de §10.2 apareciendo otra vez.

Es demurrage, y tiene linaje: Gesell, el experimento de Wörgl de 1932, Freicoin en 2012. No es
una idea improvisada, pero es una decisión monetaria con contraparte real.

**La decisión no se toma en esta sección**, porque no es monetaria sino de propósito: define si
esto es oro digital o moneda circulante. Está planteada en §9, Etapa 2, y hay que tomarla temprano
porque cambia qué clase de activo es esto desde el bloque 0.

### 7.10 Lo que esta sección deja abierto

Separar la emisión del trabajo resuelve el farmeo y deja una pregunta que este diseño **todavía no
contesta**: qué gobierna la emisión después del bloque 0.

Las piezas que sí están decididas dibujan un sistema donde el circulante sólo baja —la quema de
§7.1 retira, la dormancia de §7.9 retira, la permanencia de §8.5 retira, y nada repone— con la
divisibilidad absorbiendo la
deflación, igual que las unidades mínimas de Bitcoin absorben su techo. Es coherente y puede ser
la respuesta. Pero **no está verificado**, y presentarlo como decidido sería exactamente el error
que este documento intenta no cometer: dar por buena una arquitectura en el papel antes de
medirla.

**Lo que sí quedó cerrado es una dirección de salida**, y conviene decirlo porque es la primera que
se le ocurre a cualquiera: que la emisión responda a la demanda. No se puede, y el motivo es una
asimetría entre las dos mitades de un régimen de cantidad.

> **La actividad ya determina cuánto circulante se retira. Lo que no puede determinar es cuánto se
> agrega.**

Retirar no necesita destinatario. Quemar es un hecho del estado, se verifica solo, y el que quema
pierde (§7.3): es una palanca que **sólo perjudica a quien la acciona**, así que puede quedar
abierta a cualquiera — y §8.4 la ata directamente a la actividad económica. Agregar sí necesita
destinatario, y elegirlo es o una decisión humana o una indexación a una acción; en el segundo caso
vuelve el teorema de §7.2 —rinde a lo sumo lo que cuesta esa acción, o es farmeable— y por eso §7.2
sólo pudo resolverlo **acotado al bloque 0**, donde el costo podía ser externo y físico una única
vez. Una versión recurrente de eso es prueba de trabajo permanente, que es lo que este diseño evita
en el consenso.

Y medir la demanda para emitir contra ella falla además por cuatro caminos independientes, que vale
enumerar porque no hay un solo tapón que los cierre: on-chain la demanda **es** actividad, o sea el
`W` cuya identidad mata §7.1; la aritmética de §7.3 supone emisión cero, así que con emisión
indexada el signo del auto-pago vuelve a ser una calibración; reaparece el canal de quemar para
disparar emisión y capturar una fracción de ella, que rinde `(σ_A − 1)·X` y tiende a cero cuando el
atacante es toda la red; y si la señal fuera de precio, con el pool de §8 dentro del estado se
compraría una transición con capital prestado, que es exactamente lo que §7.6 prohíbe.

**Esto no contesta la pregunta abierta — la acota.** Quedan en pie las dos salidas que no miden
demanda: una regla determinista de expansión, cuyo costo ya está dicho en §7.7 —pierde el ancla—, y
la dormancia de §7.9, que ataca el atesoramiento sin emitir nada.

---

## 8. Liquidez nativa

El diseño incluye un **mercado determinístico como pieza del protocolo**, no como aplicación
construida encima. La razón no es de producto: es de supervivencia a las transiciones.

### 8.1 Por qué el mercado va adentro

Sin mercado nativo, cada exchange escribe su propia integración contra el formato crudo de la
cadena: derivación de direcciones, serialización, reglas de confirmación. Son N integraciones
mantenidas por N equipos que no se conocen, y en una transición se rompen las N a la vez. Un
mercado nativo **colapsa esas N superficies en una**, y esa una es parte del protocolo — o sea
que conmuta con él, sin que nadie haga trabajo de integración.

El efecto más fuerte es sobre la custodia. **Los tokens que están en un pool son estado de la
cadena**, y por I3 el estado cruza la transición intacto. Un pool no tiene que actualizar nada
para sobrevivir, porque no es un integrador: es estado. Cada unidad que se mueve de una cold
wallet de exchange a un pool on-chain es una unidad que deja de depender de que un equipo de
ingeniería externo llegue a tiempo.

### 8.2 Determinístico, y con los agentes afuera del camino crítico

El mercado es un AMM: una fórmula cerrada, sin juicio adentro. **Ningún modelo participa de la
formación de precio ni de la ejecución.** Un mercado de fórmula constante sobrevivió años de
presión adversarial precisamente porque no tiene nada que decidir, y meter un modelo en ese
camino traería tres cosas incompatibles con el diseño: no determinismo —mismo input, distinto
output, y el consenso deja de cerrar—, imposibilidad de verificar que la salida fue correcta, y
la necesidad de un operador que corra el modelo, que es el humano que se sacó por la puerta de
la gobernanza volviendo por la ventana del creador de mercado.

Hay además una violación indirecta de I2: si el estado que produce el mercado dependiera de un
proceso off-chain no determinístico, y el trigger lee estado, el trigger terminaría dependiendo
de un oráculo disfrazado.

**Los agentes van encima, como participantes.** Creadores de mercado, arbitrajistas, proveedores
de liquidez. Operan off-chain, sin permiso, y si uno se equivoca pierde su propia plata sin tocar
el consenso. Es el mismo criterio de §6.2: el mecanismo es determinístico, la estrategia es
libre.

### 8.3 Lo que el mercado nativo no puede hacer

**No cierra el camino de la custodia centralizada.** Si un exchange lista el token nativo y la
gente deposita, ese exchange tiene una dirección con saldo, y el protocolo no puede distinguirla
de cualquier otra. El mercado nativo ofrece un camino mejor; no clausura el otro. Achica la
concentración, no la elimina — y el residuo queda declarado en §10.2.

**Y reubica el problema de interfaz en vez de eliminarlo.** Quien integre contra el mercado
nativo depende de la interfaz del mercado nativo. La diferencia es que ahora es **una sola
superficie, y es propia**: I5 aplica sobre ella igual que sobre los formatos crudos, y quien la
mantiene es el protocolo.

### 8.4 El sumidero encuentra su lugar

§7.1 pide quema por consumo de los recursos de la red. Una quema sobre cada swap hace que el
sumidero sea proporcional a la **actividad económica real** y no a transferencias peladas — que
es exactamente lo que un régimen de cantidad necesita: que el circulante se retire al ritmo de la
actividad, sin que nadie decida cuándo.

### 8.5 Crear activos: el cargo va en la permanencia

Un mercado nativo necesita que haya algo más que el token nativo para cotizar. El protocolo admite
crear activos, y la forma de admitirlo es más angosta de lo que suele serlo.

**Se admite una primitiva de creación de forma fija, no una máquina abierta al estado de
terceros.** La distinción importa y es fácil de perder: la cadena **ya** ejecuta código escrito por
terceros —el predicado de aceptación de §6.2 lo escribe el cliente y lo corre la capa liviana bajo
el techo de pasos de VM— pero un predicado corre, contesta y muere. Lo que acá se admite es que un
objeto **persista** entre transacciones. Su estructura la fija el protocolo —dueño, identificador,
puntero a metadata, saldo prepago, contadores— y la elección del creador es el contenido, no la
forma. Lo que queda descartado es la máquina abierta donde cada quien define qué campos tiene su
objeto, y el motivo no es que el minteo sea peligroso: es que con forma libre **el tamaño de una
entrada lo elige el usuario**, y el estado deja de tener unidad de medida. Con forma fija el estado
vuelve a ser una cantidad contable, que es la condición para poder acotarlo.

**Una sola primitiva cubre fungible y no fungible.** Basta que la forma lleve `supply` y
divisibilidad: **un no fungible es el caso `supply = 1`, indivisible**. No hay razón para dos
objetos distintos, y con I1 fijando la máquina, una forma menos es una cosa menos que la máquina
tiene que saber para siempre. Si el emisor puede ampliar el `supply` después es asunto suyo y el
protocolo no opina — misma postura que §8.3 toma con la custodia: se ofrece el camino mejor, no se
clausura el otro.

**El cargo no va en la creación, y esto es lo menos obvio del arreglo.** La intuición dice cobrar
por mintear. No funciona, y el precedente es fiscal: donde se cobra derecho de construcción al
pedir el permiso, lo que baja no es la obra sino el permiso.

> **Un cargo a la creación no reduce la creación — reduce la registración de la creación.**

Traducido acá: si crear en la capa nativa lleva un cargo propio, no se mintea menos, se mintea
**afuera** —contrato propio, formato comprimido, un hash comprometido y el objeto en otro lado— y
ahí se pierde justo lo que §8.1 y §8.4 argumentan durante dos secciones: I3 sólo cubre el estado
nativo, el mercado sólo cotiza lo que está adentro, y el sumidero sólo puede quemar sobre swaps que
ocurren adentro. La asimetría además no es sólo de incentivos sino de aplicabilidad: **el cargo a
la creación se evade minteando afuera; el de permanencia no, porque el estado que existe lo ven
todos los nodos.**

**Entonces la tarifa tiene dos partes, y ninguna de las dos es una decisión libre.** Al crear se
paga un **piso**, que se quema, y el piso **no es una perilla: es el costo fijo del ciclo crear +
desalojar**. Queda clavado por los dos lados: por debajo, porque menos que eso subsidia el churn de
crear y dejar morir; por encima, porque todo lo que se cobre de más ya es el cargo a la creación
que el párrafo anterior descartó. Hace falta cobrarlo aparte porque la regla ad valorem de §6.1 no
muerde acá — un activo recién creado vale ~0, así que un fee proporcional a su valor tiende a cero.

**La cuenta se escribe igualando dos fracciones del mismo nodo, y las dos ya están declaradas.**
El ciclo consume una cantidad de pasos, y el nodo dedica `f*` de su ritmo a verificar: eso es una
fracción del cómputo de una época. Guardar la entrada esa época ocupa `tamaño / presupuesto de
estado` del disco. El piso es el cociente — **cuántas épocas de disco valen lo que el ciclo gasta
de cómputo**— y no aparece ningún número nuevo, porque `f*` y el presupuesto de estado ya los fijó
Genesis. Lo que sí aparece es un supuesto que conviene decir: que las dos fracciones están
igualmente ajustadas, o sea que el nodo satura las dos. Es lo que §6.1 construye a propósito al
fijar ambas contra lo que tiene un teléfono.

**Y lo que entra en el ciclo son las dos actualizaciones del árbol, no la verificación de firma.**
La distinción no es cosmética: **la firma ya la paga el fee ad valorem como en cualquier
transacción**, así que cobrarla otra vez en el piso es cobrarla dos veces, y el error no es chico
—con la firma adentro el piso sale del orden de las noventa épocas, varias veces el depósito
máximo que `L_max` permite, y entonces casi todo el costo de una entrada se paga al crearla, que es
exactamente el cargo a la creación que esta sección acaba de descartar—. Lo que la creación agrega
por encima de una transacción común es el trabajo de árbol, y eso es lo que el piso cubre.

**Con las dos actualizaciones medidas, el piso sale del orden de las diecinueve épocas** —un 5%
de lo que cuesta tener la entrada un año, y **poco más de tres cuartos de la vida máxima que
`L_max` deja comprar de una vez**. Esa última relación es la que hace falta vigilar: si el piso
fuera comparable al depósito máximo, casi todo el costo se pagaría al crear y volvería el cargo a
la creación por la puerta de atrás.

**Y a esta altura ya está incómodamente cerca.** Quien compra el depósito máximo paga menos de la
mitad al crear, pero **quien sólo quiere la entrada por poco tiempo paga casi todo**, y el
argumento de esta sección no depende de la magnitud: un cargo a la creación no reduce la
creación, reduce su registración. Que el piso quede donde quedó no es una conclusión cómoda y se
declara así.

> **El número depende de cómo se guarde el árbol, y eso no se sabía cuando se escribió la
> cuenta.** Un árbol que guarda todos sus nodos internos cuesta 32 bytes por entrada y hace la
> actualización barata; uno que guarda sólo los niveles de arriba y recomputa el resto cuesta un
> byte y hace la actualización tres veces más cara. **Los dos son el mismo árbol y dan pisos
> distintos**, así que el corte no es una decisión de implementación: entra al estado por la vía
> del piso, que se quema. Es una constante de Genesis más.

> **Los dos insumos de esa cuenta están medidos y ninguno estimado**, que es lo que la vuelve
> afirmable: el costo de una verificación de firma en la máquina chica (§12, Test 2) y el de una
> compresión de hash, medida igual y por la misma razón. El segundo hizo falta ir a buscarlo: una
> versión anterior de esta sección lo daba por despreciable frente al primero, y ese razonamiento
> valía sólo mientras la firma estuviera adentro del ciclo — sacada, era el único término que
> quedaba.

**El piso se denomina en épocas de guardado, no en unidades del token**, y esa forma hace trabajo.
Si estuviera en unidades sería un **segundo** precio que fijar al lado de la tasa, con el mismo
problema que la tasa tiene y sin ninguna de sus defensas. En épocas de guardado hereda la tasa que
rija, sea cual sea — y lo que §10.3 deja abierto vuelve a ser un solo número.

La segunda parte es un **depósito de permanencia**, que se consume quemándose época a época, a tasa
lineal en tamaño × tiempo. **Lo que el depósito compra es tiempo real de guardado, no un número de
épocas**, y la distinción no es pedante: la época se cuenta en bloques y el tiempo de bloque es un
parámetro interno, así que una transición que lo mueva cambiaría lo que un depósito ya pagado
compró — sin tocar un solo byte del estado, y sin que ninguna invariante lo señale. Se evita con
el mismo movimiento que usa el techo de §6.6: **convertir con la cantidad que el ruleset declara,
no con una que haya que medir.** El tiempo de bloque no es una lectura de reloj —eso sí violaría
I2— sino un número que la propia cadena fijó. Mientras haya saldo el objeto está en el conjunto activo; cuando se
agota, se desaloja. Para mantenerlo vivo se recarga. **Y es el depósito, no el piso, lo que hace de
antispam**: crear N objetos cuesta N depósitos, así que inundar el estado se paga a precio de
estado inundado.

**Y la vida que se puede comprar de una vez tiene tope.** Se compra hasta `L_max` por operación y
después se recarga, al precio que rija entonces. Parece una molestia y es una viga, por dos motivos
que se refuerzan:

- **cierra la última puerta a la permanencia comprada.** Sin tope, un pago finito bastante grande
  compra siglos, que es exactamente lo que esta sección existe para impedir. Con tope **no se puede
  comprar un siglo ni pagándolo**;
- **es lo que mantiene gobernable el precio del guardado.** La tasa **no puede quedar congelada en
  Genesis**: es un precio nominal sobre un recurso real, así que con la unidad flotando se rompe en
  las dos direcciones —si la moneda se aprecia, guardar se vuelve prohibitivo y el estado se vacía;
  si se deprecia, guardar es gratis y se llena—. Cualquiera sea la regla que la mueva (§10.3),
  **prepagar sin límite es apostar contra ella y dejar el estado tomado mientras tanto**: cuando la
  tasa baja, comprar largo captura slots a precio de saldo que ya no se pueden recuperar sin
  confiscar. El tope es lo que impide esa compra.

**El cargo es por entrada, no por objeto, y eso lo decide el fungible.** Un no fungible es una
entrada y no crece; un fungible es una entrada **más un saldo por cada tenedor**, y esa cuenta sí
crece con la adopción. Con el presupuesto de un nodo, un token con un millón de tenedores ocupa el
**3%** del disco: **treinta y tres tokens exitosos llenan la cadena**. Así que lo que tiene que ser
uniforme no es la forma sino el cargo — **toda entrada de estado paga permanencia, y la funda quien
la crea**. Transferir a una dirección que todavía no tiene entrada incluye piso y depósito mínimo,
a cuenta del que envía; después el tenedor recarga si quiere conservarla.

Esa regla cierra además una puerta que estaba abierta desde antes de esta sección, y que no es del
minteo: **las cuentas del token nativo también son entradas de estado**. Como el fee de §6.1 es ad
valorem, sobre polvo tiende a cero, así que llenar el disco de todos los nodos con transferencias
mínimas costaba **poco más que saturar la cadena durante medio día**, y nada en fees. La dormancia
de §7.9 no lo tapaba: corre en generaciones y su trabajo es monetario, no de disco.

> **La propiedad que todo esto compra, y es la que justifica la sección entera: en la cadena no
> existe ningún objeto cuyo costo futuro no tenga a alguien pagándolo. Nadie puede comprar espacio
> perpetuo con un pago finito.**

**Lo que hay que declarar, porque es un cambio de carácter y no un detalle:** con la regla uniforme,
**tener un saldo deja de ser gratis**. Es demurrage sobre el estado y no sobre el monto —una
billetera chica y quieta termina desalojada, recuperable con prueba— y empuja en la misma dirección
que la decisión de §9, Etapa 2. Se sostiene a sabiendas.

> **No se paga por crear — se paga por cuánto tiempo se quiere que la red lo guarde.**

Lo tasado es **tamaño × tiempo**, o sea costo y no utilidad, así que la regla no le pide al
protocolo ninguna opinión sobre qué vale un activo.

**Y la tasa no baja por depositar más.** La tentación es premiar al que deposita mucho amortizando
más lento, y se cae por aritmética: con una regla de potencia la vida crece más rápido que el
depósito, así que el precio por año tiende a cero — cien pisos comprarían diez mil años. Eso no
abarata cualquier cosa, abarata **la única operación que compra permanencia en volumen**, que es
llenar el estado de todos los nodos y no soltarlo nunca: sale un orden de magnitud más barato que
sin descuento. Es el fee fijo que §6.1 rechaza por regresivo —*"vuelve gratis el pedido grande"*—
en la dimensión del tiempo en vez de la del valor, y como el disco está topeado el descuento no
crea capacidad: se la reasigna al que tiene más capital, que es el foso que §6.1 existe para
evitar. Lo único que el volumen ahorra legítimamente es pagar el alta una vez en lugar de una por
período, y eso ya hace caer la tasa media — con piso en el costo real de guardar, en vez de con
destino a cero.

**Desalojar no es destruir, y el residuo tiene que ser O(1).** El objeto sale del conjunto activo y
el tenedor lo revive con una prueba, pagando el costo de entonces. Esa pieza es la que hace que el
desalojo no sea confiscación, y por eso no hay quema final del activo. Pero el compromiso contra el
que se prueba **no puede ser uno por objeto desalojado**, o el atacante habría comprado permanencia
igual, sólo que más barata: una lápida de 32 bytes por objeto son **1 GB por nodo para siempre**,
un cuarto del presupuesto. El desalojo **agrega el objeto a un acumulador único de sólo-append**,
del tipo donde insertar necesita apenas los picos del árbol: **unos 800 bytes en total**, no por
objeto. La reactivación prueba contra ese acumulador, y la doble reactivación no necesita lista de
nulificadores — se chequea contra el conjunto **activo**, que está acotado por construcción. La cuenta regresiva es **pública y computable con anticipación** —aviso *pull*,
la misma forma que §6.5— y esa previsibilidad no es una comodidad: un desalojo anunciado no genera
presión por un arreglo coordinado a mano, y una sorpresa sí.

**No hay deuda, y no hay remate.** La variante natural —dejar que el saldo quede en descubierto y
ejecutar el activo— pide dos cosas que el diseño no puede dar. La primera es un deudor: el dueño es
una clave, y contra una cuenta vacía no hay nada que embargar, así que lo único ejecutable sería el
objeto. La segunda es peor: rematarlo obliga a la cadena a saber cuánto vale, o sea a leer el pool,
que es exactamente lo que §7.6 prohíbe y es manipulable en la dirección obvia. La liquidación
existe igual, pero la hace el mercado y no el protocolo: quien no puede sostener el saldo vende
antes del desalojo y el comprador hereda lo que queda.

**El sumidero, para cerrar.** El piso y el depósito se queman: no tienen destinatario, así que no
hay nadie a quien elegir ni nada que farmear. Queda del lado *retirar* de la asimetría de §7.10 —
la actividad puede determinar cuánto circulante se retira— y le agrega al sumidero de §8.4 una
segunda fuente, continua y proporcional a cuánto estado carga la red.

---

## 9. Adopción

El bootstrap previsto es el de Bitcoin: nadie participa porque crea en la moneda, participa
porque hay una ventana de arbitraje. La infraestructura llega por la plata y la red queda. No
hace falta que nadie entienda el diseño, y contar con que no lo entiendan es realista.

### Etapa 1 — el claim, no el subsidio

**Este diseño tuvo una Etapa 1 distinta y hay que contar cómo se cayó, porque la que quedó es más
chica y más honesta.**

La versión original era la de todo yield farm: humanos levantan infraestructura para generar
tokens y venderlos por fiat. Tenía una diferencia estructural con Bitcoin que decidía si era sana
o tóxica. El subsidio de Bitcoin **compra seguridad**, y el trabajo lo define el protocolo:
hashear *es* lo que asegura la cadena, el costo es externo y físico, y nadie puede pagarse a sí
mismo por minar. Acá el subsidio se pagaba **encima de una transacción privada entre dos partes**,
y el protocolo a propósito no define qué trabajo vale, porque en el momento en que lo define se
convierte en un comité eligiendo ganadores.

Entonces la infraestructura que maximizaba generación de tokens no era una granja de minado: era
**un agente que se paga a sí mismo**, la forma más barata de producir *"trabajo pedido, pagado y
entregado"*.

**La ventana de arbitraje y la ventana de autotrato eran la misma ventana**, y lo único que las
separaba era el parámetro que gradúa el subsidio. La adopción necesitaba que fuera goloso; la
salud de la moneda, que no tanto como para farmearlo. Test 4 corrió esa hipótesis y **no caben**:
el parámetro entra idénticamente en las dos economías, y el margen entre ellas es la emisión neta,
que es la misma cantidad que la ganancia del que se paga a sí mismo. No hay forma de agrandar una
sin agrandar la otra.

**La Etapa 1 que queda es el claim de §7.2**, y es más chica en todo sentido: una ventana única en
el bloque 0 donde reclamar tokens cuesta demostrar capacidad de cómputo. Sigue siendo un
arbitraje —gastás electricidad, recibís tokens, los vendés si querés— y sigue sin requerir que
nadie entienda el diseño, que era la propiedad importante. Pero **está acotada en el tiempo y no
se puede farmear después de que cierra**, porque después de eso ninguna acción crea unidades.

**Lo que se pierde con eso, y hay que decirlo:** desaparece el incentivo pagado por el protocolo a
correr un nodo **antes de que exista demanda**. Bitcoin tiene subsidio de bloque durante décadas;
acá el claim compra la cohorte del día 1 y después el ingreso es fee de demanda real o nada. El
diseño no garantiza que esa demanda aparezca — sólo garantiza que si no aparece, nadie puede
fabricarla para cobrar igual. Es una elección deliberada entre dos fallas: la vieja arrancaba
seguro y se auto-farmeaba; ésta no se auto-farmea y puede no arrancar.

Corolario sobre la autonomía, que sobrevive intacto al cambio: que el humano deje de intervenir es
cierto sobre **las reglas** y falso sobre **la tenencia**. Un agente de software no tiene claves;
lo opera alguien, y ese alguien controla la billetera. El humano no desaparece — sube un nivel, de
tenedor a operador.

### Etapa 2 — que decante en moneda circulante

No tiene ningún ejemplo, y por una razón de diseño y no de suerte: **un techo duro y la
circulación tiran en direcciones opuestas.** Si el tenedor espera apreciación, guardar es racional
y gastar es tonto. Bitcoin llegó a reserva de valor y se quedó ahí exactamente por eso. Un diseño
que apunta a cantidad y deja flotar el precio hereda el mismo problema: si se adopta se aprecia, y
si se aprecia se atesora.

Acá es donde la dormancia de §7.9 deja de ser un detalle de medición, y §8.4 le da el volumen que
necesita para morder. Un costo de mantenimiento sobre el saldo quieto hace que atesorar deje de
ser gratis y gastar vuelva a ser racional — que es literalmente para lo que Gesell diseñó el
Freigeld, lo que probó Wörgl en 1932 hasta que el banco central austríaco lo cerró al año
siguiente, y lo que Freicoin llevó a blockchain en 2012.

**Consecuencia de diseño:** si el objetivo es moneda circulante y no oro digital, la dormancia no
es el precio a pagar por medir bien — es el mecanismo central. Y hay que decidirlo temprano,
porque cambia qué clase de activo es esto desde el bloque 0.

---

## 10. Fronteras declaradas

Lo que el diseño **no** resuelve, escrito acá y no en una nota al pie, porque una frontera
implícita es una mentira por omisión. Van agrupadas por lo que hay que hacer con cada una, que no
es lo mismo en los tres casos.

### 10.1 Decisiones asumidas

No son problemas a resolver: son el precio de propiedades que el diseño quiere. Se sostienen a
sabiendas.

**La adaptación está acotada a lo que Genesis anticipó.** Consecuencia directa de I1 y sin arreglo
dentro del diseño: si la condición que dispara la transición es algo no previsto, no hay ruleset
que cargar. Es el precio de que no haya código nuevo, que es lo que hace que la transición sea
verificable.

**El determinismo también saca el freno de emergencia.** Una transición mal anticipada es
exactamente el escenario donde los humanos querrían negarse, y la respuesta del diseño es
*"entonces sos un fork"*. No hay override, por construcción — que es la misma propiedad que
elimina la gobernanza, vista desde el lado incómodo.

**La ventana `Δ` compra seguridad de integración con tiempo de reacción.** Una ventana larga deja
a la cadena corriendo bajo reglas que ya se sabe que no alcanzan; una corta le pasa el costo a
todo el que integró. No hay valor que resuelva las dos, por eso `Δ` va por clase de transición
(§3). El caso peor —una migración criptográfica de urgencia, donde la cadena necesita `Δ` corto y
los integradores necesitan `Δ` largo— lo desactiva la escalera de canarios de §6.6: el canario
débil dispara la migración con años de anticipación, así que el camino de emergencia casi nunca
se usa.

> **Y construir el mecanismo mostró que, a los valores que están en Genesis, esa tensión no
> existe.** `Δ` se declara en **bloques** —64 para circulación, 8 para una migración— y con el
> tiempo de bloque inicial eso da **seis minutos y cuarenta y ocho segundos** de aviso. Ningún
> integrador reacciona en seis minutos, así que los dos valores están del mismo lado de la
> curva, el de *ningún aviso*, y la perilla que este párrafo describe no está sobre ella.
>
> Lo que de verdad le da al integrador un modo de falla tolerable no es `Δ` sino **I5**: quien no
> llegó a soportar la generación nueva sigue operando en la anterior y degrada en vez de
> detenerse (§4). Eso es lo que hace que el número chico no sea catastrófico — y también lo que
> muestra que `Δ` está haciendo bastante menos de lo que este párrafo le atribuye.
>
> Hay además un problema de unidad, y es el mismo que apareció en el depósito de permanencia
> (§8.5): **`Δ` está en bloques y el tiempo de bloque es un parámetro interno**, así que el aviso
> real varía sesenta veces a lo largo del espacio, y una transición puede moverlo mientras otra
> está en vuelo. La corrección que sirvió para el depósito no se aplica igual acá, porque la
> altura de activación se anuncia al hacer lock-in y moverla después contradice §3. **Queda
> abierto**, con las tres salidas posibles escritas en la auditoría de unidades del repo.

**El conjunto de futuros posibles deja de ser auditable.** Es el precio del intérprete (I1). Con
una lista finita de reglas, cualquiera podía leer Genesis y saber en qué se puede convertir la
cadena. Con una máquina, el espacio es infinito y esa lectura ya no existe. Se gana evolución sin
techo; se pierde poder saber hoy qué puede llegar a ser esto.

**Y el espacio declarado puede quedar corto.** Es la cara opuesta del punto anterior y la encontró
el replay de §11, no un ataque imaginado. Los parámetros internos no viven en el espacio infinito
de la máquina: viven en un rango declarado en Genesis, auditable justamente porque es finito.
Ethereum llevó el target de blobs de 3 a 14 en veintidós meses, y las dos últimas subas no fueron
posibles porque apareciera demanda —la ocupación estaba en 43% y 31%— sino porque apareció una
técnica de disponibilidad de datos que cambió cuánto puede transportar la red sin degradarse. Un
techo de 6 declarado en 2024 habría sido correcto en 2024 y habría quedado corto en 2025, y **I1 lo
congela**. La diferencia con lo que esta sección ya dice es de fondo: no es que la regla escrita
pueda ser la equivocada, es que **el rango dentro del cual la regla elige puede quedar por debajo
de lo que la red terminó pudiendo hacer**, y ampliarlo es un fork — el mecanismo devolviendo
exactamente lo que vino a evitar. La mitigación es declarar el rango con holgura, y la holgura
tiene su propio costo: un techo generoso es el que deja pasar el caso que el techo existe para
bloquear. Es la misma tensión que §10.3 declara para el techo de pasos, ahora medida sobre un
parámetro real y no sobre uno hipotético.

**El intérprete es un punto único de falla que no se puede parchear nunca.** Si tiene un bug, no
hay transición que lo arregle, porque toda transición corre sobre él. Es la única pieza del
sistema donde la verificación formal no es opcional.

**Sobrevivir el guante no es sobrevivir quince años de criptoanálisis.** Una ventana con
recompensa es una aproximación mecánica al estándar real, no un sustituto. Se mitiga con ventana
larga y recompensa grande; no se elimina.

**La activación no espera a que nadie esté listo.** La salida tentadora al problema del
integrador es condicionar la activación a que un porcentaje del supply en custodia señalice
preparación. **Eso es un voto**, y de los peores: le da poder de veto sobre la evolución del
protocolo a los actores más concentrados. Prohibido por I2. Lo que sí se admite es publicar la
señal de preparación como **información sin efecto de protocolo** — telemetría para que el
mercado la use, nunca una compuerta.

**No se le puede pagar a alguien que está offline.** La bilateralidad de §6.5 convierte todo pago
en un handshake de dos vueltas. Para una economía de agentes es irrelevante —están online—, para
humanos es fricción, y es el precio de que el receptor sea el vigilante.

**La finalidad se mide en minutos u horas, no en segundos.** Es la consecuencia de finalizar por
ventana de impugnación en vez de por quórum (§6.3). Se gana no tener conjunto de validadores; se
paga en latencia.

**El trabajo que el protocolo puede pagar es un subconjunto, no el total.** Solo los pedidos con
predicado determinístico verificable (§6.2). La emisión ya no depende de esto —§7.1 la desacopló
del trabajo— pero el fee sí: lo que no se puede expresar como predicado no se puede liquidar en la
red, y por lo tanto no genera ingreso para ningún nodo. Es una frontera nítida y es angosta, y si
resulta demasiado angosta el sistema es un nicho en vez de una economía.

**El techo de pasos del predicado es una decisión de I1 que no está tomada.** §6.6 cierra el
agujero que encontró Test 2 —el guante verifica corrección y no costo, así que una implementación
correcta pero diez veces más lenta pasaba, sobrevivía la ventana y quedaba instalada para siempre,
rompiendo el presupuesto de §6.1 desde adentro del protocolo— agregando un techo de pasos de VM al
predicado de aceptación. Lo que el mecanismo **no** dice, y hay que elegir a sabiendas, es de qué
mitad del espacio es ese techo. Congelado en la máquina, puede dejar afuera una primitiva legítima
que el hardware de dentro de veinte años haría barata. Como parámetro interno de la generación,
subirlo es exactamente la vía por la que entra la implementación lenta.

**La disyuntiva era falsa, y se resolvió sin pagar ninguna de las dos.** Lo que se congela en la
máquina no es el número: es **la cuenta que lo produce**, y el valor lo determina cada generación
con sus propios parámetros —tiempo de bloque y capacidad—, que ya están en el espacio. Así el techo
no queda ni congelado ni suelto: **no es una palanca, porque nadie puede moverlo sin mover
capacidad o tiempo de bloque**, y eso tiene sus propias consecuencias y su propio disparo. El
desarrollo está en §10.3.

> **Ese techo hace un segundo trabajo que no se ve desde acá, y es de seguridad, no de
> performance.** Es lo que impide que exista una impugnación **más cara de verificar que de
> crear** — la asimetría clásica de denegación de servicio contra el verificador. Sin techo, un
> atacante compraría trabajo de verificación barato y la cola de §6.3 pasaría a necesitar mil
> nodos para no saturar en vez de diez. Con techo, verificar una impugnación cuesta a lo sumo lo
> que costó crear la interacción disputada. **Quien mueva este parámetro está moviendo una
> condición de §6.3, no una decisión de rendimiento.**

**La máquina prohíbe el punto flotante, y eso cierra puertas para siempre.** La reproducción bit a
bit entre ARM y x86 solo aguanta con `+ − × ÷` y sin trascendentales — está medido, no supuesto. Si
el guante admitiera candidatas sin restringir eso, el lazo de §6.6 podría instalar una primitiva
que rompe el determinismo del que depende todo lo demás, PoD incluido (§6.2). Así que la
especificación de la máquina prohíbe o canonicaliza el flotante **antes de que el guante corra por
primera vez**, y como es una condición sobre Genesis, después no se levanta. El costo es concreto y
no hipotético: toda primitiva que necesite flotante queda fuera del espacio de descendientes para
siempre. Falcon / FN-DSA verifica con enteros pero firma con flotante, y con esta condición no
entra nunca.

**El linaje y la firma no pueden compartir núcleo criptográfico.** La escalera de canarios de §6.6
gradúa la respuesta, y esa gradación supone que las primitivas ceden **de a una y en orden**. El
supuesto se rompe solo si la función que encadena el linaje (§3, I4) y la primitiva de firma
comparten núcleo — que es el caso por defecto, y no por casualidad: ML-DSA usa SHAKE adentro, y el
59% de una verificación se va en expandir la matriz con él. Elegir Keccak para `H` acopla las dos
cosas, y entonces Keccak no cede un escalón: cede el linaje y la firma vigente a la vez, y la
migración tendría que correr sobre una cadena cuya verificación de linaje ya no es confiable.
Genesis elige `H` de una familia distinta de la que usa la primitiva de firma inicial. Es barato el
día uno e imposible después.

**El lock-in espera a la finalidad, y eso abre una demora que se puede forzar.** La separación
entre disparo y lock-in (§3) no es ceremonia: sin ella, una reorganización dejaría a `H0_B`
comprometido con un `state_trigger` que la cadena canónica ya no contiene, e I4 dejaría de
verificarse justo donde más importa. El precio es que toda transición paga por delante la ventana
de impugnación de §6.3, y que **demorar la finalidad pasa a demorar la transición**: un adversario
dispuesto a pagar bonos de impugnación intentaría estirar el lock-in. Apunta en la peor dirección
justo en la migración criptográfica de urgencia — el mismo caso peor que ya tensiona la ventana
`Δ`.

**El arreglo es un tope duro de bloques de demora al lock-in, fijado en Genesis por clase de
transición** — la misma forma que `Δ` en §3, aplicada a la otra mitad del cronograma. Se eligió
tope duro por encima de un bono de impugnación escalonado, y el criterio vale más que el caso:

| | bono escalonado | **tope duro** |
|---|---|---|
| mata el ataque de demora | parcialmente | **totalmente** |
| necesita identidad | no | no |
| castiga al impugnador honesto | **sí** | no |
| residuo | **compone** | plano y acotado |

> **Un residuo que compone no es un arreglo, es un préstamo.** El bono escalonado deja una demora
> residual que crece con el capital del atacante; el tope deja un residuo que se declara en un
> renglón y es igual el día 1 que el año 20.

**Ese residuo, dicho entero:** un fraude descubierto después del tope no detiene la transición. El
tope convierte *"demorar"* en *"sobrevivir el tope"*, y la forma barata de sobrevivirlo sería
inundar la cola de impugnaciones para que una prueba legítima no llegue a procesarse a tiempo. No
se puede — §6.3 explica por qué, y no es porque salga caro sino porque no hay geometría que lo
permita.

Y lo que lo vuelve tolerable sigue siendo lo de siempre: el canario débil dispara con años de
anticipación, así que el camino de emergencia casi nunca corre.

**El punto flotante queda prohibido o canonicalizado desde Genesis.** Falcon / FN-DSA verifica con
enteros pero **firma** con punto flotante, y la reproducibilidad bit a bit entre ARM y x86 solo
aguanta con `+ − × ÷` y sin trascendentales. Si el guante de §6.6 admite candidatas sin restringir
eso, el lazo puede instalar una primitiva que rompe el determinismo del que depende todo lo demás.
Es una condición sobre la especificación de la máquina (I1) y hay que escribirla **antes de que el
guante corra la primera vez**: como toda condición sobre Genesis, es barata el día uno e imposible
después. El precio es que estrecha el espacio de primitivas elegibles antes de saber cuáles van a
existir.

**El costo de entrada a la capa liviana es asimétrico por plataforma.** Medido en Test 2: un nodo
en iPhone corre **~15× más lento** que el mismo teléfono en Android, porque iOS no permite JIT a
terceros y el bytecode llega en tiempo de ejecución (§6.1). No rompe el argumento de la coalición
de bloqueo —entrar sigue siendo barato— pero *"reemplazarlo cuesta un teléfono"* es cierto solo a
menos de un factor 15 según el aparato. Es una política de plataforma, no una propiedad del diseño,
y no hay nada que el protocolo pueda hacer al respecto.

**El estado se expira, y eso cambia una garantía por una dependencia.** Con un solo activo no hacía
falta declarar ninguna frontera sobre el tamaño del estado; con la creación de §8.5 sí, y el umbral
es bajo. Contando el objeto, su parte del árbol y el índice de desalojo, una entrada activa pesa
**~120 bytes** —un saldo de tenedor, la mitad—, así que con el presupuesto de disco de un teléfono
unas **9.700 creaciones por día** lo agotan en diez años: 0,1 por segundo. Cualquier adopción real
cruza ese umbral, así que expirar no es una optimización sino lo que mantiene en pie la entrada
barata de §6.1 y, por ella, la no-saturación de §6.3. Lo que se gana está medido y es grande: el estado desalojado pasa de una copia obligatoria
por nodo a unas pocas voluntarias, tres órdenes de magnitud. Lo que se paga es que la reactivación
deja de estar garantizada por el protocolo (§10.2). Y queda un residuo sin arreglo: **la expiración
no distingue lo abandonado de lo guardado a propósito**, porque la intención no es estado — el
mismo muro que §10.2 declara para todo lo demás.

**El estado apunta a la mitad del presupuesto declarado, y no a llenarlo.** El cargo de §8.5
defiende una **ocupación objetivo**, y esa ocupación se mide contra un presupuesto de disco que
Genesis declara —del orden de los pocos gigabytes que sostienen el argumento de §6.1— y que sólo
una transición puede mover, por ser parámetro interno de I1. Así la capacidad crece por decisión de
una generación y no por deriva del hardware. El valor elegido es **la mitad**, y la mitad que queda
libre no es holgura desperdiciada: es donde vive el pico de un shock de demanda sostenido, que en
simulación llega a la mitad otra vez por encima del objetivo antes de que el precio muerda. Apuntar
al 75% o al 90% se sale del presupuesto en el primer shock.

Que el valor sea conservador es deliberado, y el motivo es la asimetría de los dos errores.
Quedarse corto encarece el guardado y hospeda menos, y se corrige subiéndolo en una transición.
Pasarse expulsa del presupuesto a los nodos chicos — y eso **no se revierte bajando el número
después**, porque el que se fue no vuelve y el estado ya financiado no se puede desalojar antes de
tiempo sin confiscar. Un error es reversible y el otro no.

### 10.2 Límites inherentes

No los resuelve este diseño ni ningún otro. Se declaran para que nadie los descubra después.

**El protocolo no tiene noción de identidad, así que toda palanca que mueva, la mueve para
todos.** Es el límite que explica de una sola vez por qué fallaron cuatro arreglos distintos
intentados sobre este diseño, cada uno contra un problema diferente:

| intento | contra qué | cómo murió |
|---|---|---|
| graduar el subsidio con un parámetro | el auto-pago | entra idéntico en el autotratante y en el honesto |
| bloquear el subsidio un tiempo | el farmeo | descuenta a los dos por igual |
| repartir el beneficio por rol | el autotrato | lo arbitra el que ocupa los dos roles |
| bono de impugnación superlineal | la demora al lock-in | castiga al impugnador honesto junto con el atacante |

No es mala suerte cuatro veces: es una propiedad. Cualquier mecanismo que quiera tratar distinto
al honesto y al atacante necesita distinguirlos, y lo único que el protocolo ve son firmas y
montos. **Toda propuesta de arreglo de la forma "que el bueno pague menos" es, en este diseño,
una propuesta de introducir identidad** — y se declara acá para que no haya que descubrirlo cuatro
veces más.

La misma regla tiene una segunda instancia, del lado monetario: **toda propuesta de la forma "que
se emita cuando hay demanda real" es también una propuesta de introducir identidad**, porque
separar demanda real de demanda fabricada es separar a dos actores que el protocolo ve iguales —
firmas y montos. El desarrollo está en §7.10.

La salida que sí funciona no es distinguir mejor sino **dejar de intentarlo**: hacer que el
circuito cerrado pierda plata por aritmética, como en §7.3. La misma forma reaparece en §6.4 —el
que firma dos veces publica su clave privada, sin que nadie tenga que juzgarlo— y en §6.3, donde
lo que frena la saturación no es un filtro sino que drenar es paralelo y llenar es serial.

**Las cinco invariantes cubren lo que el estado *es*, no lo que *significa*.** Es un límite del
marco entero y se descubrió construyendo: dos defectos distintos pasaron por debajo de las cinco
sin violar ninguna. En un caso un techo declarado como constante **excluía primitivas en vez de
encarecerlas**, contra lo que promete §6.6; en el otro, un saldo prepago estaba denominado en una
unidad que un parámetro del ruleset redefine, así que **una transición cambiaba lo que ese saldo
había comprado sin tocar un solo byte**.

Los dos son la misma forma. I3 verifica que el estado cruce íntegro, y cruzaba: las huellas
coinciden y la identidad de los objetos también. Lo que cambiaba era el valor de lo que cruzó, y
**ninguna invariante mira eso** — ni puede, sin que el protocolo tenga una noción de qué vale una
cantidad, que es justamente lo que el resto de esta sección declara imposible.

Lo que reemplaza a una sexta invariante es una pregunta que se puede hacer mecánicamente y que
conviene rehacer cada vez que el espacio de parámetros crece: **para cada cantidad que el
protocolo guarda, ¿su significado depende de algo que una transición puede mover?** Si depende,
hay dos salidas —denominarla en algo que no dependa, o recalcularla en la transición— y ninguna
es gratis. Lo que no es una salida es no darse cuenta.

**El split es ilegítimo, no imposible.** La asimetría de §5 es real: el que no conmuta es el que se
desvía, y eso se verifica con un hash. Pero legitimidad no es supervivencia. Ethereum Classic
existe, nadie discute que es un fork, y tiene mercado y mineros igual. La asimetría no mata a la
cadena disidente — la hace chica. Ninguna regla escrita en Genesis puede impedir el split, porque
la regla vive adentro del software que el disidente decidió no correr.

**El hash que encadena el linaje no se puede reemplazar.** Una primitiva de firma nueva aplica
hacia adelante y las viejas siguen válidas por I5. El hash del linaje no: `H0_B` encadena hacia
atrás hasta Genesis (§3, I4), y no hay forma de re-hashear una historia que ya está escrita sin
romper el compromiso que la hace verificable. La única salida es conservar la función vieja para
los eslabones viejos, con lo cual una función rota queda de carga estructural para siempre. Un
canario para `H` sí es construible —una colisión reclamada es un hecho del estado igual que una
preimagen— pero no compra mucho: enterarse de que `H` cedió no habilita ninguna migración, porque
lo que habría que migrar es el pasado. No es un defecto de este diseño; le pasa a cualquier cadena
que comprometa su historia con un hash. Se mitiga eligiendo la función más conservadora disponible
y declarando que ese es el piso. No se elimina.

**La regla no invoca hardware.** El protocolo puede determinar la generación siguiente hasta el
último byte, pero no puede obligar a que existan nodos corriéndola. La autonomía es cierta a nivel
de decisión y falsa a nivel de ejecución.

**Tampoco puede obligar a que exista archivo**, y es la misma frontera aplicada a la expiración de
§10.1:

> **El protocolo puede garantizar que un activo desalojado *se puede* revivir. No puede garantizar
> que alguien vaya a tener con qué.**

La prueba de reactivación pesa menos de un kilobyte, así que guardarla es gratis; lo que no es
gratis es **mantenerla al día**. La unión de los hermanos del camino de una hoja es el árbol entero
menos esa hoja, de modo que la prueba se vence en el primer bloque que toque cualquier otra cosa:
conservarla significa seguir la cadena sin cortar nunca. Alcanza para un agente permanentemente
online —que es el público declarado de este diseño, y es el mismo supuesto que sostiene *"no se le
puede pagar a alguien que está offline"*— y no alcanza para una persona, que va a depender de un
servicio de archivo, o sea de mercado y no de protocolo. Pagarle al archivo desde el protocolo no
es una salida: *"un nodo guardó un archivo"* es estado pasivo sin evidencia on-chain, de la misma
familia que *"un nodo estuvo prendido"*, así que pagarlo sería pagar por una declaración. Lo que la
falta de archivo produce, y conviene precisarlo, es **indisponibilidad y no divergencia**: el
desalojo es determinístico y la reactivación se verifica contra un compromiso que todos tienen, así
que no hay nada sobre lo que forkear.

**La concentración de custodia es riesgo de contraparte, no una propiedad del protocolo.** Un
exchange que lista el token nativo custodia una dirección como cualquier otra y el protocolo no
puede distinguirla — clasificarla sería juicio humano (§7.8). Tampoco serviría convertir la
concentración en trigger: el saldo por dirección se mide, pero la concentración económica no,
porque partir la custodia en diez mil direcciones la lleva a cero sin que cambie nada real; y
como trigger sería **evadible por el que apunta y falsificable por cualquiera** que quiera forzar
una transición juntando saldo.

Y sobre todo: **una transición no redistribuye nada.** Por I3 el estado cruza intacto, así que
quien tenía el 40% lo sigue teniendo después. Forkear contra la concentración es un bucle que no
mueve un solo saldo.

Lo que lo vuelve tolerable es que acá **la concentración no compra poder de protocolo**: no hay
votos, no hay peso por stake, no hay producción de bloques por tenencia. Un tenedor grande no
puede bloquear una transición, ni votar, ni censurar, ni mover el trigger —que solo lee
`emitido − quemado`—. Lo único que le da es poder de mercado y la capacidad de dejar varados a
sus propios clientes, que es lo mismo que *"tu exchange puede quebrar"*: cierto de todos los
activos que existieron, y no lo resolvió ningún protocolo nunca. Se mide y se publica como
telemetría; ahí se termina.

**Sí se puede pagar por acercar una transición, aunque no por cambiar cuál.** Es la contracara del
párrafo anterior, y aparece recién al indexar la tasa de permanencia de §8.5 a la ocupación del
estado, que es la única variable a la que puede indexarse sin violar I2 (§10.3). Quien ocupa disco
le sube el precio del guardado a todos; el depósito ajeno se consume quemándose más rápido; y la
quema entra en `emitido − quemado`, que es exactamente lo que el trigger lee. Nada de eso es un
oráculo ni una lectura prohibida —todo lo que pasa es un hecho del estado—, así que §7.6 no lo
alcanza: el canal no compra una transición distinta, compra **anticipación**.

Cuánta anticipación compra es lo que cambia el carácter del problema. Empujar el trigger quemando
plata propia ya está al alcance de cualquiera que tenga plata, y en el mejor de los casos cuesta uno
a uno —es la aritmética de §7.3, donde lo único que nunca vuelve es la quema—. Lo que este canal
agrega es
**descuento**. Con `s` la fracción del estado que ocupa el atacante y `ε` la elasticidad de la
demanda honesta de guardado, el control tiene que subir la tasa por `R = (1/(1−s))^(1/ε)`, y la
quema ajena que el atacante consigue por cada unidad de quema propia es `((1−s)/s) · ((R−1)/R)`:

| `s` | `ε` = 0,25 | `ε` = 0,5 | `ε` = 1,0 | `ε` = 2,0 |
|---|---|---|---|---|
| 5% | **3,52** | 1,85 | 0,95 | 0,48 |
| 25% | 2,05 | 1,31 | 0,75 | 0,40 |
| 50% | 0,94 | 0,75 | 0,50 | 0,29 |

> **La palanca es del orden de `1/ε`.** Con demanda elástica el atacante nunca quema más ajeno que
> propio, y el canal es una forma cara de hacer algo que ya podía hacer barato. Con demanda
> inelástica —quien necesita su activo vivo al precio que sea— aparece el descuento, y ocupando poco
> pasa del triple.

Y `ε` no se puede conocer sin una red corriendo, así que esto no se cierra con un número. Cerrarlo
por definición sí se puede —excluir la quema por permanencia de la cuenta del trigger— y no es
gratis: rompe *circulante es emitido menos quemado, sin excepciones* (§7.8), y la cara es la primera
excepción, no la excepción en sí, porque de ahí en adelante cada canal de quema que se agregue tiene
que discutir si cuenta. Esa es exactamente la lista creciente que §7.8 existe para no tener.

Se elige declararlo, con dos cosas que lo acotan y una que lo reabre. Lo acotan que **lo que se
compra es la fecha y no el contenido** —el sucesor está escrito de antemano y por I3 el estado cruza
intacto, así que adelantar el disparo no cambia a qué se transiciona— y que esta regla dispara por
**aproximación observable** (I2), de modo que un empujón sostenido se ve venir en la misma
telemetría que publica cuántos bloques faltan al ritmo actual. Lo reabre una medición: si con red corriendo la demanda de
guardado resulta marcadamente inelástica, la decisión correcta pasa a ser la otra, y lo que hay que
pagar es §7.8.

**El canario paga por delatar, y quien puede romper la primitiva gana más callándose.** La
recompensa de §6.6 solo atrae a quien valora cobrarla por encima de lo que obtendría explotando la
rotura en silencio. Para una capacidad criptográfica genuinamente nueva —el caso que el canario
existe para detectar— esa comparación no se gana con ninguna recompensa razonable: el que puede
falsificar firmas puede tomar la cadena entera, y eso vale más que cualquier bounty que la cadena
pueda pagar. La objeción es de la discusión original de 2018 y no la resuelve el intérprete: la
escalera encadenable arregla el costo de disparar temprano, no la razón por la que alguien
dispararía.

Lo que la acota es que el canario no necesita atraer al adversario óptimo, sino a **cualquiera** que
llegue primero — investigación académica, un equipo que busca reputación, un competidor. El
supuesto es que la capacidad de romper una primitiva no aparece en un solo lugar ni en secreto
perfecto, que es lo que históricamente pasó con DES, MD5 y SHA-1. Es un supuesto empírico sobre
cómo se difunde el criptoanálisis, no una propiedad del diseño, y hay que declararlo como tal: si
la capacidad aparece concentrada y en silencio, el canario no dispara y el lazo de §6.6 no arranca.

### 10.3 Problemas abiertos

Quedan dos. Uno es una regla que todavía no está elegida, junto con el nivel del que parte; el otro
lo abrió construir la máquina de §6.6, y no es una decisión sino una pregunta empírica que dos
máquinas no alcanzan a contestar. El techo de pasos —que era el primero de esta lista— se cerró en
agosto de 2026 y está al final de la sección, entre los resueltos.

**El primero es la regla que mueve la tasa de permanencia de §8.5.** Que la tasa no puede quedar
congelada ya está dicho: es un precio nominal sobre un recurso real, y con la unidad flotando se
rompe hacia arriba y hacia abajo. Lo que no está elegido es la regla que la mueve. La única
variable a la que puede indexarse sin violar I2 es la **ocupación del estado** —un hecho del
estado, no una lectura de mercado—, que además es la doctrina de §7.6 aplicada al disco: apuntar a
la cantidad y dejar flotar el precio. Indexarla ahí abre una puerta —como el depósito se consume
quemándose, quien llena estado acelera la quema de terceros, y la quema es lo que lee el trigger—,
pero esa puerta ya no está en discusión acá: **queda declarada como frontera en §10.2**, con la
palanca medida, con lo que la acota y con lo que la reabriría. La alternativa era excluir la quema
por permanencia de la cuenta del trigger, y cuesta la definición sin excepciones de §7.8. Lo que
esta sección deja abierto, entonces, no es si se indexa: es qué regla se escribe.

Y de esa regla falta algo más que la forma: **falta el nivel del que parte.** Una ley de control
dice cómo se mueve la tasa, no dónde empieza, y dónde empieza es un precio —cuánto vale una época
de guardado en unidades del token— que la cadena no puede leer sin violar I2. O se fija en Genesis
con un número elegido a mano, y entonces lo único que el diseño promete es que la regla lo corrija
si estaba mal, o hay que anclarlo a algo que sí esté en el estado y todavía no aparece qué. Es la
misma forma del primer problema abierto —un número, y dónde vive—, y conviene no esconderlo adentro
de la regla.

**Y hay una diferencia con aquel primer problema que ahora se puede enunciar, en vez de intuirse.**
El techo de pasos se cerró dos veces con la misma jugada —congelar la cuenta en vez del número— y
la pregunta natural es por qué la tasa no cede a lo mismo. La respuesta es que **el techo tenía sus
dos lados en el mundo físico**: pasos de uno, segundos del otro, y la cadena puede contar los dos
sin preguntarle nada a nadie. **La tasa tiene un lado físico —bytes × épocas— y uno monetario
—cuántas unidades vale eso—, y ninguna cuenta cruza esos dos lados sin leer un precio.** Leer un
precio es lo que I2 prohíbe, y es el mismo muro que §7.6 declara para el pool.

Eso no cierra el problema pero le cambia el carácter: **no es una cuenta que falta escribir, es una
frontera**, de la misma familia que las de §10.2. Y tiene una consecuencia práctica, que es la que
mandó denominar el piso en épocas de guardado (§8.5): **todo lo que se pueda expresar en fracciones
del presupuesto del nodo se deriva, y todo lo que exija una unidad monetaria queda de este lado del
muro.** Con el piso del lado derivable, lo que queda abierto es un solo número y no dos.

**El replay de §11 le puso número a este problema, y en un parámetro ajeno.** Ethereum raciona el
gas con un precio que computa el propio protocolo —el base fee de EIP-1559— y ese precio cayó **650
veces en cuatro años**. Cualquier nivel nominal fijado en Genesis habría dejado de significar lo
que significaba, que es exactamente lo que esta sección afirma de `r0` y hasta ahora no se había
podido medir.

**Y el ancla más obvia quedó descartada con datos.** Si el nivel no puede ser un número, lo natural
es volverlo adimensional: el precio contra su propia mediana anual, que es escalable, sale del
estado y no pide oráculo. Funciona donde importa —sobre el gas limit habría disparado catorce meses
antes que la coordinación humana— y falla donde no se lo ve venir: **se queda sin noción de caro**.
Con el precio ya dos órdenes de magnitud abajo, que se duplique vuelve a disparar la regla, porque
sin referencia absoluta *caro* es sólo *más que recién*. Un setpoint relativo no es un setpoint: es
un trinquete.

**Queda una consecuencia sobre la indexación a la ocupación que conviene declarar.** Como error de
un lazo de control, la ocupación sigue siendo la variable correcta y nada de esto la toca. Lo que
el replay muestra es que **deja de servir para la otra pregunta**: en un recurso que ya raciona un
precio, la ocupación queda clavada en su target por construcción —medido en Ethereum, correlación
**−0,02** contra un precio que se movió 650×— y entonces no dice nada sobre si la capacidad
alcanza. La misma variable no puede contestar *a qué precio* y *cuánta capacidad*: la primera la
contesta el lazo, y la segunda se queda sin observable.

**El segundo es cuál hardware es el peor caso, y lo abrió medir.** Todo el diseño supone que la capa
liviana es la que ata: de ahí sale la entrada barata de nodos de §6.1, y con ese supuesto se calibra
el `R_declarado` que alimenta el techo de §6.6. **Medido sobre la máquina real, el supuesto es falso
para los patrones adversariales de memoria.** Un teléfono de gama media corre el peor programa
admisible a 80,8 millones de pasos por segundo y un escritorio x86-64 lo corre a 78,9 — y con
presupuestos de memoria mayores la distancia se abre hasta el doble, a favor del teléfono. La causa
es que las dos máquinas se rompen por lugares distintos: el núcleo ARM no paga el salto indirecto
impredecible que castiga al intérprete en x86, y el escritorio no aguanta la dispersión de páginas
que el teléfono absorbe sin costo.

Eso no invalida el techo —se calibra contra el hardware que el protocolo declara como referencia, y
ahí está medido— pero **sí invalida la frase de que el hardware más barato es el peor caso**, que
aparecía como obvia. Y no se cierra pensando: **dos máquinas no alcanzan para fijar un piso de
hardware**, y menos cuando una de las dos tiene una dispersión del 80% entre corridas de la misma
medición contra el 1,6% de la otra. Necesita más máquinas, que es trabajo de otra clase que el resto
de esta sección.

> **Resuelto:** *el techo de pasos de §6.6*. Estuvo declarado acá como **un número y dónde vive**,
> con un acople que parecía obligar a elegir entre dos formas malas: congelado en la máquina hay que
> elegirlo generoso —tiene que sobrevivir primitivas que todavía no existen— y generoso es
> justamente lo que deja pasar la implementación correcta pero diez veces más lenta; apretado obliga
> a que sea parámetro interno, y un parámetro interno es una palanca que alguien va a querer mover.
>
> **La disyuntiva era falsa.** Esta misma sección ya decía dónde tenía que estar el ancla —*lo único
> que no deriva es el presupuesto de la capa liviana de §6.1*— y lo que faltaba era escribir la
> cuenta: `techo = f* × tiempo_de_bloque × R_declarado / tx_por_bloque`. Lo que I1 congela es **la
> fórmula**, no el número, y el valor lo determina cada generación con parámetros que ya están en el
> espacio. Así no queda ni congelado ni suelto: **no es una palanca, porque nadie puede moverlo sin
> mover capacidad o tiempo de bloque**. Y como no depende de qué primitiva esté instalada, **no
> compone**: evita el préstamo que cobraba el ancla relativa, donde 2× por transición son 1.024× a
> las diez.
>
> **El filo de las primitivas futuras se disuelve solo.** Una primitiva más cara no queda afuera:
> **entra pagando capacidad**, y esa cuenta la hace una transición de §3, con su `Δ` y su aviso.
> Deja de ser una decisión gratis e invisible y pasa a tener precio.
>
> **Lo que sí queda como decisión, y se declara como tal:** `f*` —la fracción del nodo liviano que
> puede ocupar la verificación de firmas— y `R_declarado` —el ritmo del hardware de entrada—.
> Ninguna sale de una medición. `f*` tiene piso: §6.3 necesita headroom para drenar la cola, y está
> medido en 10% con once nodos. `R_declarado` tiene que estar **por debajo** del hardware real, y
> errar bajo es la dirección segura porque el sobrante es headroom. Con `f* = 25%` y
> `R = 70 M pasos/s`, un bloque de seis segundos con 15 transacciones da un techo de **7 millones
> de pasos**: el doble de lo que cuesta la implementación de referencia de ML-DSA-44, y la quinta
> parte de lo que costaría la implementación lenta que Test 2 encontró.
>
> El margen de 2× es la única elección con arbitrio y tiene cota de los dos lados: en 1× el
> protocolo termina eligiendo la implementación en vez de la interfaz, que es lo contrario de lo que
> §6.6 busca; en 10× vuelve el caso que el techo existe para excluir. **Se usa una sola vez, en
> Genesis, para elegir la capacidad** — si el protocolo lo reaplicara en cada transición, volvería a
> componer.
>
> **Y la primera vez que se escribió esto, `R_declarado` decía 300 M y la capacidad 67.** Construir
> la máquina lo falsó: aquel número era el ritmo de **una** mezcla de instrucciones, la de ML-DSA, y
> el ritmo de la máquina depende de la mezcla por 23×. La fórmula sobrevivió sin un cambio; lo que
> estaba mal era su calibración, y arreglarla costó las tres cuartas partes de la capacidad del bloque. **Que el
> techo fuera una cuenta y no un número es lo que hizo que la corrección fuera de un parámetro y no
> de un mecanismo** — y que hiciera falta un segundo techo, sobre páginas tocadas, es lo que agrega
> §6.6.1. Medido en §12, Test 5.
>
> **Y el segundo techo repitió la historia del primero en miniatura.** Nació como constante, y una
> constante en ese lugar **excluye en vez de encarecer**: una primitiva que necesitara más memoria
> no tenía precio que pagar. Se cerró igual —congelando la curva en vez del punto— y el bloque 0 no
> se movió: 96 páginas, 15 transacciones, siete millones de pasos. **Que la misma jugada haya
> servido dos veces es lo que más confianza da sobre su forma:** en este diseño, un número que hay
> que elegir suele ser una cuenta que falta escribir.

> **Resuelto:** *el costo de lo que instala el guante*. El pedido de trabajo entrega una interfaz y
> unos vectores, y durante un tiempo el predicado verificó solo que la implementación fuera
> **correcta**, no que fuera **barata**. Lo encontró Test 2 y lo cierra §6.6: el predicado de
> aceptación lleva ahora dos cláusulas, y la segunda es un techo de pasos de VM. El agujero era que
> el presupuesto de §6.1 se podía romper desde adentro del protocolo, sin fork y sin atacante.

> **Resuelto:** *el presupuesto de verificación del intérprete*. Era el problema que podía tumbar
> una pieza estructural: si la matemática de retículos interpretada no entraba en el presupuesto de
> la capa liviana, se rompía §6.1 y con ella la respuesta al problema de los validadores. Medido en
> hardware real (§12, Test 2): entra, y con margen. La clave es que **determinismo e interpretación
> son cosas separadas** — wasm fija la semántica, y para código entero el JIT la reproduce bit a
> bit igual que el intérprete, así que la penalidad de la propiedad que §6.6 necesita es **~3×** y
> no los ~29× que sugiere la intuición de "interpretado es lento". En un teléfono el techo con JIT
> es el mismo que en escritorio.

> **Resuelto:** *la obsolescencia criptográfica contra I2*. El canario convierte la rotura en un
> hecho del estado; el intérprete quita el fondo de la escalera; el pedido de trabajo escribe la
> primitiva nueva y el guante decide si entra. Todo en §6.6, sin fork humano y sin límite de
> generaciones.

> **Resuelto:** *las transacciones en vuelo*. La mitad se adopta de lo que ya hacen todas las
> cadenas —vale el ruleset del bloque que incluye, y el mempool no es estado de consenso— y la
> otra mitad, los objetos a medio comprometer, sale de I5 sin agregar nada (§6.3).

> **Resuelto, y queda registrado porque el problema es el que casi todo el mundo espera
> encontrar:** *una transición que los validadores no quieren*. En PoW y PoS el productor de
> bloques cobra exactamente lo que una transición puede tocar, así que puede formar un bloque con
> interés alineado en contra. Acá el ingreso de la capa de consenso es un fee por verificación
> sobre hardware sin foso de capital (§6.1): quien se niega no bloquea, se autoexcluye, y
> reemplazarlo cuesta un teléfono.

---

## 11. Estado

Concepto con los cuatro tests de §12 cerrados y, desde agosto de 2026, con el mecanismo de §3
**corriendo**: motor de sucesión sobre un estado sintético, las cinco invariantes como predicados
que se ejecutan en cada bloque, orden y liquidación de §6.3 a §6.5, y un harness que corre reglas
candidatas contra el historial real de Ethereum. Lo construido no es una red — es §3 ejecutándose
y midiéndose.

**Construirlo corrigió tres cosas que leer no había corregido**, y las tres están escritas donde
corresponde y no en un anexo: qué pasa con **más de una transición en vuelo** (§3), que el evento
de lock-in **es estado y no un anuncio** (§3), y que **I2 estaba mal escrita** — dejaba afuera al
canario de §6.6, que es la sección de vidriera, y dejaba pasar una compuerta con dueño (§4). A eso
se sumó la tercera condición de §6.3: **cada nodo elige en su propio orden**, sin la cual el
paralelismo de la cola se evapora y el número de nodos necesarios deja de existir.

**El replay va primero porque es la única evidencia de este documento que no escribió su autor**, y
lo primero que hay que decir es que **dos de sus tres casos fueron en contra.** Tres parámetros
reales, con las alturas y los offsets verificados contra los EIPs y contra la configuración que
corren los nodos:

- **la bomba de dificultad.** Una `TRANSITION_RULE` con un solo número elegido de antemano
  reproduce las seis veces que Ethereum la corrió, dentro de 37 días, y una de ellas exacta. Pero
  ese número es el promedio de un criterio que **se estaba moviendo**: medida contra la capacidad
  de ajuste de la red, la presión a la que forkearon varió **41×**, y cinco de los seis forks
  fueron preventivos. Un umbral escrito en Genesis habría sido el equivocado en los dos extremos;
- **los blobs.** Donde la restricción era la demanda, la regla habría actuado **383 días antes**,
  con la ocupación sostenida en el 129% del target. Donde la restricción **no** era la demanda, no
  habría actuado nunca: las dos últimas subas respondieron a que Fusaka trajo PeerDAS, y *"la red
  ahora puede transportar más sin degradarse"* no es un hecho del estado;
- **el gas limit.** No hay trigger admisible, y no por falta de ingenio. La cantidad está vacía por
  construcción —EIP-1559 clava la ocupación en el target: **correlación −0,02** con el base fee
  mientras el fee se mueve 650×—, el precio nominal caduca, y anclar el precio a su propia historia
  pierde la noción de *caro*.

**El replay no produjo evidencia de que este diseño sea mejor.** Produjo los tres lugares donde se
rompe contra el mundo real, cada uno con su número. Los tres están escritos donde corresponde
—§10.1, §10.3 y §7.6— en vez de quedar en un anexo. Reproducción en `genesis/herramientas/`.

**Test 2 pasado**: el presupuesto del intérprete entra con margen, medido en hardware real, y el
§10.3 que podía tumbar una pieza estructural quedó resuelto. El agujero que el test encontró de
paso —el guante acotaba corrección y no costo— también quedó cerrado en el mecanismo de §6.6. Lo
que sigue abierto ahí **ya no es un mecanismo: es un número y dónde vive.**

**Test 3 corrido**: el hueco existe, pero más angosto. El disparo automático sin voto tiene
precedente (Drake, 2018); lo que no lo tiene es la sucesión encadenable dentro de un espacio
definido en Genesis. §6.6 se reescribió para citar esa convergencia y para responder la objeción
que dejó aquella idea sin avanzar.

**Test 1 pasado**, y es el que más mueve el diseño: el mecanismo tiene cliente —hay transiciones
reales que cumplen las tres condiciones, y la principal está corriendo hoy en Ethereum—, pero el
cliente pide la mitad barata. Ninguno de los casos encontrados necesita el intérprete ni las
generaciones encadenables, que son justamente las dos piezas que pagan las fronteras más caras de
§10.1 y que sostienen el diferenciador de §6.6. La demanda demostrada está en §3 + I2 sobre un
espacio finito de parámetros internos; la evolución criptográfica, que es la sección de vidriera, es
la única aplicación sin cliente encontrado.

**Test 4 corrido**, con el resultado más caro de los cuatro: la respuesta a su pregunta fue que
no. La emisión neta y la ganancia de quien se paga a sí mismo son la misma cantidad, así que no
existía un `k` que creara dinero nuevo sin crear exactamente esa oportunidad. Se le sumaba una
segunda falla que no dependía de `k`: con `W` medido en tokens pagados y sin preminado, el lazo
arrancaba en cero y no podía emitir la primera unidad.

**Ese resultado reescribió §7 entero, y esa reescritura es la parte más nueva y menos probada de
este documento.** La emisión dejó de depender del trabajo, las fees quedaron como único pago del
trabajo, la distribución del día 1 se resolvió por claim con costo de cómputo y quema de lo no
reclamado, y el ataque de auto-pago pasó de *"hay que calibrarlo"* a *"pierde plata a cualquier
escala"*. Alrededor de eso se cerraron cuatro preguntas que el rediseño abrió: la distribución
inicial (§7.2), la banda de circulación —se eliminó—, la asignación de trabajo (§6.5) y la
saturación de la cola de impugnaciones (§6.3).

Queda entonces un concepto partido en dos mitades de distinta **evidencia**, que es una forma más
precisa de decir lo que anticipa §12:

- **la sucesión determinista de parámetros** tiene cliente encontrado afuera, en cadenas que
  existen, y no depende de la moneda;
- **la moneda** tiene una especificación que sobrevive a todos los ataques que se le corrieron,
  y ninguno de esos ataques vino de afuera.

**Y la creación de activos de §8.5 es más nueva todavía que eso**, así que conviene decir en qué
estado está: el mecanismo —piso, depósito, tope a la vida comprable, desalojo con reactivación—
está completo y verificado contra las invariantes, pero **la regla que mueve la tasa no está
elegida** y quedó en §10.3. La colisión que la bloqueaba —indexar la tasa a la ocupación abre un
canal para pagar por acercar una transición— se resolvió del único modo disponible sin red
corriendo: se midió la palanca, se comparó contra lo que costaba cerrarla, y quedó **declarada como
frontera** en §10.2 en vez de arreglada. Vale como muestra de lo frágil que es la evidencia
propia: la primera versión de esa regla parecía estable, y lo que la
tumbó fue corregir un detalle del modelo con que se la había probado —trataba como acortables unos
plazos que el protocolo promete respetar—. Es exactamente el modo de falla que el párrafo anterior
describe, encontrado esta vez adentro.

Lo que sigue en el proyecto no es más falsación del mismo tipo: los cuatro tests que §12 propone
ya están corridos, y el quinto —el único que exigió construir— también. Para la primera mitad es la decisión de alcance que el Test 1 dejó sobre la
mesa; para la segunda, conseguir que alguien que no escribió el diseño intente romperlo.

---

## 12. Cómo falsarlo antes de construir nada

El riesgo dominante no es técnico —el mecanismo es implementable— sino que no tenga cliente.
Ninguno de los cuatro tests requiere escribir una línea de protocolo.

**Hay un quinto, y llegó después.** Los cuatro de arriba se diseñaron para falsar *antes* de
construir, que es de donde sale casi todo su valor. El Test 5 no podía: pregunta qué hace la
máquina cuando el programa lo escribe un adversario, y para contestarlo hay que tener la máquina.
Se lo escribe acá porque **reprobó**, y lo que reprobó fue un número que este mismo documento daba
por cerrado. Vale la pena tenerlo a la vista junto a los otros, con la advertencia de que la
lección que deja —*hay cosas que sólo se ven construyendo*— es exactamente la que esta sección
existe para minimizar, no para negar.

**Test 1 · La transición concreta.** ✅ **Pasado** (agosto 2026), con una corrección al alcance.
Nombrar *una* transición real que cumpla las tres condiciones a la vez: que su trigger se compute
desde el estado de la cadena; que se exprese como selección dentro de un espacio de parámetros
definible hoy; y que alguna cadena real la haya necesitado y no haya podido tenerla. Si no aparece
ninguna, el mecanismo no tiene cliente y todo lo demás es ingeniería sin destinatario.

> **Resultado: aparecen tres, y el cliente es más chico que la vidriera.** La principal está viva:
> Ethereum recalibra los parámetros de capacidad de blobs —`blobSchedule`: target, límite y fracción
> de ajuste— y construyó un tipo de fork dedicado a abaratar ese cambio (EIP-7892), porque *"los
> cambios de parámetros de blob grandes e infrecuentes generan costos e ineficiencias"*. El disparo,
> sin embargo, sigue siendo un timestamp escrito a mano en la configuración del cliente. En mayo de
> 2026 el patrón se repitió sobre el gas limit (EIP-8261): un cronograma por época que declara
> explícitamente **no** ser regla de consenso. Corroboran otros dos casos: la bomba de dificultad,
> retrasada por hard fork **seis veces** en cinco años —Muir Glacier se coordinó en menos de tres
> semanas, sobre las fiestas de 2019, para instalar un entero que la cadena podía calcular sola, y
> que un humano había calculado mal—; y la emisión terminal, que Monero escribió por adelantado y
> obtuvo sin fork ni decisión, mientras Bitcoin, que no la escribió, hoy no puede tenerla a ningún
> precio. Método, candidatos descartados y fuentes en `test1-transicion/RESULTADOS.md`.
>
> *Actualización de agosto de 2026, al verificar los datos del replay de §11.* EIP-7892 pasó a
> **`Final`**, y su motivación conviene leerla textual: *"the current approach of only modifying
> blob parameters in large, infrequent hard forks is not agile enough to keep up with L2 growth"*.
> Ethereum ya lo usó dos veces —el `blobSchedule` de mainnet fue de target 3 a 6, 10 y 14 en
> veintidós meses—, así que el cliente no sólo existe: está actuando, y acelerando. **Y la otra
> mitad hay que decirla igual de fuerte: lo resolvió abaratando el fork, no volviéndolo
> innecesario.** Un fork de sólo-parámetros sigue siendo un fork coordinado. Más todavía: las dos
> últimas subas se anunciaron **juntas y por adelantado**, o sea que el paso siguiente que dio el
> cliente por su cuenta fue *escribir el cronograma antes* — la forma de BIP-103, a una propiedad de
> lo que propone este documento, y esa propiedad es I2: el disparo sigue siendo el reloj y no el
> estado.
>
> *La corrección al alcance:* ninguno de los tres necesita el intérprete, ni generaciones
> encadenables, ni §6.6 — son parámetros internos sobre espacios de enteros. Lo que tiene demanda
> demostrada por terceros es **§3 + I2 con espacio finito**, que es la mitad del diseño que **no**
> paga las fronteras caras de §10.1. La otra mitad, incluido el diferenciador declarado frente a
> Drake, sigue sin destinatario encontrado.

**Test 2 · El presupuesto del intérprete.** ✅ **Pasado** (agosto 2026). Medir cuánto tarda una
verificación de firma post-cuántica corriendo como bytecode sobre una VM determinística, en un
teléfono. El lazo de §6.6 y la propiedad de gobernanza de §6.1 dependen los dos de que ese número
entre en el presupuesto de la capa liviana. Es un benchmark, no un protocolo: se corre con una VM
que ya exista y una implementación de referencia. Si el número no da, la capa liviana deja de ser
liviana y se cae la respuesta al problema de los validadores.

> **Resultado: entra con margen.** ML-DSA-44 desde bytes en un Motorola Edge 40 Neo: 391 µs como
> bytecode con JIT (3,51× el nativo), ~640 tx/s con un cuarto de núcleo — el mismo techo que en
> escritorio. Lo que lo decide es que **determinismo e interpretación son separables**: para código
> entero el JIT es tan determinístico como el intérprete, y cuesta ~3× en vez de ~29×. El test
> también devolvió una cláusula del predicado (§6.6), dos condiciones (§10.1, §10.3) y una
> corrección a §6.1: la asimetría Android/iOS
> es ~15×, no ~8× como se había estimado desde escritorio. Método, tablas y datos crudos en
> `test2-interprete/RESULTADOS.md`.

**Test 3 · Competidores.** ✅ **Corrido** (agosto 2026), con una corrección al hueco declarado.
Tezos se auto-enmienda por voto. Polkadot evoluciona por gobernanza. La bomba de dificultad de
Ethereum fuerza el fork pero el sucesor lo escriben humanos. El hueco declarado es **sucesión
determinista sin voto**; hay que confirmar que es real y no un artefacto de no haber buscado lo
suficiente.

> **Resultado: el hueco existe, pero es más angosto de lo que decía esta sección.** Tezos, Polkadot
> e Internet Computer quedan confirmados como dependientes de voto. El combinador de hard forks de
> Cardano hace la transición sin split, pero el sucesor lo escriben humanos y la propuesta va
> firmada. Lo que **no** era nuevo es el disparo: *cryptographic canaries* (Drake, 2018) ya combina
> trigger desde el estado y conmutación automática sin voto, con un respaldo único precableado —
> ver §6.6, *Convergencia previa*. Tampoco era nuevo escribir por adelantado la sucesión de un
> **parámetro**: BIP-103 (Pieter Wuille, 2015) propuso reemplazar el límite de tamaño de bloque de
> Bitcoin por una función determinista —+4,4% cada ~97 días hasta 2063— sin voto de mineros. No
> cierra el hueco, y por tres motivos que conviene tener a mano: el disparo es tiempo y no estado,
> el sucesor es una constante de una curva fija en vez de un punto de un espacio, y no hay
> encadenamiento. Pero es sucesión determinista sin voto, en Bitcoin, diez años antes.
> Lo que no aparece en ningún trabajo encontrado es el sucesor
> derivado dentro de un espacio definido en Genesis, con generaciones encadenables. Trabajo
> concurrente a vigilar: *Post-Quantum Blockchains with Agility in Mind* (Tectonic Labs, IACR
> 2026/609, marzo 2026), que resuelve agilidad por elección operativa de cada usuario, no por
> sucesión determinista.
>
> *Límite de la búsqueda:* una pasada, en inglés, sobre web y literatura indexada, con vocabulario
> de gobernanza y de cripto-agilidad. El hallazgo de Drake salió del segundo vocabulario y no del
> primero, y BIP-103 no salió de ninguno de los dos: apareció recién en Test 1, con vocabulario de
> recalibración de parámetros. Los dos precedentes que este test tenía que encontrar los encontró
> **fuera** de su propio vocabulario. No descarta algo en documentación mal indexada de un
> proyecto chico.

**Test 4 · La ventana de `k`.** ✅ **Corrido** (agosto 2026), y es el único de los cuatro que
obligó a reescribir una sección entera en vez de podarla. Simular si existía algún `k > 0` donde
auto-pagarse no fuera rentable y el subsidio todavía resultara significativo para un operador
honesto. Era el test con doble función —decidía a la vez si la moneda era sana y si la etapa 1 de
adopción era viable— y sin ese número la política monetaria y el plan de adopción descansaban sobre
un supuesto no medido. Es una simulación, no un protocolo.

**El `k` de este test ya no existe en el documento.** Lo que §7 y §9 dicen hoy es consecuencia de
haberlo corrido; conviene leer el resultado sabiendo que describe el diseño que se le presentó, no
el que quedó.

> **Resultado: la ventana es vacía, y por identidad.** La emisión neta y la ganancia de quien se
> paga a sí mismo son **la misma cantidad**: `(k − β·φ)·W`, donde `β·φ` es el fee por su fracción de
> quema. No son dos condiciones que haya que hacer entrar en una ventana — **todo peso de dinero
> nuevo que el protocolo crea es, exactamente, un peso disponible para quien fabrique trabajo.** El
> autotratante cobra esa emisión corriendo su propio nodo PoD, y §6.1 hace esa entrada barata a
> propósito. En el máximo `k` seguro la cuenta cierra en cero y el ingreso de los nodos PoD es
> exactamente el fee: **todo el aparato de emisión y quema hace lo mismo que un mercado de fees sin
> emisión ni quema.** No hay tercera región. Modelo y simulación en
> `test4-ventana-k/RESULTADOS.md`.
>
> *Segundo hallazgo, independiente de `k`:* `W` se medía en tokens pagados y aquella versión
> prohibía el preminado. En el bloque 0 no existe ningún token, así que nadie puede pagar, así que
> `W = 0` y `E = 0` para siempre. **El lazo era cerrado y arrancaba en cero.**

> **Lo que este test forzó, y es la única vez que un resultado negativo cambió el diseño en vez de
> podarlo.** El §7 que se lee hoy no es el que corrió este test: la emisión dejó de indexarse al
> trabajo y pasó a ser un mecanismo aparte, la distribución del día 1 se resolvió por claim con
> costo de cómputo, y las fees quedaron como único pago del trabajo. **El rediseño se sometió al
> mismo ataque que mató al original** —Alice cicla dinero entre nodos propios para fabricar
> actividad— y pierde a toda escala, incluso siendo el 100% de la red (§7.3,
> `test4-ventana-k/ataque-alice.py`). El motivo es que ya no hay nada que farmear: fabricar trabajo
> no produce unidades nuevas.
>
> Conviene ser preciso sobre qué quedó demostrado, porque *"corrido"* no es *"salió bien"*. **La
> pregunta que este test hacía tiene respuesta negativa y definitiva:** no existe un `k` sano, y
> ninguna calibración futura lo va a encontrar. Lo que la reemplaza no es un `k` mejor sino un
> diseño donde `k` no existe. El test hizo exactamente su trabajo —descartar antes de construir—, y
> el diseño que lo reemplaza está simulado, no construido ni desplegado.

**Test 5 · La máquina bajo un programa adversarial.** *(De otra clase que los cuatro de
arriba: éste no se pudo correr antes de construir, y por eso llegó tarde.)* ⚠️ **Corrido** (agosto 2026), y **el
criterio central salió reprobado**. Test 2 midió el intérprete con un guest propio, escrito por el
mismo repo. Este mide el mismo intérprete corriendo el programa de la contraparte de una
impugnación: alguien que quiere que el nodo se cuelgue o se caiga. Los criterios se escribieron
antes de la primera línea de código, en `genesis/predicado/CRITERIOS.md`, y siete de ellos son
operables con un número.

> **Resultado: seis pasaron y el séptimo destapó que el techo de §6.6 prometía de más por 23×.**
> El criterio decía: *aprobado si la peor mezcla de instrucciones corre a ≥ 300 M pasos/s*, que es
> el `R_declarado` con el que se había cerrado el techo. La peor mezcla corre a 11,3 M. **Ningún
> peso por clase de instrucción lo arregla**, porque la mezcla que produce el hueco es una lectura
> de memoria y una lectura cuesta lo mismo que una suma cuando el dato está en caché: es el mismo
> opcode y lo que cambia es dónde cae el dato. De ahí salieron **un techo nuevo sobre páginas
> tocadas** (§6.6.1), una recalibración de `R_declarado` de 300 a 70 M pasos/s, y las tres cuartas
> partes de la capacidad inicial del bloque: de 67 a 15 transacciones. Tablas y método en
> `genesis/predicado/RESULTADOS.md`.
>
> *Y tres hallazgos que no eran de rendimiento sino de superficie de ataque:* el cargador reservaba
> 64 MiB antes de validar una sola cabecera, y una cabecera de sección alterada podía forzar 128 MiB
> de predecodificado — **entrada barata, trabajo caro, que es amplificación con otro nombre**. Los
> encontró que el barrido de mutaciones tardara minutos, no un test de corrección. El tercero es que
> las banderas de segmento de un ELF no distinguen código de constantes, así que el formato de
> predicado tuvo que empezar a exigir que el binario **declare dónde está su código**.
>
> *Y una lección de método que costó tres correcciones publicadas.* La medición que fija
> `R_declarado` **estuvo mal cuatro veces, y las cuatro hacia el mismo lado**: el inseguro. Tres eran
> comparaciones entre números tomados con métodos o en momentos distintos. La cuarta es peor y no
> falló nada: **una mezcla adversarial degeneró en otra y siguió informando un número creíble** —la
> persecución de punteros cargaba mal su dirección inicial y terminaba leyendo siempre la misma
> posición, en caché—. Se cazó porque corría exactamente a la velocidad de otra mezcla, y sobre ella
> se habían apoyado dos conclusiones ya escritas acá. Ahora cada mezcla **declara cuántas páginas
> tiene que tocar y se verifica al terminar**: una medición tiene que declarar qué está midiendo.
>
> **Y la reproducibilidad entre arquitecturas quedó verificada**: los siete vectores —veredicto,
> pasos, páginas y huella de los registros— dan idénticos en x86-64 y en aarch64.

**Los tests 1 y 4 eran independientes y dieron resultados opuestos.** El Test 1 decidía si el
mecanismo generacional tiene cliente y encontró uno, más chico que el mecanismo; el Test 4 decidía
si la moneda existe y encontró que no, con la especificación que se le presentó. Pasa exactamente
lo que esta sección anticipaba: **lo que sobrevive es la mitad correspondiente, no el conjunto.**
Sobrevive la sucesión determinista de parámetros internos —cuyos clientes, además, ya tienen moneda
propia— y no sobrevive la emisión indexada a trabajo pagado.

**Y hay una asimetría entre los dos resultados que conviene no maquillar.** El Test 1 midió el
mundo: encontró tres transiciones reales, escritas por terceros, en cadenas que existen. El Test 4
midió un modelo propio con parámetros propios, y el rediseño que salió de él también. **Una
simulación que sobrevive a los ataques que su autor supo imaginar no es evidencia del mismo tipo
que un cliente encontrado afuera**, y la diferencia entre las dos mitades de este documento sigue
siendo esa, aun después del rediseño.
