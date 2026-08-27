# La máquina — §6.2, Fase 4

**Acá cambia el lenguaje y es a propósito.** El resto de `genesis/` está en Python porque lo que
modela son reglas, y las reglas se leen. Esto no: es la pieza que I1 congela para siempre y la
única que corre código de terceros bajo presupuesto.

No se escribió de cero. Reutiliza el intérprete RV32IM del arnés de `test2-interprete/telefono`,
que ya tenía lo caro medido: el set completo, el predecodificado, y el conteo de pasos que
reproduce byte a byte entre x86 y ARM. **Lo que cambia es quién escribe el programa.** Aquél
corría un guest propio; éste corre el programa de la contraparte de una impugnación, que quiere
que el nodo se cuelgue o se caiga.

```
src/
├── lib.rs        # las constantes de Genesis y los ensambladores del arnés
├── maquina.rs    # el intérprete: dos techos, trampas, veredictos canónicos
├── admision.rs   # lo que se decide antes de gastar el primer paso
└── bin/          # las mediciones — ver ../RESULTADOS.md
tests/criterios.rs  # C2, C4, C5, C6 y la regresión contra Test 2
```

## Las cuatro diferencias con el arnés, y todas son de consenso

- **el techo corta.** El arnés cuenta pasos y no para nunca. Acá `pasos` es un presupuesto: al
  agotarse la máquina para en el paso exacto y devuelve un veredicto. Es lo que impide que exista
  una impugnación más cara de verificar que de crear;
- **hay un segundo techo.** Páginas distintas tocadas. **Es el hallazgo de la Fase 4:** `lw`
  cuesta lo mismo que `addi` con el dato en caché y veintitrés veces más sin él, y es el mismo
  opcode, así que ningún peso por instrucción los separa;
- **fuera de rango es trampa, no envolver.** El arnés hace `dir & MASK`: determinista, pero
  **depende del tamaño de memoria**, y con eso el mismo programa daría distinto en dos
  generaciones. Rompe I1 justo donde no se puede;
- **todo final es un veredicto, no un `Err`.** Las dos partes de una impugnación tienen que leer
  lo mismo. El final entra al hash del bloque, así que se codifica en cinco bytes sin texto.

## Dos cosas que no están, y no por olvido

**No hay dependencias.** Cada crate que entrara sería código que un día se actualiza, y un cambio
de semántica entre dos versiones es una bifurcación de consenso que nadie eligió.

**No hay un solo número de tiempo de reloj.** Una máquina de consenso que supiera cuánto tarda
sería un oráculo (I2). Los únicos recursos que puede contar son los que reproducen igual en todo
hardware: pasos y páginas. Los milisegundos viven en los binarios de medición, y hay una prueba
en `pruebas/test_fase4_vm.py` que verifica que no se cuele ni un `f32`, ni un `f64`, ni un
literal decimal en todo el crate.

## Correrlo

```
cargo test --release              # los criterios que son propiedades
cargo run --release --bin mezclas    # C7 — el ritmo por mezcla de instrucciones
cargo run --release --bin conjunto   # de qué depende: memoria y tamaño de texto
cargo run --release --bin bloque     # C1 — 26 verificaciones como un bloque
cargo run --release --bin vectores            # genera la tabla de C3
cargo run --release --bin vectores verificar  # la compara con vectores.csv
```

### En el teléfono (Termux, aarch64) — lo que falta para cerrar C3

**Este crate no es autocontenido:** `lib.rs` hace `include_bytes!` del ELF del guest de Test 2,
que vive cuatro niveles más arriba. Copiar sólo esta carpeta al teléfono no compila. El paquete
mínimo —con las rutas relativas intactas, ~130 KB— lo arma:

```
python genesis/herramientas/empaquetar_vm.py --probar
```

`--probar` lo extrae en un directorio limpio y lo compila ahí, que es la única forma de saber
que no falta nada: un paquete que compila *porque el resto del repo estaba al lado* no sirve
para lo que se hizo.

Después, en Termux:

```
pkg install -y rust tar
tar xzf vm-telefono.tar.gz
cd genesis/predicado/vm
cargo run --release --bin vectores verificar
```

Compila en segundos: **el crate no tiene dependencias**, así que no hay red, ni registro, ni los
veinte minutos que tardaba el arnés de Test 2 con `wasmtime`.

Los siete vectores tienen que dar idénticos. **No hay tolerancia**: si dos nodos cuentan
distinto, la impugnación no tiene resultado.

Y de paso conviene correr `bloque` ahí, porque **el hardware de referencia del protocolo es el
teléfono y no un escritorio**: el margen de C1 que hay medido es el de x86-64.
