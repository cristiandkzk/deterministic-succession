//! **C3 — el conteo de pasos reproduce bit a bit entre x86-64 y ARM64.**
//!
//! No hay tolerancia y no puede haberla: si dos nodos cuentan distinto, la
//! impugnacion no tiene resultado. Y el conteo solo no alcanza como prueba —dos
//! semanticas distintas pueden retirar la misma cantidad de instrucciones y dejar
//! registros distintos—, asi que cada vector lleva **tres** cosas: el veredicto
//! canonico, los pasos, y una huella de los 32 registros mas 4 KiB de memoria.
//!
//!     cargo run --release --bin vectores            # imprime la tabla
//!     cargo run --release --bin vectores verificar  # la compara con vectores.csv
//!
//! Para cerrar C3 hay que correrlo en las dos arquitecturas. `vectores.csv` esta
//! versionado con lo que dio en x86-64; el teléfono lo verifica con `verificar`.

use std::collections::BTreeMap;
use vm::maquina::{Maquina, MEM, PAGINA};
use vm::{i, jal, r};

const DATOS: u32 = 1 << 20;
const VENTANA: u32 = 4096;
const CSV: &str = include_str!("../../vectores.csv");

struct Lcg(u64);
impl Lcg {
    fn sig(&mut self) -> u32 {
        self.0 = self.0.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
        (self.0 >> 33) as u32
    }
}

fn lui(rd: u32, top: u32) -> u32 {
    (top << 12) | (rd << 7) | 0x37
}
fn addi(rd: u32, rs1: u32, imm: i32) -> u32 {
    i(imm, rs1, 0, rd, 0x13)
}
fn s_type(imm: i32, rs2: u32, rs1: u32, f3: u32) -> u32 {
    let u = imm as u32;
    ((u >> 5) & 0x7f) << 25 | (rs2 << 20) | (rs1 << 15) | (f3 << 12) | ((u & 0x1f) << 7) | 0x23
}
fn b_type(imm: i32, rs2: u32, rs1: u32, f3: u32) -> u32 {
    let u = imm as u32;
    ((u >> 12) & 1) << 31
        | ((u >> 5) & 0x3f) << 25
        | (rs2 << 20)
        | (rs1 << 15)
        | (f3 << 12)
        | ((u >> 1) & 0xf) << 8
        | ((u >> 11) & 1) << 7
        | 0x63
}

