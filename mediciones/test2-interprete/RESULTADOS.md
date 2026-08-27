# Test 2 · El presupuesto del intérprete

> Estado: **cerrado. x86 y ARM corridos, veredicto firme.**
> Quedan tres celdas de la tabla ARM sin medición limpia; ninguna sostiene una
> conclusión. Ver §7.

Lo que pide §12: *"medir cuánto tarda una verificación de firma post-cuántica corriendo
como bytecode sobre una VM determinística, en un teléfono"*. Ningún protocolo escrito:
VM que ya existe (wasmtime 47, wasmi 2.0) + implementación de referencia
(RustCrypto `ml-dsa` 0.1.1, FIPS-204 puro Rust).

---

## 1. Qué se midió exactamente

Un único `verify` de ML-DSA compilado desde la **misma fuente** a nativo, a wasm32 y a
dos ISAs RISC-V. Eso aísla la variable que importa —el motor de ejecución— y no mezcla
implementaciones distintas.

Seis motores, que no son seis velocidades sino seis **regímenes de despliegue**:

| motor | qué representa en el diseño |
|---|---|
| `native` | la primitiva como código de nodo — justo lo que §6.6 quiere evitar |
| `wasmtime-cranelift` | bytecode con JIT optimizante — **igual de determinístico** |
| `wasmtime-pulley` | intérprete portable de wasmtime — cota pesimista |
| `wasmi` | intérprete puro de registros — el perfil "VM de cadena" |
| `rv32im` | intérprete RV32IM propio — el ISA chico, 32 bits |
| `rv64imac` | el mismo intérprete a 64 bits |

Los tres últimos son intérpretes puros, así que sus cocientes comparan ISA contra ISA.
Y `rv32im` contra `rv64imac` aísla una sola variable —el ancho de registro— sobre el
mismo diseño de intérprete.

Dos caminos, y la distinción resultó tener consecuencia de protocolo:

- **`decode+verify`** — el nodo recibe clave pública y firma como bytes y verifica. Es el
  número honesto por defecto.
- **`verify_only`** — la clave ya está expandida en memoria.

## 2. Resultados — x86_64, Intel i5-9400 @2.9 GHz, un núcleo

**`decode+verify`** (µs por firma · firmas/s · penalidad vs. nativo)

| | native | cranelift (JIT) | wasmi (int.) | pulley (int.) |
|---|---|---|---|---|
| **ML-DSA-44** | 107 µs · 9 332/s | 392 µs · 2 548/s · **3,7×** | 3,11 ms · 322/s · **29,0×** | 8,42 ms · 119/s · 78,6× |
| **ML-DSA-65** | 172 µs · 5 813/s | 591 µs · 1 691/s · **3,4×** | 4,82 ms · 208/s · **28,0×** | 12,88 ms · 78/s · 74,9× |
| **ML-DSA-87** | 279 µs · 3 586/s | 896 µs · 1 116/s · **3,2×** | 7,25 ms · 138/s · **26,0×** | 19,53 ms · 51/s · 70,0× |

**`verify_only`** (clave ya expandida)

| | native | cranelift | wasmi | pulley |
|---|---|---|---|---|
| **ML-DSA-44** | 43,7 µs · 22 888/s | 248 µs · 5,7× | 1,97 ms · 45,2× | 5,13 ms · 117× |
| **ML-DSA-65** | 60,7 µs · 16 475/s | 354 µs · 5,8× | 2,89 ms · 47,6× | 7,39 ms · 122× |
| **ML-DSA-87** | 86,9 µs · 11 504/s | 524 µs · 6,0× | 4,35 ms · 50,1× | 11,21 ms · 129× |

**Costo de instalar el bytecode** (una vez por nodo, al conmutar de primitiva —
el momento del lazo de §6.6): cranelift **221–243 ms**, wasmi **1,2–1,5 ms**, para un
módulo de 223 KB. Es ruido. Esa parte del lazo no tiene problema de presupuesto.

*Varianza:* una segunda corrida completa dio `wasmi`/ML-DSA-44 en 26,1× en vez de 29,0×.
La dispersión entre corridas es del orden del **10%**; ningún dígito de estas tablas
significa nada más allá de eso.

*Nota sobre la base:* la columna `native` es Rust portable, no AVX2. Una ML-DSA
vectorizada a mano corre ~2–3× más rápido todavía, así que la penalidad real del
bytecode contra el mejor nativo posible es mayor que la de la tabla. No mueve el
veredicto, pero la tabla es la versión optimista.

