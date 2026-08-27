# Roadmap — Genesis

**Para quien se suma al proyecto.** Esto dice dónde está parado el proyecto, qué significan las
palabras que vas a ver en los nombres de archivo, y en qué orden se construye. Leelo antes de
abrir código.

> **Convención de citas.** `§X.Y` se refiere siempre al **[paper](paper.md)**, que es la fuente
> de verdad. El [resumen](resumen.md) tiene **numeración propia** —tiene 10 secciones y el
> paper 12—, así que los números no coinciden entre los dos documentos. Si un `§` no cierra,
> estás mirando el archivo equivocado.

---

## 0. Dónde está parado el proyecto

**Las seis fases están corridas.** La implementación de referencia corre 246 criterios
ejecutables con 31 mutaciones cazadas, más una máquina determinista en Rust con 18 criterios
propios, corrida también en aarch64. *Esa implementación no está en este repositorio* — acá está
el diseño, las mediciones, y el registro de qué corrigió construirlo.

**Lo que falta al final no es diseño: es medición externa.** Ver
[problemas abiertos](problemas-abiertos.md).

> **Este documento se escribió antes de construir**, y las fases de abajo conservan su redacción
> original en futuro a propósito: son la especificación contra la que se corrió cada una, con su
> criterio de aprobado escrito de antemano. Lo que cada fase encontró está anotado en su lugar, y
> desarrollado en [la bitácora](bitacora.md).

Y el proyecto está partido en dos mitades con **evidencia de distinta clase**, que es lo primero
que hay que entender para no construir lo que no toca:

| mitad | qué es | evidencia |
|---|---|---|
| **sucesión de parámetros** (§3 + I2 sobre espacio finito) | la cadena cambia sus propios parámetros internos sin voto | **cliente encontrado afuera**: Ethereum recalibra `blobSchedule` a mano (EIP-7892), el gas limit por cronograma (EIP-8261), la bomba de dificultad se retrasó por fork seis veces |
| **la moneda + el intérprete + §6.6** | economía propia, VM determinista, evolución criptográfica encadenable | **sólo evidencia propia**: sobrevivió a todos los ataques que se le corrieron, y todos los corrió quien escribió el diseño |

> **Se construye primero la mitad de arriba, y no es una preferencia: es dónde está la evidencia.**
> La mitad de abajo paga las fronteras más caras de §10.1 y todavía no tiene un caso encontrado
> afuera.

**Lo que este roadmap no cubre, a propósito:** el lanzamiento del bloque 0. Depende de dos cosas
que no son código —encontrar comprador para el trabajo verificable de §6.2, y cerrar los dos
problemas abiertos de §10.3— y el claim es **irrepetible**, así que lanzar antes de tiempo gasta el
único evento de distribución que existe.

---

## 1. Glosario: las palabras que hay que tener antes de abrir un archivo

Están en el orden en que se necesitan, no alfabético.

**Generación.** Una versión del ruleset. La cadena no se bifurca en generaciones: **es una sola
cadena que cambia de reglas**. La generación 3 es la misma cadena que la 1, con otros parámetros.

**Ruleset.** El conjunto de parámetros vigente en una generación: emisión, fees, tamaño de
bloque, tiempos, formatos. Es *datos*, no código — ésa es toda la diferencia con un hard fork.

**Conmutación.** El acto de cambiar de ruleset. **El mismo proceso, con el mismo estado en
memoria, ejecutando reglas distintas a partir de un bloque.** No hay reinicio, no hay migración,
no hay snapshot, no hay bridge. Si tu implementación necesita reiniciar el nodo, no es
conmutación: es un fork con otro nombre.

**`TRANSITION_RULE`.** La condición de disparo. Se computa **sólo desde el estado de la cadena**
(I2). No lee precios, no lee oráculos, no lee votos, no lee el reloj de nadie.

**Los tres tiempos.** No confundirlos nunca, y son tres y no dos:

1. **Disparo** — `TRANSITION_RULE` da TRUE en el bloque `N`. **No compromete nada**: es advisorio
   y una reorganización lo deshace.
2. **Lock-in** — cuando `N` es final, el disparo se vuelve **irrevocable** y se emite on-chain el
   ruleset nuevo completo con la altura de activación. Esperar la finalidad no es ceremonia:
   `H0_B` compromete el estado que disparó, y comprometerlo antes dejaría el checkpoint apuntando
   a un estado que una reorganización puede sacar de la cadena.