/// **El vector grande: un flujo pseudoaleatorio que toca todo el ISA.**
///
/// Cubrir cada opcode con un programa a mano seria mucho codigo y menos cobertura:
/// lo que bifurca una cadena no suele ser un opcode olvidado sino un caso borde de
/// uno que si esta —el desplazamiento de 33, el `sra` de un negativo, el `divu`
/// por cero—. Un flujo largo con operandos que se realimentan los recorre solos.
///
/// Dos disciplinas para que el flujo sea util y no caotico:
///
/// - `x10` queda **fijo** en la base de datos y nunca es destino, asi que toda
///   direccion efectiva cae dentro del rango y ningun vector termina en trampa por
///   accidente;
/// - los saltos condicionales van siempre a `+8`, asi que el control avanza y el
///   programa termina. Los saltos de verdad se prueban aparte.
fn flujo_del_isa(n: usize) -> Vec<u32> {
    let mut g = Lcg(0x243F6A8885A308D3);
    let mut p = vec![lui(10, DATOS >> 12)];
    // Semillas variadas: ceros, negativos, el minimo, el maximo.
    for (k, v) in [0u32, 1, 0x8000_0000, 0xffff_ffff, 0x7fff_ffff, 33, 0xdead_beef]
        .into_iter()
        .enumerate()
    {
        p.push(lui(11 + k as u32, v >> 12));
        p.push(addi(11 + k as u32, 11 + k as u32, (v & 0xfff) as i32));
    }
    for _ in 0..n {
        // Destinos: cualquiera menos x0 (descartado) y x10 (la base fija).
        let rd = 1 + g.sig() % 30;
        let rd = if rd >= 10 { rd + 1 } else { rd };
        let rs1 = g.sig() % 32;
        let rs2 = g.sig() % 32;
        p.push(match g.sig() % 12 {
            0 => r(0x00, rs2, rs1, g.sig() % 8, rd, 0x33), // add/sll/slt/xor/srl/or/and
            1 => r(0x20, rs2, rs1, if g.sig() % 2 == 0 { 0 } else { 5 }, rd, 0x33), // sub/sra
            2 => r(0x01, rs2, rs1, g.sig() % 8, rd, 0x33), // mul/div/rem
            3 => addi(rd, rs1, (g.sig() % 4096) as i32 - 2048),
            // slti/sltiu/xori/ori/andi. **Sin f3=5**: ahi vive `srli`/`srai`, que
            // exigen que los siete bits altos del inmediato sean 0x00 o 0x20, y un
            // inmediato al azar los deja en cualquier cosa. La primera version de
            // este generador no lo excluia y el flujo moria en trampa a los 22 pasos.
            4 => i(
                (g.sig() % 4096) as i32 - 2048,
                rs1,
                [2, 3, 4, 6, 7][(g.sig() % 5) as usize],
                rd,
                0x13,
            ),
            5 => i((g.sig() % 32) as i32, rs1, 1, rd, 0x13),                        // slli
            6 => i((g.sig() % 32) as i32, rs1, 5, rd, 0x13),                        // srli
            7 => i(0x400 | (g.sig() % 32) as i32, rs1, 5, rd, 0x13),                // srai
            8 => i((g.sig() % 2048) as i32, 10, g.sig() % 3, rd, 0x03),             // lb/lh/lw
            9 => i((g.sig() % 2048) as i32, 10, 4 + g.sig() % 2, rd, 0x03),         // lbu/lhu
            10 => s_type((g.sig() % 2048) as i32, rs2, 10, g.sig() % 3),            // sb/sh/sw
            _ => b_type(8, rs2, rs1, [0, 1, 4, 5, 6, 7][(g.sig() % 6) as usize]),
        });
    }
    // Cuatro `ecall` y no uno: los saltos condicionales van a `+8`, asi que el
    // ultimo del flujo puede saltear el final. Con uno solo el vector terminaba en
    // `PcFueraDelTexto` en vez de terminar — determinista igual, pero probando menos.
    p.extend([0x73u32; 4]);
    p
}

struct Vector {
    nombre: &'static str,
    prog: Vec<u32>,
    techo: u64,
    paginas: u32,
}

fn v(nombre: &'static str, prog: Vec<u32>, techo: u64, paginas: u32) -> Vector {
    Vector { nombre, prog, techo, paginas }
}

fn vectores() -> Vec<Vector> {
    let mut vs = Vec::new();
    vs.push(v("isa-revuelto-200k", flujo_del_isa(200_000), u64::MAX, u32::MAX));

    // Los bordes de la division, que es donde RV32M define lo que otros ISA
    // dejan como trampa. Si una implementacion los tomara del hardware anfitrion,
    // x86 y ARM darian distinto — y es exactamente el caso que hay que fijar.
    let mut p = vec![lui(10, DATOS >> 12), addi(5, 0, -1), addi(6, 0, 0), lui(7, 0x80000)];
    for (f3, k) in [(4u32, 0u32), (5, 1), (6, 2), (7, 3)] {
        p.push(r(0x01, 6, 5, f3, 8, 0x33)); // divisor cero
        p.push(s_type((k * 8) as i32, 8, 10, 2));
        p.push(r(0x01, 5, 7, f3, 9, 0x33)); // INT_MIN / -1
        p.push(s_type((k * 8 + 4) as i32, 9, 10, 2));
    }
    p.push(0x73);
    vs.push(v("division-bordes", p, 1000, u32::MAX));

    // Los tres finales que no son retorno. Un veredicto es dato de consenso: se
    // fija su codificacion canonica, no solo que ocurra.
    vs.push(v("trampa-lectura", vec![lui(5, MEM >> 12), i(0, 5, 2, 6, 0x03), jal(0, 0)], 100, u32::MAX));
    vs.push(v("trampa-pc", vec![jal(0, 4096)], 100, u32::MAX));
    vs.push(v("techo-pasos", vec![jal(0, 0)], 4_242, u32::MAX));
    vs.push(v(
        "techo-paginas",
        vec![
            lui(5, DATOS >> 12),
            lui(7, PAGINA >> 12),
            i(0, 5, 2, 6, 0x03),
            r(0x00, 7, 5, 0, 5, 0x33),
            jal(0, -8),
        ],
        10_000,
        7,
    ));
    vs
}

