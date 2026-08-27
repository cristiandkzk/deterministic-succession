//! **De qué depende el 23×.** La segunda mitad de C7.
//!
//! `mezclas` dijo *que* el paso no es una unidad honesta. Esto pregunta *por qué*,
//! porque la respuesta decide cuál de las dos salidas del criterio sirve.
//!
//! Si el 23× fuera del opcode —una division cuesta veinte sumas— la salida seria
//! pesar el paso por clase, que es lo que hace el gas. Pero la mezcla que lo
//! produce es `lw`, y `lw` ya cuesta lo mismo que `addi` cuando el dato esta en
//! cache: `lw-secuencial` corre a 224 y `lw-persecucion` a 11. **Es el mismo
//! opcode.** Lo que cambia es cuánta memoria toca el programa, y eso no se puede
//! leer del binario.
//!
//! Dos mediciones:
//!
//! 1. el ritmo de la persecucion en funcion del tamano de la region, de 16 KiB a
//!    63 MiB. Dice dónde deja de morder el cache;
//! 2. cuántas paginas de 4 KiB toca de verdad una verificacion ML-DSA-44. Dice si
//!    un limite de memoria chico deja pasar la carga real o la mata.
//!
//!     cargo run --release --bin conjunto

use std::time::Instant;
use vm::maquina::{Maquina, Veredicto, MEM};
use vm::{i, jal};

const CUERPO: usize = 1024;
const DATOS: u32 = 1 << 20;

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
fn lw(rd: u32, rs1: u32, off: i32) -> u32 {
    i(off, rs1, 2, rd, 0x03)
}

/// `li rd, dir` — el idioma de RISC-V, con el redondeo que hay que hacer.
///
/// **La version ingenua —`lui` + `addi` con los doce bits bajos— arruino la seccion 4
/// de este mismo archivo y la peor mezcla de `mezclas`.** El inmediato de `addi` es de
/// doce bits con signo: con los bajos >= 2048 resta 4096 en vez de sumar. La
/// persecucion arrancaba en la pagina anterior, leia un cero, y despues seguia el
/// puntero cero — leyendo siempre la misma direccion, siempre en L1, e informando un
/// numero perfectamente creible.
fn cargar_direccion(rd: u32, dir: u32) -> [u32; 2] {
    let alto = (dir.wrapping_add(0x800)) >> 12;
    let bajo = (dir as i32) - ((alto << 12) as i32);
    [lui(rd, alto), i(bajo, rd, 0, rd, 0x13)]
}

/// La misma persecucion de `mezclas`, pero confinada a `region` bytes.
fn persecucion(region: u32) -> (Vec<u32>, Vec<u8>) {
    let lineas = (region / 64) as usize;
    let mut orden: Vec<u32> = (0..lineas).map(|k| DATOS + (k as u32) * 64).collect();
    let mut g = Lcg(0xDEADBEEF12345678);
    for k in (1..orden.len()).rev() {
        let j = (g.sig() as usize) % (k + 1);
        orden.swap(k, j);
    }
    let mut ram = vec![0u8; region as usize];
    for k in 0..orden.len() {
        let sig = orden[(k + 1) % orden.len()];
        let off = (orden[k] - DATOS) as usize;
        ram[off..off + 4].copy_from_slice(&sig.to_le_bytes());
    }
    let mut p = vec![lui(5, DATOS >> 12), lw(5, 5, 0)];
    p.extend((0..CUERPO).map(|_| lw(5, 5, 0)));
    p.push(jal(0, -4 * CUERPO as i32));
    (p, ram)
}

fn ritmo(programa: &[u32], ram: &[u8]) -> f64 {
    let mut m = Maquina::desde_palabras(programa, 0);
    assert!(m.escribir(DATOS, ram));
    let mut tramo: u64 = 1 << 18;
    loop {
        m.techo = m.pasos + tramo;
        let t0 = Instant::now();
        let v = m.correr();
        let dt = t0.elapsed().as_secs_f64();
        assert_eq!(v, Veredicto::TechoExcedido);
        if dt > 0.4 || tramo > (1 << 29) {
            return (tramo as f64) / dt / 1e6;
        }
        tramo *= 2;
    }
}

