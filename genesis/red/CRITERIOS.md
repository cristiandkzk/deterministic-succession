# `red/` — criterios de aprobado

**Escritos el 22/8/2026, antes de la primera línea.** No es una fase del roadmap: el roadmap
lista `red/` en su estructura (§3) y no lo incluyó en ninguna de las seis fases. Se puede decir
con verdad *"terminamos las fases"* y estar lejos de *"la red anda"*, y esto cierra esa
distancia.

## Lo que hay que saber antes de empezar

**Hasta hoy nunca hubo un segundo nodo.** Todo lo que dice *"N nodos"* —la cola drenando en
paralelo, los once nodos de la Fase 3, que todos vean la misma conmutación— está modelado como
objetos en un proceso.

Y hay algo más puntual, que se verificó antes de escribir esto:

> **No existe ningún camino de validación.** `NodoPoD` sólo produce. Cada transición de estado
> del proyecto ocurrió **por construcción, nunca por verificación** — y una cadena donde nada
> puede ser inválido no es una cadena, es un programa que lleva una lista.

Ésa es la asimetría que estos criterios atacan.

---

## R1 · Producir y validar son caminos distintos

**Aprobado si** existe una función que recibe un bloque que este nodo **no produjo**, recalcula
el estado desde sus transacciones y **compara** contra la raíz que el bloque declara. Y si
difieren, rechaza.

**Reprobado si** validar es volver a producir y confiar. La diferencia es exactamente la
comparación: un validador que no puede decir *"no"* no está validando.

---

## R2 · Sincronizar desde cero llega al mismo estado, bit a bit

**Aprobado si** un nodo vacío que recibe la cadena entera termina con **la misma huella de
estado** que el que la produjo, y eso incluye **cruzar una conmutación**: el que sincroniza tiene
que activar el ruleset nuevo en la misma altura sin que nadie se lo diga.

---

## R3 · El linaje se verifica contra una cadena ajena (I4)

Hasta ahora `verificar_linaje` corrió sobre checkpoints que el mismo proceso había creado.

**Aprobado si** el que sincroniza verifica la cadena de `H0_B` desde Genesis sobre checkpoints
que recibió, y **falla si se altera cualquiera de los tres insumos** —`H0_A`, `state_trigger` o
los parámetros—.

---

## R4 · Una raíz mentida se rechaza

**Aprobado si** un bloque con `raiz_estado` alterada en un solo byte se rechaza al validarlo.

Es el caso más simple y por eso el que más importa: si éste no anda, ninguno de los otros
significa nada.

---

## R5 · Una conmutación en la altura equivocada se rechaza *(el que puede reprobar)*

**Acá está el riesgo real.** Un productor malicioso puede activar el ruleset nuevo antes de
tiempo, o tarde, o no activarlo. El que valida **no puede leer del bloque cuándo conmutar**:
tiene que derivarlo del estado que él mismo calculó, exactamente igual que el productor.

**Aprobado si** una cadena donde la conmutación ocurre en una altura distinta de la que el
validador deriva se rechaza. **Reprobado si** el validador toma la altura del productor — porque
entonces §3 entero descansa en la buena fe del que produce, y todo el diseño existe para no
descansar en eso.

---

## R6 · Dos nodos independientes producen la misma cadena

**Aprobado si** dos nodos arrancados por separado, con las mismas reglas y las mismas
transacciones, producen **hashes de bloque idénticos** en cada altura.

Es determinismo **entre nodos** y no dentro de uno, que es lo único que hasta ahora se probó. El
paralelo es C3 en la Fase 4: la máquina reprodujo bit a bit entre arquitecturas, y eso valió
porque se corrió en dos lados de verdad.

---

## Lo que esto NO contesta

- **No hay transporte.** No hay sockets, ni descubrimiento de pares, ni gossip. Los bloques se
  pasan como objetos entre dos nodos del mismo proceso. Lo que se prueba es **la separación entre
  producir y validar**, que es la propiedad de protocolo; el transporte es ingeniería y no cambia
  ninguna invariante.
- **No hay adversario de red** — particiones, mensajes fuera de orden, eclipse.
- **No hay incentivo a validar.** Por qué un nodo gastaría en verificar en vez de confiar es una
  pregunta de §6 y no se toca acá.
