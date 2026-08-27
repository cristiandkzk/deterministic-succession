//! **C7 — el paso, ¿es una unidad honesta?**
//!
//! `R_declarado = 300 M pasos/s` se derivo de UNA mezcla de instrucciones: la de
//! ML-DSA. El techo de §10.3 se cerro con ese numero. Si un paso de division o un
//! paso que falla en cache cuesta mucho mas que un paso de suma, entonces el techo
//! promete un presupuesto que no cumple, la cadena se atrasa de forma
//! determinista, y ninguna invariante lo ve.
//!
//! El criterio esta en `../CRITERIOS.md`, escrito antes de correr esto.
//!
//! ## Lo que se compara es un cociente, no un ritmo
//!
//! Los M pasos/s de una maquina no se transfieren a otra: esta corrida es en un
//! escritorio x86-64 y el hardware de referencia es un telefono. Lo que si se
//! transfiere —aproximadamente, y es la unica via que hay sin correr las dos— es
//! **el cociente entre la peor mezcla y ML-DSA medidos en la misma maquina**. Con
//! ese cociente y el ritmo de ML-DSA en el telefono sale el `R_declarado` que
//! aguanta el peor caso.
//!
//! Notar que el instrumento de medicion es el propio techo: cada mezcla es un
//! bucle infinito que para en el paso exacto que se le pide.
//!
//!     cargo run --release --bin mezclas

use std::time::Instant;
use vm::maquina::{Maquina, Veredicto, MEM, PAGINA};
use vm::{i, jal, r};

/// Cuerpo del bucle: suficientemente largo para que el `jal` de vuelta sea ruido
/// (1/1024 = 0,1%) y para no caber entero en el predictor de saltos del host.
const CUERPO: usize = 1024;

/// Donde empieza la region de datos de las mezclas de memoria.
const DATOS: u32 = 1 << 20;

/// ML-DSA-44 sobre el hardware de referencia **con esta maquina**, en M pasos/s.
///
/// **No son los 316 de Test 2, y la diferencia importa.** Aquellos se midieron con el
/// interprete sin endurecer; esta maquina agrega chequeo de rango en cada acceso, el
/// techo de pasos y el conteo de paginas, y eso cuesta **1,19x** sobre la carga real:
/// 10,57 ms pasaron a 12,55 en el mismo telefono. Usar 316 contra un cociente medido
/// sobre la maquina endurecida es mezclar dos interpretes, y la cota sale 19% mas
/// alta de lo que corresponde — hacia el lado inseguro.
const ML_DSA_ENDURECIDO_EN_TELEFONO: f64 = 266.2;

/// Si esto corre en aarch64 se asume que es el telefono de referencia, y entonces
/// **la cota no hay que trasladarla: se mide directo**. El traslado entre maquinas
/// es la parte mas floja de toda esta cuenta, y aca deja de hacer falta.
fn es_hardware_de_referencia() -> bool {
    std::env::consts::ARCH == "aarch64"
}

struct Lcg(u64);
impl Lcg {
    fn sig(&mut self) -> u32 {
        self.0 = self.0.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
        (self.0 >> 33) as u32
    }
}

fn programa(setup: Vec<u32>, cuerpo: Vec<u32>) -> Vec<u32> {
    let n = cuerpo.len() as i32;
    let mut p = setup;
    p.extend(cuerpo);
    p.push(jal(0, -4 * n));
    p
}

fn addi(rd: u32, rs1: u32, imm: i32) -> u32 {
    i(imm, rs1, 0, rd, 0x13)
}
fn lui(rd: u32, top: u32) -> u32 {
    (top << 12) | (rd << 7) | 0x37
}
fn lw(rd: u32, rs1: u32, off: i32) -> u32 {
    i(off, rs1, 2, rd, 0x03)
}

