# Fase 4 — resultados

**Corrida el 20 y 21/8/2026.** Los criterios están en `CRITERIOS.md`, escritos antes y sin
tocar después. Hardware de referencia del protocolo: el teléfono de Test 2 (Motorola Edge 40
Neo, Cortex-A78, Termux). **Todas las cifras que deciden algo están medidas ahí**; el
escritorio x86-64 aparece sólo donde la comparación entre máquinas es el punto.

| criterio | veredicto |
|---|---|
| **C1** el presupuesto entra bajo carga de bloque | **aprobado**, 354 ms de 1.500 en el teléfono |
| **C2** el flotante prohibido antes de la primera corrida | **aprobado**, con dos correcciones |
| **C3** el conteo reproduce entre x86-64 y ARM64 | **aprobado**, los 7 vectores idénticos |
| **C4** ninguna entrada hace panic | **aprobado**, con dos amplificaciones corregidas |
| **C5** el techo corta, y cortar es un veredicto | **aprobado** |
| **C6** fuera de rango es trampa, no envolver | **aprobado** |
| **C7** el paso es una unidad honesta | **REPROBADO por 23×** |

**C7 es el resultado de la fase.** Movió tres constantes de Genesis, bajó la capacidad del
bloque de 67 a 15 transacciones, dejó abierto un problema que el paper no tenía, y destapó **un
muro en el diseño**: el segundo techo, escrito como constante, excluía primitivas en vez de
encarecerlas. Eso último es lo único que tocaba el núcleo, y se cerró el 21/8.

---

## Lo que quedó en Genesis

| qué | antes | ahora |
|---|---:|---:|
| `R_declarado` | 300 M pasos/s, constante | **una curva medida**, 70 M en el punto de Genesis |
| presupuesto de páginas | — | **96**, y es un parámetro del ruleset |
| `tx_por_bloque` | 67 | **15** |
| techo de pasos | 6.716.417 | **7.000.000** |

| primitiva | pasos | margen en pasos | páginas | margen en páginas |
|---|---:|---:|---:|---:|
| ML-DSA-44 | 3.339.364 | **2,10×** | 26 | **3,7×** |
| ML-DSA-65 | 5.379.218 | 1,30× | 40 | 2,4× |
| ML-DSA-87 | 9.111.691 | 0,77× — entra pagando capacidad | 65 | 1,48× |

**El techo en pasos casi no se movió; lo que cambió es cuántos pasos garantizados compra un
segundo de reloj.** Como el costo en pasos de una verificación lo fija el ISA y no el ruleset,
bajar el ritmo declarado deja menos transacciones por bloque.

---

## C7 · El paso no era una unidad honesta

### Lo que se midió, en el hardware de referencia

Siete mezclas, cada una un bucle infinito que para en el paso exacto que se le pide — **el
instrumento de medición es el propio techo**. Peor de tres pasadas.

| mezcla | M pasos/s | vs ML-DSA |
|---|---:|---:|
| `mul` | 326,6 | 1,23 |
| `aritmetica-revuelta` (ocho opcodes al azar) | 325,4 | 1,22 |
| `addi-uniforme` | 322,7 | 1,21 |
| **`ML-DSA-44` (la carga real)** | **266,0** | **1,00** |
| `divu` | 197,7 | 0,74 |
| `lw-secuencial` (2 KiB, todo en L1) | 186,3 | 0,70 |
| **`lw-persecucion` (96 páginas)** | **82,1** | **0,31** |
| `lw-persecucion` (sin techo de páginas) | *cortada* | — |

Sin el techo de páginas esa última corría a **11,3 M pasos/s**: el techo prometía 22 ms por
transacción y la mezcla tardaba **596**. La cadena se atrasa de forma determinista y ninguna
invariante lo ve, porque nada de eso es incorrecto: es lento.

### Por qué no se arregla con gas

La salida obvia —pesar cada paso por clase de instrucción— **no funciona, y la propia tabla
dice por qué**: `lw-secuencial` corre a 186,3 y `lw-persecucion` a 82,1, y **es el mismo
opcode**. Lo que los separa no es qué instrucción es sino dónde cae el dato, y eso no se lee
del binario: sólo se sabe corriéndolo. Un peso por clase tendría que cobrarle a toda lectura
el precio de la peor, y entonces ML-DSA —que está llena de accesos que sí pegan en caché—
dejaría de entrar.

Lo único contable mientras corre son **las páginas distintas que toca**.

### La curva de conjunto de trabajo

