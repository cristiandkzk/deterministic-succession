# La cola de impugnaciones — ¿satura?

**Estado: cerrado (17/8/2026). Cierra, y con la condición fuerte.**

Script: `saturacion.py`. Sin datos externos, reproducible.

---

## 1. Qué se preguntaba

El tope duro de demora al lock-in (§7.4 de `CONTEXTO.md`) se había anotado con
esta condición: *"para que cierre hace falta que la cola de impugnaciones **no sea
saturable**"*. Después apareció la forma de colas por nodo con desborde, que da
demora **acotada** y no imposible — dos cosas distintas. La pregunta era si el
tope cierra igual con la versión débil.

**El ataque que hay que matar no es demorar.** Demorar ya está acotado por el tope
mismo: pase lo que pase, el lock-in ocurre a los `F_max` bloques. El ataque real
que el tope *crea* es **censurar**: llenar la capacidad de verificación con
impugnaciones basura para que una impugnación **legítima** no llegue a procesarse
dentro de `F_max`, y entonces el fraude queda firme. Ese es exactamente el residuo
que §7.4 declara: *"un fraude descubierto después del tope no detiene la
transición"*.

Así que la pregunta computable es: **¿puede un atacante sostener la cola llena
durante `F_max` bloques?**

## 2. El resultado, y no es el que se esperaba

**No puede, y la razón es estructural, no paramétrica.**

> **Llenar es serial. Drenar es paralelo.**
>
> Una impugnación no existe hasta que entra en un bloque, así que el techo para
> llenar es la capacidad de la cadena, `T` transacciones por bloque — un solo
> caño. Drenar lo hacen los `N` nodos PoD **en paralelo**, porque la verificación
> PoD reproduce bit a bit en cualquier hardware (§6.1) y cualquiera puede tomar
> cualquier impugnación.

```
fill  ≤ T                        (una cadena, un bloque por vez)
drain = N · h · T / γ            (N nodos, cada uno con headroom h)

margen = drain / fill = N · h / γ
```

con `h` = trabajo extra que un nodo hace por bloque además de verificar el bloque
entero, y `γ` = costo de verificar una impugnación medido en transacciones
equivalentes.

**La cola no puede acumular backlog mientras `N · h > γ`.** No es que el atacante
pierda plata saturando: es que **no puede saturar**, porque el desagüe es `N` veces
más ancho que la canilla.

### N crítico (Tabla B)

| γ | h=0.05 | h=0.10 | h=0.25 | h=1.00 |
|---|---|---|---|---|
| **1** | 20 | **10** | 4 | 1 |
| 2 | 40 | 20 | 8 | 2 |
| 10 | 200 | 100 | 40 | 10 |
| 100 | 2.000 | 1.000 | 400 | 100 |

Con `γ = 1` y `h = 0,10` hacen falta **diez nodos PoD** para que la cola deje de
ser saturable. Y `h = 0,10` es conservador por un factor grande: Test 2 midió 640
tx/s con **un cuarto de núcleo** en un teléfono de 8 núcleos, así que el headroom
real es de varios múltiplos del bloque, no de una décima.

> **Nota del 20/8/2026 — la Fase 3 corrió esta fórmula con una cola de verdad, y le
> encontró un supuesto.** No se reescribe nada de arriba: el modelo es correcto y su
> aritmética también. Lo que la implementación mostró es que **`drenar = N·h·T/γ`
> supone que los `N` nodos no se pisan**, y esta medición no lo dice porque no tenía
> por qué — es un modelo de capacidades, no de asignación.
>
> Corrido con nodos que eligen: con **partición por hash** da los diez clavados, pero
> eso exige saber cuántos nodos hay, que es justo lo que un diseño sin conjunto de
> validadores no tiene. **Al azar, sin coordinación, hacen falta once**, y el atraso
> se estabiliza en vez de crecer. Y con la regla que cualquiera escribiría —*la más
> vieja primero*— los `N` nodos verifican la misma impugnación y **no alcanza ninguna
> cantidad de nodos**.
>
> El diez de esta tabla sigue siendo el piso teórico correcto. Lo que faltaba era una
> condición sobre cómo elige cada nodo, y **se escribió en §6.3 el mismo día**.
> Detalle en `genesis/liquidacion/RESULTADOS.md` §3.

## 3. La pieza que sostiene todo: el techo de pasos de VM

`γ` es el parámetro que decide, y no es libre.

`γ > 1` significa que una impugnación cuesta **más verificar que crear** — la
asimetría clásica de DoS al verificador. Si existiera, el atacante compraría
trabajo de verificación barato y `N` crítico crecería linealmente con `γ`.