3. **Activación** — `Δ` bloques **después del lock-in**, no después del disparo. Así el aviso al
   integrador es exactamente `Δ` y no depende de cuánto tardó la finalidad.

**`Δ` (delta).** La ventana de aviso, fijada en Genesis **por clase de transición**. Una
transición de circulación tolera `Δ` largo; una migración criptográfica de urgencia necesita
`Δ` corto.

**Linaje / `H0_B`.** `H0_B = H( H0_A ‖ state_trigger ‖ params_nuevos )`. No es el génesis de una
cadena nueva: es un **marcador de checkpoint generacional** dentro de la misma cadena. Hace el
linaje verificable con un hash desde cualquier generación hacia atrás. Genesis A no conoce el
hash de B —no puede— pero conoce cómo se calculará.

**Las cinco invariantes (I1–I5).** El marco duro. Cada una elimina una forma de reintroducir al
humano en el lazo. **En este repo no son documentación: son aserciones ejecutables que toda fase
tiene que seguir pasando** (ver Fase 0).

- **I1** — el intérprete vive en Genesis y **no cambia nunca**. Una transición selecciona un
  punto de un espacio que el nodo ya sabe ejecutar; no introduce código de nodo.
- **I2** — el trigger se computa sólo desde el estado, **y nadie elige el momento**. Computable no
  alcanza: *"la dirección X recibió 1 wei"* se computa desde el estado y es una compuerta con
  dueño. Se cumple de dos formas y toda regla declara en cuál está: por **aproximación
  observable** —publica *cuántos bloques faltan al ritmo actual* y no puede disparar desde el
  reposo— o por **capacidad demostrada** —no hay aproximación y no puede haberla, y producir el
  hecho exige exactamente la capacidad ante la que la transición reacciona: el canario de §6.6—.
  *(Reformulada el 19/8/2026: la letra anterior dejaba fuera al propio canario. Ver C9–C11.)*
- **I3** — el estado cruza la transición **íntegro**. Sin migración, sin reasignación.
- **I4** — cada generación commitea a su ancestro.
- **I5** — las transiciones son **aditivas en la interfaz**. Se pueden agregar formatos, nunca
  quitarlos, y todo objeto lleva etiqueta de generación desde el bloque 0.

**Nodo PoD.** Verifica y liquida, cobra fee cuando dos contratos interactúan. Corre en cualquier
hardware —la verificación reproduce bit a bit en x86-64, ARM64 y un teléfono—. **Es la capa de
consenso.**

**Nodo de cómputo.** GPU y RAM, hostea los modelos que hacen el trabajo pedido. **No participa
del consenso.** Su ingreso es el pago del pedido que ejecutó.

**Predicado de aceptación.** Todo pedido de trabajo lleva uno: determinista y barato de correr en
la capa liviana. La inferencia **no se verifica** — se verifica que la salida satisfaga el
predicado. Lo que no se puede expresar así, la red no lo puede liquidar.

**Los dos techos del predicado.** Además de pasar los vectores, hay que verificar por debajo de un
tope de **pasos ejecutados** y tocando menos de un tope de **páginas de 4 KiB** (nunca tiempo de
reloj — el reloj sería un oráculo). **Son condiciones de seguridad, no de rendimiento:** son lo que
impide que exista una impugnación más cara de verificar que de crear.

El de pasos **no es un número elegido: es una cuenta** —`f* × tiempo_de_bloque × R_declarado /
tx_por_bloque`—, y lo que Genesis congela es la fórmula, no el valor. *(Cerrado el 20/8/2026; era
el primer problema abierto de §10.3.)*

El de páginas **también se deriva**, desde el 21/8/2026: es un parámetro del ruleset —96 páginas de
4 KiB en Genesis— y lo que Genesis congela es la **curva** de ritmo contra memoria. **Lo agregó la Fase 4 y no estaba en
el diseño:** un techo de pasos solo supone que un paso vale un paso, y la peor mezcla de
instrucciones corre 23× más lento que la carga real. No se arregla pesando instrucciones —`lw`
cuesta lo mismo que `addi` con el dato en caché y 23× más sin él, **es el mismo opcode**—, así que
hay que contar lo único que se ve mientras corre: las páginas distintas que toca.