/// `nombre -> "veredicto,pasos,huella"`.
fn medir() -> BTreeMap<String, String> {
    let mut fila = BTreeMap::new();
    for vec in vectores() {
        let mut m = Maquina::desde_palabras(&vec.prog, vec.techo);
        m.techo_paginas = vec.paginas;
        let ver = m.correr();
        let canon = ver
            .canonico()
            .iter()
            .map(|b| format!("{:02x}", b))
            .collect::<String>();
        fila.insert(
            vec.nombre.to_string(),
            format!(
                "{},{},{},{:016x}",
                canon,
                m.pasos,
                m.paginas_usadas,
                m.huella_estado(DATOS, VENTANA)
            ),
        );
    }

    // Y la carga real: el ELF de Test 2, el mismo que dio `steps_per_verify`.
    if let Ok((mut m, syms)) = vm::admitir(vm::GUEST_RV, u64::MAX) {
        m.arrancar();
        if let (Some(prep), Some(run)) = (syms.get("prepare"), syms.get("run")) {
            m.llamar(*prep, &[0]);
            m.borrar_paginas();
            let base = m.pasos;
            let ver = m.llamar(*run, &[0, 1]);
            let canon = ver.canonico().iter().map(|b| format!("{:02x}", b)).collect::<String>();
            fila.insert(
                "mldsa44-una-verificacion".to_string(),
                format!(
                    "{},{},{},{:016x}",
                    canon,
                    m.pasos - base,
                    m.paginas_usadas,
                    m.huella_estado(0x3f000, VENTANA)
                ),
            );
        }
    }
    fila
}

fn esperado() -> BTreeMap<String, String> {
    CSV.lines()
        .filter(|l| !l.trim().is_empty() && !l.starts_with('#') && !l.starts_with("vector,"))
        .filter_map(|l| l.split_once(','))
        .map(|(n, resto)| (n.to_string(), resto.trim().to_string()))
        .collect()
}

fn main() {
    let medido = medir();
    let verificar = std::env::args().nth(1).as_deref() == Some("verificar");

    if !verificar {
        println!("# vectores de C3 — arquitectura: {}", std::env::consts::ARCH);
        println!("# veredicto canonico (5 bytes), pasos, paginas, huella de 32 registros + 4 KiB");
        println!("vector,veredicto,pasos,paginas,huella");
        for (n, r) in &medido {
            println!("{},{}", n, r);
        }
        return;
    }

    let esp = esperado();
    if esp.is_empty() {
        println!("vectores.csv esta vacio: generar primero sin argumentos");
        std::process::exit(2);
    }
    let mut difieren = 0;
    println!("# verificando contra vectores.csv — arquitectura: {}", std::env::consts::ARCH);
    for (n, e) in &esp {
        match medido.get(n) {
            Some(m) if m == e => println!("ok   {}", n),
            Some(m) => {
                difieren += 1;
                println!("DIFIERE {}\n  esperado: {}\n  medido:   {}", n, e, m);
            }
            None => {
                difieren += 1;
                println!("FALTA {}", n);
            }
        }
    }
    println!();
    if difieren == 0 {
        println!("# C3 en {}: los {} vectores reproducen bit a bit.", std::env::consts::ARCH, esp.len());
    } else {
        println!("# C3 REPROBADO: {} de {} vectores difieren.", difieren, esp.len());
        std::process::exit(1);
    }
}
