# Fase 6 — criterios de aprobado

**Escritos el 21/8/2026, antes de la primera línea del devnet.**

## Lo primero, porque el roadmap lo exige por escrito

> **Un devnet con tokens gratis contesta preguntas de software, no de economía.** Con tokens sin
> valor no hay ingreso, no hay atesoramiento, no se mide la elasticidad de la demanda de guardado
> y el antispam no se prueba. Peor: la actividad fabricada es indistinguible de la demanda real
> —y ahí, además, es gratis—.

**Todo lo que se construya acá es desechable por declaración**, y se reescribe cuando se sepa qué
espacio de parámetros tiene que anticipar Genesis. **Fecha de reset: el día que se elija la regla
de la tasa de permanencia** (§10.3), porque ése es el número que cambia el espacio.

## Y la fase se acota, porque dos de sus cuatro preguntas ya están contestadas

El roadmap dice que la Fase 6 cierra cuatro preguntas de mecanismo. Dos ya se midieron:

| pregunta | dónde se contestó |
|---|---|
| la cola con `N` real | Fase 3, once nodos con 10% de headroom |
| el presupuesto bajo bloques reales | Fase 4, C1 en el hardware de referencia |
| **la conmutación real bajo carga** | **acá** |
| **el ciclo de desalojo** | **acá** |

Correr de nuevo lo ya medido no agrega evidencia y sí agrega la tentación de mirar el número
hasta que dé.

---

## B1 · La conmutación bajo carga no rompe el estado

La Fase 1 conmutó sobre un estado sintético quieto. Acá la cadena está haciendo cosas mientras
conmuta: entradas cobrando permanencia, objetos venciendo, la cola con impugnaciones abiertas.

**Aprobado si** el estado cruza **bit a bit idéntico** (I3) con carga corriendo, el linaje sigue
verificando (I4), y **ninguna entrada cambia de estado por el solo hecho de la conmutación** — ni
se desaloja ni se revive porque cambió el ruleset.

---

## B2 · El ciclo de desalojo corre a escala y a través de una conmutación

La Fase 5 probó el ciclo entrada por entrada. Acá corre con miles, a lo largo de épocas, y con
una conmutación en el medio.

**Aprobado si** el ciclo cierra para todas: ninguna se pierde, ninguna se desaloja antes de que se
le agote el depósito, y el acumulador sigue en cientos de bytes.

---

## B3 · Un depósito comprado antes de la conmutación vale lo mismo después *(el que puede reprobar)*

**Acá está el riesgo real de integrar, y no lo vio ninguna fase suelta.** El depósito se compra en
**byte-épocas**; la época se cuenta en **bloques**; y `tiempo_bloque_ms` es un **parámetro
interno**, o sea que una transición lo puede mover.

Si una conmutación cambia el tiempo de bloque, la misma época pasa a durar otra cantidad de
tiempo real — y entonces **un depósito ya pagado compra más o menos guardado del que compró**,
sin que nadie lo toque. I3 dice que el estado cruza íntegro, y cruza: los bytes son los mismos.
Lo que cambia es lo que valen.

**Aprobado si** el guardado real que compró un depósito no cambia cuando cambia el tiempo de
bloque. **Reprobado si** cambia — y en ese caso hay que decidir si la época deja de contarse en
bloques, si `tiempo_bloque_ms` sale del espacio, o si el depósito se reprecia en la transición.
Ninguna de las tres es gratis.

---

## B4 · El desalojo y la cola comparten presupuesto, y nunca se midieron juntos

La Fase 3 midió la cola sin permanencia corriendo; la Fase 5 midió la permanencia sin cola. **En
un nodo real las dos salen del mismo presupuesto**, y §6.3 depende de que sobre headroom para
drenar.

**Aprobado si el número queda escrito**: qué fracción del bloque se lleva el ciclo de desalojo en
régimen, y cuánto headroom queda para la cola. Sin umbral que pasar — lo que reprueba es no
poder medirlo.

---

## B5 · La conmutación no puede desalojar a nadie por sorpresa

§8.5 pide que la cuenta regresiva sea **pública y computable con anticipación**, porque *un
desalojo anunciado no genera presión por un arreglo coordinado a mano, y una sorpresa sí*.

Una conmutación que cambie el techo, la capacidad o el tiempo de bloque **no puede acortarle la
vida a una entrada ya pagada** sin aviso. **Aprobado si** para toda entrada viva, la cuenta
regresiva publicada antes de la conmutación se cumple después.

---

## Lo que esta fase NO contesta, y no hay que confundirse

- si alguien deja la GPU prendida;
- cuál es la elasticidad de la demanda de guardado;
- si la moneda se atesora;
- si el antispam aguanta.

**Eso necesita plata real o revisión externa, y va por otro carril.**
