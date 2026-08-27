//! Test 2 — guest RISC-V de 64 bits (RV64IMAC).
//!
//! Identico al guest RV32 salvo el ancho: mismo `pqcore`, misma ABI, mismo
//! allocator (incluido por `#[path]`, no duplicado). El par RV32/RV64 aisla
//! una sola variable —el ancho de registro— sobre el mismo interprete, que es
//! lo que mide el costo real de que Keccak trabaje en carriles de 64 bits.

#![no_std]
#![no_main]

extern crate alloc;

#[path = "../../guest-rv/src/alloc_ff.rs"]
mod alloc_ff;

use core::cell::UnsafeCell;
use core::panic::PanicInfo;
use pqcore::{Fixture, Level};

/// Debe coincidir con MEM_SIZE / STACK del emulador en `host/src/rv64.rs`.
const MEM_SIZE: usize = 64 * 1024 * 1024;
const STACK: usize = 1024 * 1024;
const HEAP_END: usize = MEM_SIZE - STACK;

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

#[no_mangle]
pub extern "C" fn guest_init() {
    unsafe {
        let start = core::ptr::addr_of!(__heap_start) as usize;
        alloc_ff::init(start, HEAP_END);
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

#[panic_handler]
fn panicked(_: &PanicInfo) -> ! {
    unsafe {
        core::arch::asm!("li a0, 0xdead", "ecall", "1: j 1b", options(noreturn));
    }
}
