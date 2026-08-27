# El predicado adentro de un nodo — criterios de aprobado

**Escritos el 22/8/2026, antes de la primera línea.**

## El hueco

`predicado/aceptacion.py` existe. La máquina de §6.6 existe, en Rust, medida en dos
arquitecturas y con siete vectores que reproducen bit a bit. **Y ningún nodo corrió jamás un
predicado.**

Los dos techos —pasos y páginas— se midieron sueltos en la Fase 4 y nunca se aplicaron dentro de
una cadena. El veredicto se hizo canónico *para que entrara al hash del bloque* y nunca entró a
ninguno. Toda la cañería entre *"la máquina da un veredicto"* y *"ese veredicto es un hecho del
estado"* no existe.

---

## P1 · Un veredicto entra al estado y cambia la raíz

**Aprobado si** una transacción que evalúa un predicado deja el veredicto en el estado, y la raíz
del bloque cambia con él. **Reprobado si** el veredicto queda afuera del estado — porque entonces
dos nodos podrían discrepar sobre el resultado de una impugnación sin que la cadena lo note.

## P2 · Los dos techos se cobran, y exceder cualquiera de los dos rechaza

**Aprobado si** un predicado que se pasa de pasos y otro que se pasa de páginas **se rechazan los
dos**, con veredictos distintos y ambos deterministas. Es lo que la Fase 4 midió suelto.

## P3 · El techo que se aplica es el de la generación vigente

`techo_vigente` se deriva del ruleset. **Aprobado si** el nodo usa el techo de la generación en
la que corre el bloque, no uno guardado.

## P4 · Qué le pasa a un predicado que cruza una conmutación *(el que puede reprobar)*

**Acá está el riesgo, y viene directo de la auditoría de unidades.**

El techo de pasos se deriva de `tx_por_bloque`, `tiempo_bloque_ms` y `paginas_vm` — los tres
parámetros internos. O sea que **una conmutación cambia el techo**, y eso es a propósito (§6.6).

Pero un pedido de trabajo de §6.2 se publica con su predicado y **se acepta más tarde**. Si entre
una cosa y la otra hay una conmutación, el predicado que era admisible puede dejar de serlo — o
al revés. **Nadie tocó el pedido y lo que vale cambió**: es exactamente la forma que encontró B3
con el depósito de permanencia, y la que la auditoría de unidades dice que hay que buscar en cada
cantidad guardada.

**Aprobado si** el pedido lleva de qué generación es y el nodo puede decidir sin ambigüedad.
**Reprobado si** el resultado depende de cuándo se lo evalúe sin que nada lo declare — y en ese
caso hay que elegir: o el predicado se juzga con el techo de cuando se publicó, o el pedido se
vence en la conmutación, o se declara la frontera.

## P5 · El costo de correr predicados sale de algún presupuesto declarado

`f*` es la fracción del nodo **para verificar firmas**; §6.2 pide que el predicado sea *barato de
correr en la capa liviana* sin decir con cargo a qué.

**Aprobado si el número queda escrito**: cuántos predicados por bloque entran y de qué
presupuesto salen. Sin umbral — lo que reprueba es no poder decirlo.

---

## Lo que esto NO es

- **La máquina no se reimplementa en Python.** El nodo la invoca; que sea Rust es la decisión de
  I1 y no se toca. Donde correr el binario de verdad sea caro para una prueba, se usa un doble
  **que devuelve veredictos canónicos**, y se declara cuál es cuál.
- **No hay mercado de trabajo.** Quién publica pedidos y quién los toma es §6.2 y §6.5, y acá
  sólo interesa la evaluación.
