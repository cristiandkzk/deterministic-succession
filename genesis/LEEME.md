# Genesis · la implementación

Acá vive el código. El diseño está en `../Genesis Paper.md` (fuente de verdad) y
el plan de construcción en `../ROADMAP.md`. **`§X.Y` siempre cita el paper.**

```
python verificar.py            # las invariantes y los criterios de aprobado
python verificar.py -v         # con el nombre de cada criterio
python herramientas/demo.py    # la conmutación corriendo, en una pantalla
python herramientas/replay.py  # Fase 2, caso 1: la bomba de dificultad
python herramientas/replay_blobs.py   # Fase 2, caso 2: el blobSchedule
python herramientas/replay_gas.py     # Fase 2, caso 3: el gas limit
python herramientas/cola.py           # Fase 3: la cola de impugnaciones bajo ataque
python herramientas/techo.py          # el techo de pasos de VM, derivado (§10.3)

cd predicado/vm && cargo test --release   # la máquina: 18 criterios (Fase 4)
```

Las series de Ethereum que usa el replay ya están en el repo (`herramientas/datos/`,
144 KB), así que **todo corre offline**. Para actualizarlas:
`python herramientas/traer_datos.py blobs|gas|dificultad` — endpoint público, sin clave.

Sin dependencias: sólo la biblioteca estándar de Python 3.11+. `pytest` también
corre las pruebas si está instalado, pero nada lo necesita.

---

## Dónde está parado esto

| fase | qué es | estado |
|---|---|---|
| **0 · invariantes ejecutables** | I1–I5 como predicados que corren contra cualquier estado y cualquier transición | ✅ **corriendo** |
| **1 · motor de sucesión** | `protocolo/` + `sucesion/` sobre estado sintético, con la conmutación de verdad | ✅ **los seis criterios pasan** |
| **2 · harness de replay** | la evidencia externa: bomba de dificultad, blobs, gas limit | ✅ **cerrada, 3 de 3.** Los tres corridos y escritos, con los datos verificados contra los EIPs y `config.go`. El veredicto, en `herramientas/RESULTADOS.md` |
| **3 · orden y liquidación** | doble gasto por lock, doble firma, la cola de §6.3 con `N` real | ✅ **los tres criterios pasan**, con una corrección al paper: la cola necesita **11** nodos y no 10 — y con la regla que cualquiera escribiría, ninguna cantidad alcanza. Ver `liquidacion/RESULTADOS.md` |
| **4 · la VM y el predicado** | la máquina determinista, en Rust — reutiliza el arnés de `test2-interprete` | ✅ **cerrada** (21/8). Seis criterios pasaron; el séptimo reprobó por 23× y de ahí salió el segundo techo |
| 5 · estado con costo | — | bloqueada parcialmente por la regla de la tasa (§10.3) |
| 6 · devnet desechable | — | pendiente |

**§3 corrió por primera vez el 19/8/2026.** Antes de eso el mecanismo central del
paper nunca se había ejecutado. Lo que se ve en la demo —tres generaciones, las dos
clases de transición **superpuestas**, el estado cruzando intacto— es eso.

> **Todo lo de acá es desechable por declaración** (ROADMAP §4). Los parámetros
> son de juguete: no se sabe todavía qué espacio tiene que anticipar Genesis, así
> que estos números existen para que el mecanismo corra, no para heredarlos.

---

## El mapa: módulo ↔ paper

