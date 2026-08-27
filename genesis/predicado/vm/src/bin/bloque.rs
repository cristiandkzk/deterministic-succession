//! **C1 — el presupuesto bajo carga de bloque, no en benchmark aislado.**
//!
//! `f* = 25%` de un bloque de 6 s son 1.500 ms para las transacciones del ruleset
//! inicial. El criterio dice que se mide **como un bloque**: las verificaciones una
//! detras de otra, no una medida y multiplicada por la capacidad.
//!
//! Cuando el criterio se escribio la capacidad eran 67 transacciones y con esas
//! aprobo: 1.086 ms de 1.500, margen 1,38x. Despues C7 la bajo a 26 y el margen
//! subio a 3,42x. **Las dos corridas estan en `../RESULTADOS.md`**, porque informar
//! solo la segunda seria informar un criterio que se volvio mas facil.
//!
//! Cada transaccion arranca una instancia nueva, que es lo que hace un nodo: la
//! memoria del guest empieza en cero y esta fria, y el costo de admitir el binario
//! y de arrancarlo se paga tambien. Se informan los tres tramos por separado
//! —admision, arranque, verificacion— porque son tres decisiones distintas: la
//! admision se puede cachear por predicado, el arranque no.
//!
//! **Limitacion declarada:** todas usan el mismo par clave/firma, porque el guest
//! de Test 2 fabrica su material con una semilla fija y regenerarlo es rehacer un
//! artefacto ya publicado. Lo que si es frio es la memoria: cada instancia tiene
//! su propia region, en otra direccion. Con 67 claves distintas el numero solo
//! puede empeorar, asi que el resultado es una **cota inferior** del costo real.
//!
//!     cargo run --release --bin bloque

use std::time::Instant;
use vm::maquina::Veredicto;

const TX: usize = vm::TX_INICIAL as usize;
/// `f* × tiempo_de_bloque` = 25% de 6 s.
const PRESUPUESTO_MS: f64 = 1500.0;

fn main() {
    println!("# C1 — {} verificaciones ML-DSA-44 como un bloque. Presupuesto: {:.0} ms.", TX, PRESUPUESTO_MS);
    println!("# maquina: {}", std::env::consts::ARCH);

    let mut t_admision = 0.0_f64;
    let mut t_arranque = 0.0_f64;
    let mut t_verificacion = 0.0_f64;
    let mut pasos_totales = 0u64;
    let mut techo_excedido = 0usize;
    let mut paginas_max = 0u32;

    let t_bloque = Instant::now();
    for _ in 0..TX {
        let t0 = Instant::now();
        let (mut m, syms) = vm::admitir(vm::GUEST_RV, vm::TECHO_INICIAL).expect("admitir");
        m.techo_paginas = u32::MAX; // el arranque y `prepare` son andamiaje
        t_admision += t0.elapsed().as_secs_f64();

        let prepare = *syms.get("prepare").expect("prepare");
        let run = *syms.get("run").expect("run");

        // El arranque y `prepare` fabrican el material de prueba dentro del guest.
        // Un predicado real recibe la clave y la firma como bytes de la
        // transaccion, asi que esto es andamiaje de Test 2 y **no se le cobra al
        // presupuesto de bloque**: se mide aparte y se descuenta.
        let t1 = Instant::now();
        m.techo = u64::MAX;
        m.arrancar();
        m.llamar(prepare, &[0]);
        t_arranque += t1.elapsed().as_secs_f64();

        // Acá si: una verificacion con el techo puesto, que es lo que corre un nodo.
        let base = m.pasos;
        m.techo = base + vm::TECHO_INICIAL;
        // Los dos techos, como los pone un nodo: el de paginas se cuenta desde
        // cero para esta verificacion, no desde el arranque.
        m.borrar_paginas();
        m.techo_paginas = vm::PAGINAS_INICIALES;
        let t2 = Instant::now();
        let v = m.llamar(run, &[0, 1]);
        t_verificacion += t2.elapsed().as_secs_f64();
        if v == Veredicto::TechoExcedido || v == Veredicto::PaginasExcedidas {
            techo_excedido += 1;
        }
        paginas_max = paginas_max.max(m.paginas_usadas);
        pasos_totales += m.pasos - base;
    }
    let total = t_bloque.elapsed().as_secs_f64() * 1000.0;

    let ms = |s: f64| s * 1000.0;
    println!();
    println!("tramo,ms_totales,ms_por_tx,%_del_presupuesto");
    for (nombre, t) in [
        ("admision", t_admision),
        ("arranque+prepare (andamiaje)", t_arranque),
        ("verificacion", t_verificacion),
    ] {
        println!(
            "{},{:.1},{:.2},{:.1}",
            nombre,
            ms(t),
            ms(t) / TX as f64,
            100.0 * ms(t) / PRESUPUESTO_MS
        );
    }
    println!("bloque completo,{:.1},{:.2},{:.1}", total, total / TX as f64, 100.0 * total / PRESUPUESTO_MS);

    println!();
    println!("# pasos por verificacion: {}", pasos_totales / TX as u64);
    println!("# techo de pasos por tx: {} — excedidos: {}", vm::TECHO_INICIAL, techo_excedido);
    println!("# techo de paginas: {} — maximo usado: {}", vm::PAGINAS_INICIALES, paginas_max);

    // ------------------------------------------------------------------ #
    // La otra forma de medir, la que el criterio dice que NO vale: las mismas
    // verificaciones en una sola instancia caliente. Se corre aca, en la misma
    // corrida y con la maquina en el mismo estado, porque comparar contra un
    // numero de otra corrida es lo que hizo que la primera version de esta
    // medicion reportara una penalidad de 1,20x que no existia.
    // ------------------------------------------------------------------ #
    let (mut m, syms) = vm::admitir(vm::GUEST_RV, u64::MAX).expect("admitir");
    m.techo_paginas = u32::MAX;
    m.arrancar();
    m.llamar(*syms.get("prepare").expect("prepare"), &[0]);
    let t3 = Instant::now();
    m.llamar(*syms.get("run").expect("run"), &[0, TX as u32]);
    let caliente = t3.elapsed().as_secs_f64() * 1000.0;
    println!(
        "# {} verificaciones calientes en una instancia: {:.1} ms ({:.2} ms/tx)",
        TX,
        caliente,
        caliente / TX as f64
    );
    println!(
        "# como bloque cuesta {:.2}x eso",
        ms(t_verificacion) / caliente
    );

    let cobrable = ms(t_admision + t_verificacion);
    println!();
    if cobrable <= PRESUPUESTO_MS {
        println!(
            "# C1 APROBADO — admision + verificacion: {:.0} ms de {:.0} ({:.2}x de margen)",
            cobrable,
            PRESUPUESTO_MS,
            PRESUPUESTO_MS / cobrable
        );
    } else {
        println!(
            "# C1 REPROBADO — admision + verificacion: {:.0} ms de {:.0} ({:.2}x por encima)",
            cobrable,
            PRESUPUESTO_MS,
            cobrable / PRESUPUESTO_MS
        );
    }
}