**Y ésa fue la corrección más importante de la fase, porque tocaba el núcleo:** un techo derivado
*encarece* —una primitiva cara entra bajando `tx_por_bloque`— y uno constante **sólo puede
excluir**. Las tres primitivas de la familia ML-DSA tocan 26, 40 y 65 páginas, así que el primer
número elegido (48) dejaba a la tercera afuera para siempre. **En este diseño, un número que hay
que elegir suele ser una cuenta que falta escribir** — pasó dos veces con el mismo techo. *(21/8/2026,
`genesis/predicado/RESULTADOS.md`.)*

**Ventana de impugnación.** Cómo se finaliza: una interacción queda firme cuando pasa la ventana
sin que nadie presente prueba de conflicto. No hay quórum ni conjunto de validadores. Lo que
impide que se sature es una asimetría: **llenar es serial —hay que entrar en un bloque— y drenar
es paralelo —lo hacen todos los nodos PoD a la vez—.**

**Lock.** Comprometer fondos en un contrato los saca del saldo disponible. Es lo que elimina la
contienda: no se pueden comprometer dos veces.

**Oferta dirigida vs. abierta.** Toda transferencia es **bilateral** (Alice ofrece, Bob acepta).
Una transferencia común nombra al receptor; **un pedido de trabajo no nombra a nadie** y lo toma
el nodo que pueda cumplirlo. Es *pull*, no *push*: **nadie asigna pedidos.**

**Época.** La unidad de tiempo del cobro de permanencia (§8.5). No confundir con generación, que
corre en años.

**Permanencia / desalojo.** Toda entrada de estado paga por seguir existiendo: un **piso** que se
quema al crear, más un **depósito** que se consume quemándose, lineal en tamaño × tiempo. Cuando
se agota, la entrada se **desaloja** —sale del conjunto activo, no se destruye— y se revive con
una prueba. **Tener un saldo deja de ser gratis**, y eso incluye las cuentas del token nativo.

**Claim.** La distribución del día 1: reclamar tokens **se paga demostrando la capacidad que se
reclama**. Ocurre una sola vez, en el bloque 0, y después ninguna acción crea unidades.

---

## 2. Si venís de Bitcoin o Ethereum, esto es distinto en cinco puntos

Es la sección que más tiempo ahorra, porque son cinco supuestos que traés puestos y acá no valen.

1. **No hay prueba de trabajo en el consenso.** No hay minería, no hay dificultad, no hay nonce
   de bloque, no hay hashrate. El único cómputo con costo externo aparece **una vez**, en el claim
   del bloque 0, y no es hashing sino la tarea de referencia. **Si escribís un `proof_of_work.py`
   dentro de `consenso/`, estás construyendo otro protocolo.**
2. **No hay orden global.** Cada cuenta lleva su propia secuencia. Dos interacciones que no
   comparten colateral **no tienen orden relativo**, y eso es distinto de tenerlo indefinido. La
   "cadena más larga" no es el criterio de nada.
3. **La finalidad es por ventana de impugnación**, no por quórum ni por confirmaciones. Se mide
   en minutos u horas, y es una frontera declarada, no un defecto a optimizar.
4. **No hay envío unilateral.** No se le puede pagar a alguien que está offline. El receptor firma
   para aceptar, y por eso *"esperar la finalidad"* deja de ser una disciplina y pasa a ser
   estructura: no hay transacción hasta que firmó.
5. **La bifurcación no se resuelve, se previene por construcción.** El cliente estándar conmuta
   solo, así que **para no conmutar hay que modificar activamente el software**. El que se queda
   en las reglas viejas no preserva la cadena original: se desvía de Genesis, y eso se verifica
   con un hash. No hace falta lógica de "elegir la rama buena".

---

## 3. La estructura

**Por qué no sirve la propuesta genérica.** La que circula en los tutoriales
(`core/ consensus/ network/ api/` con PoW y mempool) modela un protocolo distinto: pone la
minería en el centro, la resolución de bifurcaciones en `blockchain.py` y no tiene lugar para
**lo único que hace a este proyecto** — la sucesión. Un dev que abre `consensus/proof_of_work.py`
ya entendió mal el sistema.

La estructura sigue las piezas del paper, para que el mapeo documento ↔ código sea directo:

