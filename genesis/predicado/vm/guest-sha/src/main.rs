//! **El insumo que le falta al piso de §8.5: cuántos pasos cuesta un SHA-256.**
//!
//! La Fase 5 escribió la cuenta del piso y quedó colgando de este número. El piso es el
//! costo del ciclo crear + desalojar medido contra el presupuesto del nodo, y sacada la
//! verificación de firma —que ya la paga el fee de §6.1— **lo que queda es trabajo de
//! árbol, o sea hashes**. Mover el estimado por 10x movia el piso por 10x, asi que el
//! numero no estaba cerrado.
//!
//! Esto es el mismo trabajo que produjo `steps_per_verify` en Test 2: compilar la
//! primitiva a la maquina chica y contar. El conteo es **exacto y reproduce entre
//! arquitecturas** por la misma razon que aquel — es una propiedad del programa, no del
//! reloj.
//!
//! ## Por que escrito a mano y sin dependencias
//!
//! Lo que se mide es el costo del algoritmo en esta maquina. Una implementacion de
//! terceros metaria sus propias decisiones —desenrollado, tablas, tamano contra
//! velocidad— en el medio del numero, y despues no se sabria si el piso salio de
//! SHA-256 o de como alguien lo compilo. Esta es la version del libro: sin desenrollar,
//! sin tablas mas alla de las constantes que el estandar define.

#![no_std]
#![no_main]

use core::panic::PanicInfo;

core::arch::global_asm!(
    r#"
    .section .text._start
    .globl _start
_start:
    .option push
    .option norelax
    la   gp, __global_pointer$
    .option pop
    li   sp, 0x04000000
    ecall
    "#
);

/// Las constantes de ronda del estandar. No es una eleccion de implementacion: son los
/// primeros treinta y dos bits de la parte fraccionaria de las raices cubicas de los
/// primeros sesenta y cuatro primos.
const K: [u32; 64] = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4,
    0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe,
    0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f,
    0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
    0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc,
    0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
    0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116,
    0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7,
    0xc67178f2,
];

const H0: [u32; 8] = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab,
    0x5be0cd19,
];

/// Una compresion: el bloque de 512 bits que el estandar llama `f`.
///
/// **Es la unidad que el piso necesita.** Una actualizacion del arbol son ~26 de estas
/// —la altura del arbol sobre el presupuesto de disco—, y el ciclo crear + desalojar son
/// dos actualizaciones.
#[inline(never)]
fn comprimir_uno(estado: &mut [u32; 8], bloque: &[u32; 16]) {
    let mut w = [0u32; 64];
    let mut i = 0;
    while i < 16 {
        w[i] = bloque[i];
        i += 1;
    }
    while i < 64 {
        let s0 = w[i - 15].rotate_right(7) ^ w[i - 15].rotate_right(18) ^ (w[i - 15] >> 3);
        let s1 = w[i - 2].rotate_right(17) ^ w[i - 2].rotate_right(19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16]
            .wrapping_add(s0)
            .wrapping_add(w[i - 7])
            .wrapping_add(s1);
        i += 1;
    }

    let (mut a, mut b, mut c, mut d) = (estado[0], estado[1], estado[2], estado[3]);
    let (mut e, mut f, mut g, mut h) = (estado[4], estado[5], estado[6], estado[7]);

    let mut r = 0;
    while r < 64 {
        let s1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
        let ch = (e & f) ^ ((!e) & g);
        let t1 = h
            .wrapping_add(s1)
            .wrapping_add(ch)
            .wrapping_add(K[r])
            .wrapping_add(w[r]);
        let s0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
        let maj = (a & b) ^ (a & c) ^ (b & c);
        let t2 = s0.wrapping_add(maj);

        h = g;
        g = f;
        f = e;
        e = d.wrapping_add(t1);
        d = c;
        c = b;
        b = a;
        a = t1.wrapping_add(t2);
        r += 1;
    }

    estado[0] = estado[0].wrapping_add(a);
    estado[1] = estado[1].wrapping_add(b);
    estado[2] = estado[2].wrapping_add(c);
    estado[3] = estado[3].wrapping_add(d);
    estado[4] = estado[4].wrapping_add(e);
    estado[5] = estado[5].wrapping_add(f);
    estado[6] = estado[6].wrapping_add(g);
    estado[7] = estado[7].wrapping_add(h);
}

/// Corre `n` compresiones encadenadas y devuelve una palabra del estado.
///
/// **Se devuelve algo para que el optimizador no borre el trabajo**, que es la misma
/// precaucion que toma el guest de Test 2. Y se encadenan —cada bloque depende del
/// estado anterior— para que tampoco pueda sacarlas del bucle.
#[no_mangle]
pub extern "C" fn comprimir(n: u32) -> u32 {
    let mut estado = H0;
    let mut bloque = [0u32; 16];
    let mut k = 0;
    while k < n {
        bloque[0] = estado[0] ^ k;
        bloque[15] = k;
        comprimir_uno(&mut estado, &bloque);
        k += 1;
    }
    estado[0]
}

#[panic_handler]
fn panicked(_: &PanicInfo) -> ! {
    unsafe {
        core::arch::asm!("li a0, 0xdead", "ecall", "1: j 1b", options(noreturn));
    }
}
