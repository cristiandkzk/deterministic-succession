# Piso de hardware — corridas de terceros

Acá aterrizan las mediciones que manda gente de afuera. Es el registro del
**problema abierto 1 — cuál hardware es el peor caso**, que es el único del
proyecto que no cierra pensando: cierra con más máquinas.

> **How to contribute a measurement.** Clone the repo, run the two benchmarks
> below, and open an issue with the
> [measurement template](https://github.com/cristiandkzk/deterministic-succession/issues/new?template=medicion.yml) — or paste the
> output in the thread and it gets transcribed here.
>
>     cd genesis/predicado/vm
>     cargo run --release --bin mezclas     # instruction mixes
>     cargo run --release --bin conjunto    # working-set sweep
>
> Both binaries print an `environment` block first. **Paste it with the tables** —
> a rate without the machine that produced it can't be compared to anything, and
> the fields it marks `unknown` are the ones you need to fill in by hand.

---

## Por qué se juntan estas corridas

El diseño supone que **la capa liviana es la restricción que ata**: de ahí sale la
entrada barata de nodos, y eso sostiene dos cosas separadas —que una coalición
bloqueante no dure, y que la cola de impugnaciones no sature—.

Medido sobre dos máquinas, la frase *el hardware más barato es el peor caso* es
falsa para patrones adversariales de memoria. Lo que sale de acá no es una
curiosidad de rendimiento: **es una constante de Geminis**, porque `R_declarado`
se calibra contra el peor caso y una vez congelada no se levanta.

## Criterio, escrito antes de juntar nada

Sigue la regla de la sección 4 del roadmap: el criterio va antes, porque uno
escrito después de ver los números se acomoda a los números.

**Qué cuenta como corrida válida:**

1. **Compilada con `--release`.** El bloque de entorno dice `DEBUG` si no lo está,
   y esa corrida no entra a la tabla.
2. **La peor de varias pasadas, no la media.** `mezclas` ya reporta la peor de
   tres internamente. `conjunto` hace una sola pasada por punto, así que una
   máquina con dispersión alta necesita informarse dos veces y quedan las dos
   filas.
3. **Bloque de entorno completo**, con los campos que el binario marca `unknown`
   llenados a mano. Sin modelo de CPU y sin tamaños de cache, la fila no se puede
   leer: el desplome del barrido cae donde el conjunto de trabajo deja de entrar
   en el último nivel, así que el cache **es** la explicación, no un adorno.
4. **Si tocaste el arnés, decilo.** El bloque marca `MODIFIED` solo; hace falta la
   frase de qué cambiaste. Levantar el techo de páginas para la última fila es
   legítimo y está pedido en el post — pero esa fila no es la misma medición que
   las otras.

**Qué lo cierra:** cuando una máquina nueva deja de mover el mínimo observado del
cociente peor/ML-DSA, sobre una muestra que cubra al menos x86-64 y aarch64, y al
menos un móvil y un núcleo grande. Hoy hay dos máquinas y las dos son mías.

**Qué NO lo cierra:** más análisis sobre las dos que ya están. Ese es exactamente
el movimiento que el problema abierto declara insuficiente.

## Lo que se compara es el cociente, no el ritmo

Los M pasos/s de una máquina no se transfieren a otra. Lo que sí —aproximadamente,
y es la única vía sin correr las dos— es **el cociente entre la peor mezcla
admisible y ML-DSA-44 medidos en la misma máquina**. Con ese cociente y el ritmo
de ML-DSA en el hardware de referencia sale el `R_declarado` que aguanta el peor
caso.

Por eso la columna que importa de la tabla es la última, y por eso una corrida que
manda la peor mezcla sin mandar ML-DSA de la misma máquina no sirve.

## Las máquinas

| máquina | arch | cache | peor mezcla admisible | ML-DSA-44 | cociente | fuente |
|---|---|---|---:|---:|---:|---|
| Motorola Edge 40 Neo · MediaTek MT6879V/ZA, 8 GB, Android 15 | aarch64 | — | **82,1** | 266,0 | **0,31** | `genesis/predicado/RESULTADOS.md` — máquina de referencia |
| Intel Core i5-9400 · 6c/6t, 2,90 GHz, Windows 11 | x86-64 | L2 1,5 MB total · L3 9 MB | **85,9** | 229,0 | **0,375** | corrida del 30/8/2026, ver nota |
| MXQ genérica · Amlogic S805 (Meson8b), Cortex-A5, Android 4.4.2 | armv7 (32 bits) | no determinada, ver nota | **8,1**¹ | 21,8 | **0,370** | corrida del 12/9/2026, ver nota |

Ritmos en M pasos/s. El cociente es peor mezcla ÷ ML-DSA de **esa misma** máquina.
¹ En esta máquina la peor mezcla no es `lw-persecución` — ver más abajo.

**Nota sobre la fila del i5.** Es una corrida sola de `mezclas` (peor de tres
internamente) con la máquina no ociosa. La dispersión de esa máquina ya está
declarada como problema: el barrido de `conjunto` dio entre 40 y 88 M pasos/s en
384 KiB según cuándo corriera, contra 1,6% de variación en el teléfono. **La
dispersión del escritorio es ella misma un resultado sin explicar**, y una segunda
máquina x86 que la reproduzca o la contradiga vale tanto como una arquitectura
nueva.

## La MXQ, y un hueco en el método de esta tabla

**Amlogic S805 (Meson8b), Cortex-A5, ARMv7 de 32 bits — la máquina más débil medida hasta
ahora, y la primera que no entra en el presupuesto real.**

Por el cociente, esta fila no mueve nada: 0,370 queda arriba del 0,31 del teléfono, que sigue
siendo el que más aprieta a `R_declarado` por esta vía. Si el método de esta tabla fuera todo lo
que hay, sería una fila sin consecuencia.

**Pero acá se pudo comparar el cociente contra el original, y difieren.** El mismo bloque de
referencia (quince verificaciones ML-DSA-44 bajo el presupuesto de 1.500 ms) se corrió directo
en la MXQ, sin traducir nada — y dio **2.499 ms: 1,67× por encima, reprobado.** Es la primera de
las tres máquinas que no entra en el presupuesto real, y el cociente no lo vio venir.

**Por qué no lo vio.** El cociente compara la peor mezcla contra la carga real de **la misma
máquina**, así que una máquina categóricamente lenta puede tener una proporción interna
"normal" y aun así ser demasiado lenta contra el reloj que importa, que es el del bloque. **El
cociente sirve para decidir cuál mezcla es peor entre arquitecturas — no reemplaza correr el
bloque de verdad cuando correrlo es posible.**

**Y cambió cuál mezcla es la peor.** En el teléfono y en el escritorio, `lw-persecución`
(memoria) gana por buen margen. Acá casi empata con `divu` (división entera):

| mezcla | M pasos/s | nota |
|---|---:|---|
| `divu` | **8,1** | división sin signo — la más cara acá |
| `lw-persecución` (96 páginas) | 8,2 | la más cara en las otras dos máquinas |
| `lw-secuencial` | 15,6 | 2 KiB en orden, todo en L1 |
| `mul` | 26,1 | — |
| `addi-uniforme` | 26,9 | — |
| `aritmética-revuelta` | 27,0 | — |
| ML-DSA-44 (real) | 21,8 | — |

El núcleo A5 no tiene pipeline de división; el segundo techo de §6.6.1 se diseñó para el patrón
de memoria y no cobra esto. Margen chico (1,2% entre las dos primeras): confirmar con más
corridas antes de tratarlo como establecido — no se repitió tres veces como pide la sección 4
del roadmap.

**Caché: no determinada.** Este kernel no expone `cache/` en sysfs
(`/sys/devices/system/cpu/cpu0/` no tiene ese directorio), y no se encontró una fuente pública
confiable del tamaño de L2 del S805/Meson8b. Se incluye la fila igual, con el hueco declarado:
lo que decide el punto de esta sección —el cociente no predice la falla directa, y la mezcla
peor cambia de identidad— no depende de ese dato.

## Dónde se desploma el barrido

| máquina | región plana | desplome | último nivel de cache |
|---|---|---|---|
| teléfono (aarch64) | 384 KiB – 2 MiB | 4 MiB (10,9 M pasos/s) | — |
| i5-9400 (x86-64) | hasta 4 MiB | 16 MiB (15,6 M pasos/s) | 9 MB L3 |
| MXQ (armv7) | ninguna — cae desde 16 KiB (15,1) | sin desplome nítido, declina hasta 3,5 en 16 MiB | no determinado |

**La MXQ no tiene acantilado.** Las otras dos máquinas se mantienen planas hasta que se quedan
sin un nivel de caché y ahí se derrumban de golpe. Acá el ritmo ya viene bajando desde la región
más chica medida (16 KiB) sin ningún tramo plano — consistente con una jerarquía de caché mucho
más chica desde el arranque, no con un límite que se cruza a mitad de camino. Es otra forma de
decir lo mismo que el cociente: **el peor caso no es una versión más lenta del mismo patrón, es
un régimen distinto.**

Consistente con que lo que manda es la jerarquía de memoria del host y no una
propiedad del programa —consistente con, no prueba de—. **Es el patrón que hay que
mirar en cada corrida nueva:** si el desplome de una máquina cae donde su último
nivel de cache dice que tiene que caer, la explicación se sostiene una vez más; si
no, se cayó.

## El resultado que menos se esperaba, y que sigue abierto

Arriba de cierto conjunto de trabajo **la máquina más débil deja de ser el peor
caso**: en 2 MiB el teléfono dio 77,6 y el escritorio 40,6 y 55,5 en dos corridas.
No hay punto de cruce publicable, porque en 384 KiB las dos corridas del *mismo*
escritorio caen a lados opuestos del teléfono.

Eso es lo que dos máquinas no alcanzan a resolver, y es literalmente lo que se le
está pidiendo a quien lea el hilo.