```
genesis/
├── protocolo/            # lo que Genesis congela y no cambia nunca (I1)
│   ├── genesis.py          # el bloque 0: ruleset inicial, espacio de descendientes,
│   │                       #   Δ por clase de transición, θ*, L_max
│   ├── invariantes.py      # I1–I5 como aserciones ejecutables — no comentarios
│   ├── generacion.py       # etiqueta de generación en cada objeto (I5), ruleset vigente
│   └── linaje.py           # H0_B = H(H0_A ‖ state_trigger ‖ params) y su Verify (I4)
│
├── sucesion/             # §3 — el corazón, y lo primero que se construye
│   ├── regla.py            # TRANSITION_RULE evaluada contra el estado (I2)
│   ├── distancia.py        # "cuántos bloques faltan al ritmo actual" — I2 lo exige
│   ├── cronograma.py       # disparo → lock-in (espera finalidad) → activación (+Δ)
│   └── conmutador.py       # el cambio de ruleset en caliente: mismo proceso, mismo estado
│
├── estado/               # I3: lo que cruza intacto
│   ├── cuentas.py          # cola por cuenta, índice, saldo
│   ├── entradas.py         # toda entrada paga permanencia: objetos y saldos por igual
│   ├── arbol.py            # árbol con corte d; el tope que muerde es actualizar, no probar
│   ├── permanencia.py      # piso, depósito, tasa, L_max, época
│   └── desalojo.py         # acumulador append-only y reactivación con prueba
│
├── liquidacion/          # §6.3–6.5: cómo se cierra una interacción
│   ├── oferta.py           # bilateral; dirigida vs. abierta (pull); timeout declarado
│   ├── lock.py             # comprometer saca del disponible — elimina la contienda
│   ├── impugnacion.py      # ventana, bono plano, orden de llegada, drenado paralelo
│   └── doble_firma.py      # nonce = f(índice): firmar dos veces publica la clave privada
│
├── predicado/            # §6.2 — qué puede pagar la red
│   ├── aceptacion.py       # vectores + techo de pasos
│   └── vm/                 # la máquina determinista. Rust, no Python — ver §5
│
├── nodo/
│   ├── pod.py              # verifica, liquida, cobra fee. Es la capa de consenso
│   └── computo.py          # acepta pedidos, ejecuta, entrega. Fuera del consenso
│
├── red/
│   ├── p2p.py              # transporte entre nodos — NO EXISTE, y es ingeniería
│   └── sync.py             # ✅ validación y sincronización: el primer nodo que no produce
│
├── api/
│   └── server.py           # HTTP: consultar estado, publicar pedidos, ver la distancia al disparo
│
└── herramientas/
    └── replay.py           # el harness contra el historial real de Ethereum (Fase 2)
```

**Dos decisiones que conviene saber que son decisiones:**

- **Los nombres de módulo van en castellano** porque cada uno mapea a un concepto definido en un
  paper en castellano, y el costo de onboarding acá es el mapeo doc ↔ código, no el idioma. **Si
  en algún momento esto se abre al público, conviene traducirlo** — y cuanto antes, más barato.
- **`api/` es una comodidad de desarrollo, no una pieza del protocolo.** Un nodo real habla p2p.
  No metas lógica de protocolo ahí adentro.

---

## 4. El principio que gobierna todas las fases

> **Cada fase declara su criterio de aprobado y reprobado ANTES de correrla.**

No es burocracia, es la lección más cara que ya se pagó en este proyecto: la primera ley de
control de la tasa de permanencia parecía estable y absorbía un shock de 3×. Lo que la tumbó no
fue un ataque — fue **corregir un detalle del modelo con que se la había probado**. Un criterio
escrito después de ver el resultado se acomoda al resultado.

Y su corolario, que aplica a todo lo que sigue:

> **Un devnet con tokens gratis contesta preguntas de software, no de economía.** Con tokens sin
> valor no hay ingreso, no hay atesoramiento, no se mide la elasticidad de la demanda de guardado
> y el antispam no se prueba. Peor: la actividad fabricada es indistinguible de la demanda real
> —y ahí, además, es gratis—. **Todo lo que se construya acá es desechable por declaración**, y
> hay que reescribirlo cuando se sepa qué espacio de parámetros tiene que anticipar Genesis.

---

## 5. Las fases

### Fase 0 · El andamio y las invariantes ejecutables

**Objetivo.** Que I1–I5 dejen de ser prosa. Antes de la primera línea de mecanismo.

Se construye `protocolo/invariantes.py` con las cinco como predicados que se corren contra
cualquier estado y cualquier transición, más el arnés de tests y CI que las ejecuta en cada
commit.