/// `li rd, dir` — el idioma de RISC-V, con el redondeo que hay que hacer.
///
/// **Esto estaba mal y arruino una medicion entera.** El inmediato de `addi` es de
/// doce bits **con signo**: si los doce bits bajos de la direccion son >= 2048, sumarlos
/// resta 4096 en vez de sumar lo que uno cree. La persecucion arrancaba entonces en la
/// pagina anterior, leia un cero, y a partir de ahi todos los `lw` seguian el puntero
/// cero — o sea leian siempre la misma direccion, siempre en L1. **Reportaba 194 M
/// pasos/s, que es exactamente el ritmo de `lw-secuencial`: no perseguia nada.**
fn cargar_direccion(rd: u32, dir: u32) -> [u32; 2] {
    let alto = (dir.wrapping_add(0x800)) >> 12;
    let bajo = (dir as i32) - ((alto << 12) as i32);
    [lui(rd, alto), addi(rd, rd, bajo)]
}

/// Persecucion de punteros por las paginas que se le den, en orden aleatorio.
fn persecucion(paginas: &[u32], semilla: u64) -> (Vec<u32>, Vec<(u32, [u8; 4])>) {
    let mut g = Lcg(semilla);
    let mut lineas: Vec<u32> = paginas
        .iter()
        .flat_map(|pg| (0..PAGINA / 64).map(move |l| pg + l * 64))
        .collect();
    for k in (1..lineas.len()).rev() {
        let j = (g.sig() as usize) % (k + 1);
        lineas.swap(k, j);
    }
    let escrituras: Vec<(u32, [u8; 4])> = (0..lineas.len())
        .map(|k| (lineas[k], lineas[(k + 1) % lineas.len()].to_le_bytes()))
        .collect();
    let p0 = lineas[0];
    let mut prog = vec![];
    prog.extend(cargar_direccion(5, p0));
    prog.push(lw(5, 5, 0));
    prog.extend((0..CUERPO).map(|_| lw(5, 5, 0)));
    prog.push(jal(0, -4 * CUERPO as i32));
    (prog, escrituras)
}

struct Mezcla {
    nombre: String,
    nota: &'static str,
    prog: Vec<u32>,
    ram: Vec<(u32, [u8; 4])>,
    /// Si se espera que el techo de paginas la corte. Una mezcla cortada **no es
    /// lenta: es rechazada**, y no entra en la cuenta de la peor.
    se_corta: bool,
    /// Cuantas paginas distintas **tiene que** tocar. `None` = no se declara.
    ///
    /// Existe porque una mezcla puede degenerar en otra sin avisar: la persecucion
    /// arrancaba mal y terminaba leyendo siempre la misma direccion, con un numero
    /// perfectamente creible. **Una medicion tiene que declarar que esta midiendo.**
    paginas_esperadas: Option<u32>,
}

