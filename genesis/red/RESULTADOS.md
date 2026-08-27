# `red/` — resultados

**Corrida el 22/8/2026.** Los criterios están en `CRITERIOS.md`, escritos antes de la primera
línea. No es una fase del roadmap: cierra el hueco entre *"terminamos las seis fases"* y *"la red
anda"*.

| criterio | veredicto |
|---|---|
| **R1** producir y validar son caminos distintos | **aprobado** |
| **R2** sincronizar llega al mismo estado, bit a bit | **aprobado**, cruzando una conmutación |
| **R3** el linaje se verifica contra una cadena ajena | **aprobado**, los tres insumos pesan |
| **R4** una raíz mentida se rechaza | **aprobado** |
| **R5** la conmutación no se lee del bloque | **aprobado** |
| **R6** dos nodos independientes producen la misma cadena | **aprobado**, hash por hash |

---

## Lo que había antes: nada

**`NodoPoD` sólo producía.** Cada transición de estado del proyecto ocurrió por construcción, y
no existía ninguna función capaz de decir que un bloque estaba mal. Una cadena donde nada puede
ser inválido no es una cadena — y toda la propiedad que §5 le atribuye a la conmutación, *el que
no conmuta es el que se desvía y eso se verifica con un hash*, presupone que alguien verifica.

Ahora existe `validar_bloque`, y la diferencia con producir es exactamente una: **la comparación,
y la capacidad de rechazar.**

## R5 · Lo que el validador no lee del bloque

Es el criterio que importaba y el que tenía riesgo. Un productor malicioso puede activar el
ruleset nuevo antes de tiempo, tarde, o no activarlo.

**El validador no le cree.** Deriva la altura de activación del estado que él mismo calculó, con
las mismas reglas. Si el productor conmutó una altura antes, el estado que el validador computa
es otro, la raíz no cierra y el bloque se rechaza entero.

Medido: una cadena a la que se le saca un bloque antes de la conmutación **se rechaza**, porque
el disparo cae en otra altura. Y un nodo que sólo vio bloques vacíos no llega a la generación 2
por más que le manden un bloque que lo afirme.

> **Ahí es donde §3 deja de descansar en la buena fe del que produce**, que es para lo que existe
> todo el diseño.

## R1 · Un rechazo no puede dejar el nodo movido

Si un bloque inválido dejara al validador a medio aplicar, bastaría con mandar basura para
envenenarlo. Se respalda antes de re-ejecutar y se restaura si la comparación falla.

**Y el respaldo no es un `deepcopy` del nodo**, porque no se puede: las reglas guardan
referencias que no se copian. Se copian a mano los contenedores que la producción muta — lo cual
tiene un efecto lateral útil, que es **dejar a la vista cuáles son**.

## R6 · Determinismo entre nodos

Dos nodos arrancados por separado, con las mismas reglas y transacciones, producen **hashes de
bloque idénticos en cada altura**, y cada uno valida la cadena del otro.

Es el paralelo de C3 en la Fase 4: la máquina reprodujo bit a bit entre arquitecturas y eso valió
porque se corrió en dos lados de verdad. Acá es lo mismo con nodos.

---

## Lo que esto NO es

**No hay transporte.** No hay sockets, ni descubrimiento de pares, ni gossip: los bloques se pasan
como objetos entre dos nodos del mismo proceso. Lo que se prueba es **la separación entre producir
y validar**, que es la propiedad de protocolo; el transporte es ingeniería y no mueve ninguna
invariante.

Tampoco hay adversario de red —particiones, mensajes fuera de orden, eclipse— ni ninguna respuesta
a por qué un nodo gastaría en verificar en vez de confiar, que es pregunta de §6.

## Estado

**268 criterios en Python, 20 en Rust, 34 mutaciones, todas cazadas.**

```
cd genesis
python verificar.py red_sync    # los criterios de red/
python verificar.py             # los 268
python herramientas/mutar.py    # 34 mutaciones
```