| páginas | región | M pasos/s | vs ML-DSA |
|---:|---:|---:|---:|
| 4 | 16 KiB | 163,6 | 0,63 |
| 16 | 64 KiB | 125,5 | 0,48 |
| 32 | 128 KiB | 101,1 | 0,39 |
| 48 | 192 KiB | 86,2 | 0,33 |
| **96** | **384 KiB** | **80,8** | **0,31** |
| 256 | 1 MiB | 79,3 | 0,30 |
| 512 | 2 MiB | 77,6 | 0,30 |
| 1024 | 4 MiB | 10,9 | 0,04 |

Cae fuerte hasta ~64 páginas, después es casi plana, y **se derrumba entre 2 y 4 MiB** —el
alcance de la TLB de ese núcleo—. Ahí está el agujero que el techo cierra.

### Que contar páginas alcance: medido, y esta vez bien

| disposición (96 páginas) | aarch64 | x86-64 |
|---|---:|---:|
| juntas | 81,4 | 78,9 |
| desparramadas por 64 MiB | **81,4** | 65,4 |

**En el hardware de referencia, desparramar no cuesta nada: 1,00×.** Contar páginas alcanza y
no hace falta acotar además la dispersión.

### Y el texto no es la palanca que ata

| texto | M pasos/s | vs ML-DSA |
|---:|---:|---:|
| 4 – 32 KiB | 246,1 | 0,94 |
| 128 KiB | 196,2 | 0,75 |
| 512 KiB | 166,6 | 0,64 |
| 1 MiB | 163,3 | 0,63 |

Un binario grande recorrido con saltos impredecibles hace fallar el caché del **host** sin
tocar un byte de la memoria del guest. Es una palanca real pero floja: 163,3 contra los 82,1
de la memoria. Queda anotada y sin cerrar.

---

## El techo de páginas: por qué 96, y por qué dejó de ser una constante

**Éste es el hallazgo de diseño, y no depende de ninguna medición de tiempo.**

| primitiva | páginas | con techo 48 | con techo 96 |
|---|---:|---|---|
| ML-DSA-44 | 26 | entra | entra (3,7×) |
| ML-DSA-65 | 40 | entra | entra (2,4×) |
| **ML-DSA-87** | **65** | **afuera** | entra (1,48×) |

Con 48, ML-DSA-87 no quedaba cara: **quedaba excluida, y sin precio que pagar.** El techo de
pasos se deriva de la capacidad, así que una primitiva cara entra bajando `tx_por_bloque`;
**el techo de páginas es una constante, así que sólo puede excluir**. Eso contradice §6.6, que
es el mecanismo entero.

Con 96, ML-DSA-87 entra en páginas (1,48×) y **no** en pasos (0,77×) — o sea entra bajando la
capacidad de 15 a 11 transacciones. Un precio, no un muro.

> **Los conteos de páginas son exactos y coinciden entre arquitecturas**, así que este
> criterio no lo puede mover ninguna corrida. Es el único que sobrevivió: hubo un segundo
> —*el techo más alto para el que el hardware de referencia sigue siendo el que ata*— que
> daba el mismo número y **se cayó**, porque se apoyaba en una medición rota. Ver abajo.

> **Cerrado el 21/8/2026.** Mientras el presupuesto fue constante, una primitiva que necesitara
> más de 96 páginas no tenía precio que pagar. Ahora Genesis congela **la curva** de ritmo contra
> memoria y el presupuesto es un parámetro del ruleset: pedir más páginas baja `R_declarado`, que
> baja el techo de pasos, que se paga en capacidad. **El punto de Genesis no se movió** —96
> páginas, 15 tx, 7.000.000 de pasos—; lo que cambió es que ahora todo punto tiene precio:
>
> | páginas | KiB | `R` declarado | tx a 2× |
> |---:|---:|---:|---:|
> | 32 | 128 | 87 M | 19 |
> | **96** | **384** | **70 M** | **15** |
> | 512 | 2.048 | 67 M | 15 |
> | 1.024 | 4.096 | 9 M | 2 |
> | 4.096 | 16.384 | 3 M | 1 |
>
> **De 96 a 512 páginas la memoria es casi gratis y el paso siguiente divide la capacidad por
> siete** — es el acantilado de la TLB, y el mecanismo lo cobra sin que nadie lo declare.

---

## De dónde sale `R_declarado = 70 M`, y las tres veces que estuvo mal

Es un **requisito sobre las implementaciones**, no una medición: la que corra más lento está
fuera de spec. Tiene que quedar por debajo de lo que el hardware de referencia sostiene con el
peor programa admisible, y eso ahora está medido directo: **80,8 M pasos/s**, con tres
mediciones independientes dentro del 1,6% entre sí (`mezclas` 82,1, `conjunto` §4 81,4,
`conjunto` §1 80,8). Se toma la más baja y se declara 70, un **13% por debajo**.

