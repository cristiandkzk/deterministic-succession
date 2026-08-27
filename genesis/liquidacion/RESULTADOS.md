# Fase 3 · orden y liquidación

**Corrida el 20/8/2026.** Los tres criterios del roadmap, escritos antes de correrlos.

```
cd genesis
python verificar.py fase3       # los tres criterios
python herramientas/cola.py     # la medición de la cola bajo ataque
```

---

## 1 · El doble gasto lo impide el lock, sin orden global — ✅

Dos propiedades distintas, y la segunda es la que se olvida.

**El lock.** Comprometer saca del disponible: `disponible = saldo − comprometido`.
Publicar una oferta compromete en el mismo acto, así que una oferta abierta ya tomada
**no tiene con qué pagarle a un segundo**. Nadie arbitra cuál transacción va primero —
al segundo simplemente no le alcanza.

**Y sin orden global no quiere decir con el orden indefinido.** Quiere decir que dos
interacciones que no comparten colateral **dan el mismo estado en cualquier orden**, y
eso es falsable con dos huellas: se corren `(alice→carol, bob→carol)` y su inversa, y
la huella del libro coincide. Cada cuenta lleva su propia secuencia; avanzar el índice
de Alice no toca el de Bob.

---

## 2 · La doble firma publica la clave privada — ✅

`s₁ = k + e₁·x` y `s₂ = k + e₂·x` con el mismo nonce dan `x = (s₁ − s₂)/(e₁ − e₂)`.
**Una resta y una división**, con lo que está en la cadena y nada más.

El mecanismo es que **el nonce se deriva del índice de la cuenta**. Si fuera aleatorio,
firmar dos veces en el mismo índice sería un accidente sin consecuencia y el fraude
tendría que detectarse y castigarse desde afuera; derivado, el castigo lo ejecuta
cualquier tercero movido por el botín — el mismo patrón que el canario de §6.6 y el
impugnador de §6.3.

Lo que las pruebas fijan, además de la recuperación: que **índices distintos no filtran
nada**, que firmar dos veces el mismo mensaje no es doble firma —es la misma firma—, y
que el grupo **se rederiva** en vez de creerle a las constantes, con la misma disciplina
que el canario: `q = 2¹²⁷−1`, `p = 2·j·q+1` con el `j` más chico que da primo, `g` con
el `h` más chico que da orden `q`.

> **No es criptografía de producción y no pretende serlo**: el grupo es de 134 bits,
> elegido para que el mecanismo corra y se pueda leer. La primitiva real la elige
> Genesis (§6.6). Lo que esto demuestra es **la propiedad**, que es lo que el criterio
> pedía.

---

## 3 · La cola no satura — ✅, con una corrección al paper

El criterio decía: *el margen medido se compara contra los diez nodos PoD que predice
§6.3. Si hacen falta cien, la predicción del paper está mal y hay que decirlo.*

**No hacen falta cien. Hace falta uno más — o infinitos, según una regla que §6.3 no
especificaba.**

`cola-impugnaciones/` había cerrado esto **como fórmula**: `margen = N·h/γ`, y con
`γ = 1`, `h = 0,10` alcanzan diez nodos. La fórmula supone que los `N` nodos **no se
pisan**, y §6.3 no dice cómo se reparten — no puede, porque no hay conjunto de
validadores y ningún nodo sabe cuántos son. Corrida con una cola de verdad:

| cómo elige cada nodo | N crítico | backlog en régimen (N=11) | espera media |
|---|---|---|---|
| partición por hash | **10** = la fórmula | 0 | 0 |
| al azar (sin coordinación) | **11** | 424 | 4,2 bloques |
| **la más vieja primero** | **nunca** | crece ~90 por bloque | rampa de `9·T` |

**La regla natural es la que colapsa el mecanismo.** *La más vieja primero* es lo que
cualquiera escribiría, y hace que los `N` nodos verifiquen exactamente la misma
impugnación: con cincuenta nodos se verifica lo mismo que con uno.

**Y en lo único que importa de verdad —si la impugnación legítima se procesa a tiempo—
la falla no es un plazo fijo sino una rampa.** Con FIFO el atraso crece ~90 por bloque y
se drena a 10, así que lo que llega en la altura `T` espera del orden de `9·T`. Medido:

| llega en la altura | 5 | 10 | 20 |
|---|---|---|---|
| espera (bloques) | 45 | 90 | 180 |

Si el tope duro de demora al lock-in (§10.1) queda por debajo de esa rampa, el fraude
queda firme. Es el residuo que §10.1 declara, ocurriendo por un motivo que no estaba
escrito.

### La propiedad que hace que once alcancen

Con selección al azar **el atraso no crece sin techo: se estabiliza.** Cuanto más larga
la cola, menos se pisan los nodos, así que el desagüe efectivo sube solo hasta igualar a
la canilla. Con once nodos el equilibrio queda en ~424 impugnaciones y cuatro bloques de
espera media; con veinte, en 24 y dos décimas. *La cola es larga, no infinita.*

> **Y ahí hubo una trampa de medición que conviene no volver a pisar.** La primera
> pasada midió el `N` crítico con corridas de 80 bloques y dio **13**. Era un artefacto:
> a 80 bloques el sistema todavía no había llegado al equilibrio, así que un backlog que
> iba a estabilizarse se leía como uno que crecía. Medido comparando **dos largos de
> corrida** —250 y 500 bloques—, el número real es **11**. Quedó escrito en el docstring
> de `satura()`, y las pruebas comparan dos largos y no uno.

### Lo que se escribió al paper

§6.3 pasó de **dos** condiciones a **tres**, y la tercera es ésta: *cada nodo elige en
su propio orden, y no en el de la cola*. El orden de llegada resuelve la **prioridad**
—el capital no compra turno— pero no dice **qué toma cada nodo**, y ahí estaban chocando
dos frases de la misma sección. La regla que lo arregla no necesita coordinación: cada
nodo recorre la cola en un orden pseudoaleatorio derivado de su identidad. **El número
del paper cambió de diez a once**, se escribió que el atraso se estabiliza, y también
por qué la alternativa exacta —repartir la cola— no está disponible: exige saber cuántos
son.

## Estado de la Fase 3

**Aprobada, tres de tres.** Con una corrección al paper que no salió de un ataque
imaginado sino de correr el mecanismo: **el margen medido es menor que el calculado, y
la diferencia depende de una regla que no estaba escrita.**

Lo que **no** cubre esta fase, y está declarado: no hay economía —las fees son unidades
abstractas—, no hay VM (Fase 4), no hay permanencia (Fase 5) y la cola se mide con un
modelo de nodos, no con nodos en red. El paso de esto a una red es la Fase 6, y con
tokens gratis contesta software y no economía.
