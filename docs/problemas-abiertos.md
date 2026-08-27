# Lo que falta, y dónde pegar primero

*[English version](open-problems.en.md)*

Este documento es la agenda de debate del proyecto. Tiene tres partes:

- **[Parte 1 · Dónde pegar primero](#parte-1--dónde-pegar-primero)** — ocho ataques, en orden
  de cuánto costaría descubrirlos tarde. Si tenés tiempo para una cosa, es esto.
- **[Parte 2 · Los problemas abiertos declarados](#parte-2--los-problemas-abiertos-declarados)**
  — lo que el diseño sabe que no tiene resuelto, con la razón de por qué sigue abierto.
- **[Parte 3 · Lo que necesita medición y no análisis](#parte-3--lo-que-necesita-medición-y-no-análisis)**
  — donde el cuello de botella no es pensar más.

**Cómo leer esta lista.** Nada de acá está escondido en una nota al pie: todo está declarado
en el [paper](paper.md), y varios de estos puntos **existen porque un intento de arreglarlos
falló y quedó escrito**. La [bitácora](bitacora.md) tiene el índice de lo que ya murió — vale
la pena mirarlo antes de proponer, no porque una propuesta repetida esté prohibida, sino
porque una que no contesta la refutación existente no avanza.

---

## Parte 1 · Dónde pegar primero

### A · ¿El subconjunto de trabajo verificable es una economía o un nicho?

**Es la hipótesis más cara del diseño, y la única que nunca se salió a falsar.**

Todo el ingreso de la red depende de que existan pedidos con predicado determinista barato:
*"entregá algo que compile y pase estos tests"*. Hoy la mayor parte del valor económico de un
modelo está en salidas **sin** predicado barato.

**Pregunta concreta, y es de mercado y no de diseño:** ¿pagarías por esto, contra un proveedor
centralizado que responde en segundos, con finalidad de horas?

*Qué lo cerraría:* un comprador real diciendo que sí, o un análisis de por qué el conjunto de
tareas con predicado barato es más grande (o más chico) de lo que el diseño supone.

### B · ¿El claim del bloque 0 recluta operadores, o reclutantes?

El reclamante óptimo es **una flota de GPU alquilada durante la ventana, que se devuelve
cuando cierra**. El diseño demuestra que el hardware **existió**, no que se **queda** — y
como la emisión está desacoplada del trabajo, tener tokens no da ninguna razón para seguir
trabajando. El claim además es **irrepetible**.

### C · ¿La tarea de referencia es replayable?

Si la instancia es fija y publicada en Genesis, el primero que la resuelve publica la
solución y **el costo del claim colapsa a cero para todos los demás**. Se arreglaría
derivando la instancia de la clave del reclamante — *no está escrito*.

### D · En `t = 0` todas las defensas están denominadas en una unidad sin precio

El fee es ad valorem; el piso y el depósito son nominales; y el nivel inicial de la tasa es
el [problema abierto 2](#2--la-regla-de-la-tasa-de-permanencia-y-el-nivel-del-que-parte). **En
la ventana en que la cadena es más frágil, el antispam vale aproximadamente nada.**

### E · El escenario peligroso es el éxito, no el fracaso

Si la moneda se aprecia —que es lo que pasa si se adopta— el guardado se vuelve prohibitivo
en términos reales y **el estado se vacía**. Lo que lo compensa es la regla que no está
escrita, **y la primera versión de esa regla ya se cayó** (ver [bitácora
2.5](bitacora.md#25--una-ley-de-control-que-parecía-cerrar-y-no-cerraba)).

### F · El canario instala criptografía de consenso escrita por un postor anónimo

Con *"nadie rompió una instancia debilitada en una ventana fija"* como único filtro.
**¿Alcanza?**

*Lo que ya está resuelto de esto, para no repetirlo:* la instancia debilitada **se deriva** de
una semilla pública, no se genera — si alguien la generara, retendría la trampa y el canario
sería suyo. Eso está cerrado ([bitácora
3.1](bitacora.md#31--fases-0-y-1--el-motor-y-tres-huecos-que-sólo-se-ven-corriendo)). Lo que
sigue abierto es si el filtro de la ventana alcanza como criterio de admisión.

### G · El intérprete no se puede parchear nunca

Es I1, y es la invariante que hace posible todo lo demás. **¿Es realista verificar
formalmente una VM determinista completa, y qué pasa el día que aparezca un bug?**

*Contexto que puede servir para atacar esto:* construir la máquina encontró tres
vulnerabilidades de amplificación que ningún test de corrección habría encontrado, y tres
criterios que existían y no probaban nada. Ese es el tipo de cosa que I1 vuelve permanente.

### H · El diseño no puede corregir un error económico del día 1

Por construcción. Y un lanzamiento es exactamente el momento en que se descubre qué no se
anticipó. **Toda otra cadena arregla eso por gobernanza. ¿Es sostenible?**

---

## Parte 2 · Los problemas abiertos declarados

### 1 · Cuál hardware es el peor caso

Todo el diseño supone que **la capa liviana es la que ata** — de ahí sale la entrada barata
de nodos, que es viga en dos lugares distintos: la coalición de bloqueo no dura si entrar es
barato, y la cola de impugnaciones no satura porque alcanzan once nodos.

**Medido, el supuesto es falso** para los patrones adversariales de memoria:

| | peor programa admisible |
|---|---|
| teléfono de gama media | **80,8 M pasos/s** |
| escritorio x86-64 | **78,9 M pasos/s** |

Y con más memoria la distancia se abre al doble **a favor del teléfono**. Las dos máquinas se
rompen por lugares distintos: el núcleo ARM no paga el salto indirecto impredecible que
castiga al intérprete en x86 (327 contra 145 M pasos/s en la mezcla revuelta), y el escritorio
no aguanta la dispersión de páginas que el teléfono absorbe sin costo.

No invalida el techo —se calibra contra el hardware declarado como referencia— pero sí la
frase de que *el hardware más barato es el peor caso*, que aparecía como obvia.

> **Dos máquinas no alcanzan para fijar un piso, y cerrarlo necesita más máquinas, no más
> análisis.** Ver [parte 3](#parte-3--lo-que-necesita-medición-y-no-análisis).

### 2 · La regla de la tasa de permanencia, y el nivel del que parte

Que la tasa no puede quedar congelada ya está dicho: **un precio nominal fijo no puede
racionar un recurso real bajo una moneda que flota.** Con apreciación del 50% anual el
guardado sale 57× más caro en términos reales a diez años y el estado se vacía; con
depreciación se vuelve gratis y se llena.

La única variable a la que puede indexarse sin violar I2 es la **ocupación del estado** — un
hecho del estado, no una lectura de mercado. Lo que falta es qué regla se escribe. **Y falta
algo más que la forma: falta el nivel del que parte**, que es un precio que la cadena no puede
leer sin violar I2.

**Dos cosas que ya se sabe de este problema, y que hay que contestar para avanzar:**

- **la primera versión de la ley de control ya se cayó**, y no por sintonía sino por una razón
  económica: prepago con precio flotante es arbitraje intertemporal. Ver [bitácora
  2.5](bitacora.md#25--una-ley-de-control-que-parecía-cerrar-y-no-cerraba);
- **indexar a la ocupación deja de servir cuando un precio ya raciona el recurso.** Medido en
  un segundo parámetro independiente, con datos de terceros: con el base fee de Ethereum
  moviéndose 650× en cuatro años, la ocupación media se queda en 50,9% y su correlación con el
  fee es **−0,02** sobre 1.026 muestras. No es débil: es cero.

**Y hay una razón enunciable de por qué esto no cede a la jugada que cerró el techo dos
veces:**

> El techo tenía sus dos lados en el mundo físico —pasos y segundos— y la cadena puede contar
> los dos. **La tasa tiene un lado físico, bytes × épocas, y uno monetario, y ninguna cuenta
> cruza esos dos lados sin leer un precio.** No es una cuenta que falta escribir: es una
> frontera.

De ahí salió denominar el piso en épocas de guardado en vez de en unidades del token — con eso
**lo que queda abierto es un solo número y no dos**.

### 3 · La ventana de aviso `Δ`: una unidad y una magnitud

Lo encontró la auditoría de unidades, y **son dos problemas distintos que conviene no
fundir**.

**El problema de unidad.** `Δ` está en bloques y el tiempo de bloque es un parámetro interno,
así que el aviso real varía **60×** a lo largo del espacio. Y una transición puede moverlo
**mientras otra está en vuelo**, con lo cual el aviso ya anunciado se acorta después de
anunciado. Tres salidas, ninguna gratis:

1. **recalcular la altura de activación** cuando cambia el tiempo de bloque — preserva el
   aviso, pero la altura anunciada deja de ser fija;
2. **prohibir que un cambio de tiempo de bloque active con una transición en vuelo** —
   angosto, chequeable, y no toca la sección del mecanismo;
3. **declararlo** como una frontera más.

**El problema de magnitud, que es el más grande.** A los valores actuales `Δ` da **6,4 minutos
y 48 segundos**, y el paper describe esa perilla como un compromiso real entre la urgencia de
la cadena y el tiempo de reacción de un integrador — **a estos números los dos valores están
del mismo lado, el de ningún aviso**. La perilla está descripta como un compromiso y no está
sobre esa curva.

Lo que de verdad le da al integrador un modo de falla tolerable es **I5**, no `Δ`. Eso hace
que el número chico no sea catastrófico, y también muestra que **`Δ` hace bastante menos de lo
que el paper le atribuye**.

### 4 · El canal de quema: una frontera declarada, con su condición de reapertura

Si la tasa se indexa a la ocupación del estado, **un atacante que llena estado acelera la
quema de terceros**, y la quema entra en la cuenta que lee el trigger. O sea que **se puede
pagar por acelerar una transición**. La palanca es del orden de `1/ε`, con `ε` la elasticidad
de la demanda honesta de guardado:

| fracción de estado del atacante | ε=0,25 | ε=0,5 | ε=1,0 | ε=2,0 |
|---|---|---|---|---|
| 5% | **3,52** | 1,85 | 0,95 | 0,48 |
| 50% | 0,94 | 0,75 | 0,50 | 0,29 |

Con demanda elástica el atacante nunca quema más ajeno que propio y el canal es inofensivo.
Con demanda **inelástica** el canal es real. Y `ε` no se puede conocer antes de tener red.

**Se decidió declararlo como frontera en vez de cerrarlo por definición**, y el argumento
importa porque es reutilizable: la salida alternativa —excluir esa quema de la cuenta—
**cobra un precio cierto por un riesgo incierto**, y *lo caro no es la excepción, es la
primera excepción*: con una escrita, cada canal de quema futuro tiene que discutir si cuenta.

**Lo que la vuelve honesta es que la frontera declara qué medición la revoca:** si con red
corriendo la demanda de guardado resulta marcadamente inelástica, la decisión correcta pasa a
ser la otra.

### 5 · Los límites que el marco no puede cubrir

**Ninguno de éstos es un problema a resolver: son límites declarados**, y están acá para que
un ataque no gaste tiempo redescubriéndolos.

- **escribir la regla por adelantado no elimina el fork: lo mueve al caso en que la regla
  escrita es la equivocada.** Con dos casos reales medidos, y un *cómo* que salió del segundo:
  la regla no se vuelve equivocada porque cambie el mundo, sino **porque los que la
  escribieron aprenden**;
- **el espacio declarado puede quedar corto.** El techo de lo que la cadena puede llegar a
  hacer puede estar acotado por una tecnología que no existía cuando se declaró el espacio — y
  ampliarlo es un fork. Medido sobre un caso real;
- **el conjunto de futuros deja de ser auditable.** La cara opuesta del anterior;
- **el protocolo puede garantizar que un activo desalojado *se puede* revivir. No puede
  garantizar que alguien vaya a tener con qué;**
- **las cinco invariantes cubren lo que el estado *es*, no lo que *significa*.** Dos defectos
  reales pasaron por debajo de las cinco. No se puede cubrir sin que el protocolo tenga una
  noción de cuánto vale una cantidad, que es justo lo que el diseño declara imposible;
- **el protocolo no tiene noción de identidad**, así que toda palanca que mueva la mueve para
  todos. Ver las dos reglas para revisores en la [bitácora
  2.1](bitacora.md#21--el-muro-cuatro-arreglos-una-sola-causa).

---

## Parte 3 · Lo que necesita medición y no análisis

**Ésta es la parte donde ayuda más un extraño que un argumento.**

### Correr el benchmark en más máquinas

El [problema abierto 1](#1--cuál-hardware-es-el-peor-caso) no se cierra pensando: se cierra
con más hardware. **El número que salga de ahí es una constante de Genesis.**

Lo que hace falta es correr las mezclas adversariales en todo lo que se consiga —otro
teléfono, un ARM de servidor, una notebook, un núcleo grande de x86— y ver dónde cae la peor
mezcla. El paquete del benchmark es autocontenido y está en
[`mediciones/test2-interprete/`](../mediciones/test2-interprete/RESULTADOS.md), con el
procedimiento escrito.

Un dato útil sobre la dispersión: **el escritorio dio entre 44 y 79 M pasos/s según cuándo se
corriera, contra 1,6% de variación en el teléfono.** Cualquier medición nueva tiene que
informar la peor de varias corridas, no la media.

### Revisión adversarial externa

Todo lo que el diseño sobrevivió, lo corrió quien lo escribió. Eso es exactamente el tipo de
evidencia que no vale, y el paper lo dice con todas las letras.

### El test que nunca se corrió

El del comprador: [ataque A](#a--el-subconjunto-de-trabajo-verificable-es-una-economía-o-un-nicho).
No es una simulación — es salir a preguntar.

---

## Cómo reportar

Ver **[CONTRIBUTING.md](../CONTRIBUTING.md)**. En una frase: un ataque útil dice **contra qué
invariante va** y **qué observación lo confirmaría o lo mataría**.
