//! Cuantas paginas toca cada nivel de ML-DSA. **El dato que faltaba para elegir el
//! techo de paginas**: si el sucesor natural de la primitiva de Genesis no entra,
//! el techo no lo esta encareciendo —lo esta excluyendo—, y §6.6 dice que una
//! primitiva mas cara tiene que poder entrar pagando capacidad.
//!
//! El conteo es independiente de la arquitectura (x86-64 y aarch64 dieron 26 para
//! el nivel 44), asi que esto no necesita el telefono.

fn main() {
    println!("nivel,pasos,paginas_4KiB,KiB");
    for (nombre, nivel) in [("ML-DSA-44", 0u32), ("ML-DSA-65", 1), ("ML-DSA-87", 2)] {
        let (mut m, syms) = vm::admitir(vm::GUEST_RV, u64::MAX).expect("admitir");
        m.arrancar();
        m.llamar(*syms.get("prepare").expect("prepare"), &[nivel]);
        m.borrar_paginas();
        let p0 = m.pasos;
        m.llamar(*syms.get("run").expect("run"), &[0, 1]);
        println!(
            "{},{},{},{}",
            nombre,
            m.pasos - p0,
            m.paginas_usadas,
            m.paginas_usadas * 4
        );
    }
}