**No se subió a 75 al ver que la medición daba mejor que la estimación.** El 70 se fijó antes
de esa corrida; subirlo después de un resultado favorable es lo que la sección 4 del roadmap
prohíbe.

Las tres versiones anteriores, y qué tenía mal cada una:

| valor | de dónde salía | qué estaba mal |
|---:|---|---|
| 300 M | `steps_per_verify` ÷ 10,57 ms del teléfono | el ritmo de **una** mezcla, la de ML-DSA |
| 120 M | 316 M × cociente medido en x86-64 | **dos intérpretes distintos** —los 316 son del sin endurecer— y el escritorio no es la referencia |
| **70 M** | peor mezcla medida en el teléfono | — |

**Los dos techos y los chequeos de rango cuestan 1,19×** sobre la carga real: los 10,57 ms de
Test 2 pasaron a 12,55 en el mismo teléfono. Ése es el precio de tener una máquina de consenso
en vez de un intérprete de benchmark, y no estaba medido.

---

## C1 · El presupuesto bajo carga de bloque, en el teléfono

| tramo | ms totales | ms por tx | % del presupuesto |
|---|---:|---:|---:|
| admisión | 26,2 | 1,01 | 1,7 |
| verificación | 327,4 | 12,59 | 21,8 |
| **cobrable** | **353,6** | | **23,6** — margen **4,24×** |

### La penalidad que el criterio anticipaba no existe

El criterio decía que medir una verificación y multiplicar no vale, porque *"una verificación
sola vive en caché caliente"*. **Medido en las dos arquitecturas, no cuesta nada:** las mismas
verificaciones calientes en una instancia dan 12,55 ms/tx contra los 12,59 del bloque —
**1,00×** en el teléfono, y 0,99×–1,06× en el escritorio.

La explicación está en el número que dio C7: **una verificación toca 104 KiB**, y eso entra en
caché aunque llegue frío. Lo que el criterio temía era la clave, y la clave es lo chico al lado
del espacio de trabajo del algoritmo.

> **La medición no puede detectar el efecto que el criterio nombraba, y eso hay que decirlo.**
> Todas usan el mismo par clave/firma, porque el guest de Test 2 fabrica su material con una
> semilla fija. **Lo único que distinguiría al bloque del bucle caliente —material distinto por
> transacción— es justamente lo que quedó constante.** De la memoria fría el resultado es
> concluyente; de lo otro no dice nada.

---

## C3 · Cerrado

Los siete vectores dan idénticos en x86-64 y aarch64: veredicto canónico, pasos, páginas y una
huella de los 32 registros más 4 KiB de memoria. La huella está porque el conteo solo no
alcanza —dos semánticas distintas pueden retirar la misma cantidad de instrucciones y dejar
registros distintos, y ésas son las que bifurcan sin que nadie las vea—.

El vector grande es un flujo de 200.000 instrucciones pseudoaleatorias sobre todo el ISA, con
operandos que se realimentan; `division-bordes` fija aparte los casos que RV32M define y otros
ISA dejan como trampa. Se reverifica con un comando:
`cargo run --release --bin vectores verificar`.

---

## C2 · El flotante, y dos correcciones que salieron de correrlo

Aprobado, pero **la primera implementación rebotó el binario real dos veces**, y las dos veces
la corrección fue del chequeo y no del binario:

1. **rechazar toda palabra que no decodifique** rebota en el relleno de alineación de `.text`,
   que son ceros. Rellenar no es delinquir → se rechaza por **espacio de opcode**;
2. **barrer las páginas ejecutables** lo rebota por una constante de `.rodata`: el enlazador
   junta `.text` y `.rodata` en un mismo `PT_LOAD` de sólo-lectura-ejecutable → se barren las
   **secciones** con `SHF_EXECINSTR`, y **el formato de predicado exige que el binario declare
   dónde está su código**.

Quedan congelados ocho opcodes mayores —`0x07`, `0x27`, `0x2F`, `0x43`, `0x47`, `0x4B`, `0x4F`,
`0x53`—: todo F, D y Q más los atómicos de A. **Cerrar el espacio es más fuerte que no
implementarlo:** el día que alguien quiera agregar flotante tiene que romper una constante
declarada, no agregar una rama. Y no está prohibido por caro: **el redondeo es la única
operación de un ISA donde dos implementaciones correctas pueden diferir**, y un ulp entre dos
nodos es una bifurcación.

---

## C4 · Ninguna entrada hace panic — y dos amplificaciones

Aprobado: todo truncamiento del ELF real y 6.660 mutaciones de sus cabeceras devuelven `Ok` o
`Err`, ninguna aborta. Pero el barrido tardaba minutos, y **eso era el hallazgo**:

