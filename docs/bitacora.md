# Bitácora: cómo se construyó, y qué se cayó en el camino

*[English version](build-log.en.md)*

Este documento no es un registro de avances. **Es el registro de qué se descartó y por
qué.**

El [paper](paper.md) dice a qué se llegó; esto dice cómo se llegó, qué murió en el
camino y qué ataque sobrevivió cada pieza. Existe por dos razones:

- **para el que viene a romper el diseño** — para que no gaste su tiempo proponiendo algo
  que ya se probó y falló. Al final hay un [índice de lo que ya murió](#índice-lo-que-ya-murió);
- **porque es lo caro de rederivar.** Un resultado se vuelve a mirar en un minuto; el
  razonamiento que lo produjo, no.

Está en orden cronológico, y cada tramo dice qué corrigió del paper.

---

## Índice

- [0 · El método, que es la mitad del resultado](#0--el-método-que-es-la-mitad-del-resultado)
- [1 · Los cuatro tests de falsación, antes de construir nada](#1--los-cuatro-tests-de-falsación-antes-de-construir-nada)
- [2 · El rediseño monetario, y el muro de la identidad](#2--el-rediseño-monetario-y-el-muro-de-la-identidad)
- [3 · La construcción: seis fases, y lo que leer no había corregido](#3--la-construcción-seis-fases-y-lo-que-leer-no-había-corregido)
- [4 · La auditoría de unidades: lo que pasa por debajo de las cinco](#4--la-auditoría-de-unidades-lo-que-pasa-por-debajo-de-las-cinco)
- [5 · Las lecciones de método, que valen fuera de este proyecto](#5--las-lecciones-de-método-que-valen-fuera-de-este-proyecto)
- [6 · La primera revisión externa](#6--la-primera-revisión-externa)
- [Índice: lo que ya murió](#índice-lo-que-ya-murió)

---

## 0 · El método, que es la mitad del resultado

Tres reglas gobernaron todo lo que sigue, y conviene tenerlas antes de leer los resultados
porque son lo que decide si un resultado significa algo.

**1 · Los criterios de aprobado se escriben antes de correr nada, y no se ablandan
después.** Cada fase tiene su archivo de criterios, escrito antes de la primera línea de
código, y no se editó al ver el resultado. **Agregar criterios está permitido; ablandarlos
no.** En un caso el número medido permitía subir una constante a 140 y se dejó en 120,
justamente porque subirla después de ver un resultado favorable es lo que la regla prohíbe.

**2 · Una prueba tiene que verse fallar una vez.** Tres veces en dos días apareció un
criterio que existía, tenía nombre y no probaba nada: un chequeo de flotantes escrito con
un escape mal puesto que no matcheaba jamás; la revalidación de una prueba criptográfica
que se podía borrar entera sin que se cayera ningún test; y el orden de recorrido del
conjunto activo, que se podía cambiar por uno no determinístico sin consecuencia visible.

> **Una prueba que no prueba es peor que no tenerla, porque además da confianza.**

De ahí sale la herramienta que más se pagó sola: un arnés de mutaciones que rompe el motor
a propósito, de formas que el diseño declara imposibles, y verifica que la suite las cace.
Sin eso, *"246 criterios pasan"* no distingue entre un predicado y un `return true`.

**3 · Toda medición declara qué está midiendo.** Salió del peor error de todo el proyecto
(§3.4), donde una medición degeneró en otra sin avisar y **no falló nada**: siguió
informando un número, plausible y equivocado, sobre el cual ya se habían apoyado dos
conclusiones escritas.

---

## 1 · Los cuatro tests de falsación, antes de construir nada

El paper se escribió con una sección final que decía cómo falsarlo **antes de construir
nada**. Se corrieron los cuatro. El detalle está en [`mediciones/`](../mediciones/); acá va
lo que produjeron.

**Test 1 — ¿el mecanismo tiene cliente afuera?** Sí, y ésta es la única mitad del proyecto
con evidencia de terceros. Ver §2 de este documento y la sección 4 del [README](../README.md).

**Test 2 — el presupuesto del intérprete en hardware real.** Midió que una verificación de
ML-DSA cuesta lo mismo, **byte a byte, en x86 y en ARM**: 3.339.364 pasos para ML-DSA-44.
Ese resultado es lo que hace posible que el techo del protocolo se denomine en *pasos* — en
tiempo de reloj sería un oráculo. También encontró la asimetría iOS/Android de 15×, que
debilitó el argumento de descentralización por costo de entrada y obligó a reemplazarlo por
uno mejor (§2).

**Test 4 — la ventana de `k`.** Buscaba una calibración que hiciera no rentable al
autotratante sin castigar al usuario honesto. **La ventana resultó vacía**, y ése fue el
resultado más productivo del proyecto: forzó el rediseño monetario entero que se cuenta en
la parte 2.

---

## 2 · El rediseño monetario, y el muro de la identidad

Todo esto salió de que Test 4 diera negativo. La economía se rediseñó entera, y el
resultado central no fue un mecanismo sino **un límite del diseño**.

### 2.1 · El muro: cuatro arreglos, una sola causa

Cuatro intentos de arreglar cosas distintas murieron por la misma razón:

| intento | cómo murió |
|---|---|
| `k` como palanca de calibración | entra idéntico en el autotratante y en el honesto |
| bloquear el subsidio (lockup) | descuenta a los dos por igual |
| repartir el beneficio por rol | lo arbitra el que ocupa los dos roles |
| bono de impugnación superlineal | castiga al impugnador honesto junto con el atacante |

> **El protocolo no tiene noción de identidad, así que toda palanca que mueva, la mueve
> para todos.** No es mala suerte cuatro veces: es una propiedad del diseño, y explica los
> cuatro resultados de una sola vez.

Está declarado en el paper como límite inherente, con **dos reglas para revisores** que
existen para que cuatro personas distintas no propongan las mismas cuatro palancas:

> Toda propuesta de la forma **"que el bueno pague menos"** es una propuesta de introducir
> identidad.
>
> Toda propuesta de la forma **"que se emita cuando hay demanda real"** es también una
> propuesta de introducir identidad.

**La salida fue dejar de intentar distinguir.** El rediseño no pregunta *"¿es demanda
externa?"*; hace que el circuito cerrado **pierda**. La aritmética no necesita saber quién
es nadie. Medido: el ataque de auto-pago pierde **incluso siendo el 100% de la red**
(−0,000600 por ciclo). Y la quema resultó ser la única pieza irreemplazable del esquema —
con quema 0% el atacante queda a mano y el ataque pasa a ser gratis.

### 2.2 · La distribución del día 1, y el teorema que la cerró

Cuatro mecanismos se propusieron y murieron antes de que apareciera el que sobrevive:

- **repartir el pool al primero que produzca trabajo** — en el bloque 0 no hay demanda real
  por definición, así que *"el primero que trabaje"* es el que fabrica trabajo más rápido. Y
  es **una sola vez y no se corrige**: no hay dilución posterior que lo arregle;
- **repartir entre todos los nodos existentes después de un tiempo `T`** — Sybil pura (un
  nodo cuesta un teléfono, a propósito), y algo peor: **la cadena no puede observar que un
  nodo existe, sólo lo que hace**. Bitcoin puede medir hashear porque un hash se evidencia
  solo; *"un nodo estuvo prendido"* no;
- **reparto por claim gratis** — decir "Hola" es una firma, y en el bloque 0 no hay tokens
  para cobrarle fee ni stake para exigirle. El pool se lo lleva el que genere más pares de
  claves;
- **el certificado como licencia para cobrar** — activamente mala: vuelve artificialmente
  escasa la cantidad de nodos y crea exactamente el foso de capital que el diseño existe
  para evitar.

> **El teorema, en su forma final.** Una distribución de tokens nuevos indexada a una
> acción rinde **a lo sumo lo que cuesta esa acción, o es farmeable**. Si el pool paga
> menos que el costo, nadie lo reclama; si paga más, se farmea. Bitcoin pudo porque la
> acción era hashear —costo externo, físico, imposible de fingir— y porque duró años en vez
> de un instante.

Y un hallazgo de encuadre que cerró la pregunta entera: se intentó encuadrar el bloque 0
como un fork de una generación anterior. Pero I3 dice que *el estado se conserva íntegro a
través de la transición*, o sea que **una transición preserva la distribución, no la crea**,
y el regreso no termina.

> **La distribución del día 1 está por definición fuera del mecanismo.** Acá no hay que
> buscar un mecanismo: hay que **tomar una decisión**, que es otra clase de trabajo.

Lo que sobrevivió: **claim pagado en cómputo**, con lo no reclamado quemándose. Y la
propiedad que lo justifica: si el claim cuesta y lo no reclamado se quema, entonces **la
oferta inicial no la fija el creador — la fija cuánta capacidad real apareció**. *Declarado
con honestidad: sigue siendo una subasta pagada en cómputo. El que tiene más GPUs se lleva
más. No es reparto igualitario y no hay que venderlo como tal — es abierto, que es otra
cosa.*

### 2.3 · La asimetría retirar/agregar

> **La actividad ya determina cuánto circulante se RETIRA. Lo que no puede determinar es
> cuánto se AGREGA.**

Retirar no necesita destinatario: quemar es un hecho del estado, se verifica solo, y el que
quema pierde. Es una palanca que **sólo perjudica a quien la acciona**, así que puede quedar
abierta a cualquiera. Agregar sí necesita destinatario, y elegirlo es o una decisión humana
o una indexación a una acción — y ahí vuelve el teorema.

### 2.4 · Crear activos: dónde va el cargo, y por qué no en la creación

Se propuso cobrar un cargo por crear un activo, importando el modelo de *rent* de otra
cadena. Se rechazó, y el argumento que lo cerró vino de un caso fuera de cripto —el derecho
de construcción en Argentina, que se paga al pedir el permiso **además** del impuesto
recurrente:

> **Un cargo a la creación no reduce la creación — reduce la *registración* de la
> creación.**

Transferido: si crear en la capa nativa lleva un cargo propio, no se crea menos, se crea
**afuera**, y ahí se pierde lo que el diseño argumenta durante una sección entera. La
asimetría, que además es de *enforceability* y no sólo de incentivos:

| | cargo a la creación | mecanismo de permanencia |
|---|---|---|
| ¿distorsiona? | sí — grava producción | no |
| ¿se puede evadir? | **sí, creando afuera** | **no — el estado que existe lo ven todos los nodos** |

La forma que cierra es un **depósito prepago que se consume quemándose**, y su frase:
*no pagás por crear — pagás por cuánto tiempo querés que la red te lo guarde.*

**Descartadas en el camino, con su motivo:**

- **la subasta del activo abandonado.** Se traba en dos cosas que no dependen del precio.
  Primera: la basura no la compra nadie —por eso es basura—, así que lo único que se vende
  efectivamente es lo que sí valía, y un activo valioso abandonado es casi siempre de
  alguien que perdió el acceso o murió. **El mecanismo selecciona propiedad valiosa de gente
  sin acceso, no basura.** Segunda: lo que la expiración recupera es **disco**, no supply, y
  contra el sumidero real esto es ruido;
- **la deuda contra la red.** No hay deudor: el dueño es una clave, y contra una cuenta
  vacía no hay nada que embargar. Lo único ejecutable es el objeto, así que la deuda no es
  un mecanismo, es el disparador de un remate — y el remate obliga a tasar, o sea a leer un
  precio de mercado on-chain, que está prohibido y es manipulable en la dirección obvia;
- **avisar al último dueño antes de actuar.** *La cadena no tiene canal de salida.* El dueño
  es una clave, no una persona;
- **la tasa decreciente como regla de potencia** (`r(D) = r0·(D0/D)^α`). Manda el precio por
  año a cero, y no abarata cualquier cosa: abarata **la única operación que compra vida en
  volumen**, que es llenar el estado de todos los nodos y no soltarlo. La forma que conserva
  la intuición sin el defecto es una tarifa en dos partes, donde lo que cae al comprar más
  vida es el piso repartido entre más tiempo, **y nunca baja del costo real de guardar**.

### 2.5 · Una ley de control que parecía cerrar, y no cerraba

Se simuló una ley de control sobre la ocupación del estado —la forma de EIP-1559 aplicada a
disco en vez de gas— y dio muy bien: absorbía un shock de demanda ×3 sin oscilar. **El
resultado era un artefacto del modelo.** La simulación recalculaba la vida de todas las
cohortes en cada época, o sea que al subir el precio **acortaba retroactivamente plazos ya
pagados**. Con plazos respetados, el lazo **no converge con ninguna ganancia**.

La causa no es de sintonía, es económica:

> **Prepago con precio flotante es arbitraje intertemporal: comprar largo cuando está
> barato.** Esos slots quedan tomados por siglos a precio de saldo, y el lazo no los
> recupera porque están pagados y desalojar antes sería confiscación.

El arreglo fue un tope a la vida comprable de una vez, con recarga al precio de entonces —
y con eso el tope **dejó de ser una recomendación económica y pasó a ser condición de
estabilidad del mecanismo**.

> Este episodio quedó citado en el paper como muestra de lo frágil que es la evidencia
> propia: **la primera versión de la regla parecía estable, y la tumbó corregir el modelo
> con que se la había probado.**

---

## 3 · La construcción: seis fases, y lo que leer no había corregido

Hasta acá el mecanismo era prosa que había sobrevivido a ataques imaginados. Se construyó
en seis fases, cada una con su criterio de aprobado escrito antes.

**Construir corrigió cinco cosas que leer no había corregido**, y las cinco están hoy en el
paper.

> **Cuidado con leer esto de más.** Que el mecanismo corra no es evidencia de que sirva:
> sigue siendo evidencia propia, con parámetros propios. Lo que cambió es más chico y es
> real: **la sección del mecanismo dejó de ser prosa.**

### 3.1 · Fases 0 y 1 — el motor, y tres huecos que sólo se ven corriendo

Las cinco invariantes se escribieron como predicados ejecutables, con un caso que **tiene**
que fallar por cada una. La conmutación corre de verdad: el mismo proceso, el mismo objeto
de estado, `arranques == 1` de punta a punta.

Y aparecieron tres huecos que el paper no tenía. Ninguno era un bug del código.

**Hueco 1 — más de una transición en vuelo a la vez.** *Se cayó solo, sin que nadie forzara
el caso.* Entre el lock-in y la activación la cadena sigue corriendo con las reglas viejas
aunque las nuevas ya estén comprometidas, así que una regla de acumulación sigue evaluando
TRUE ahí adentro y vuelve a disparar. Cuatro decisiones, con lo que se descartó en cada una:

- **la regla se rearma en la activación, no en el lock-in.** Si pudiera disparar en el medio
  estaría midiendo un estado que no refleja el cambio que ella misma acaba de comprometer:
  **un lazo de control con tiempo muerto**. Hay un contracaso real —la EDA de Bitcoin Cash,
  2017: regla automática escrita de antemano, reaccionaba más rápido de lo que su propio
  efecto se hacía visible, osciló, y hubo que reemplazarla por fork humano a los tres meses—
  y **entró al paper con este hueco**, en el lugar donde argumenta en vez de sólo ilustrar;
- **la espera es por regla, no global.** *Descartado bloquear todos los disparos mientras
  haya uno en vuelo:* pone una migración criptográfica de urgencia a esperar detrás de una
  de circulación **antes incluso de comprometerse**;
- **las activaciones van en orden de lock-in.** Esto no era obvio y apareció al escribir la
  prueba de lo anterior: con ventanas distintas por clase, una transición comprometida
  *después* vencía *antes*. La razón es de I1: `params_nuevos` es **un punto completo del
  espacio, no un incremento**, así que las generaciones son una secuencia totalmente
  ordenada y no un conjunto de parches conmutables;
- **los parámetros se computan en el lock-in, que verifica antes de comprometer.** Eso abrió
  una pregunta nueva: *¿qué pasa si el sucesor no es un punto del espacio?* Un checkpoint es
  irrevocable, así que comprometerlo dejaría al nodo llegando a la activación sin poder
  conmutar — **cadena parada**. Se verifica antes y hay rechazo on-chain. *Descartado
  recortar el sucesor al borde del espacio: cambia la regla en silencio, que es exactamente
  lo que I2 existe para impedir.*

**Hueco 2 — el lock-in es estado, no un anuncio.** Y acá **el diagnóstico inicial estaba
mal**, que es la parte que vale. Se anotó como un problema de *lectura*: el integrador se
queda sin el aviso si una reorganización se lleva el bloque. Al escribirlo se vio que la
severidad era otra:

> **La raíz de estado se bifurca** entre el nodo que reorganizó y el que no. No es un aviso
> ilegible: es una **bifurcación**, y de la peor clase, porque los dos nodos coinciden en
> absolutamente todo lo demás y ninguno tiene motivo para sospechar.

Un hueco de documentación pasó a ser una regla de consenso. Y no se prueba mirando un nodo:
la prueba corre **dos nodos con la misma historia** —uno reorganiza el bloque del lock-in,
el otro no— y exige que terminen con la misma raíz; un tercero resincroniza desde cero y
tiene que llegar al mismo checkpoint.

**Hueco 3 — I2 estaba mal escrita, y fallaba en las dos direcciones.** Es la primera vez que
se tocó una invariante. El planteo era que el canario criptográfico no cumple I2 porque no
se ve venir. Mirado de cerca, el problema era de la invariante:

- **dejaba afuera lo que tiene que estar adentro.** La rotura de una primitiva no se
  aproxima: ocurre;
- **dejaba pasar lo que existe para excluir.** *"Cuando la dirección X reciba 1 wei"* se
  computa sólo desde el estado, tiene progreso monótono y distancia publicable — y es una
  compuerta con dueño. **La forma de la curva no distingue una cosa de la otra: los dos son
  escalones.**

> **Lo que distingue al canario de la puerta trasera no es cómo se ve venir, es quién puede
> producir el hecho y qué le cuesta.**

Y de ahí salió una condición que el paper no tenía y que es lo más importante de ese día:
si Genesis **genera** la instancia debilitada de la primitiva, **quien la generó retiene la
trampa** y puede reclamar el canario cuando quiera. Sería la misma gobernanza que el diseño
elimina, pero mucho más difícil de ver, y firmada por el propio autor del bloque 0.

> **Un canario que no se puede rederivar de su semilla no es un canario: es de alguien.**

El límite de la segunda forma quedó **probado como límite, no escondido**: hay un test que
corre la misma puerta trasera declarada por capacidad y **la deja pasar**, con su
declaración a la vista.

### 3.2 · Fase 2 — el replay contra el historial real de Ethereum

La única fase que se puede mostrar afuera sin pedirle a nadie que crea nada: correr la regla
determinista contra decisiones que humanos ya tomaron, y comparar. Tres casos, con datos
bajados de endpoints públicos sin clave.

**Caso 1 · la bomba de dificultad.** Los seis forks ocurrieron con el término de la bomba
entre `2^37` y `2^41` — **varió 16×**. No hubo umbral humano consistente. Con un umbral fijo
la regla reproduce las seis decisiones dentro de 37 días, media de 20, y una de ellas exacta.
Pero la serie de dificultad contestó una pregunta abierta **en contra**: medido contra la
capacidad de ajuste, la dispersión real es **41×, no 16×**, y **uno solo de los seis forks
ocurrió con la bomba mordiendo** — los otros cinco fueron preventivos, y hay tendencia
temporal. *Los humanos aprendieron a actuar cada vez más temprano.*

> **El cálculo tiene una validación externa que no se buscó.** Uno de los forks fue de
> emergencia porque los bloques treparon a ~17 s. El modelo, que no sabe nada de esa
> historia y no se calibró contra ella, da **17,2 s**.

El hallazgo: el número que reproduce el historial **sólo se conoce mirando hacia atrás**, y
un umbral escrito al principio habría sido el equivocado en los dos extremos. *La regla
escrita no se vuelve equivocada porque cambie el mundo, sino porque **los que la escribieron
aprenden**.*

**Caso 2 · el `blobSchedule`.** Donde la restricción era demanda, la regla gana por
muchísimo: la ocupación llegó al 80% del target **37 días** después del fork que la
introdujo, se quedó saturada el 64% del tiempo y picó al 129%; Ethereum tardó **383 días**
en responder. *Ésa es la cuenta de la coordinación, medida.* Pero donde la restricción **no**
era demanda, la regla es ciega: dos subas de target ocurrieron con la ocupación al 43% y
31%, respondiendo a una tecnología nueva y no a la demanda. Una regla de demanda no habría
subido nada, y habría tenido razón según su propio criterio y le habría errado a la red.

Y de ahí salió una frontera que el paper no tenía:

> ¿Podía la regla subir el target en su momento? Sólo si ese valor estaba en el espacio
> declarado en Genesis **y era seguro** — y no fue seguro hasta que existió la tecnología
> que lo hizo seguro. **El techo del espacio de descendientes estaba acotado por una
> tecnología que no existía cuando se declaró el espacio.** No es que la regla pueda ser la
> equivocada: es que el **espacio** puede quedar corto, y I1 lo congela en Genesis.

**Caso 3 · el gas limit — el único donde el rival no es un fork.** El gas limit ya se vota
bloque a bloque: acá el mecanismo compite contra una coordinación liviana, descentralizada y
sin fork **que ya funciona**. Es el rival más difícil, y el resultado es que **para este
parámetro no hay trigger admisible**, con las tres formas posibles cerradas y con número:

- **cantidad — vacía por construcción.** El mercado de fees fija el target en la mitad del
  límite y mueve el precio hasta que el uso vuelve ahí. Con el base fee moviéndose **650×**,
  la ocupación media se queda en 50,9% y su correlación con el fee es **−0,02** sobre 1.026
  muestras. No es débil: es cero;
- **precio nominal — caduca.** El fee mediano cayó de 36,4 a 0,056 gwei;
- **precio adimensional — ratchetea.** Acierta donde importa (dispara catorce meses antes
  que los humanos) pero pierde la noción de *caro*: sin referencia absoluta, *caro* es sólo
  *más que recién*.

> El problema no está en la procedencia del dato ni en la forma del trigger: **el único
> observable con información sobre este recurso es un precio, y ningún precio nominal sirve
> de setpoint a largo plazo.**

**El cierre honesto de la fase:** tres de tres aprobados como *diferencia explicada*, y la
fase **no produjo evidencia de que el diseño sea mejor**. Dos de tres dieron hallazgos en
contra y el tercero es un empate con asterisco. Lo que produjo son los tres lugares exactos
donde el mecanismo se rompe contra el mundo real. Después de esto, la sección del paper que
se describía a sí misma abría con *"Nada construido"*, que ya era falso — y se reescribió
**poniendo el replay primero, diciendo que dos de sus tres casos fueron en contra**.

**Y una lección sobre datos que vale para cualquiera:** muestrear un bloque cada N da una
estimación pésima de una tasa (el 29% de las muestras daba cero). La salida no fue bajar más
bloques sino **leer el acumulador que la cadena ya lleva**. *Buscar el acumulador antes de
promediar la muestra.* Con un asterisco que apareció después: **un acumulador on-chain es el
observable correcto hasta que alguien le cambia la fórmula** — y eso no se ve en el dato, se
ve leyendo el EIP.

### 3.3 · Fase 3 — orden y liquidación, y la contradicción adentro de una sección

El criterio decía: *si hacen falta cien nodos, la predicción del paper está mal y hay que
decirlo*. **No hacen falta cien: hace falta uno más, o infinitos.**

La cuenta previa había cerrado esto como fórmula, y la fórmula suponía algo que nadie había
escrito: **que los nodos no se pisan**.

| cómo elige cada nodo | N crítico | qué pasa en régimen |
|---|---|---|
| partición por hash | 10 = la fórmula | sin atraso |
| al azar | **11** | atraso **estable** en ~424, espera media 4,2 bloques |
| **la más vieja primero** | **nunca** | atraso creciente: con 50 nodos se verifica lo mismo que con 1 |

> **Y el hueco estaba adentro de la sección, entre dos de sus propias frases.** Decía
> *drenar lo hacen todos los nodos a la vez* y también *orden de llegada* — y si todos toman
> **de la cabeza** de una cola por orden de llegada, todos toman la misma. **La
> contradicción no se ve leyendo; se ve corriendo.**

La regla nueva no pide coordinación ni saber cuántos nodos son: cada uno recorre la cola en
un orden pseudoaleatorio derivado de su identidad. La alternativa exacta —repartir la cola
entre los `N`— clava el diez pero **exige saber cuántos son**, que es justo lo que un diseño
sin conjunto de validadores no tiene.

Dos cosas más quedaron de esta fase:

- **la corrección del 13 al 11.** La primera medición usó corridas de 80 bloques y dio 13.
  Era un artefacto: a 80 bloques el sistema no había llegado al equilibrio, así que un
  atraso que iba a estabilizarse se leía como uno que crecía. **Toda medición de saturación
  compara dos largos de corrida**, y así quedó escrito en el código. El 13 llegó a estar en
  el paper unos minutos;
- **una mutación se escapó porque el default no estaba probado.** Todas las pruebas pasaban
  la estrategia explícitamente, y el default es la decisión de diseño — es lo que se lleva
  quien no leyó la sección. *Cuando una mutación cambia un default y se escapa, no sobra la
  mutación: falta el criterio.*

### 3.4 · Fase 4 — la máquina, y el techo que prometía de más por 23×

Seis criterios aprobados, uno reprobado. **El reprobado es lo que valió la fase.**

**Un paso no vale un paso.** El ritmo declarado del hardware salía de dividir el costo de
una verificación por el tiempo que tardaba. **Es el ritmo de una mezcla de instrucciones
específica.** Medidas seis mezclas elegidas para ser lentas, la peor —persecución de
punteros por 63 MiB— corre a **11,3 M pasos/s**: el techo prometía 22 ms por transacción y
esa mezcla tardaba **596**.

**Y no se arregla pesando instrucciones**, que es la salida obvia y la que hace el gas. La
mezcla que abre el hueco es una lectura de memoria, y esa instrucción corre a 207 M pasos/s
cuando el dato está en caché y a 11 cuando no: **es el mismo opcode**. Un peso por clase
tendría que cobrarle a toda lectura el precio de la peor, y entonces la primitiva real
—que está llena de accesos que sí pegan— dejaría de entrar.

La salida fue contar **páginas distintas tocadas**, y el número no se eligió: se leyó del
cruce de dos curvas. Tres cosas se midieron porque no eran obvias y **las tres podrían haber
tumbado la salida**: cuánto cuesta dispersar las páginas, cuánto cuesta contarlas (14%, para
cerrar un agujero de 23×), y si el tamaño del texto era una segunda palanca.

> **Ésta es la mejor evidencia de que valía la pena que el techo fuera fórmula.** Un insumo
> se corrigió por 2,5× y **el mecanismo no cambió una línea**: cambió un parámetro. Si el
> techo hubiera sido el número que el paper pedía, la corrección habría sido de diseño.

**Tres agujeros que no eran de rendimiento, y cómo aparecieron.** Ninguno lo habría
encontrado un test de corrección. **Los encontró que un barrido tardara minutos**, lo cual
conviene recordar la próxima vez que un test lento parezca sólo un test lento: una reserva
de 64 MiB antes de validar la cabecera; una cabecera de sección alterada que podía forzar
128 MiB de predecodificado; y que las banderas de segmento de un ELF **no distinguen código
de constantes**, porque el enlazador junta ambos en el mismo segmento.

**El peor error de todo el proyecto, y no falló nada.** Una de las mezclas de medición
cargaba mal su dirección inicial —un inmediato de doce bits con signo que restaba en vez de
sumar—, así que la cadena de punteros arrancaba en la página anterior, leía un cero, y desde
ahí **leía siempre la misma dirección, siempre en caché L1**. Informaba un número plausible.
Se cazó porque **corría exactamente a la velocidad de otra mezcla que tenía que ser
distinta**, al cruzar dos herramientas que debían coincidir y no coincidían. Sobre ese número
ya se apoyaban dos conclusiones escritas.

Lo que quedó puesto, y es la regla 3 del método:

> **Cada mezcla declara cuántas páginas tiene que tocar, y se verifica al terminar. Una
> medición tiene que declarar qué está midiendo.**

**Tres formas de medir mal, todas del mismo tipo.** Toda la cuenta es **un cociente entre dos
ritmos**, así que medir uno de los dos peor que el otro la corrompe — y las tres veces el
sesgo empujaba hacia el lado inseguro: la referencia medida con una sola llamada corta; la
referencia medida al final, después de segundos de carga máxima (~20% más lenta); y una
comparación contra un ritmo de otra ejecución, que reportó una penalidad de 1,20× que era
**íntegramente ruido** (la real: 1,01×).

> Un número que se compara con otro se mide en la misma corrida, con el mismo método, y el
> que hace de referencia se mide **primero y en frío**. Y cuando el sesgo tiene un lado
> seguro y uno inseguro, **hay que saber de antemano cuál es cuál.**

Y tres cosas se descubrieron mirando pruebas y no código: una constante de Genesis duplicada
en dos archivos (*una constante en dos archivos es una bifurcación esperando a que alguien
edite uno solo*); una prueba que no probaba nada por un escape mal puesto; y un contador que
tenía un interruptor de cuando era instrumentación (*un chequeo que se puede apagar es una
bifurcación esperando a que dos nodos elijan distinto*).

**El problema que la fase abrió y dejó abierto:** no se sabe cuál hardware es el peor caso,
y el diseño suponía que sí. Las dos máquinas medidas se rompen por lugares distintos — el
núcleo ARM no paga el salto indirecto impredecible que castiga al x86, y el escritorio no
aguanta la dispersión de páginas que el teléfono absorbe sin costo. **Dos máquinas no
alcanzan.**

### 3.5 · El muro del techo de páginas — el mismo movimiento, por segunda vez

El paper promete que **no hay muros, sólo precios**: una primitiva más cara no queda afuera,
entra pagando capacidad. El techo de pasos cumple, porque se deriva de la capacidad. **El
techo de páginas, escrito como constante, no podía cumplir**: no hay precio que una
primitiva pueda pagar para conseguir más memoria. Sólo puede excluir.

Y no era hipotético. Las tres primitivas de la familia tocan 26, 40 y 65 páginas: con el
techo en 48, la tercera **quedaba afuera para siempre** sin que ninguna cuenta lo señalara.
Se salvó por dos páginas de suerte cuando el techo pasó a 96, y la primitiva siguiente podía
no tenerla.

> **Durante un día el protocolo contuvo exactamente la cosa que su sección central dice que
> no existe.**

El arreglo fue el mismo que había cerrado el primer techo: **congelar la curva en vez del
punto.** El ritmo declarado deja de ser un número y pasa a ser una tabla medida; pedir más
páginas baja el ritmo, y eso se paga en capacidad.

**Y la objeción que había que responder estaba mal, escrita por mí mismo el día anterior**:
que el presupuesto no podía ser parámetro porque el mismo programa daría distinto en dos
generaciones. Confundía dos cosas:

> **¿Cambia lo que el programa computa, o sólo si cabe?** La primera es semántica y va
> congelada; la segunda es presupuesto y puede ser parámetro. El techo de pasos **ya
> funcionaba así desde el primer día** y a nadie le pareció que rompiera I1.

Lo que la curva cobra no se podía anticipar: de 96 a 512 páginas la memoria es casi gratis
—4% de ritmo— y **el paso siguiente divide la capacidad por siete**. Es el acantilado de la
TLB del núcleo de referencia, y el mecanismo lo cobra sin que nadie lo declare.

> **La misma jugada sirvió dos veces sobre el mismo techo.** Las dos veces el síntoma fue
> igual —un número que había que elegir y ninguna elección era buena— y la salida fue igual:
> **el número no se elige, se deriva; lo que se congela es la cuenta.**
>
> Conviene tenerlo como sospecha permanente: **un parámetro que hay que elegir a ojo suele
> ser una cuenta que falta escribir.**

### 3.6 · Fase 5 — un piso que estaba mal por dos órdenes de magnitud

El paper afirmaba que cierto piso salía *"unas dieciséis horas de guardado"*. **Escrita la
cuenta, no da eso:** con la firma adentro del ciclo son ~91 épocas contra las 0,67 que
afirmaba — **137×** —, y como el tope de vida comprable son 25 épocas, el piso quedaba en
varias veces el depósito máximo. O sea: casi todo el costo de una entrada se pagaría al
crearla, **que es exactamente el cargo a la creación que la sección descarta dos párrafos
antes**.

La corrección: la firma ya la paga el fee ordinario, y cobrarla otra vez en el piso es
cobrarla dos veces.

**Y ahí apareció lo interesante.** Sacada la firma, el término dominante pasó a ser un
número que estaba **estimado y no medido** — y ese estimado se había declarado inofensivo
por una razón circular: *"no importa porque la verificación de firma lo domina"*. Era cierto
sólo mientras la firma estuviera adentro del ciclo.

> **El término descartado por chico pasó a ser el único que queda.**

Se midió (4.898 pasos por compresión; el estimado estaba 2× arriba, en la dirección
conservadora) y el número ahora se afirma porque sus dos insumos están medidos.

**Y la fase separó dos problemas que parecían el mismo.** La sospecha de la sección anterior
—*un número a elegir a ojo suele ser una cuenta que falta escribir*— se corrió contra la
tasa de permanencia, y no cede:

> **El techo se cerró dos veces porque sus dos lados eran físicos**: pasos de uno, segundos
> del otro, y la cadena puede contar los dos sin preguntarle nada a nadie. **La tasa tiene
> un lado físico —bytes × épocas— y uno monetario, y ninguna cuenta cruza eso sin leer un
> precio.**

Y no es retórica: **se ve en los tipos.** Todo lo que el módulo calcula está en byte-épocas
o en épocas, y no aparece una unidad monetaria en ningún lado. El día que aparezca, aparece
con un oráculo al lado.

> **La regla que queda:** todo lo que se pueda expresar en fracciones del presupuesto del
> nodo se deriva; todo lo que exija una unidad monetaria queda del otro lado del muro.

De ahí una decisión de forma que achicó el problema abierto: **el piso se denomina en épocas
de guardado, no en unidades del token.** En unidades sería un *segundo* precio que fijar al
lado de la tasa, con el mismo problema y ninguna de sus defensas. Con eso, lo que queda
abierto es **un solo número y no dos**.

> **Corregido el 28/8/2026, después de medir.** *«Ninguna cuenta cruza eso sin leer un
> precio»* sigue siendo cierto y sigue sin alcanzar. El operador de exceso de 4844/7999 no
> converge solo —es un integrador, `c = 1` con demanda exógena— y lo que lo hace converger es
> la elasticidad de la demanda. **La frontera pasó de «hay que conocer el precio» a «la demanda
> tiene que ser elástica por encima de 2,05 en 25 épocas»**: no se cruzó, se volvió medible.
> Ver [`mediciones/convergencia-tasa/`](../mediciones/convergencia-tasa/RESULTADOS.md) y la
> [sección 6](#6--la-primera-revisión-externa).

### 3.7 · Fase 6 — el devnet, y lo que ninguna invariante miraba

La fase se acotó a propósito: de las cuatro preguntas que tenía asignadas, dos ya las habían
contestado fases anteriores. *Correr de nuevo lo ya medido no agrega evidencia, y sí agrega
la tentación de mirar el número hasta que dé.*

**El hallazgo, que era invisible para las cinco invariantes.** El depósito de permanencia se
llevaba en byte-**épocas**; la época se cuenta en bloques; y el tiempo de bloque es un
parámetro interno que una transición puede mover:

```
bloque de  6.000 ms  ->  240 horas de guardado real
bloque de 12.000 ms  ->  480 horas, con el MISMO depósito
```

> **Lo incómodo: I3 se cumplía.** El estado cruzó íntegro —los bytes son idénticos y el
> conmutador lo verifica por huella y por identidad de objeto—. Lo que cambió no fue el
> estado sino **lo que ese estado vale**, y eso no lo mira ninguna de las cinco invariantes.

La corrección es el mismo movimiento por tercera vez: denominar el depósito en **tiempo
declarado**, no en épocas. Y el punto fino, para no confundirlo con una violación de I2:
**el tiempo de bloque no es una lectura de reloj, es un parámetro que el ruleset declara.**
La cadena no mide el tiempo — usa el número que ella misma fijó.

> **La regla, ya con tres casos:** cuando un mecanismo necesita una magnitud física, se usa
> **la declarada, no la derivada ni la medida.**

Y el arnés de mutaciones encontró el tercer criterio vacío en dos días: se podía recorrer el
conjunto activo **por orden de hash** al desalojar y ningún test se caía. Eso es una
bifurcación, y se esconde bien, porque un recorrido de diccionario por hash **parece
determinístico dentro de un proceso y no lo es entre dos**.

---

## 4 · La auditoría de unidades: lo que pasa por debajo de las cinco

Dos fases seguidas encontraron un defecto que **no violaba ninguna de las cinco
invariantes** — el techo de páginas constante, y el depósito en épocas. Los dos son la misma
forma:

> **I3 protege los bytes; nada protege lo que los bytes significan.**

De ahí salió una pregunta que se puede hacer mecánicamente, y que hay que rehacer cada vez
que el espacio de parámetros crezca:

> **Para cada cantidad que el protocolo guarda o declara: ¿su significado depende de un
> parámetro que una transición puede mover?**

El barrido completo quedó escrito, con una prueba que **se cae si alguien agrega un parámetro
al espacio sin rehacer el barrido**.

**Lo que encontró, y sigue abierto:** la ventana de aviso `Δ` está en bloques, y el tiempo de
bloque es parámetro interno, así que el aviso real varía **60×** a lo largo del espacio. Y
hay un segundo problema, más grande que el de unidad: a los valores actuales, `Δ` da 6,4
minutos y 48 segundos, y el paper describe esa perilla como un compromiso real entre la
urgencia de la cadena y el tiempo de reacción de un integrador — **a estos números los dos
valores están del mismo lado, el de ningún aviso.**

> **Los valores nunca aparecieron en el paper.** Vivían en el código desde la primera fase,
> donde alcanzaban para que las pruebas corrieran, y el paper habla de *"Δ largo"* y *"Δ
> corto"* sin dar números. **Nadie los contrastó nunca contra lo que la sección dice que
> compran** — que es exactamente el hueco que esta auditoría existe para cerrar.

Lo que de verdad le da al integrador un modo de falla tolerable es **I5**, no `Δ`: quien no
llegó a soportar la generación nueva sigue operando en la anterior. Eso hace que el número
chico no sea catastrófico, y también muestra que **`Δ` hace bastante menos de lo que el paper
le atribuye**.

Las pruebas de esta parte **afirman el defecto**: se caen el día que se decida, y esa caída
es la señal de reescribirlas, no un fallo.

---

## 5 · Las lecciones de método, que valen fuera de este proyecto

- **Construir corrige lo que leer no corrige.** Cinco cosas, y ninguna era un bug del
  código: eran cosas que el diseño no decía y que sólo se ven cuando el mecanismo se
  ejecuta. Una de ellas era una contradicción entre dos frases de la misma sección.
- **Un número que hay que elegir a ojo suele ser una cuenta que falta escribir** — y cuando
  no lo es, hay una razón enunciable de por qué no (un lado físico y uno monetario no cruzan
  sin leer un precio).
- **Congelar la curva, no el punto.** Un mecanismo que congela una fórmula sobrevive a que
  su insumo se corrija por 2,5×; uno que congela un número, no.
- **Cuando un mecanismo necesita una magnitud física, usar la declarada** — no la medida ni
  la derivada. Medirla es un oráculo; derivarla se reinterpreta cuando cambia un parámetro.
- **Una medición tiene que declarar qué está midiendo**, y verificarlo al terminar. Una
  medición que degeneró en otra no falla: sigue informando un número plausible.
- **Un número que se compara con otro se mide en la misma corrida**, y cuando el sesgo tiene
  un lado seguro y uno inseguro, hay que saber de antemano cuál es cuál.
- **Toda prueba que pretenda prohibir algo tiene que verse fallar una vez.** Tres criterios
  vacíos aparecieron en dos días, y los tres tenían nombre.
- **Cuando una mutación cambia un default y se escapa, no sobra la mutación: falta el
  criterio.** El default es parte del mecanismo, no de la comodidad.
- **Un test lento puede no ser sólo un test lento.** Tres vulnerabilidades de amplificación
  se encontraron porque un barrido tardaba minutos.
- **Buscar el acumulador antes de promediar la muestra** — y recordar que un acumulador
  on-chain es el observable correcto hasta que alguien le cambia la fórmula.
- **Antes de agregar capital como palanca, buscar el castigo que el mecanismo ya produce.**
  Cuatro veces el reflejo fue un bono o un lockup, y las cuatro el diseño ya tenía el
  castigo adentro.

---

## 6 · La primera revisión externa

**Es la primera entrada de esta bitácora que no escribió el autor del diseño.**

El repositorio se hizo público el 27/8/2026. Doce horas después, una pregunta en
[`ethereum/EIPs#12107`](https://github.com/ethereum/EIPs/pull/12107) —por qué `CPSB` se
recalibra con un EIP nuevo en vez de derivarse del gas limit activo— recibió respuesta de
**Maria Silva**, autora de EIP-8037. Trajo tres cosas, y ninguna estaba anotada acá.

### 6.1 · La propuesta ya se había pensado, y se descartó

CPSB variable con el gas limit **fue el diseño original de EIP-8037**. Se descartó por dos
razones — y las dos son fronteras que este diseño no tenía escritas.

### 6.2 · «Un valor que no está mandado por el protocolo» — I2, confirmada desde afuera

La primera razón: el gas limit **es estado de la cadena, pero no lo deriva el protocolo** —lo
eligen los validadores, bloque a bloque—, y colgar un costo de consenso de él rompe el testing
en EELS, que espera costos de gas fijos.

**Eso es I2, y llegó de afuera.** La reformulación del 19/8 dice que *computable desde el estado
no alcanza*: lo que importa es **quién puede producir el hecho y qué le cuesta**. El
contraejemplo que la motivó fue *"cuando la dirección X reciba 1 wei"*. El gas limit es el mismo
objeto —estado computable, con dueño— y el proceso de EIPs lo rechazó por esa razón, sin haber
visto esta invariante.

**Es la primera confirmación externa de una pieza del marco.** Vale menos que una refutación,
pero vale más que cualquiera de las propias: no la corrió quien escribió el diseño.

### 6.3 · La segunda razón es de integración, y toca `Δ`

*"Contratos que funcionaban con un `CPSB` dado dejarían de funcionar con uno más alto."*

Es exactamente lo que §10.1 dice que compra `Δ` — y lo que la [auditoría de
unidades](#4--la-auditoría-de-unidades-lo-que-pasa-por-debajo-de-las-cinco) encontró que `Δ`
**no** compra a los valores actuales, con sus 6,4 minutos.

Lo que importa es qué hizo Ethereum con el mismo problema enfrente: **no eligió una ventana de
aviso más larga, eligió no mover el costo.** Es una salida que este diseño nunca consideró,
porque da por sentado que el parámetro se mueve y que lo que se negocia es el aviso. Queda
anotada contra el [problema abierto 3](problemas-abiertos.md#3--la-ventana-de-aviso-δ-una-unidad-y-una-magnitud).

### 6.4 · El pointer, que es lo más valioso de los tres

El destino final, según la respuesta, es **EIP-7999**: que **el base fee varíe para sostener la
tasa objetivo de crecimiento del estado**, en vez de variar el costo.

Eso cae encima del [problema abierto 2](problemas-abiertos.md#2--la-regla-de-la-tasa-de-permanencia-y-el-nivel-del-que-parte),
donde está desarrollado. En una línea: **allá la ley de control está entera y el nivel inicial
no**, igual que acá — y EIP-1559 sugería que el nivel inicial podría no hacer falta, porque el
precio es el punto fijo del lazo y no un insumo.

**Se midió el 28/8/2026, y esa lectura era falsa como estaba escrita**
([`mediciones/convergencia-tasa/`](../mediciones/convergencia-tasa/RESULTADOS.md)). El operador
de exceso es un **acumulador**: con demanda exógena dos niveles iniciales mantienen su diferencia
exactamente, `c = 1`. La convergencia no está en la regla, está en la demanda respondiendo al
precio. El problema abierto 2 **no se cayó: se reubicó** a una pregunta empírica sobre
elasticidad, con un número — 2,05 sobre 25 épocas.

### 6.5 · Lo que costó, y de qué forma era el post que lo produjo

Vale anotarlo porque contradice el reflejo:

- el post **no hablaba del diseño**. Era una pregunta angosta sobre el EIP de otra persona;
- lo primero que decía del trabajo propio era **cuáles dos de las tres mediciones habían
  fallado**;
- el link al repositorio iba **entre paréntesis, al final**, subordinado;
- **nadie leyó el paper.** La respuesta vino por la pregunta.

**Lo que consiguió revisión externa no fue publicar el diseño: fue serle útil a otro en su
propio problema.** Doce horas, contra dieciocho meses de no tener ninguna.

---

## Índice: lo que ya murió

Antes de proponer algo de esta lista, mirá dónde murió. **No es que estén prohibidas: es
que ya tienen una refutación escrita, y una propuesta que no la contesta no avanza.**

| propuesta | dónde está por qué murió |
|---|---|
| calibrar un parámetro para que el atacante pague más que el honesto | [2.1](#21--el-muro-cuatro-arreglos-una-sola-causa) — el muro de la identidad |
| bono superlineal contra el flooding de la cola | [2.1](#21--el-muro-cuatro-arreglos-una-sola-causa) |
| lockup del subsidio contra el farmeo | [2.1](#21--el-muro-cuatro-arreglos-una-sola-causa) |
| repartir el beneficio por rol | [2.1](#21--el-muro-cuatro-arreglos-una-sola-causa) |
| emitir cuando hay demanda real | [2.1](#21--el-muro-cuatro-arreglos-una-sola-causa) y [2.3](#23--la-asimetría-retiraragregar) |
| repartir el pool inicial al primero que trabaje | [2.2](#22--la-distribución-del-día-1-y-el-teorema-que-la-cerró) |
| repartir entre los nodos que existan tras un tiempo `T` | [2.2](#22--la-distribución-del-día-1-y-el-teorema-que-la-cerró) — la cadena no puede observar que un nodo existe |
| claim gratis del pool inicial | [2.2](#22--la-distribución-del-día-1-y-el-teorema-que-la-cerró) |
| el certificado del bloque 0 como licencia para cobrar | [2.2](#22--la-distribución-del-día-1-y-el-teorema-que-la-cerró) |
| cobrar un cargo por crear un activo | [2.4](#24--crear-activos-dónde-va-el-cargo-y-por-qué-no-en-la-creación) |
| subastar el activo abandonado | [2.4](#24--crear-activos-dónde-va-el-cargo-y-por-qué-no-en-la-creación) |
| dejar que el depósito quede en descubierto (deuda) | [2.4](#24--crear-activos-dónde-va-el-cargo-y-por-qué-no-en-la-creación) |
| avisarle al dueño antes de desalojar | [2.4](#24--crear-activos-dónde-va-el-cargo-y-por-qué-no-en-la-creación) — la cadena no tiene canal de salida |
| descuento por depositar más (regla de potencia) | [2.4](#24--crear-activos-dónde-va-el-cargo-y-por-qué-no-en-la-creación) |
| pagarle a un nodo por archivar | [2.2](#22--la-distribución-del-día-1-y-el-teorema-que-la-cerró) — misma familia: estado pasivo, sin evidencia on-chain |
| bloquear todos los disparos mientras haya una transición en vuelo | [3.1](#31--fases-0-y-1--el-motor-y-tres-huecos-que-sólo-se-ven-corriendo) |
| activar transiciones fuera del orden de lock-in | [3.1](#31--fases-0-y-1--el-motor-y-tres-huecos-que-sólo-se-ven-corriendo) |
| recortar el sucesor al borde del espacio si se pasa | [3.1](#31--fases-0-y-1--el-motor-y-tres-huecos-que-sólo-se-ven-corriendo) |
| derivar el evento de lock-in sin guardarlo en el estado | [3.1](#31--fases-0-y-1--el-motor-y-tres-huecos-que-sólo-se-ven-corriendo) |
| que Genesis genere la instancia debilitada del canario | [3.1](#31--fases-0-y-1--el-motor-y-tres-huecos-que-sólo-se-ven-corriendo) — quien la generó retiene la trampa |
| pesar instrucciones por clase, estilo gas | [3.4](#34--fase-4--la-máquina-y-el-techo-que-prometía-de-más-por-23) |
| el presupuesto de páginas como constante | [3.5](#35--el-muro-del-techo-de-páginas--el-mismo-movimiento-por-segunda-vez) |
| indexar la tasa a la ocupación sin tope a la vida comprable | [2.5](#25--una-ley-de-control-que-parecía-cerrar-y-no-cerraba) |
| derivar `CPSB` del gas limit activo (propuesto afuera, no acá) | [6.1](#61--la-propuesta-ya-se-había-pensado-y-se-descartó) — el gas limit no está mandado por el protocolo |