fn mezclas() -> Vec<Mezcla> {
    let mut v = Vec::new();
    let m = |nombre: &str, nota, prog, ram, se_corta| Mezcla {
        nombre: nombre.to_string(),
        nota,
        prog,
        ram,
        se_corta,
        paginas_esperadas: None,
    };

    v.push(m(
        "addi-uniforme",
        "un solo opcode: el despacho del interprete acierta siempre",
        programa(vec![], (0..CUERPO).map(|_| addi(5, 5, 1)).collect()),
        vec![],
        false,
    ));

    // La primera mezcla verdaderamente adversarial, y es especifica de un
    // interprete: cada instruccion del guest cuesta un salto indirecto en el host,
    // y un cuerpo con opcodes distintos en orden impredecible es exactamente lo que
    // rompe el predictor del host. El programa no hace nada util; no tiene por que.
    let mut g = Lcg(0x9E3779B97F4A7C15);
    let baraja: Vec<u32> = (0..CUERPO)
        .map(|_| {
            let (f7, f3) = match g.sig() % 8 {
                0 => (0x00, 0),
                1 => (0x20, 0),
                2 => (0x00, 4),
                3 => (0x00, 6),
                4 => (0x00, 7),
                5 => (0x00, 1),
                6 => (0x00, 5),
                _ => (0x00, 2),
            };
            r(f7, 6, 5, f3, 7, 0x33)
        })
        .collect();
    v.push(m(
        "aritmetica-revuelta",
        "ocho opcodes en orden impredecible: rompe el despacho del interprete",
        programa(vec![addi(5, 0, 1234), addi(6, 0, 7)], baraja),
        vec![],
        false,
    ));

    v.push(m(
        "mul",
        "multiplicacion de 32x32",
        programa(
            vec![addi(5, 0, 1234), addi(6, 0, 7)],
            (0..CUERPO).map(|_| r(0x01, 6, 5, 0, 7, 0x33)).collect(),
        ),
        vec![],
        false,
    ));

    v.push(m(
        "divu",
        "division sin signo, la instruccion mas larga del ISA",
        programa(
            vec![addi(5, 0, -1), addi(6, 0, 3)],
            (0..CUERPO).map(|_| r(0x01, 6, 5, 5, 7, 0x33)).collect(),
        ),
        vec![],
        false,
    ));

    v.push(m(
        "lw-secuencial",
        "2 KiB recorridos en orden, todo en L1",
        programa(
            vec![lui(5, DATOS >> 12)],
            (0..CUERPO).map(|k| lw(6, 5, ((k % 512) * 4) as i32)).collect(),
        ),
        vec![],
        false,
    ));

    // **La peor mezcla de memoria que entra en el presupuesto.** 48 paginas
    // desparramadas por los 64 MiB, recorridas como una cadena serial de punteros:
    // cada `lw` depende del anterior, falla el cache y usa una entrada de TLB
    // distinta. Es legitima, es admisible, y no la corta nada.
    let total_pgs = (MEM - DATOS) / PAGINA;
    let mut g = Lcg(0xC0FFEE);
    let mut pgs: Vec<u32> = Vec::new();
    while pgs.len() < vm::PAGINAS_INICIALES as usize {
        let c = DATOS + (g.sig() % total_pgs) * PAGINA;
        if !pgs.contains(&c) {
            pgs.push(c);
        }
    }
    let (prog, ram) = persecucion(&pgs, 0xBADC0DE);
    let mut peor_memoria = m(
        &format!("lw-persecucion-{}pg", vm::PAGINAS_INICIALES),
        "paginas desparramadas por 64 MiB: el peor caso que SI entra",
        prog,
        ram,
        false,
    );
    peor_memoria.paginas_esperadas = Some(vm::PAGINAS_INICIALES);
    v.push(peor_memoria);

    // Y la que el techo de paginas existe para frenar: la misma persecucion sin
    // limite. Antes de la Fase 4 esto corria a 11 M pasos/s y gastaba el techo
    // entero en 596 ms.
    let libres: Vec<u32> = (0..2048).map(|k| DATOS + k * PAGINA).collect();
    let (prog, ram) = persecucion(&libres, 0xDEADBEEF);
    v.push(m(
        "lw-persecucion-libre",
        "la misma sin limite de paginas: 8 MiB. La que el segundo techo frena",
        prog,
        ram,
        true,
    ));

    v
}

/// Corre la mezcla **tres veces y devuelve la peor**.
///
/// Una sola corrida en este arnes tiene una dispersion de hasta 20% —lo midio el propio
/// proyecto cruzando dos herramientas que tenian que coincidir y no coincidian—, y el
/// numero que sale de aca fija una constante de Genesis. Tomar la peor es la direccion
/// segura: `R_declarado` tiene que quedar por debajo de lo que el hardware sostiene en su
/// peor momento, no en el mejor.
fn ritmo(mz: &Mezcla) -> Option<f64> {
    let mut peor = f64::INFINITY;
    for _ in 0..3 {
        peor = peor.min(ritmo_una_vez(mz)?);
    }
    Some(peor)
}