1. **`admitir` reservaba 64 MiB antes de validar una sola cabecera.** Un ELF de trescientos
   bytes con la firma correcta y el resto basura costaba esa reserva;
2. **una cabecera de sección alterada podía forzar 128 MiB de predecodificado**, declarando
   megabytes de código que no existen.

Las dos son amplificación: entrada barata, trabajo caro. **Un `panic` tira un nodo; esto lo
frena**, que en una red de nodos livianos es casi lo mismo. Ninguna la habría encontrado un
test de corrección — las encontró que el test fuera lento.

---

## Cómo se midió mal, cuatro veces

Toda la cuenta de `R_declarado` es **un cociente entre dos ritmos**, y cada forma de medir uno
peor que el otro la corrompe. Las cuatro empujaban hacia el mismo lado: el inseguro.

1. **la referencia se medía con una sola llamada corta** mientras las mezclas calibraban hasta
   medio segundo. Daba 268 M en una corrida y 194 en la siguiente;
2. **la referencia se medía al final**, con el procesador ya caliente: ~20% más lenta;
3. **C1 comparaba el bloque contra un ritmo de otra ejecución**, y reportó una penalidad de
   caché de 1,20× que era íntegramente ruido;
4. **la persecución de punteros no perseguía nada.** El inmediato de `addi` es de doce bits con
   signo: con los doce bits bajos de la dirección ≥ 2048, sumarlos resta 4096. La cadena
   arrancaba en la página anterior, leía un cero, y desde ahí todos los `lw` seguían el puntero
   cero — **leyendo siempre la misma dirección, siempre en L1**. Informaba 194 M pasos/s, que
   es exactamente el ritmo de `lw-secuencial`.

**La cuarta es la peor y la más instructiva.** No falló nada: una mezcla degeneró en otra y
siguió reportando un número creíble. Se cazó cruzando dos herramientas que tenían que coincidir
y no coincidían, y sobre ella se habían apoyado dos conclusiones ya escritas —*"desparramar
cuesta 1,07×"* y *"48 páginas es donde se cruzan las curvas"*—, las dos falsas.

Lo que quedó puesto para que no se repita en silencio:

- **cada mezcla declara cuántas páginas tiene que tocar y se verifica al terminar.** Es lo que
  habría cazado esto en la primera corrida: una medición tiene que declarar qué está midiendo;
- el idioma de carga de dirección quedó en una función con el redondeo correcto;
- **cada mezcla corre tres veces y se informa la peor**;
- la referencia se mide **primero y en frío**, y con la forma que usa un nodo —una tanda del
  tamaño de un bloque, no un bucle largo—.

---

## Lo que esta fase dejó abierto

**No se sabe cuál hardware es el peor caso.** Todo el diseño supone que la capa liviana es la
que ata —de ahí sale la entrada barata de nodos de §6.1— y con ese supuesto se calibra
`R_declarado`. Medido, es falso para los patrones adversariales de memoria:

| páginas | aarch64 | x86-64 | quién es el peor |
|---:|---:|---:|---|
| 48 | 86,2 | 122,2 | teléfono |
| 96 | 80,8 | 78,9 | **escritorio** |
| 512 | 77,6 | 40,6 | **escritorio, por 1,9×** |

De 96 páginas para arriba el escritorio corre la peor mezcla más lento que el teléfono. **Dos
máquinas no alcanzan para fijar un piso de hardware**, y menos con la dispersión que tiene el
escritorio: la misma medición dio entre 44 y 79 M pasos/s según cuándo se corriera, contra
1,6% en el teléfono.

Por eso queda declarado como frontera y **no absorbido dentro de `R_DECLARADO`**, que se
calibra sobre el hardware que el protocolo declara como referencia. Cerrarlo necesita más
máquinas, no más análisis.

---

## Cómo reproducir

```
cd genesis/predicado/vm
cargo test --release                 # C2, C4, C5, C6 y la regresión — 18 criterios
cargo run --release --bin mezclas    # C7
cargo run --release --bin conjunto   # de qué depende, y la curva de conjunto de trabajo
cargo run --release --bin paginas    # el conteo de páginas de los tres niveles
cargo run --release --bin bloque     # C1
cargo run --release --bin vectores verificar   # C3

cd genesis && python verificar.py    # 197 criterios, incluido que los dos lenguajes coincidan
python herramientas/mutar.py         # 21 mutaciones, todas cazadas
```

En el teléfono, `python herramientas/empaquetar_vm.py` arma el paquete: el crate no es
autocontenido, porque el ELF del guest de Test 2 vive fuera de su carpeta.
