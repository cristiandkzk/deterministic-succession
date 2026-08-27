//! Test 2 — nucleo compartido.
//!
//! Una sola implementacion de "verificar una firma ML-DSA" que se compila:
//!   - nativa (baseline), y
//!   - a wasm32 (bytecode sobre VM determinista).
//!
//! El camino medido es el que corre un nodo real: decodificar la clave publica
//! y la firma desde bytes, y despues verificar. Se expone tambien la variante
//! solo-verify para separar cuanto cuesta el decode.

#![no_std]

extern crate alloc;

use alloc::vec::Vec;
use ml_dsa::{
    B32, EncodedSignature, EncodedVerifyingKey, ExpandedSigningKey, MlDsa44, MlDsa65,
    MlDsa87, MlDsaParams, Signature, VerifyingKey,
};

/// Mensaje fijo de 32 bytes: el tamano de un hash de transaccion.
const MSG: [u8; 32] = [0x5a; 32];
const CTX: &[u8] = b"";

/// Material de prueba ya serializado, tal como viajaria en un bloque.
pub struct Fixture {
    pub vk_bytes: Vec<u8>,
    pub sig_bytes: Vec<u8>,
}

fn fixture<P: MlDsaParams>(seed_byte: u8) -> Fixture {
    let seed: B32 = [seed_byte; 32].into();
    let sk = ExpandedSigningKey::<P>::from_seed(&seed);
    let vk = sk.verifying_key();
    let sig = sk.sign_deterministic(&MSG, CTX).expect("sign");
    Fixture {
        vk_bytes: vk.encode().to_vec(),
        sig_bytes: sig.encode().to_vec(),
    }
}

/// decode(vk) + decode(sig) + verify. Lo que hace un nodo por firma.
fn decode_and_verify<P: MlDsaParams>(vk_bytes: &[u8], sig_bytes: &[u8]) -> bool {
    let enc_vk = EncodedVerifyingKey::<P>::try_from(vk_bytes).expect("vk len");
    let enc_sig = EncodedSignature::<P>::try_from(sig_bytes).expect("sig len");
    let vk = VerifyingKey::<P>::decode(&enc_vk);
    match Signature::<P>::decode(&enc_sig) {
        Some(sig) => vk.verify_with_context(&MSG, CTX, &sig),
        None => false,
    }
}

fn verify_only<P: MlDsaParams>(vk: &VerifyingKey<P>, sig: &Signature<P>) -> bool {
    vk.verify_with_context(&MSG, CTX, sig)
}

/// Niveles de seguridad NIST expuestos al benchmark.
#[derive(Clone, Copy)]
pub enum Level {
    Dsa44 = 0,
    Dsa65 = 1,
    Dsa87 = 2,
}

impl Level {
    pub fn from_u32(v: u32) -> Level {
        match v {
            0 => Level::Dsa44,
            1 => Level::Dsa65,
            _ => Level::Dsa87,
        }
    }
    pub fn name(self) -> &'static str {
        match self {
            Level::Dsa44 => "ML-DSA-44",
            Level::Dsa65 => "ML-DSA-65",
            Level::Dsa87 => "ML-DSA-87",
        }
    }
}

macro_rules! dispatch {
    ($lvl:expr, $f:ident $(, $arg:expr)*) => {
        match $lvl {
            Level::Dsa44 => $f::<MlDsa44>($($arg),*),
            Level::Dsa65 => $f::<MlDsa65>($($arg),*),
            Level::Dsa87 => $f::<MlDsa87>($($arg),*),
        }
    };
}

pub fn make_fixture(lvl: Level) -> Fixture {
    dispatch!(lvl, fixture, 0x11)
}

/// Corre `iters` verificaciones completas (decode + verify).
/// Devuelve la cuenta de exitos para que el optimizador no borre el trabajo.
pub fn bench_decode_verify(lvl: Level, fx: &Fixture, iters: u32) -> u32 {
    let mut ok = 0u32;
    for _ in 0..iters {
        if dispatch!(lvl, decode_and_verify, &fx.vk_bytes, &fx.sig_bytes) {
            ok += 1;
        }
    }
    ok
}

/// Corre `iters` verificaciones sin el decode (claves ya en memoria).
pub fn bench_verify_only(lvl: Level, fx: &Fixture, iters: u32) -> u32 {
    fn inner<P: MlDsaParams>(vk_bytes: &[u8], sig_bytes: &[u8], iters: u32) -> u32 {
        let enc_vk = EncodedVerifyingKey::<P>::try_from(vk_bytes).expect("vk len");
        let enc_sig = EncodedSignature::<P>::try_from(sig_bytes).expect("sig len");
        let vk = VerifyingKey::<P>::decode(&enc_vk);
        let sig = Signature::<P>::decode(&enc_sig).expect("sig decode");
        let mut ok = 0u32;
        for _ in 0..iters {
            if verify_only::<P>(&vk, &sig) {
                ok += 1;
            }
        }
        ok
    }
    dispatch!(lvl, inner, &fx.vk_bytes, &fx.sig_bytes, iters)
}