| módulo | qué implementa |
|---|---|
| `protocolo/serializacion.py` | codificación canónica. **El flotante está prohibido desde el primer archivo** — la Fase 4 lo exige antes de que el guante corra, y una condición sobre Genesis no se levanta después |
| `protocolo/genesis.py` | el bloque 0: la máquina, el espacio de descendientes, `Δ` por clase, la ventana de finalidad, `θ*`, `L_max`, **la fórmula del techo de pasos** —que es lo que se congela, no el número (§10.3)— y **el techo de páginas**, que sí es un número y no se deriva |
| `protocolo/generacion.py` | ruleset, etiqueta de generación, decodificación que **falla cerrado** (I5) |
| `protocolo/linaje.py` | `H0_B = H( H0_A ‖ state_trigger ‖ params )` y su `Verify` (I4, §3) |
| `protocolo/invariantes.py` | **I1–I5 ejecutables.** No son comentarios (Fase 0). Incluye las dos formas de cumplir I2 y el chequeo del canario derivado |
| `sucesion/regla.py` | `TRANSITION_RULE` contra el estado (I2). Dos reglas, una por cada forma de cumplirlo: aproximación observable y capacidad demostrada |
| `sucesion/distancia.py` | *cuántos bloques faltan al ritmo actual* (I2), en enteros |
| `sucesion/cronograma.py` | disparo → lock-in → activación, el tope duro de C7.4, y §3 *Más de una transición en vuelo*: espera por regla, orden de activación, sucesor computado en el lock-in y rechazo |
| `sucesion/conmutador.py` | la conmutación. Es corto a propósito: si necesitara mover datos, no sería conmutar |
| `estado/sintetico.py` | el estado mínimo de la Fase 1 |
| `estado/cuentas.py` | **Fase 3**: cola por cuenta, saldo, comprometido. `disponible = saldo − comprometido` es lo que impide el doble gasto |
| `liquidacion/oferta.py` | bilateral; dirigida vs. abierta (pull); el lock ocurre al publicar, y eso la vuelve exclusiva |
| `liquidacion/doble_firma.py` | el nonce se deriva del índice: firmar dos veces publica la clave privada |
| `liquidacion/impugnacion.py` | la cola de §6.3, con las tres formas de elegir qué verificar — y la que colapsa |
| `nodo/pod.py` | aplica bloques, evalúa la regla, conmuta, reorganiza. **Todavía no liquida nada** |
| `pruebas/` | Fase 0 y los seis criterios de la Fase 1, uno por clase, con el texto del criterio en el docstring. `test_transiciones_en_vuelo.py` y `test_eventos_y_reorganizacion.py` fijan las dos subsecciones nuevas de §3; `test_i2_quien_elige_el_momento.py`, la reformulación de I2 |
| `herramientas/demo.py` | ver el mecanismo corriendo, con las dos clases **superpuestas** — que es el caso incómodo |
| `herramientas/techo.py` | la derivación del techo de pasos con el dato de Test 2, y qué queda como decisión |
| `predicado/aceptacion.py` | el predicado de §6.2: los vectores y **los dos techos**. La máquina no está acá |
| `predicado/vm/` | **la máquina, en Rust.** El único directorio que cambia de lenguaje, y `LEEME.md` dice por qué |
| `predicado/CRITERIOS.md` | los siete criterios de la Fase 4, escritos antes de la primera línea y sin tocar después |
| `predicado/RESULTADOS.md` | qué dio: seis aprobados, uno reprobado, y las tres constantes de Genesis que movió |
| `herramientas/traer_datos.py` | lo único que toca la red: baja las series de Ethereum a `datos/*.csv`, con la procedencia adentro del archivo |
| `herramientas/replay.py` · `replay_blobs.py` · `replay_gas.py` · `historial.py` | **Fase 2**: la regla candidata contra las seis veces que Ethereum corrió la bomba de dificultad. Cada dato lleva **de dónde salió y contra qué se verificó**. El resultado, en `herramientas/RESULTADOS.md` |

**Lo que a propósito no está:** token, fees repartidas, oferta, lock, impugnación,
VM, permanencia, p2p. Nada de eso es Fase 1, y construirlo antes sería construir
la mitad sin evidencia (ROADMAP §0).

---

## Lo que aparecía al construir, y qué se hizo con eso

Ninguna de estas cosas es un bug del código: son huecos del diseño que sólo se ven
cuando el mecanismo corre. **Los tres se cerraron y los tres están en el paper.**

