# `estado/arbol.py` — resultados

**Corrido el 22/8/2026.** Criterios en `CRITERIOS-ARBOL.md`, escritos antes.

| criterio | veredicto |
|---|---|
| **T1** el árbol anda | **aprobado** |
| **T2** probar es barato y actualizar es lo que muerde | **medido** |
| **T3** la tabla ya medida se reproduce | **aprobado**, exacta |
| **T4** a qué `d` corresponde el 26 de la Fase 5 | **REPROBADO** |

---

## T4 · El 26 era el árbol que el diseño descartó

La Fase 5 derivó el piso de §8.5 con `hashes_por_actualizacion = 26`, sacado de una cuenta —la
altura del árbol sobre el presupuesto de disco— **sin que el árbol existiera**.

Construido, actualizar cuesta `2^d − 1 + (H − d)`: recomputar el subárbol que no está guardado,
más subir por los niveles que sí. Y con `d = 1` eso da exactamente `H`.

> **O sea que 26 es el costo de guardar todos los nodos internos** — la fila que cuesta 32 B por
> entrada, la que `presupuesto-nodo/` descartó el 18/8. Con el corte que el diseño sí eligió son
> **83**, un factor de 3,2.

| `d` | B/entrada | hashes por actualización | piso (épocas) | % de `L_max` |
|---:|---:|---:|---:|---:|
| 1 | 32,0 | 26 | 6,03 | 24% |
| 4 | 4,0 | 37 | 8,58 | 34% |
| **6** | **1,0** | **83** | **19,25** | **77%** |
| 7 | 0,5 | 146 | 33,86 | **135%** |
| 9 | 0,125 | 528 | 122,44 | 490% |

**El piso pasó de 6,03 a 19,25 épocas.**

### Y ahí §8.5 vuelve a quedar en duda

La sección descarta el cargo a la creación con un argumento que **no depende de la magnitud**:
*un cargo a la creación no reduce la creación, reduce la registración de la creación.* Con el
piso en 19,25 épocas:

- quien compra el depósito máximo paga 43% al crear — todavía menos de la mitad;
- **quien sólo quiere la entrada por una época paga el 95% al crear.**

Para vida corta, el piso *es* el costo. Es exactamente la forma que la sección rechaza, y ya no
alcanza con decir que el piso es chico.

> El criterio de la Fase 5 que exigía el piso por debajo del 35% de `L_max` **se cayó y se
> reescribió para decir lo que ahora es cierto**, no se aflojó el umbral.

---

## Lo más grande: el corte no es una decisión de implementación

`presupuesto-nodo/RESULTADOS.md` cierra su tabla con esta frase:

> *"Es una decisión de implementación que hay que tomar, no un costo que se sufre."*

**No puede serlo.** El piso se deriva del costo de actualizar el árbol, y el piso **se quema** —
o sea que entra al estado. Dos nodos con `d` distinto no coincidirían sobre cuánto se quemó al
crear una entrada, que es una divergencia de consenso por un parámetro que nadie declaró.

**O `d` es constante de Genesis, o el piso deja de ser derivado** — y lo segundo perdería lo que
la Fase 5 ganó. Quedó como `CORTE_ARBOL` en `protocolo/genesis.py`.

Es la misma forma que ya apareció dos veces: **algo que parecía libre resulta estar atado, porque
alguna otra cuenta lo usa.** El techo de páginas parecía una constante y era un precio; el corte
del árbol parecía implementación y es consenso.

---

## T3 · La tabla de bytes se reprodujo exacta

32,0 / 1,0 / 0,125 / 0,016 B por entrada para `d` = 1 / 6 / 9 / 12, y la fórmula cerrada es
`64 / 2^d`. La medición del 18/8 estaba bien; lo que no se sostiene es su última frase.

**Se anotó al lado, no se reescribió** — es una medición cerrada.

## T2 · Probar y actualizar cuestan lo mismo por vez

Y ahí está el matiz de la frase del roadmap: **el costo unitario es idéntico**; lo que separa las
dos operaciones es la frecuencia. Actualizar pasa en cada transacción y probar sólo cuando
alguien revive un desalojado. Por eso la decisión de `d` se toma mirando actualizar.

---

## Lo que queda abierto

**Qué `d` elegir**, ahora que se sabe que son tres monedas y no dos: disco, presupuesto de hash y
el piso de §8.5. Se dejó en 6 porque es lo que el diseño eligió cuando sólo se veían dos — pero
**a 7 el piso ya supera el depósito máximo**, así que el margen es fino y elegir de nuevo es una
decisión con información nueva.

## Estado

**282 criterios en Python, 20 en Rust, 36 mutaciones, todas cazadas.**