## 3. Resultados — ARM64, Motorola Edge 40 Neo (Dimensity 7030, Cortex-A78 @2,5 GHz)

Bajo Termux. La tabla está **ensamblada a partir de celdas limpias de varias corridas**;
el criterio de limpieza está en §6 y los CSV crudos quedan listados al final.

**`decode+verify`**

| | native | cranelift (JIT) | wasmi (int.) | pulley (int.) | rv32im | rv64imac |
|---|---|---|---|---|---|---|
| **ML-DSA-44** | 111 µs · 8 994/s | 391 µs · 2 560/s · **3,51×** | 5,96 ms · 168/s · 53,6× | 9,83 ms · 102/s · 88,4× | 10,57 ms · 95,1× | 11,67 ms · 105,0× |
| **ML-DSA-65** | 180 µs · 5 556/s | 589 µs · 1 697/s · **3,27×** | 9,12 ms · 110/s · 50,7× | 15,17 ms · 66/s · 84,3× | 16,75 ms · 93,1× | 18,09 ms · 100,5× |
| **ML-DSA-87** | 307 µs · 3 259/s | 905 µs · 1 105/s · **2,95×** | 14,16 ms · 71/s · 46,2× | 23,64 ms · 42/s · 77,1× | 28,49 ms · 92,8× | 33,09 ms · 107,8× |

**`verify_only`**

| | native | cranelift | wasmi | pulley | rv32im | rv64imac |
|---|---|---|---|---|---|---|
| **ML-DSA-44** | 52,5 µs · 19 054/s | — | 3,76 ms · 71,7× | — | 3,56 ms · 67,2× | 5,05 ms · 96,1× |
| **ML-DSA-65** | 75,0 µs · 13 349/s | 370 µs · **4,93×** | 5,49 ms · 73,2× | — | 4,77 ms · 63,7× | 6,82 ms · 91,0× |
| **ML-DSA-87** | 109 µs · 9 195/s | 554 µs · **5,09×** | 8,35 ms · 76,8× | 13,23 ms · 121,7× | 7,08 ms · 65,1× | 10,38 ms · 95,4× |

**Costo de instalar el bytecode en ARM:** cranelift **335–344 ms** (x86: 221–243), wasmi
**1,5–2,1 ms**. Sigue siendo ruido.

### 3.1 El teléfono contra el PC, motor por motor

| motor | ARM / x86 |
|---|---|
| `native` | 1,02–1,22× |
| `wasmtime-cranelift` | **1,00–1,06×** |
| `wasmtime-pulley` | 1,17–1,21× |
| `rv32im` | 0,82–1,07× por paso |
| `rv64imac` | 1,46–1,74× por paso |
| **`wasmi`** | **1,86–2,21×** |

Cranelift en el teléfono corre a **1,00× del i5-9400** en las celdas medidas limpias:
390 614 ns contra 392 462, 589 377 contra 591 224, 905 159 contra 895 815. No es un
ajuste, es el mismo tiempo absoluto en dos arquitecturas.

### 3.2 `steps_per_verify` es idéntico entre arquitecturas

El conteo de instrucciones ejecutadas por los intérpretes RISC-V coincide **byte a byte**
entre x86 y ARM en las seis configuraciones, en todas las corridas. Es el único número de
todo el test que ninguna contaminación puede tocar, porque no depende del reloj.

Esa es la propiedad I1 medida directamente: la máquina fija no se degrada al cambiar de
arquitectura anfitriona. También es lo que hace viable el techo de pasos de §5.1.

## 4. El veredicto

**El número entra, y entra con margen — pero no por el motivo que el paper supone.
El teléfono lo confirma.**

§10.3 dice *"matemática de retículos interpretada es mucho más lenta que nativa"*.
Es cierto: **26–29×** bajo intérprete en x86, **46–54×** en ARM. Lo que el paper no
considera es que **determinismo e interpretación son cosas separadas**. Wasm fija la
semántica; el JIT la reproduce bit a bit en x86-64 y ARM64 igual que el intérprete —para
código entero no hay ninguna libertad que el compilador pueda tomar. La penalidad real de
la propiedad que §6.6 necesita (I1: la máquina fija, la lista abierta) es:

- **3,2–3,7×** en x86
- **2,95–3,51×** en ARM

No 29×, y no 50×.

Traducido a lo que §6.1 necesita: si un nodo liviano puede gastar **un cuarto de un
núcleo** en verificar firmas —el resto se lo lleva el predicado de aceptación de §6.2,
la red y la liquidación bilateral de §6.5—, el techo de transacciones por segundo es:

| régimen | ML-DSA-44 desde bytes, x86 | ML-DSA-44 desde bytes, **teléfono** |
|---|---|---|
| bytecode + JIT | ~640 tx/s | **~640 tx/s** |
| bytecode interpretado (wasmi) | ~80 tx/s | **~42 tx/s** |
| intérprete pesimista (pulley) | ~30 tx/s | **~25 tx/s** |

El techo con JIT es **el mismo en el teléfono que en el PC de escritorio**. El techo
interpretado se corta a la mitad, por la razón de §5.5.

Contra una cadena que en §10.2 **ya aceptó finalidad en minutos u horas**, hasta la
fila peor sobra. Una cadena de esa clase no está peleando por 10 000 tx/s. **El problema
abierto de §10.3 no tumba §6.1, y baja a §10.1** con las condiciones de §5.1 y §5.4
escritas.

## 5. Lo que el test encontró y no estaba buscando

Cinco cosas, y la primera es un agujero de protocolo, no una medición.

### 5.1 El guante de §6.6 no acota el costo de lo que instala — y debería

El pedido de trabajo dice *"entregá una implementación que cumpla esta interfaz y
estos vectores"*. El predicado verifica **corrección**. Nada verifica **costo**. Una
implementación correcta pero diez veces más lenta pasa el guante, sobrevive la ventana
(nadie la rompe: es correcta) y queda instalada para siempre. En ese momento el
presupuesto de §6.1 se rompe *desde adentro del protocolo*, sin fork, sin atacante y
sin que ninguna regla se haya violado.

El arreglo es barato y no necesita maquinaria nueva: **el predicado de aceptación tiene
que incluir un techo de pasos de VM**, no de tiempo de reloj. El conteo de instrucciones
ejecutadas es determinístico y reproducible —§3.2 lo confirma entre arquitecturas—, así
que califica como predicado bajo §6.2 y como trigger bajo I2. Tiempo de reloj no
calificaría; pasos de VM sí.

Sin eso, el lazo que resuelve la obsolescencia criptográfica puede matar la propiedad
de gobernanza que el mismo capítulo usa para resolver el problema de los validadores.

### 5.2 El límite duro no es criptográfico, es una política de plataforma — y cuesta el doble de lo que decía

Android permite JIT; **iOS no lo permite a terceros**. Y como acá el bytecode llega
*en tiempo de ejecución* desde la cadena, tampoco se puede precompilar AOT antes de
publicar la app. Un nodo liviano en iPhone queda forzado al intérprete.

La versión anterior de esta sección estimaba ese costo en ~8×, con datos de x86. Medido
en el teléfono, es **el doble**:

| | x86 (estimación previa) | ARM (medido) |
|---|---|---|
| ML-DSA-44 | 7,9× | **15,3×** |
| ML-DSA-65 | 8,2× | **15,5×** |
| ML-DSA-87 | 8,1× | **15,7×** |

(cociente wasmi / cranelift; con pulley en vez de wasmi la brecha es mayor todavía)

Eso no rompe nada, pero corrige una frase de §6.1. *"Reemplazar al que se niega cuesta
un teléfono"* es cierto; lo que no es cierto es que todos los teléfonos cuesten lo
mismo. La coalición de bloqueo sigue sin poder durar —entrar sigue siendo barato— pero
el costo de entrada es **~15×** según de qué lado del duopolio esté el aparato. Va a
§10.1 como decisión asumida, no a §10.3.

Es el hallazgo que justifica haber corrido la etapa teléfono: era una afirmación sobre
teléfonos hecha con datos de escritorio, y el número real es el doble de malo.

### 5.3 Expandir la clave pesa más que verificar la firma

En ML-DSA el 59% de una verificación desde bytes se va en expandir la matriz Â desde ρ
con SHAKE128 (107 µs totales contra 44 µs de verify puro, nivel 44, x86). En ARM la
proporción es parecida: 111 µs contra 52,5 µs. Es la operación que `decode` hace y
`verify_only` se saltea.

Cachear claves expandidas por cuenta **multiplica el techo por 1,6×** y es gratis: no
toca consenso, es estado local del nodo. Es la única palanca de rendimiento grande que
aparece sin tocar ni una regla, y el paper no la menciona.

### 5.4 Corolario que ya estaba medido en `Chain`