fn ritmo_una_vez(mz: &Mezcla) -> Option<f64> {
    let mut m = Maquina::desde_palabras(&mz.prog, 0);
    m.techo_paginas = vm::PAGINAS_INICIALES;
    for (a, b) in &mz.ram {
        assert!(m.escribir(*a, b), "la region de datos no entra");
    }
    let mut tramo: u64 = 1 << 20;
    loop {
        m.techo = m.pasos + tramo;
        let t0 = Instant::now();
        let v = m.correr();
        let dt = t0.elapsed().as_secs_f64();
        match v {
            Veredicto::PaginasExcedidas => return None,
            Veredicto::TechoExcedido => {}
            otro => panic!("la mezcla {} termino en {:?}", mz.nombre, otro),
        }
        if dt > 0.5 || tramo > (1 << 30) {
            // **La mezcla tiene que haber tocado lo que declaro.** Sin esto, una
            // persecucion que degenera en leer siempre la misma direccion informa un
            // numero creible y nadie se entera.
            if let Some(esperadas) = mz.paginas_esperadas {
                assert_eq!(
                    m.paginas_usadas, esperadas,
                    "{} declaro {} paginas y toco {}: no esta midiendo lo que dice",
                    mz.nombre, esperadas, m.paginas_usadas
                );
            }
            return Some((tramo as f64) / dt / 1e6);
        }
        tramo *= 2;
    }
}

/// El ritmo de la carga real, **medido como lo usa un nodo**: una tanda del tamano
/// de un bloque, sobre una instancia recien arrancada.
///
/// La forma de medir esto no es un detalle, porque el cociente contra las mezclas
/// sale de aca. Un bucle largo de miles de verificaciones en una sola instancia da
/// ~200 M pasos/s; una tanda del tamano de un bloque da ~250. La diferencia es el
/// conjunto de trabajo del allocator del guest, que en el bucle largo crece.
///
/// **Se toma la tanda, y ademas la corrida mas rapida de varias.** Un ritmo de
/// referencia mas alto da un cociente mas bajo, un cociente mas bajo da una cota mas
/// baja para `R_declarado`, y una cota mas baja es la direccion segura. Elegir el
/// numero que le conviene al resultado seria al reves.
fn ritmo_mldsa() -> Option<(f64, u64, u32)> {
    let mut por_verificacion = 0u64;
    let mut paginas = 0u32;
    let mut mejor = 0.0f64;

    for _ in 0..5 {
        let (mut m, syms) = vm::admitir(vm::GUEST_RV, u64::MAX).ok()?;
        m.arrancar();
        let prepare = *syms.get("prepare")?;
        let run = *syms.get("run")?;
        m.llamar(prepare, &[0]);

        if por_verificacion == 0 {
            let p0 = m.pasos;
            m.llamar(run, &[0, 10]);
            let p10 = m.pasos - p0;
            let p1 = m.pasos;
            m.llamar(run, &[0, 20]);
            let p20 = m.pasos - p1;
            por_verificacion = (p20 - p10) / 10;
            continue; // esta instancia ya quedo caliente: no sirve de referencia
        }

        m.borrar_paginas();
        let p2 = m.pasos;
        let t0 = Instant::now();
        m.llamar(run, &[0, vm::TX_INICIAL as u32]);
        let dt = t0.elapsed().as_secs_f64();
        let mp = ((m.pasos - p2) as f64) / dt / 1e6;
        if mp > mejor {
            mejor = mp;
            paginas = m.paginas_usadas;
        }
    }
    Some((mejor, por_verificacion, paginas))
}

