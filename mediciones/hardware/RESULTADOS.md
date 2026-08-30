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
curiosidad de rendimiento: **es una constante de Genesis**, porque `R_declarado`
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

Ritmos en M pasos/s. El cociente es peor mezcla ÷ ML-DSA de **esa misma** máquina.

**Nota sobre la fila del i5.** Es una corrida sola de `mezclas` (peor de tres
internamente) con la máquina no ociosa. La dispersión de esa máquina ya está
declarada como problema: el barrido de `conjunto` dio entre 40 y 88 M pasos/s en
384 KiB según cuándo corriera, contra 1,6% de variación en el teléfono. **La
dispersión del escritorio es ella misma un resultado sin explicar**, y una segunda
máquina x86 que la reproduzca o la contradiga vale tanto como una arquitectura
nueva.

## Dónde se desploma el barrido

| máquina | región plana | desplome | último nivel de cache |
|---|---|---|---|
| teléfono (aarch64) | 384 KiB – 2 MiB | 4 MiB (10,9 M pasos/s) | — |
| i5-9400 (x86-64) | hasta 4 MiB | 16 MiB (15,6 M pasos/s) | 9 MB L3 |

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