fn main() {
    println!("# 1. ritmo de la persecucion segun el tamano de la region");
    println!("region_KiB,ritmo_Mpasos_s,cociente_vs_ML_DSA");
    // 260,4 M pasos/s: ML-DSA-44 medido en esta misma maquina por `mezclas`.
    let referencia = 260.4_f64;
    for kib in [16u32, 64, 128, 192, 256, 384, 512, 1024, 2048, 4096, 16384] {
        let region = kib * 1024;
        if region >= MEM - DATOS {
            continue;
        }
        let (p, ram) = persecucion(region);
        let mp = ritmo(&p, &ram);
        println!("{},{:.1},{:.2}", kib, mp, mp / referencia);
    }

    println!();
    println!("# 2. conjunto de trabajo real de una verificacion ML-DSA-44");
    let (mut m, syms) = vm::admitir(vm::GUEST_RV, u64::MAX).expect("admitir guest");
    m.arrancar();
    let prepare = *syms.get("prepare").expect("prepare");
    let run = *syms.get("run").expect("run");
    m.llamar(prepare, &[0]);

    m.borrar_paginas();
    let p0 = m.pasos;
    m.llamar(run, &[0, 1]);
    let pasos = m.pasos - p0;
    let paginas = m.paginas_tocadas();

    println!("paginas_4KiB,KiB,pasos");
    println!("{},{},{}", paginas, paginas * 4, pasos);
    println!();
    println!(
        "# una verificacion toca {} KiB. El techo declara {} MiB de memoria.",
        paginas * 4,
        MEM / (1024 * 1024)
    );

    // ------------------------------------------------------------------ #
    // 3. La segunda palanca: el tamano del texto.
    //
    // Acotar los datos no alcanza si el programa puede ser inmenso. Este
    // interprete predecodifica el texto a un arreglo de `Insn` de 8 bytes, asi
    // que un binario grande recorrido con saltos impredecibles hace fallar el
    // cache del **host** sin tocar un solo byte de la memoria del guest. Es el
    // mismo ataque por otra puerta, y si esta abierta, cerrar la primera no sirve.
    // ------------------------------------------------------------------ #
    println!();
    println!("# 3. ritmo con saltos impredecibles segun el tamano del texto");
    println!("texto_KiB,insn,ritmo_Mpasos_s,cociente_vs_ML_DSA");
    for kib in [4u32, 32, 128, 512, 1024] {
        let insn = (kib as usize * 1024) / 4;
        let mut g = Lcg(0x5DEECE66D);
        // Cada instruccion es un `jal` a otra posicion del texto, elegida al azar.
        // El rango de `jal` es +-1 MiB, que es por que el barrido para ahi.
        let mut p: Vec<u32> = Vec::with_capacity(insn);
        for k in 0..insn {
            let destino = (g.sig() as usize) % insn;
            let salto = (destino as i64 - k as i64) * 4;
            p.push(jal(0, salto as i32));
        }
        let mut m = Maquina::desde_palabras(&p, 0);
        let mut tramo: u64 = 1 << 20;
        let mp = loop {
            m.techo = m.pasos + tramo;
            let t0 = Instant::now();
            let v = m.correr();
            let dt = t0.elapsed().as_secs_f64();
            assert_eq!(v, Veredicto::TechoExcedido);
            if dt > 0.4 || tramo > (1 << 29) {
                break (tramo as f64) / dt / 1e6;
            }
            tramo *= 2;
        };
        println!("{},{},{:.1},{:.2}", kib, insn, mp, mp / referencia);
    }

    // ------------------------------------------------------------------ #
    // 4. Acotar el tamano de la region no sirve: la imagen del guest sola son
    //    253 KiB. Lo que hay que acotar son las **paginas tocadas**, que es lo
    //    que la instrumentacion ya sabe contar. Pero un programa puede tocar 48
    //    paginas juntas o 48 desparramadas por 64 MiB. Si desparramarlas es peor,
    //    contar paginas no alcanza y hace falta algo mas.
    // ------------------------------------------------------------------ #
    println!();
    println!("# 4. {} paginas ({} KiB) juntas contra desparramadas por 64 MiB",
        vm::PAGINAS_INICIALES, vm::PAGINAS_INICIALES * 4);
    println!("disposicion,ritmo_Mpasos_s,cociente_vs_ML_DSA");
    for (nombre, desparramar) in [("juntas", false), ("desparramadas", true)] {
        let pgs_n: usize = vm::PAGINAS_INICIALES as usize;
        let mut g = Lcg(0xC0FFEE);
        let paginas: Vec<u32> = if desparramar {
            let total = (MEM - DATOS) / 4096;
            let mut v: Vec<u32> = (0..pgs_n)
                .map(|_| DATOS + (g.sig() % total) * 4096)
                .collect();
            v.sort_unstable();
            v.dedup();
            while v.len() < pgs_n {
                let c = DATOS + (g.sig() % total) * 4096;
                if !v.contains(&c) {
                    v.push(c);
                }
            }
            v
        } else {
            (0..pgs_n as u32).map(|k| DATOS + k * 4096).collect()
        };
        // Una permutacion de todas las lineas de cache de esas paginas.
        let mut lineas: Vec<u32> = paginas
            .iter()
            .flat_map(|pg| (0..64u32).map(move |l| pg + l * 64))
            .collect();
        for k in (1..lineas.len()).rev() {
            let j = (g.sig() as usize) % (k + 1);
            lineas.swap(k, j);
        }
        let mut prog = cargar_direccion(5, lineas[0]).to_vec();
        prog.push(lw(5, 5, 0));
        prog.extend((0..CUERPO).map(|_| lw(5, 5, 0)));
        prog.push(jal(0, -4 * CUERPO as i32));

        let mut m = Maquina::desde_palabras(&prog, 0);
        for k in 0..lineas.len() {
            let sig = lineas[(k + 1) % lineas.len()];
            assert!(m.escribir(lineas[k], &sig.to_le_bytes()));
        }
        let mut tramo: u64 = 1 << 18;
        let mp = loop {
            m.techo = m.pasos + tramo;
            let t0 = Instant::now();
            let v = m.correr();
            let dt = t0.elapsed().as_secs_f64();
            assert_eq!(v, Veredicto::TechoExcedido);
            if dt > 0.4 || tramo > (1 << 29) {
                // Declarar cuantas paginas tiene que tocar y verificarlo es lo que
                // habria cazado el bug de la direccion en la primera corrida.
                assert_eq!(
                    m.paginas_usadas, pgs_n as u32,
                    "{} declaro {} paginas y toco {}",
                    nombre, pgs_n, m.paginas_usadas
                );
                break (tramo as f64) / dt / 1e6;
            }
            tramo *= 2;
        };
        println!("{},{:.1},{:.2}", nombre, mp, mp / referencia);
    }
}