Falcon / FN-DSA verifica con enteros pero **firma con punto flotante**. `ARCHIVO.md`
de PoD ya midió que la reproducibilidad bit a bit entre ARM y x86 solo aguanta con
`+ − × ÷` y sin trascendentales. Si el guante admite candidatas sin restringir eso, el
lazo de §6.6 puede instalar una primitiva que rompe el determinismo del que depende
todo lo demás. **La especificación de la máquina (I1) tiene que prohibir o canonicalizar
el punto flotante antes de que el guante corra por primera vez** — es una condición
sobre Genesis, y Genesis es lo único que después no se puede cambiar.

### 5.5 Los cocientes entre motores sí dependen del hardware

La versión anterior de este documento afirmaba que *"los ratios entre motores no dependen
del hardware; las magnitudes sí"*. Medido, **es falso en general** — y cierto solo donde
el veredicto lo necesita, que es suerte y no diseño.

Penalidad contra nativo, misma celda (`decode+verify`, ML-DSA-44), las dos máquinas:

| motor | x86 | ARM | cambio del cociente |
|---|---|---|---|
| `cranelift` | 3,66× | 3,51× | **0,96×** |
| `pulley` | 78,6× | 88,4× | 1,13× |
| `rv32im` | 112,8× | 95,1× | 0,84× |
| `rv64imac` | 69,5× | 105,0× | **1,51×** |
| `wasmi` | 27,4× | 53,6× | **1,96×** |

Solo `cranelift` mantiene el cociente. `pulley` queda dentro del 13%. Los otros tres se
mueven entre 0,84× y 1,96×, en las dos direcciones.

Dos consecuencias:

**Para el veredicto:** §4 se apoya exactamente en la única fila estable de la tabla. Eso
lo vuelve firme, pero no era predecible antes de medir — y no hay ninguna razón de
principio por la que Cranelift tuviera que ser la fila estable. Si el paper hubiera
apostado al intérprete, la extrapolación desde x86 habría estado errada por 2×.

**Para el diseño:** `pulley` es también un intérprete puro y solo pierde 13%, así que la
degradación de `wasmi` no es una propiedad de la interpretación sino de su despacho en
ARM64. **La elección de intérprete —no la decisión de interpretar— es lo que hay que
medir en el hardware objetivo** antes de comprometerse. Y `rv32im` contra `rv64imac`
sobre el mismo diseño de intérprete se separan 1,8× al cambiar de anfitrión, lo que
significa que la elección de ancho de registro del ISA chico tampoco se puede decidir
en escritorio.

## 6. Cómo se detectaron las celdas sucias

Buena parte de las corridas en el teléfono salió contaminada, y separar señal de
artefacto requirió dos invariantes. Quedan escritos porque hacen falta para reproducir.

**Invariante 1 — ns por paso.** `steps_per_verify` es determinístico, así que
`ns_per_verify / steps_per_verify` tiene que ser constante por motor. En ARM: **3,11–3,19
ns/paso** para `rv32im` y **5,85–6,00** para `rv64imac`. Cualquier celda fuera de ese
rango está contaminada, sin excepción. Una celda dio 14,7 ns/paso y otra 19,7.

**Invariante 2 — `compile_ms`.** Limpio da 335–344 ms para cranelift y 364–381 para
pulley. Contaminado da 1310–1450: exactamente 4×, que es el cociente entre un Cortex-A78
y un Cortex-A55. Es el rastro de la migración al cluster chico. Cuidado: `compile_ms` se
mide al principio de la celda, así que un valor limpio no garantiza que la medición
posterior también lo sea.

**Un chequeo de consistencia interna** que atrapó una corrida entera: `rv32im` nivel 65
`verify_only` (1,47 M pasos) salió más lento que nivel 87 `verify_only` (2,22 M pasos).
Menos trabajo, más tiempo. Imposible.

### 6.1 Dos causas distintas, y una de ellas no es térmica

La contaminación tiene dos orígenes que se comportan al revés uno del otro:

**(a) Migración al cluster chico.** Variable entre corridas, factor ~4×, delatada por
`compile_ms`. Es térmica y de scheduler.

**(b) Degradación por proceso largo.** **Reproducible a cuatro cifras significativas**
—`native · 65 · decode+verify` dio 696 591 y 696 761 ns en dos corridas distintas— y por
lo tanto **no es térmica**: una corrida con 45 s de enfriamiento antes de cada bloque no
la movió ni un 0,02%. Afecta solo a `decode+verify` en los niveles 65 y 87, que son los
caminos que reservan la matriz Â más grande en cada llamada. La hipótesis que mejor
encaja es fragmentación de memoria —wasmtime reserva regiones virtuales enormes por
store, y el allocator de bionic se degrada con muchas VMAs— pero **está sin probar**. Es
un defecto del arnés, no un resultado sobre el sistema medido.

