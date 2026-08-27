//! Test 2 — guest RISC-V (RV32IM).
//!
//! Mismo `pqcore` y misma ABI que el guest wasm: el host llama `prepare(level)`
//! una vez y despues `run(mode, iters)` tantas veces como necesite el
//! calibrador. La unica diferencia con el guest wasm es el andamiaje bare-metal
//! de este archivo — el codigo medido es identico, compilado desde la misma
//! fuente a otro ISA.

#![no_std]
#![no_main]

extern crate alloc;

mod alloc_ff;

use core::cell::UnsafeCell;
use core::panic::PanicInfo;
use pqcore::{Fixture, Level};

/// Debe coincidir con MEM_SIZE / STACK del emulador en `host/src/rv32.rs`.
const MEM_SIZE: u32 = 64 * 1024 * 1024;
const STACK: u32 = 1024 * 1024;
const HEAP_END: u32 = MEM_SIZE - STACK;

#[global_allocator]
static ALLOC: alloc_ff::FirstFit = alloc_ff::FirstFit;

extern "C" {
    static __heap_start: u8;
}

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
    call guest_init
    ecall
    "#
);

/// Corre una sola vez, antes de cualquier llamada del host: deja `gp`/`sp`
/// fijados y el heap declarado.
#[no_mangle]
pub extern "C" fn guest_init() {
    unsafe {
        let start = core::ptr::addr_of!(__heap_start) as usize;
        alloc_ff::init(start, HEAP_END as usize);
    }
}

struct Slot<T>(UnsafeCell<T>);
unsafe impl<T> Sync for Slot<T> {}

static FIX: Slot<Option<Fixture>> = Slot(UnsafeCell::new(None));
static LVL: Slot<u32> = Slot(UnsafeCell::new(0));

#[no_mangle]
pub extern "C" fn prepare(level: u32) -> u32 {
    unsafe {
        *LVL.0.get() = level;
        *FIX.0.get() = Some(pqcore::make_fixture(Level::from_u32(level)));
    }
    level
}

#[no_mangle]
pub extern "C" fn run(mode: u32, iters: u32) -> u32 {
    unsafe {
        let lvl = Level::from_u32(*LVL.0.get());
        let fx = (*FIX.0.get()).as_ref().unwrap();
        if mode == 0 {
            pqcore::bench_decode_verify(lvl, fx, iters)
        } else {
            pqcore::bench_verify_only(lvl, fx, iters)
        }
    }
}

/// Un panic sale por `ecall` con 0xDEAD en a0. El host lo distingue de un
/// retorno normal porque el retorno normal llega al centinela de `ra`.
#[panic_handler]
fn panicked(_: &PanicInfo) -> ! {
    unsafe {
        core::arch::asm!("li a0, 0xdead", "ecall", "1: j 1b", options(noreturn));
    }
}
