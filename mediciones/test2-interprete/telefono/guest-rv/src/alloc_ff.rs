//! Allocator de first-fit con lista libre ordenada por direccion.
//!
//! RV32IM no trae la extension A, asi que no hay compare-and-swap y ningun
//! allocator basado en spinlock compila para ese target. El guest es monohilo,
//! de modo que la lista va en `static mut` sin sincronizacion.
//!
//! Granularidad de 16 bytes, cabecera de 16 bytes por bloque asignado. Se
//! fusiona con el vecino anterior y el siguiente en cada `dealloc`, asi el
//! heap no se fragmenta a lo largo de millones de verificaciones.
//!
//! Escrito en `usize` para que sirva igual al guest de 32 y al de 64 bits: el
//! guest RV64 lo incluye con `#[path]` en vez de duplicarlo.

use core::alloc::{GlobalAlloc, Layout};

const GRAN: usize = 16;
const HDR: usize = 16;
/// La direccion 0 nunca cae en el heap (el texto arranca en 0x1000), asi que
/// sirve de centinela de fin de lista.
const NIL: usize = 0;

#[inline(always)]
fn round_up(v: usize) -> usize {
    (v + GRAN - 1) & !(GRAN - 1)
}

#[inline(always)]
unsafe fn rd(a: usize) -> usize {
    *(a as *const usize)
}

#[inline(always)]
unsafe fn wr(a: usize, v: usize) {
    *(a as *mut usize) = v;
}

// Bloque libre:     [usize size][usize next]
// Bloque asignado:  [usize size][usize _   ] y el payload arranca en blk + HDR
#[inline(always)]
unsafe fn size_of_blk(b: usize) -> usize {
    rd(b)
}
#[inline(always)]
unsafe fn next_of(b: usize) -> usize {
    rd(b + core::mem::size_of::<usize>())
}
#[inline(always)]
unsafe fn set_size(b: usize, v: usize) {
    wr(b, v)
}
#[inline(always)]
unsafe fn set_next(b: usize, v: usize) {
    wr(b + core::mem::size_of::<usize>(), v)
}

pub struct FirstFit;

static mut FREE: usize = NIL;

/// Declara `[start, end)` como el heap. Se llama una sola vez desde `_start`.
pub unsafe fn init(start: usize, end: usize) {
    let s = round_up(start);
    let e = end & !(GRAN - 1);
    set_size(s, e - s);
    set_next(s, NIL);
    FREE = s;
}

unsafe impl GlobalAlloc for FirstFit {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        // La cabecera de 16 bytes mantiene el payload alineado a 16; un pedido
        // con alineacion mayor no lo puede satisfacer este allocator.
        if layout.align() > GRAN {
            return core::ptr::null_mut();
        }
        let want = round_up(HDR + layout.size());

        let mut prev = NIL;
        let mut cur = FREE;
        while cur != NIL {
            let sz = size_of_blk(cur);
            if sz >= want {
                let rest = sz - want;
                if rest >= GRAN * 2 {
                    // Parte el bloque y deja el remanente en la lista.
                    let nb = cur + want;
                    set_size(nb, rest);
                    set_next(nb, next_of(cur));
                    if prev == NIL {
                        FREE = nb;
                    } else {
                        set_next(prev, nb);
                    }
                    set_size(cur, want);
                } else {
                    // Se lleva el bloque entero.
                    if prev == NIL {
                        FREE = next_of(cur);
                    } else {
                        set_next(prev, next_of(cur));
                    }
                }
                return (cur + HDR) as *mut u8;
            }
            prev = cur;
            cur = next_of(cur);
        }
        core::ptr::null_mut()
    }

    unsafe fn dealloc(&self, ptr: *mut u8, _layout: Layout) {
        let blk = ptr as usize - HDR;
        let sz = size_of_blk(blk);

        // Insercion ordenada por direccion.
        let mut prev = NIL;
        let mut cur = FREE;
        while cur != NIL && cur < blk {
            prev = cur;
            cur = next_of(cur);
        }
        set_next(blk, cur);
        if prev == NIL {
            FREE = blk;
        } else {
            set_next(prev, blk);
        }

        // Fusion con el siguiente y con el anterior, en ese orden.
        if cur != NIL && blk + sz == cur {
            set_size(blk, sz + size_of_blk(cur));
            set_next(blk, next_of(cur));
        }
        if prev != NIL {
            let psz = size_of_blk(prev);
            if prev + psz == blk {
                set_size(prev, psz + size_of_blk(blk));
                set_next(prev, next_of(blk));
            }
        }
    }
}
