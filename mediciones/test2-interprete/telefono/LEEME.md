# Test 2 — cómo correrlo en el teléfono

Mismo teléfono que cerró el eje ARM en `Chain` (Motorola Edge 40 Neo, Termux, aarch64).

```
pkg install -y rust
cd telefono
bash correr.sh          # interpretes + nativo
bash correr.sh jit      # + Cranelift JIT y Pulley (compila lento)
```

Qué mide cada motor:

| motor | qué representa |
|---|---|
| `native` | baseline: la primitiva como código de nodo, lo que §6.6 quiere evitar |
| `wasmtime-cranelift` | bytecode con JIT — determinista igual, disponible en Android |
| `wasmi` | interprete puro de registros — el perfil "VM de cadena" |
| `wasmtime-pulley` | interprete portable, cota pesimista |
| `rv32im` | interprete RV32IM propio — la máquina chica a 32 bits |
| `rv64imac` | el mismo interprete a 64 bits — la máquina chica con el ancho correcto |

`decode+verify` es el número honesto: un nodo recibe clave y firma como bytes en cada
transacción. `verify_only` es el caso con la clave ya expandida en memoria.

## Los dos guests

Es el **mismo `pqcore`** compilado a dos ISA distintos:

- `guest/guest.wasm` — target `wasm32-unknown-unknown`.
- `guest-rv/guest.elf` — target `riscv32im-unknown-none-elf`, más el andamiaje
  bare-metal de `guest-rv/src/` (allocator propio: RV32IM no tiene la extensión A,
  así que no hay CAS y ningún allocator con spinlock compila).

Los dos exponen la misma ABI (`prepare(level)`, `run(mode, iters)`), así que el
código medido es idéntico y lo único que cambia es el motor.

Ambos van versionados: el teléfono no necesita ninguno de los dos toolchains.
Para regenerarlos hace falta `rustup target add wasm32-unknown-unknown` /
`riscv32im-unknown-none-elf` y correr `construir-rv.sh` (RISC-V).

## La columna `steps_per_verify`

Solo la reporta `rv32im`: es el conteo exacto de instrucciones retiradas por
verificación. Es determinístico e independiente del hardware — la misma cifra en
x86 y en ARM — que es exactamente lo que pide el techo de pasos de RESULTADOS §4.1.
`wasmi` y `wasmtime` tienen conteo de *fuel*, pero es una feature del motor y no
del spec de Wasm, así que no sirve como primitiva de consenso sin fijar además
una versión del motor.

## Por qué los dos intérpretes RISC-V están escritos a mano

Para que la comparación mida el ISA y no la calidad de un emulador de terceros,
y porque el punto que se evalúa es justamente que el set entra en un archivo.
Los dos usan el mismo diseño —predecodificar una vez, despachar por match— así
que el par RV32/RV64 aísla una sola variable: el ancho de registro.

`rv64` tiene una vuelta de más que `rv32` no necesita. Con instrucciones
comprimidas una instrucción puede empezar en cualquier dirección par, así que la
versión ingenua indexa la tabla predecodificada cada 2 bytes y queda con el
doble de entradas, la mitad basura. Eso costaba ~1,5× por instrucción y no tiene
nada que ver con el ISA. La versión actual hace un **barrido lineal** del texto
—lee el largo real y avanza por él— y deja `code` con una entrada por
instrucción y sin huecos; el sucesor en caída libre es la entrada siguiente del
arreglo. Una tabla aparte traduce dirección a índice y solo se consulta cuando
el control salta. Con eso el costo por instrucción de RV64 quedó en 1,04-1,18×
el de RV32, que es lo que explica el tamaño de la entrada decodificada (12 vs 8
bytes), no las comprimidas.

Los conteos de `steps_per_verify` no cambiaron ni una unidad con ese arreglo:
son la prueba de regresión de que la semántica quedó intacta.
