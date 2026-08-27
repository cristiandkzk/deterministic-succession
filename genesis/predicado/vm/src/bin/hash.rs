//! **Cuántos pasos cuesta un SHA-256 en la máquina de §6.6.**
//!
//! Es el insumo que le faltaba al piso de §8.5: la Fase 5 escribio la cuenta y el
//! resultado quedo colgando de este numero, estimado en 10.000 pasos por compresion.
//! Mover el estimado por 10x movia el piso por 10x.
//!
//! Se mide igual que `steps_per_verify` en Test 2 —diferencia entre dos llamadas, para
//! que el costo fijo de entrar y salir no entre en la cuenta marginal— y el resultado es
//! **exacto e independiente de la arquitectura**: es una propiedad del programa.
//!
//!     cargo run --release --bin hash

use vm::maquina::Veredicto;

fn main() {
    let (mut m, syms) = vm::admitir(vm::GUEST_SHA, u64::MAX).expect("admitir el guest de SHA-256");
    println!("# guest-sha admitido: {} bytes, {} simbolos", vm::GUEST_SHA.len(), syms.len());
    m.arrancar();
    let comprimir = *syms.get("comprimir").expect("simbolo comprimir");

    // Dos tandas y una resta: el marco de la llamada se cancela.
    let base = m.pasos;
    let r1 = m.llamar(comprimir, &[100]);
    let p100 = m.pasos - base;
    let base = m.pasos;
    let r2 = m.llamar(comprimir, &[200]);
    let p200 = m.pasos - base;

    assert!(matches!(r1, Veredicto::Retorno(_)), "{:?}", r1);
    assert!(matches!(r2, Veredicto::Retorno(_)), "{:?}", r2);

    let por_compresion = (p200 - p100) / 100;
    println!("pasos_100,{}", p100);
    println!("pasos_200,{}", p200);
    println!();
    println!("pasos_por_compresion,{}", por_compresion);

    // Y la consecuencia, que es para lo que se midio.
    let hashes_por_actualizacion = 26u64;
    let ciclo = 2 * hashes_por_actualizacion * por_compresion;
    println!("hashes_por_actualizacion,{}", hashes_por_actualizacion);
    println!("pasos_del_ciclo_crear_desalojar,{}", ciclo);
    println!();
    println!("# el estimado de la Fase 5 era 10.000 pasos por compresion");
    println!("# medido: {} — el estimado estaba {:.1}x", por_compresion,
        10_000.0 / por_compresion as f64);
}