fn main() {
    println!("# C7 — ritmo por mezcla de instrucciones.");
    println!("# maquina: {} · techo de paginas: {}", std::env::consts::ARCH, vm::PAGINAS_INICIALES);
    println!();
    println!("mezcla,ritmo_Mpasos_s,nota");

    // **La referencia se mide primero, antes de que las mezclas calienten la
    // maquina.** Medirla al final la daba ~20% mas lenta, y una referencia lenta da
    // un cociente alto, y un cociente alto da una cota alta para `R_declarado`:
    // justo la direccion insegura. Es el mismo error que C1 nombra —comparar
    // numeros tomados en estados distintos— una capa mas abajo.
    let (mldsa, por_verificacion, paginas) = ritmo_mldsa().expect("ML-DSA");

    let mut peor = f64::INFINITY;
    let mut peor_nombre = String::new();

    for mz in mezclas() {
        match ritmo(&mz) {
            None => {
                assert!(mz.se_corta, "{} se corto y no deberia", mz.nombre);
                println!("{},cortada,{}", mz.nombre, mz.nota);
            }
            Some(mp) => {
                assert!(!mz.se_corta, "{} deberia haberse cortado", mz.nombre);
                if mp < peor {
                    peor = mp;
                    peor_nombre = mz.nombre.clone();
                }
                println!("{},{:.1},{}", mz.nombre, mp, mz.nota);
            }
        }
    }

    println!("ML-DSA-44-real,{:.1},la carga real — {} pasos y {} paginas por verificacion",
        mldsa, por_verificacion, paginas);

    // ------------------------------------------------------------------ #
    // El veredicto, en cocientes.
    // ------------------------------------------------------------------ #
    let cociente = peor / mldsa;
    // Sobre el hardware de referencia la peor mezcla **es** la cota: `R_declarado`
    // tiene que ser un ritmo que ese hardware sostenga con el peor programa
    // admisible, y eso es exactamente lo que se acaba de medir.
    let (tope_telefono, como) = if es_hardware_de_referencia() {
        (peor, "medida directo sobre el hardware de referencia")
    } else {
        (
            ML_DSA_ENDURECIDO_EN_TELEFONO * cociente,
            "trasladada por cociente — correr en aarch64 para medirla directo",
        )
    };
    // f* x tiempo_de_bloque = 25% de 6 s. Vive aca y no en el crate.
    let declarado = (vm::TECHO_INICIAL * vm::TX_INICIAL) as f64 / 1.5 / 1e6;

    println!();
    println!("# peor mezcla admisible: {} a {:.1} M pasos/s", peor_nombre, peor);
    println!("# ML-DSA en esta maquina: {:.1} M pasos/s", mldsa);
    println!("# cociente peor/ML-DSA: {:.3}", cociente);
    if !es_hardware_de_referencia() {
        println!(
            "# ML-DSA endurecido en el telefono: {:.0} M pasos/s",
            ML_DSA_ENDURECIDO_EN_TELEFONO
        );
    }
    println!("# => cota para R_declarado: {:.0} M pasos/s ({})", tope_telefono, como);
    println!("# R_declarado vigente: {:.0} M pasos/s", declarado);

    // La consecuencia, para no tener que hacerla a mano: cuantas transacciones por
    // bloque tolera la cota medida dandole a ML-DSA-44 el margen de 2x que eligio
    // Genesis. **El costo en pasos de una verificacion lo fija el ISA**, asi que
    // todo lo que baje `R_declarado` sale de la capacidad.
    let pasos_por_bloque = tope_telefono * 1e6 * 1.5; // f* x tiempo_de_bloque
    let tx = pasos_por_bloque / (2.0 * 3_339_364.0);
    println!(
        "# a esa cota, con margen 2x sobre ML-DSA-44: {:.0} tx/bloque (hoy: {})",
        tx.floor(),
        vm::TX_INICIAL
    );
    println!("#   y `R_declarado` tiene que quedar POR DEBAJO de la cota, no en ella.");
    println!();
    if declarado <= tope_telefono {
        println!(
            "# C7 APROBADO con el techo de paginas puesto: R_declarado esta {:.0}% por debajo de la cota.",
            100.0 * (1.0 - declarado / tope_telefono)
        );
    } else {
        println!(
            "# C7 REPROBADO: R_declarado esta {:.2}x por encima de lo que aguanta la peor mezcla.",
            declarado / tope_telefono
        );
    }
}