Lo que sí quedó probado en negativo: **el nivel 87 no tiene ningún comportamiento
especial**. Aislado y en frío, `native · 87 · decode+verify` da 306 884 ns, o sea 1,06×
el x86, en línea con todas las demás celdas. Los 1,18–1,23 ms de las corridas largas
eran artefacto.

**Y la pausa fue contraproducente.** Insertar 45 s de sleep entre bloques hace que el
governor de Android pierda el rastro del proceso y lo reubique en el cluster chico al
despertar. La corrida con pausas salió *peor* que la corrida sin pausas.

**La receta que funciona: una celda por proceso, sin pausas, sin cargador enchufado.**

## 7. Lo que falta

Tres celdas de la tabla ARM sin medición limpia: `cranelift · 44 · verify_only`,
`pulley · 44 · verify_only` y `pulley · 65 · verify_only`. Ninguna sostiene una
conclusión —Cranelift está medido limpio en cinco celdas y todas dicen lo mismo— así que
es prolijidad de tabla, no evidencia faltante.

Se completan con dos pasadas por celda, tomando el mínimo por fila (el ruido de este
sistema es de un solo signo: solo puede hacer las cosas más lentas, nunca más rápidas):

```bash
~/host-jit 44 decode+verify > celdas-1.csv
for c in "44 verify_only" "65 decode+verify" "65 verify_only" "87 decode+verify" "87 verify_only"; do
  ~/host-jit $c | grep -vE '^#|^engine|^$' >> celdas-1.csv
done
```

Lo que **no** hace falta: nada más para decidir. El veredicto de §4 no depende de esas
tres celdas.

Fuera de alcance y anotado por si vuelve: la causa de §6.1(b) sigue sin diagnosticar.

---

## Reproducir

`telefono/` es el paquete completo y autocontenido: `pqcore/` (la verificación,
compartida), `guest/guest.wasm` (223 KB), `guest-rv/` y `guest-rv64/` (los ELF de
RISC-V) y `host/` (el arnés de seis motores). Los tres guests van **empotrados en el
binario** con `include_bytes!`, así que el ejecutable es un archivo suelto sin
dependencias de ruta. Calibra iteraciones hasta pasar 1,2 s por medición y reporta la
mediana de 5.

El arnés acepta filtros para medir una celda sola:

```
host                        la matriz completa
host 87                     solo ML-DSA-87
host 87 decode+verify       solo esa celda
host --pausa 45             enfriamiento entre bloques (NO USAR, ver §6.1)
```

### En x86

```
cargo run --release --features jit
```

### En el teléfono

El intérprete solo (`wasmi` + nativo + RISC-V) compila en Termux sin problema:

```
pkg install -y rust
bash telefono/correr.sh
```

**Con JIT no compila en Termux.** `cranelift-codegen` hace desbordar la pila de rustc
—en el *parser*, no en codegen: el backend ARM64 que genera ISLE son bloques anidados a
una profundidad que `rustc_parse` no aguanta— y subir `RUST_MIN_STACK` hasta 1 GB no
alcanza. Hay que cross-compilar desde la PC:

```
rustup target add aarch64-linux-android
cargo build --release --target aarch64-linux-android --features jit
```

La configuración del linker está en `telefono/host/.cargo/config.toml`, y apunta a
`clang.exe` directo y no al wrapper `aarch64-linux-android30-clang.cmd` del NDK, que
tiene un bug: calcula el directorio del binario y después lo pisa con vacío justo antes
de usarlo, así que termina buscando `clang.exe` en el PATH.

Después se copia el ejecutable al teléfono y se hace `chmod +x` **dentro de `~`**: el
almacenamiento compartido (`/storage/emulated/0`, que es lo que Termux expone en
`~/storage/`) está montado `noexec` y no admite el bit de ejecución. Compilar o correr
desde ahí no funciona, con root o sin root.

### Los CSV crudos

| archivo | qué es |
|---|---|
| `resultados_pc.csv` | x86, cuatro motores con JIT |
| `resultados_rv_pc.csv` | x86, con los dos intérpretes RISC-V |
| `test2.csv` | ARM, sin JIT |
| `test2-jit.csv` | ARM, seis motores |
| `test2-87dv-frio.csv` | ARM, celda 87 `decode+verify` aislada y en frío |
| `test2-limpio.csv` | ARM, corrida con pausas — **contaminada**, ver §6.1 |
