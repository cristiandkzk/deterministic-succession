# Sucesión determinista de reglas

[![invariantes](https://github.com/cristiandkzk/deterministic-succession/actions/workflows/invariantes.yml/badge.svg)](https://github.com/cristiandkzk/deterministic-succession/actions/workflows/invariantes.yml)

**Una cadena que lleva escrita, en su bloque génesis, la regla por la cual cambian sus propias
reglas — y ejecuta ese cambio sin voto, sin fork político y sin un humano en el lazo de
decisión.**

*[English version](README.en.md)*

> **Esto no es un pitch. Es un pedido de que lo rompas.**
>
> El diseño sobrevivió a todos los ataques que se le corrieron, y **todos los corrió quien lo
> escribió** — que es exactamente la clase de evidencia que no cuenta. Este repositorio existe
> para que eso deje de ser cierto.
>
> Si tenés tiempo para una sola cosa: **[dónde pegar primero](docs/problemas-abiertos.md)**.

---

## Lo primero que conviene leer

**El diseño estaba terminado y no había una línea de código.** Después se construyó: las seis
fases del roadmap, cada una con su criterio de aprobado y reprobado escrito *antes* de correrla.

**Construirlo corrigió el paper siete veces.** No siete bugs del código: siete lugares donde el
diseño estaba mal y sólo se vio al ejecutarlo.

| lo que decía el paper | lo que encontró construirlo | dónde |
|---|---|---|
| la invariante I2 excluye disparos que nadie puede prever | I2 estaba **mal escrita en las dos direcciones**: dejaba afuera al canario de §6.6, y dejaba pasar una puerta trasera — *"cuando la dirección X reciba 1 wei"* también tiene progreso monótono y distancia publicable | [`genesis/LEEME.md`](genesis/LEEME.md) |
| el techo de pasos de la VM es una constante a elegir | **no es un número, es una cuenta** — y la misma jugada sirvió tres veces sobre tres parámetros distintos | [`predicado/RESULTADOS.md`](genesis/predicado/RESULTADOS.md) |
| un presupuesto de pasos acota el costo de verificar | **un paso no vale un paso.** La peor mezcla corre **23× más lento**, y no se arregla pesando opcodes: `lw` cuesta lo mismo que `addi` con el dato en caché y 23× más sin él — es el mismo opcode. De ahí salió un segundo techo, sobre **páginas tocadas** | [`predicado/RESULTADOS.md`](genesis/predicado/RESULTADOS.md) |
| el techo de páginas es una constante | escrito como constante **excluía primitivas en vez de encarecerlas** — las tres de la familia ML-DSA tocan 26, 40 y 65 páginas, así que el primer número elegido (48) dejaba a la tercera afuera para siempre, contra lo que promete §6.6 | [`predicado/RESULTADOS.md`](genesis/predicado/RESULTADOS.md) |
| el piso de §8.5 compra unas dieciséis horas de guardado | mal por dos órdenes de magnitud — y mal otra vez al construir el árbol: 26 hashes era el árbol que el diseño había descartado | [`estado/RESULTADOS.md`](genesis/estado/RESULTADOS.md) |
| el estado cruza la transición íntegro (I3), así que un depósito pagado está a salvo | un depósito denominado en byte-**épocas** lo **reinterpretaba una conmutación sin que nadie lo tocara**: los bytes cruzaban idénticos, lo que cambiaba era lo que valían. **Ninguna invariante lo miraba** | [`devnet/RESULTADOS.md`](genesis/devnet/RESULTADOS.md) |
| el corte `d` del árbol es una decisión de implementación | entra al consenso por la vía del piso | [`estado/RESULTADOS-ARBOL.md`](genesis/estado/RESULTADOS-ARBOL.md) |

Esa lista es la razón por la que este repositorio tiene la forma que tiene. **Un documento de
diseño que nunca se ejecutó es una hipótesis sobre sí mismo.**

---

## Comprobarlo en treinta segundos

Sin dependencias fuera de la biblioteca estándar. Python 3.11+.

```sh
cd genesis
python verificar.py            # 296 criterios: I1-I5 y el aprobado de cada fase
python herramientas/demo.py    # la conmutación corriendo, en una pantalla
python herramientas/mutar.py   # 39 roturas deliberadas, todas cazadas
```

La última es la que importa. **Un criterio que sólo se corre contra código que funciona no
distingue entre un predicado y un `return true`.** `mutar.py` rompe el motor a propósito de 39
formas que el paper declara imposibles y verifica que la suite las cace. Ya encontró tres
criterios que existían, tenían nombre y no probaban nada.

La máquina en Rust tiene los suyos:

```sh
cd genesis/predicado/vm && cargo test --release   # 20 criterios
```

---

## El mecanismo, en una pantalla

Lo que hace que esto no sea un fork disfrazado es que **el nodo no se reemplaza, se conmuta**:
mismo proceso, mismo estado en memoria, ejecutando reglas distintas a partir de un bloque.

```
   +-------- ruleset A --------+ +- F -+ +---- D ----+ +--- ruleset B ---+
                                                     |
   ---#---#---#---#---#---#---#---#---#---#---#---#--|--#---#---#---#--->
                              ^       ^              |
                          bloque N  N final      activación
                       TRANSITION_    LOCK-IN    la conmutación
                        RULE -> TRUE  irrevocable  toma efecto
                        (advisorio)   params on-chain

   el MISMO nodo . el MISMO estado . sin migración, sin bridge, sin snapshot
```

**Son tres tiempos, no dos:**

1. **Disparo.** En el bloque `N`, `TRANSITION_RULE` da TRUE. No compromete nada: es advisorio
   y una reorganización lo deshace.
2. **Lock-in.** Cuando `N` es final, el disparo se vuelve irrevocable. El lock-in emite el
   ruleset completo y la altura de activación **on-chain**.
3. **Activación.** `Δ` bloques después del lock-in — no después del disparo, así el aviso es
   exactamente `Δ` sin importar cuánto tardó la finalidad.

---

## La evidencia es de dos clases, y mezclarlas sería deshonesto

| mitad | qué es | evidencia |
|---|---|---|
| **sucesión de parámetros** (§3) | la cadena cambia sus propios parámetros internos sin voto | **cliente encontrado afuera**: Ethereum recalibra `blobSchedule` a mano (EIP-7892), el gas limit por cronograma (EIP-8261), y la bomba de dificultad se retrasó por fork seis veces |
| **la moneda, el intérprete, §6.6** | economía propia, VM determinista, evolución criptográfica encadenable | **sólo evidencia propia** — sobrevivió a todos los ataques, y todos los corrió el autor |

El harness de replay ([`genesis/herramientas/`](genesis/herramientas/)) es lo único acá que
produce evidencia que no escribió el autor: corre una regla determinista contra el historial
real de Ethereum y la compara con lo que los humanos efectivamente decidieron. El veredicto,
incluido dónde falla, en [`herramientas/RESULTADOS.md`](genesis/herramientas/RESULTADOS.md).

---

## Si tenés una máquina, podés cerrar un problema abierto hoy

El diseño supone que la capa liviana es la que ata. **Medido, eso es falso para los patrones
adversariales de memoria:**

| páginas tocadas | aarch64 (teléfono) | x86-64 (escritorio) | peor caso |
|---:|---:|---:|---|
| 48 | 86,2 | 122,2 | teléfono |
| 96 | 80,8 | 78,9 | **escritorio** |
| 512 | 77,6 | 40,6 | **escritorio, por 1,9×** |

*(M pasos/s, peor mezcla de instrucciones.)*

De 96 páginas para arriba el escritorio corre la peor mezcla **más lento que el teléfono**, y
la dispersión del escritorio es de 44 a 79 M pasos/s según cuándo se corra, contra 1,6% en el
teléfono.

**Dos máquinas no alcanzan para fijar un piso de hardware, y cerrarlo necesita más máquinas, no
más análisis.** Si corrés el arnés y pegás tus números en un issue, eso es un problema abierto
declarado que se cierra. Ver [`genesis/predicado/vm/LEEME.md`](genesis/predicado/vm/LEEME.md).

---

## Lo que a propósito no está

**No hay transporte de red** — no hay sockets, ni descubrimiento de pares, ni gossip. Los nodos
se pasan bloques como objetos en un mismo proceso. Lo que se prueba es *la separación entre
producir y validar*, que es la propiedad de protocolo; el transporte es ingeniería y no mueve
ninguna invariante.

**No hay nodo de cómputo, ni mercado de trabajo, ni test de mercado** — y eso último es lo que
el propio paper llama el riesgo dominante. Nunca se le preguntó a nadie si pagaría por esto. Es
el [ataque A](docs/problemas-abiertos.md).

**Todo lo de acá es desechable por declaración.** Los parámetros son de juguete: no se sabe
todavía qué espacio tiene que anticipar Genesis, así que estos números existen para que el
mecanismo corra, no para heredarlos.

---

## Cómo está organizado

| dónde | qué |
|---|---|
| [`docs/paper.md`](docs/paper.md) | el diseño completo, 12 secciones. Fuente de verdad — `§X.Y` siempre cita esto |
| [`docs/problemas-abiertos.md`](docs/problemas-abiertos.md) | **la agenda de debate**: dónde pegar primero, los problemas abiertos declarados, y lo que necesita medición y no análisis |
| [`docs/roadmap.md`](docs/roadmap.md) | glosario, estructura de módulos, y cada fase con su criterio de aprobado |
| [`docs/bitacora.md`](docs/bitacora.md) | qué murió ya, y por qué. Conviene mirarlo antes de proponer |
| [`genesis/`](genesis/) | **la implementación.** Empezar por [`genesis/LEEME.md`](genesis/LEEME.md) |
| [`mediciones/`](mediciones/) | los cuatro tests de falsación y las cinco mediciones anteriores a la implementación |

Cada fase tiene su `CRITERIOS.md` (escrito antes de correrla, sin tocar después) al lado de su
`RESULTADOS.md` (qué dio, incluido lo que reprobó). **Agregar criterios estaba permitido;
ablandarlos no.**

---

## Licencia

Código (`genesis/`, `mediciones/`) bajo [MIT](LICENSE). Prosa (`docs/`, `README*`,
`CONTRIBUTING*`, todo `RESULTADOS.md`) bajo [CC BY 4.0](LICENSE-DOCS).

Cómo contribuir — y en particular cómo atacar esto: [CONTRIBUTING.md](CONTRIBUTING.md).
