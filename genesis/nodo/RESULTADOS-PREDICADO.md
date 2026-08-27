# El predicado adentro de un nodo — resultados

**Corrido el 22/8/2026.** Criterios en `CRITERIOS-PREDICADO.md`, escritos antes.

| criterio | veredicto |
|---|---|
| **P1** el veredicto entra al estado y mueve la raíz | **aprobado** |
| **P2** los dos techos se cobran y cada uno rechaza | **aprobado** |
| **P3** el techo es el de la generación vigente | **aprobado** |
| **P4** un pedido que cruza una conmutación | **encontrado y decidido** |
| **P5** de qué presupuesto salen los predicados | **medido** |

---

## Lo que faltaba: la cañería

La máquina de §6.6 estaba medida en dos arquitecturas, con siete vectores que reproducen bit a
bit y dos techos calibrados. `predicado/aceptacion.py` modelaba el predicado. **Y ningún nodo
corrió jamás uno**: los techos se midieron sueltos y el veredicto se hizo canónico *para entrar
al hash del bloque* sin entrar a ninguno.

Ahora el veredicto va a `eventos`, que ya era la lista canónica donde se publican los lock-in.
**No hizo falta un campo nuevo**, y eso dice algo: un veredicto es un hecho publicado, de la misma
clase que un lock-in.

### La propiedad que eso compra

**El veredicto lo computa el nodo, no lo trae la transacción.** Si viniera en la transacción, el
que la manda elegiría el resultado. Computándolo:

- dos nodos con la misma máquina llegan al mismo hecho y a la misma raíz;
- **el que llegue a otro produce una raíz distinta y su bloque se rechaza** (`red/sync.py`).

Medido: un validador que no produjo el bloque lo reproduce y llega a la misma huella. Ahí es donde
el determinismo de la máquina —que la Fase 4 midió entre arquitecturas— deja de ser una propiedad
del intérprete y pasa a ser una propiedad de la cadena.

---

## P4 · Un pedido que cruza una conmutación

**Encontrado con la auditoría de unidades en la mano, que es para lo que se hizo.**

El techo de §6.6 se deriva de `tx_por_bloque`, `tiempo_bloque_ms` y `paginas_vm` — los tres
parámetros internos. O sea que **una conmutación lo mueve, y eso es a propósito**.

Pero un pedido de trabajo de §6.2 se publica y se acepta más tarde. Si en el medio hay una
conmutación, **el predicado que era admisible puede dejar de serlo sin que nadie lo toque.** Es
exactamente la forma de B3: la cantidad no cambió, cambió lo que significa.

### La salida elegida

**El pedido lleva la generación en la que se publicó y se juzga con las reglas de entonces.** Un
pedido evaluado contra otro ruleset levanta `GeneracionEquivocada` en vez de dar un resultado
distinto en silencio.

Lo contrario —juzgarlo con el techo vigente— haría que aceptar el mismo trabajo diera distinto
según cuándo llegue la respuesta. El nodo guarda el historial de rulesets, así que recuperar el de
entonces es una lectura.

> **Y esto abre una pregunta que no es de esta pieza:** un pedido publicado bajo la generación 1
> podría quedar vivo indefinidamente si nadie lo toma. Que se juzgue con reglas viejas para
> siempre es coherente pero no está declarado en ningún lado, y §6.2 no habla de vencimiento. Es
> decisión, no bug.

---

## P5 · De qué presupuesto salen

`f*` es la fracción del nodo **para verificar firmas**, y §6.2 pide que el predicado sea *barato
de correr en la capa liviana* sin decir con cargo a qué.

| | pasos por bloque |
|---|---:|
| del bloque entero | 420.000.000 |
| para firmas (`f*` = 25%) | 105.000.000 |
| **fuera de `f*`** | **315.000.000** |
| predicados del tamaño del techo que entran ahí | **45** |

Ese 75% lo comparten el predicado, la red, la liquidación de §6.5 y —desde la Fase 6— el ciclo de
desalojo, que se lleva un 3%. **La cuenta no elige una fracción nueva**: deja escrito contra qué
compiten.

---

## Lo que esto no es

**La máquina no se reimplementó en Python.** El nodo la invoca por una interfaz; para las pruebas
hay un doble que **devuelve veredictos canónicos**, no simplificados. Lo que se prueba acá es la
cañería —que el nodo cobre los dos techos y publique el hecho—, no la máquina, que está probada
en `predicado/vm/tests/criterios.rs` y en siete vectores sobre dos arquitecturas.

Y no hay mercado de trabajo: quién publica pedidos y quién los toma es §6.2 y §6.5.

## Estado

**296 criterios en Python, 20 en Rust, 39 mutaciones, todas cazadas.**