**Aprobado:** toda fase posterior las sigue pasando sin excepciones ni *skips*. El día que haya
que marcar una como excepción, se para y se discute el diseño, no el test.

### Fase 1 · El motor de sucesión

**Es la mitad con cliente encontrado, no necesita token ni VM ni economía, y no depende de
ninguno de los dos problemas abiertos de §10.3.**

Se construye `protocolo/` y `sucesion/` completos, sobre un estado sintético mínimo. Una cadena
de juguete con parámetros de juguete, pero **la conmutación de verdad**.

**Aprobado —escrito antes de correr—:**

- una cadena con estado sintético conmuta y **el estado cruza bit a bit idéntico** (I3);
- `Verify(H0_B, H0_A, state_trigger, params)` da TRUE para toda la cadena de generaciones, y
  falla si se altera cualquiera de los tres insumos (I4);
- una reorganización **antes** del lock-in deshace el disparo; **después**, no lo deshace;
- el aviso entre lock-in y activación es exactamente `Δ`, **independiente** de cuánto tardó la
  finalidad;
- la distancia al disparo es consultable y **monótona** en la aproximación (I2);
- **el nodo no se reinicia.** Si hace falta reiniciar, la fase no está aprobada.

### Fase 2 · El harness de replay — la única evidencia externa que produce código

**Objetivo.** Contestar con datos de terceros: *si `blobSchedule` hubiera sido una
`TRANSITION_RULE` escrita de antemano, ¿qué habría pasado?*

Se reproduce el historial real: los parámetros de blobs de Ethereum, el gas limit de EIP-8261 y
la bomba de dificultad con sus seis retrasos. Se corre la regla determinista contra el estado
histórico y se compara con lo que los humanos efectivamente decidieron.

**Aprobado:** para cada caso, o la regla reproduce la decisión humana, o queda escrito
**exactamente dónde difiere y si esa diferencia era mejor o peor**. Un empate cuenta como
aprobado; lo que no cuenta es no poder explicar la diferencia.

> **Esta fase es la que más vale por unidad de trabajo de todo el roadmap**, porque es la única
> que produce evidencia que no escribió el autor del diseño. También es la que se puede mostrar
> afuera sin pedirle a nadie que crea nada.

### Fase 3 · Orden y liquidación

Se construye `estado/cuentas.py`, `liquidacion/` completo y `nodo/pod.py`. Sin economía todavía:
los fees en unidades abstractas.

**Aprobado:**

- doble gasto imposible por el lock, sin orden global;
- **la doble firma publica la clave privada** y cualquiera puede barrer el saldo — verificado con
  dos firmas y una resta;
- bajo carga adversarial con `N` nodos, la cola **drena más rápido de lo que se llena**, y el
  margen medido se compara contra los diez nodos PoD que predice §6.3. Si hacen falta cien, la
  predicción del paper está mal y hay que decirlo.

### Fase 4 · La VM y el predicado — ✅ cerrada

**Acá cambia el lenguaje, y es a propósito.** La máquina determinista **no se escribe en
Python**: ya existe el arnés de seis motores de `test2-interprete/telefono` en Rust, con
`steps_per_verify` idéntico entre arquitecturas medido. Se reutiliza.

**Aprobado:**

- el presupuesto del intérprete entra **bajo carga de bloque real**, no en benchmark aislado;
- el flotante está prohibido o canonicalizado **antes de que el guante corra por primera vez** —
  es condición sobre Genesis y después no se levanta;
- el conteo de pasos reproduce bit a bit entre x86-64 y ARM64.

**Corrida el 20/8/2026, con seis criterios aprobados y el séptimo reprobado** —y el reprobado es
lo que valió la fase—. Se agregaron cuatro criterios a los tres del roadmap al leer el intérprete
que se iba a reutilizar: el arnés de Test 2 corre un guest de confianza y esto corre el programa de
un adversario. Agregar criterios está permitido; ablandarlos no.

> **El hallazgo:** el techo de pasos prometía un presupuesto que no cumplía **por 23×**, porque un
> paso no vale un paso. Salieron de ahí un segundo techo sobre páginas tocadas, `R_declarado` de
> 300 a 70 M pasos/s, y la capacidad inicial de 67 a 15 tx por bloque. Más dos agujeros de
> amplificación en el cargador que ningún test de corrección habría encontrado —los encontró que un
> barrido tardara minutos—. Todo en `genesis/predicado/RESULTADOS.md`.

