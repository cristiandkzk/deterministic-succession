# `estado/arbol.py` — criterios de aprobado

**Escritos el 22/8/2026, antes de la primera línea.** El roadmap lista `arbol.py` en su
estructura y ninguna fase lo construyó: *"árbol con corte `d`; el tope que muerde es actualizar,
no probar"*.

## Por qué importa ahora y no antes

La Fase 5 derivó el piso de §8.5 usando `hashes_por_actualizacion = 26`, y ese 26 salió de una
cuenta —la altura del árbol sobre el presupuesto de disco— **sin que el árbol existiera**.

Y el diseño del árbol ya estaba decidido y medido (`presupuesto-nodo/RESULTADOS.md`, 18/8/2026):
no se guardan todos los nodos internos, se guardan los niveles **por encima de un corte `d`** y
se recomputa el subárbol de `2^d` hojas. Con `d=6` el árbol cuesta ~1 B por entrada en vez de 32,
y el precio son ocho puntos del presupuesto de hash.

> **La sospecha que hay que verificar: 26 es la altura, o sea el costo de actualizar cuando se
> guarda todo — `d=1`, la fila que el diseño descartó por costar 32 B por entrada.** Si es así, el
> piso está calculado con el árbol que no se usa.

---

## T1 · El árbol anda

**Aprobado si** insertar, actualizar y probar cierran: la prueba de una hoja verifica contra la
raíz, y deja de verificar si se altera la hoja, el camino o la raíz.

## T2 · Probar es barato y actualizar es lo que muerde

Es la frase que el roadmap usa para justificar el diseño, y nunca se midió.

**Aprobado si el número queda escrito**: hashes por prueba y hashes por actualización, en función
de `d`. Sin umbral — lo que reprueba es no poder medirlo.

## T3 · La tabla ya medida se reproduce

`presupuesto-nodo/RESULTADOS.md` afirma **32 B por entrada con `d=1`, 1,0 B con `d=6` y 0,125 B
con `d=9`**.

**Aprobado si** el árbol construido da esos bytes por entrada. **Reprobado si** no —y entonces
hay que ver cuál de los dos está mal, porque de esa tabla salió el presupuesto de §10.1.

> Aquella medición está **cerrada**: si difiere, se anota al lado, no se reescribe.

## T4 · A qué `d` corresponde el 26 de la Fase 5 *(el que puede reprobar)*

**Aprobado si** `hashes_por_actualizacion = 26` corresponde al `d` que el diseño eligió.

**Reprobado si** corresponde a otro — y en ese caso hay que rehacer el piso de §8.5 con el número
del árbol que de verdad se usa, y ver si sigue quedando por debajo del depósito máximo. Con la
firma adentro del ciclo el piso ya se pasó una vez de `L_max`, así que no hay margen para suponer
que un factor de tres no cambia nada.

---

## Lo que esto NO contesta

- **Cuál `d` elegir.** Es una decisión de implementación con un precio medido en las dos
  monedas —disco y hash—, y el roadmap la deja como tal.
- **Nada sobre el árbol bajo carga concurrente.** No hay concurrencia en ningún lado del
  proyecto.