### ✅ Resuelto y escrito en el paper · más de una transición en vuelo

Entre el lock-in y la activación pasan `Δ` bloques con las reglas viejas todavía en
vigor y las nuevas ya comprometidas. **No es un caso de borde: pasa solo en la
primera corrida** con una regla de acumulación. §3 tiene ahora la subsección *Más
de una transición en vuelo*, y el mecanismo está en `sucesion/cronograma.py` con
sus pruebas en `pruebas/test_transiciones_en_vuelo.py`. Cuatro decisiones:

1. **una regla no vuelve a disparar hasta su propia activación**, no hasta su
   lock-in. Si no, mide un estado que no refleja el cambio que ella misma acaba de
   comprometer — un lazo de control con tiempo muerto, que es cómo se cayó la EDA
   de Bitcoin Cash en 2017;
2. **la espera es por regla, no global.** Bloquear todo mientras haya una
   transición en vuelo pone una migración criptográfica urgente a esperar detrás de
   una de circulación, y eso vacía la razón por la que `Δ` es por clase;
3. **las activaciones van en orden de lock-in**, aunque las `Δ` sean distintas.
   Esto apareció al escribir la prueba de (2) y es más profundo de lo que parece:
   `params_nuevos` es un **punto completo** del espacio y no un incremento, así que
   activar la generación 2 antes que la 1 aplicaría también los cambios de la 1,
   con el aviso de la 2. **Residuo declarado:** una transición urgente puede
   esperar hasta el `Δ` restante de la que tenga adelante — acotado por la `Δ` más
   larga del espacio, y no compone;
4. **`params_nuevos` se computa en el lock-in**, donde ya se computaba `H0_B`. Y el
   lock-in **verifica antes de comprometer**: un checkpoint irrevocable con un punto
   fuera del espacio dejaría al nodo sin poder conmutar y pararía la cadena. Si no
   pasa, hay **rechazo** on-chain — no se recorta al borde ni se detiene el consenso.

**Una nota sobre el criterio de la Fase 1.** *"El aviso entre lock-in y activación
es exactamente `Δ`"* sigue valiendo tal cual cuando hay una sola transición en
vuelo, que es el caso que ese criterio contemplaba. Con cola, el aviso es **más**
que `Δ`, nunca menos — y eso no es una relajación del criterio escrito: es un caso
que el criterio no contemplaba, y su comportamiento está declarado arriba y
probado en `test_ningun_aviso_es_menor_que_su_delta`.

### ✅ Resuelto y escrito en el paper · el evento de lock-in es estado, no un anuncio

El lock-in es irrevocable, pero el bloque que lo publica on-chain **no es final**
—recién se produjo—, así que una reorganización legítima puede reemplazarlo.

Al escribirlo se vio que la falla no era la que parecía. No es que el integrador se
quede sin poder leer el aviso: es que un nodo que publicara sólo *lo recién
madurado* terminaría con un lock-in vigente y sin registro en el estado, y **su raíz
se separaría de la de un nodo que no reorganizó**. Eso es una bifurcación, y de la
peor clase, porque los dos nodos coinciden en todo lo demás.

La regla, ahora en §3: **el evento se emite en función de la altura en que `N` se
vuelve final, no de que el nodo acabe de enterarse.** Es un hecho derivado de la
cadena —sus dos insumos son finales e irrevocables—, así que cualquiera que
reproduzca los bloques lo produce idéntico. Y vive **en el estado** y no en la
memoria del nodo por dos razones distintas: para que un integrador lo lea con
cabecera y prueba, sin replicar la cadena; y porque §5 —*la cadena que no conmutó no
tiene checkpoint válido*— sólo es verificable por un tercero si el checkpoint está
en el estado que la cadena commitea.

Lo prueba `pruebas/test_eventos_y_reorganizacion.py`, y lo prueba de la única forma
que corresponde a un problema de consenso: **dos nodos, uno que reorganizó el bloque
del lock-in y otro que no, tienen que llegar a la misma raíz** — más un tercero que
resincroniza desde cero y llega también.

