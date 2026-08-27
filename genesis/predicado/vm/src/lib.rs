//! La maquina de §6.2 — Fase 4.
//!
//! **Acá cambia el lenguaje y es a proposito.** El resto de `genesis/` esta en
//! Python porque lo que modela son reglas, y las reglas se leen. Esto no: esto es
//! la pieza que I1 congela para siempre y la unica que corre codigo de terceros
//! bajo presupuesto. Reutiliza el interprete RV32IM del arnes de Test 2, que ya
//! tenia medido lo que importa —el conteo de pasos, identico entre x86 y ARM—.
//!
//! Los criterios de aprobado estan en `../CRITERIOS.md`, escritos antes de esto.

// **Acá no hay un solo numero de tiempo de reloj, y es una condicion y no un
// descuido.** El presupuesto en milisegundos vive en los binarios de medicion:
// una maquina de consenso que supiera cuanto tarda seria un oraculo (I2), y el
// unico recurso que puede contar es el que reproduce igual en todo hardware —los
// pasos y las paginas—. Hay una prueba en `pruebas/test_fase4_vm.py` que verifica
// que no se cuele un `f32`, un `f64` ni un literal decimal en todo el crate.

pub mod admision;
pub mod maquina;

pub use admision::{admitir, Rechazo};
pub use maquina::{Causa, Clase, Maquina, Op, Veredicto, MEM, TEXT_BASE};

/// El techo de pasos del ruleset inicial, de `protocolo/genesis.py`:
/// `f* × tiempo_de_bloque × R_declarado / tx_por_bloque`
/// = `0,25 × 6000 ms × 70 M pasos/s / 15`.
///
/// **Esta duplicado a proposito y hay una prueba que lo verifica contra el Python.**
/// Que el numero viva en dos lenguajes es exactamente el riesgo que I1 senala: se
/// chequea, no se confia.
pub const TECHO_INICIAL: u64 = 7_000_000;

/// `tx_por_bloque` del ruleset inicial. Bajo de 67 a 26 cuando la Fase 4 corrigio
/// `R_declarado`: el techo en pasos casi no se movio, lo que cambio es cuantos
/// pasos garantizados compra un segundo de reloj.
pub const TX_INICIAL: u64 = 15;


/// **El segundo techo, y el hallazgo de la Fase 4.**
///
/// El techo de pasos solo no alcanza: `lw` cuesta lo mismo que `addi` cuando el
/// dato esta en cache y veintitres veces mas cuando no, y **es el mismo opcode**,
/// asi que ninguna lectura del binario los distingue. Un predicado que persigue
/// punteros por 63 MiB gasta su techo de pasos en 596 ms en vez de los 22 que el
/// techo promete.
///
/// **Esto es el punto de Genesis, no una constante del protocolo.** Hasta el
/// 21/8/2026 lo era, y mientras lo fue el techo de paginas **excluia en vez de
/// encarecer**: una primitiva que necesitara mas memoria no tenia precio que pagar.
/// Ahora el presupuesto es un parametro del ruleset y pedir mas paginas baja el
/// ritmo declarado —ver `R_DECLARADO_POR_PAGINAS` en `protocolo/genesis.py`—, que
/// baja el techo de pasos. La maquina recibe los dos techos y no deriva ninguno.
pub const PAGINAS_INICIALES: u32 = 96;

/// Un hash chico para comparar salidas entre arquitecturas (C3). FNV-1a de 64
/// bits: no es criptografico y no pretende serlo — lo que tiene que hacer es
/// depender de todos los bytes y dar lo mismo en toda maquina, y eso lo hace.
pub fn huella(bytes: &[u8]) -> u64 {
    let mut h: u64 = 0xcbf2_9ce4_8422_2325;
    for b in bytes {
        h ^= *b as u64;
        h = h.wrapping_mul(0x0000_0100_0000_01b3);
    }
    h
}

/// Ensambla una instruccion tipo R (`add`, `mul`, `div`, ...).
pub fn r(f7: u32, rs2: u32, rs1: u32, f3: u32, rd: u32, opc: u32) -> u32 {
    (f7 << 25) | (rs2 << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | opc
}

/// Ensambla una instruccion tipo I (`addi`, `lw`, `jalr`, ...).
pub fn i(imm: i32, rs1: u32, f3: u32, rd: u32, opc: u32) -> u32 {
    (((imm as u32) & 0xfff) << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | opc
}

/// Ensambla un `jal`. El inmediato es relativo al propio `jal` y va en bytes.
pub fn jal(rd: u32, imm: i32) -> u32 {
    let u = imm as u32;
    ((u >> 20) & 1) << 31
        | ((u >> 1) & 0x3ff) << 21
        | ((u >> 11) & 1) << 20
        | ((u >> 12) & 0xff) << 12
        | (rd << 7)
        | 0x6f
}

/// El guest RV32IM de Test 2: el mismo `pqcore` que dio `steps_per_verify`.
///
/// **No se copia el archivo**, se apunta al que ya esta versionado en
/// `test2-interprete/`. Es la carga de trabajo real de C1 y la prueba de
/// regresion de que la maquina endurecida no cambio ni una unidad la semantica.
pub const GUEST_RV: &[u8] =
    include_bytes!("../../../../test2-interprete/telefono/guest-rv/guest.elf");

/// Un SHA-256 escrito a mano y compilado a RV32IM (`guest-sha/`).
///
/// **Es el insumo que le faltaba al piso de §8.5**, y de paso es la segunda carga
/// independiente que pasa por la admision: el guest de Test 2 lo produjo otro repo y
/// este lo produjo el nuestro, asi que C2 y C4 quedan probados contra dos binarios y
/// no contra uno.
pub const GUEST_SHA: &[u8] = include_bytes!("../guest-sha/guest.elf");