**El techo de pasos de VM de §10.1 es exactamente lo que la prohíbe.** Una
impugnación que excediera el techo es inválida de cara, así que verificarla cuesta
a lo sumo lo que costó crear la interacción disputada: `γ ≈ 1`.

> Ese techo estaba en el paper por otro motivo —acotar el costo de verificación en
> hardware liviano—. Resulta ser **la condición de la que depende que la cola de
> impugnaciones no sature**. Vale escribirlo, porque nadie lo adivinaría leyendo
> §10.1.

Las filas de `γ = 10` y `γ = 100` de la Tabla B están para ver el contrafáctico:
qué pasaría **sin** techo. Es la diferencia entre necesitar 10 nodos y necesitar
1.000.

## 4. Las otras dos piezas, y qué hace cada una

Las tres condiciones que se habían propuesto tienen trabajos distintos y no son
intercambiables:

| pieza | qué mata |
|---|---|
| cualquier nodo PoD resuelve cualquier impugnación | habilita el drenaje paralelo — sin esto no hay `N` en la fórmula |
| **FIFO + bono plano** | *"el capital compra prioridad"* |
| **techo de pasos de VM** (§10.1) | `γ ≈ 1`, que es lo que hace chico a `N` crítico |

**El bono no tiene que ser grande, sólo distinto de cero.** Es costo y no puja:
se pierde si la impugnación no verifica, y *"no verifica"* es determinístico
—§6.3/§6.4—, así que no hace falta juez ni criterio administrativo.

Y ahí aparece la asimetría de la Tabla D, que es la que da vuelta el problema:

| | impugnación válida | impugnación basura |
|---|---|---|
| verifica | sí | no |
| bono | **vuelve** | **se quema** |
| costo de 10.000 | **0** | 100 (a b = 0,01) |

**El impugnador honesto puede inundar gratis; el atacante no.** El honesto puede
mandar mil copias de una prueba válida y no le cuesta nada, porque los bonos
vuelven. Es la primera vez en toda la sesión que una asimetría juega enteramente
del lado correcto sin necesitar identidad.

## 5. El régimen donde sí satura, y por qué no importa

Debajo de `N` crítico —con `γ = 1` y `h = 0,10`, menos de diez nodos PoD— la cola
sí satura, y ahí vale la Tabla C: censurar `F_max = 100` bloques (~17 min) cuesta
sostener 6.400 impugnaciones por bloque, o sea 640.000 bonos quemados.

Pero el régimen es el del arranque, y con menos de diez nodos PoD la cadena tiene
problemas más grandes que este. **No es un agujero del mecanismo, es la misma
familia del arranque en frío**, y se cierra igual que el resto: con la
distribución del día 1, que pone nodos antes de que haya nada que atacar.

## 6. Veredicto

**El tope duro cierra, y no necesita la versión débil de la condición.** La
condición original —*"la cola no debe ser saturable"*— **se cumple**, sólo que no
por diseño de la cola sino por la geometría del sistema: fill serial contra drain
paralelo, con `γ` acotado por el techo de §10.1.

Correcciones que este cálculo obliga a hacer en la anotación previa:

1. La forma no es *"colas por nodo con desborde"* — eso es un detalle de
   implementación. **Lo que cierra es que la verificación es paralela y la
   inyección serial.** El desborde entre nodos es la consecuencia, no la causa.
2. La condición no se debilitó de *"no saturable"* a *"demora acotada"*. **Se
   cumple la fuerte.**
3. El techo de pasos de VM (§10.1) pasa de ser una decisión de performance a ser
   **una condición de seguridad de §6.3**.

## 7. Supuestos, declarados

- `T = 6.400` tx/bloque, de Test 2 (640 tx/s medidos en un Motorola Edge 40 Neo)
  con bloque de 10 s. El paper no fija tiempo de bloque; el resultado no depende
  de él, porque `T` aparece en fill y en drain y se cancela en el margen.
- El atacante puede usar **el 100% del espacio de bloque** para basura. Es
  generoso: en realidad compite por espacio con transacciones reales y paga fee
  por cada una.
- `h ≥ 0,10` por nodo. Conservador por lo menos en un orden de magnitud según
  Test 2.
- No se modela que el atacante corra nodos PoD que se nieguen a drenar. No hace
  falta: un nodo que no trabaja no censura, sólo no trabaja — la impugnación sigue
  disponible para cualquier otro. Ese es el motivo por el que la primera condición
  (cualquier nodo resuelve cualquier impugnación) es necesaria.