### ✅ Resuelto y escrito en el paper · I2, y quién elige el momento

El canario de §6.6 no se ve venir, y la letra vieja de I2 decía que eso no es
admisible. O sea que **la sección de vidriera del paper no cumplía una de las
cinco invariantes.**

Lo que se vio al mirarlo de cerca es que la invariante estaba mal escrita, y falla
**en las dos direcciones**: deja afuera al canario, que tiene que estar adentro, y
deja pasar una puerta trasera —*"cuando la dirección X reciba 1 wei"*—, que tiene
progreso monótono y distancia publicable igual que el canario. La forma de la curva
no los distingue: **los dos son escalones**.

Lo que los distingue es **quién puede producir el hecho y qué le cuesta**, y ésa es
la reformulación que quedó en §4. Dos formas de cumplir I2, declaradas por cada
regla y verificadas en cada bloque:

- **por aproximación observable** — y entonces la regla *no puede disparar desde el
  reposo*: si el bloque anterior no publicó una distancia, era un escalón. Es el
  chequeo que caza la puerta trasera;
- **por capacidad demostrada** — no hay aproximación ni puede haberla, y es
  admisible sólo si producir el hecho exige exactamente la capacidad ante la que la
  transición reacciona. Obliga a declarar cuál, on-chain, y a **no inventar una
  fecha**.

**Y de ahí salió una condición sobre §6.6 que no estaba escrita.** *"Genesis publica
una versión debilitada de la primitiva"* deja abierto quién la genera — y si la
genera alguien, ese alguien **retiene la trampa** y puede reclamar el canario cuando
quiera. Ahí *capacidad demostrada* es *un secreto que alguien se guardó*, y el
canario deja de ser una alarma para ser una compuerta con disfraz criptográfico.
La instancia se **deriva** de una semilla pública (`protocolo/genesis.py`), y el
nodo lo verifica en cada bloque: **un canario que no se puede rederivar de su
semilla no es un canario, es de alguien.**

**El límite, declarado y probado como tal:** ningún nodo puede verificar que la
capacidad declarada sea la verdadera. La misma puerta trasera, declarada por
capacidad, pasa — y `test_declarada_por_capacidad_pasa_y_queda_a_la_vista` la deja
escrita. Lo que el protocolo sí garantiza es que la razón esté on-chain y a la vista
para la auditoría de Genesis, que es donde el espacio de reglas está fijo (I1).

---

## Cómo se prueba que las pruebas sirven

Un criterio que sólo se corre contra código que funciona no distingue entre un
predicado y un `return`. `python herramientas/mutar.py` rompe el motor a propósito
de doce formas que el paper declara imposibles y verifica que la suite las cace:

| falla introducida | criterios que se caen |
|---|---|
| la conmutación toca el estado (rompe I3) | 30 |
| el sucesor se computa sobre Genesis y no sobre el ruleset comprometido | 24 |
| `Δ` se cuenta desde el disparo y no desde el lock-in | 8 |
| las activaciones no respetan el orden de lock-in | 6 |
| una regla se rearma en el lock-in y no en la activación (lazo abierto) | 8 |
| el evento de lock-in se publica al madurar y no por altura | 6 |
| el lock-in se puede deshacer en una reorganización | 1 |
| una regla de aproximación puede disparar desde el reposo | 1 |
| el trigger de capacidad publica una cuenta regresiva inventada | 1 |
| la instancia del canario no se verifica contra su semilla | 1 |
| el contrafáctico del replay usa el offset equivocado | 3 |
| una regla rechazada reintenta contra el mismo ancestro | 1 |

**Al agregar un mecanismo, agregarle su mutación.** Cuesta una entrada en la lista
y compra saber que el criterio nuevo prueba algo. Si una mutación dice `ANCLA
PERDIDA`, el código se movió debajo de ella y hay que reescribirla — no ignorarla:
una mutación que no se aplica no está probando nada.