**Cerrada el 21/8/2026**, con los siete criterios resueltos: los vectores reproducen bit a bit entre
x86-64 y aarch64, y C1 está medido sobre el hardware de referencia (354 ms de 1.500, margen 4,24×).

> **Y dejó un problema abierto que el paper no tenía:** cuál hardware es el peor caso. El diseño
> supone que la capa liviana es la que ata, y medido eso es falso para los patrones adversariales de
> memoria. **Dos máquinas no alcanzan para fijar un piso de hardware** — cerrarlo necesita más
> máquinas, no más análisis.

### Fase 5 · Estado con costo — ✅ corrida

Se construye `estado/permanencia.py`, `arbol.py` y `desalojo.py`.

**Aprobado:** el ciclo crear → pagar → agotar → desalojar → reactivar cierra completo; el
acumulador se mantiene en el orden de los cientos de bytes **totales** y no por objeto; y se mide
qué cuesta de verdad mantener una prueba de reactivación al día, que es la dependencia de archivo
que §10.2 declara y no puede garantizar.

**Corrida el 21/8/2026**, con ocho criterios aprobados y uno reprobado — y el que reprobó lo hizo
**contra el paper**: §8.5 afirmaba que el piso salía dieciséis horas de guardado, y la cuenta, ya
escrita, da otro orden. Desarrollo en `genesis/estado/RESULTADOS.md`.

**Sigue bloqueada donde estaba:** la regla que mueve la tasa no está elegida y no hay con qué
calibrarla. Lo que sí se cerró es **por qué ésa no es una cuenta que falta escribir sino una
frontera** —el techo tenía sus dos lados físicos y la tasa tiene uno monetario, y ninguna cuenta
cruza eso sin leer un precio—. De ahí salió denominar el piso en épocas de guardado, con lo cual
**el problema abierto pasó a ser un número en vez de dos**.

### Fase 6 · El devnet desechable — ✅ corrida

Recién acá se junta todo y aparece un token — **con la advertencia de la sección 4 puesta por
escrito y con fecha de reset declarada de antemano.**

**Para qué sirve:** cerrar las cuatro preguntas de mecanismo que ninguna otra cosa contesta —la
conmutación real bajo carga, la cola con `N` real, el presupuesto bajo bloques reales, el ciclo
de desalojo—.

**Para qué no sirve, y no hay que confundirse:** para saber si alguien deja la GPU prendida, cuál
es la elasticidad de la demanda de guardado, si la moneda se atesora, o si el antispam aguanta.
**Eso necesita plata real o revisión externa, y va por otro carril.**

**Corrida el 21/8/2026, acotada a dos de las cuatro preguntas** — la cola con `N` real la contestó
la Fase 3 y el presupuesto bajo bloques reales la Fase 4, y correr de nuevo lo ya medido no agrega
evidencia pero sí agrega la tentación de mirar el número hasta que dé.

> **El hallazgo (B3):** el depósito de permanencia se compraba en byte-**épocas**, la época se
> cuenta en bloques y el tiempo de bloque es un parámetro interno — así que una conmutación que lo
> moviera hacía que **un depósito ya pagado comprara el doble de guardado**. I3 se cumplía: los
> bytes cruzaban idénticos. Lo que cambiaba era lo que valían, y **eso no lo mira ninguna de las
> cinco invariantes**. Corregido denominando en byte-segundos declarados. Desarrollo en
> `genesis/devnet/RESULTADOS.md`.

---

## 6. Lo que corre en paralelo y no es código

Dos cosas que deciden más que cualquier fase de arriba, y que si esperan a que el código esté
listo, llegan tarde:

- **Buscar comprador para el trabajo verificable de §6.2.** Es la hipótesis más cara del diseño y
  es la única que nunca se salió a falsar: los cuatro tests miden la mitad de la sucesión y
  ninguno pregunta si alguien compraría esto. **No necesita protocolo** — un broker manual con
  pago real alcanza. Diez transacciones reales dicen más que diez mil de un devnet.
- **Revisión adversarial externa.** El diseño sobrevivió sólo a los ataques de quien lo escribió.
  Cuesta poco y vuelve rápido, y el repositorio ya está armado para eso: ver
  [problemas abiertos](problemas-abiertos.md), que abre con dónde pegar primero.
