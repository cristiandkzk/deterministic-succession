//! Los criterios de `../CRITERIOS.md` que no son mediciones, como pruebas.
//!
//! C1 y C7 son mediciones y viven en `src/bin/`: no se pueden afirmar, se corren y
//! se informa el numero. Los otros cinco son propiedades, y una propiedad se fija.
//!
//!     cargo test --release

use vm::maquina::{Causa, Maquina, Op, Veredicto, MEM, PAGINA, TEXT_BASE};
use vm::{admitir, i, jal, r, Rechazo, PAGINAS_INICIALES};

fn u32a(b: &[u8], o: usize) -> u32 {
    u32::from_le_bytes([b[o], b[o + 1], b[o + 2], b[o + 3]])
}
fn u16a(b: &[u8], o: usize) -> u16 {
    u16::from_le_bytes([b[o], b[o + 1]])
}

/// El offset de archivo del punto de entrada del guest, para poder parchearlo.
fn offset_de_entrada(elf: &[u8]) -> usize {
    let entrada = u32a(elf, 24);
    let (phoff, phent, phnum) = (
        u32a(elf, 28) as usize,
        u16a(elf, 42) as usize,
        u16a(elf, 44) as usize,
    );
    for k in 0..phnum {
        let p = phoff + k * phent;
        if u32a(elf, p) != 1 {
            continue;
        }
        let (off, vaddr, filesz) = (u32a(elf, p + 4), u32a(elf, p + 8), u32a(elf, p + 16));
        if entrada >= vaddr && entrada < vaddr + filesz {
            return (off + (entrada - vaddr)) as usize;
        }
    }
    panic!("no se encontro el segmento del punto de entrada");
}

// =========================================================================== //
// C2 — el flotante prohibido antes de que el guante corra por primera vez
// =========================================================================== //

/// La primera mitad de C2, verificable leyendo el decodificador: **no hay ni una
/// rama de punto flotante**. Se recorren los 128 opcodes mayores y se comprueba
/// que los ocho reservados no producen ninguna instruccion ejecutable.
#[test]
fn c2_el_isa_no_tiene_punto_flotante() {
    for opc in [0x07u32, 0x27, 0x2F, 0x43, 0x47, 0x4B, 0x4F, 0x53] {
        // Se prueban todas las combinaciones de funct3 y funct7, no una sola: si
        // alguna colara, seria justo la que no se probo.
        for f3 in 0..8u32 {
            for f7 in [0x00u32, 0x01, 0x08, 0x20, 0x60] {
                let w = r(f7, 1, 2, f3, 3, opc);
                assert_eq!(
                    vm::maquina::decodificar(w).op,
                    Op::Ilegal,
                    "el opcode {:#x} con f3={} f7={:#x} decodifico a algo ejecutable",
                    opc,
                    f3,
                    f7
                );
            }
        }
    }
}

/// La segunda mitad: **una sola palabra de flotante en una seccion de codigo
/// rechaza el binario, y rechaza con cero pasos**. No se descubre al llegar a la
/// instruccion: se descubre antes de empezar.
#[test]
fn c2_una_palabra_de_flotante_rechaza_el_binario() {
    let mut elf = vm::GUEST_RV.to_vec();
    let o = offset_de_entrada(&elf);
    // `fadd.s f3, f2, f1` — opcode 0x53.
    elf[o..o + 4].copy_from_slice(&r(0x00, 1, 2, 0, 3, 0x53).to_le_bytes());

    match admitir(&elf, u64::MAX) {
        Err(Rechazo::OpcodeReservado { opcode, .. }) => assert_eq!(opcode, 0x53),
        Err(otro) => panic!("rechazado por la razon equivocada: {:?}", otro),
        Ok(_) => panic!("se admitio un binario con punto flotante"),
    }
}

/// Y el binario real, sin tocar, **si** entra. Un criterio que rechaza todo es
/// facil de cumplir y no sirve para nada.
#[test]
fn c2_el_binario_real_entra() {
    let (m, syms) = admitir(vm::GUEST_RV, u64::MAX).expect("el guest de Test 2 tiene que entrar");
    assert_eq!(m.pasos, 0, "admitir no puede ejecutar nada");
    assert!(syms.contains_key("prepare"));
}

/// El relleno de alineacion de `.text` son ceros, y `0x00000000` no decodifica.
/// **Rellenar no es delinquir**: la primera version del barrido rechazaba el guest
/// real por esto, y la correccion fue rechazar por espacio de opcode y no por
/// "no decodifico". Esta prueba fija la correccion para que no vuelva.
#[test]
fn c2_el_relleno_de_ceros_no_es_un_rechazo() {
    assert_eq!(vm::maquina::decodificar(0).op, Op::Ilegal);
    admitir(vm::GUEST_RV, u64::MAX).expect("el guest tiene relleno de ceros y entra igual");
}

// =========================================================================== //
// C4 — ninguna entrada hace panic
// =========================================================================== //

/// Un ELF truncado en cualquier punto devuelve `Ok` o `Err`, nunca aborta. Si
/// alguna de estas entradas hiciera `panic`, **una transaccion malformada tiraria
/// un nodo**, y eso cuesta una transaccion.
#[test]
fn c4_ningun_truncamiento_hace_panic() {
    let elf = vm::GUEST_RV;
    // Todos los cortes chicos, donde viven las cabeceras, y despues un barrido.
    let cortes = (0..256).chain((256..elf.len()).step_by(1013));
    for n in cortes {
        let _ = admitir(&elf[..n], 1000);
    }
}

/// Y una bateria de bytes alterados en las cabeceras, que es donde estan todos los
/// tamanos y desplazamientos con los que se puede mentir.
#[test]
fn c4_ninguna_cabecera_alterada_hace_panic() {
    let base = vm::GUEST_RV;
    // Las 52 de la cabecera ELF mas las de programa y seccion.
    let phoff = u32a(base, 28) as usize;
    let shoff = u32a(base, 32) as usize;
    let zonas = [(0usize, 52usize), (phoff, 256), (shoff, 1024)];
    for (inicio, largo) in zonas {
        for off in inicio..(inicio + largo).min(base.len()) {
            for valor in [0x00u8, 0x01, 0x7f, 0x80, 0xff] {
                let mut e = base.to_vec();
                e[off] = valor;
                let _ = admitir(&e, 1000);
            }
        }
    }
}

/// Y las entradas degeneradas, que son las que nadie prueba.
#[test]
fn c4_las_entradas_degeneradas_hacen_err() {
    assert!(admitir(&[], 1000).is_err());
    assert!(admitir(b"\x7fELF", 1000).is_err());
    assert!(admitir(&[0u8; 52], 1000).is_err());
    assert!(admitir(&[0xffu8; 4096], 1000).is_err());
}

// =========================================================================== //
// C5 — el techo corta, y cortar es un veredicto y no un error
// =========================================================================== //

fn bucle_infinito() -> Vec<u32> {
    vec![jal(0, 0)] // `j .` — se salta a si mismo
}

#[test]
fn c5_el_bucle_infinito_para_en_el_paso_exacto() {
    for techo in [1u64, 2, 1000, 999_999, 6_923_076] {
        let mut m = Maquina::desde_palabras(&bucle_infinito(), techo);
        assert_eq!(m.correr(), Veredicto::TechoExcedido);
        assert_eq!(m.pasos, techo, "el corte tiene que caer en el paso exacto");
    }
}

/// El corte es **el mismo en toda corrida**: no depende de un reloj, de un timeout
/// ni de una senal. Dos nodos que lo corran leen exactamente los mismos bytes.
#[test]
fn c5_el_veredicto_es_dato_de_consenso() {
    let canonicos: Vec<[u8; 5]> = (0..8)
        .map(|_| {
            let mut m = Maquina::desde_palabras(&bucle_infinito(), 12_345);
            m.correr().canonico()
        })
        .collect();
    assert!(canonicos.windows(2).all(|p| p[0] == p[1]));
    assert_eq!(canonicos[0], [2, 0, 0, 0, 0]);
}

/// Un techo de cero no ejecuta nada. Es el caso borde donde una implementacion
/// ingenua retira un paso antes de mirar el presupuesto.
#[test]
fn c5_techo_cero_no_ejecuta_nada() {
    let mut m = Maquina::desde_palabras(&bucle_infinito(), 0);
    assert_eq!(m.correr(), Veredicto::TechoExcedido);
    assert_eq!(m.pasos, 0);
}

/// **El segundo techo, el que agrego la Fase 4.** Un programa que toca mas paginas
/// de las que tiene presupuestadas se corta igual que uno que se pasa de pasos.
#[test]
fn c5_el_techo_de_paginas_tambien_corta() {
    // Un `lw` por pagina, avanzando de a 4 KiB: toca una pagina nueva cada vez.
    // El paso va en un registro y no en el inmediato: el inmediato de tipo I es de
    // doce bits con signo y 4096 no entra — la primera version de esta prueba lo
    // truncaba a cero, el puntero no avanzaba y el bucle no terminaba nunca.
    let prog = vec![
        (1u32 << 20 >> 12) << 12 | (5 << 7) | 0x37, // lui x5, 1 MiB
        (PAGINA >> 12) << 12 | (7 << 7) | 0x37,     // lui x7, 4096
        i(0, 5, 2, 6, 0x03),                        // lw  x6, 0(x5)
        r(0x00, 7, 5, 0, 5, 0x33),                  // add x5, x5, x7
        jal(0, -8),
    ];

    // El techo de pasos se pone finito **a proposito**: si el de paginas no
    // cortara, esto termina en `TechoExcedido` y la prueba falla, en vez de colgarse.
    let mut m = Maquina::desde_palabras(&prog, 10_000);
    m.techo_paginas = 3;
    assert_eq!(m.correr(), Veredicto::PaginasExcedidas);
    assert_eq!(m.paginas_usadas, 3);
}

/// Y no se corta por volver a la misma pagina: lo que se cuenta son paginas
/// **distintas**. Un bucle sobre 4 KiB corre para siempre con una sola pagina.
#[test]
fn c5_volver_a_la_misma_pagina_no_gasta_presupuesto() {
    let prog = vec![
        (1u32 << 20 >> 12) << 12 | (5 << 7) | 0x37, // lui x5, 1MiB
        i(0, 5, 2, 6, 0x03),                        // lw x6, 0(x5)
        jal(0, -4),
    ];
    let mut m = Maquina::desde_palabras(&prog, 100_000);
    m.techo_paginas = 1;
    assert_eq!(m.correr(), Veredicto::TechoExcedido);
    assert_eq!(m.paginas_usadas, 1);
}

// =========================================================================== //
// C6 — fuera de rango es trampa, no envolver
// =========================================================================== //

/// El arnes de Test 2 hacia `dir & MASK`: toda direccion invalida envolvia dentro
/// de la memoria. Determinista, si — pero **dependiente del tamano de memoria**, y
/// entonces el mismo programa daria distinto en dos generaciones. Acá es trampa.
#[test]
fn c6_leer_fuera_de_rango_es_trampa() {
    // lui x5, MEM  →  lw x6, 0(x5): la primera direccion que ya no existe.
    let prog = vec![
        (MEM >> 12) << 12 | (5 << 7) | 0x37,
        i(0, 5, 2, 6, 0x03),
        jal(0, 0),
    ];
    let mut m = Maquina::desde_palabras(&prog, 1000);
    m.techo_paginas = PAGINAS_INICIALES;
    assert_eq!(
        m.correr(),
        Veredicto::Trampa(Causa::MemoriaFueraDeRango),
        "envolver seria determinista pero dependeria del tamano de memoria"
    );
}

/// El caso que se escapa si el chequeo se hace sumando sin cuidado: una direccion
/// a cuatro bytes del final, donde `dir + ancho` envuelve el `u32`.
#[test]
fn c6_la_direccion_que_envuelve_el_contador_tambien_es_trampa() {
    let prog = vec![
        0xffff_f000u32 | (5 << 7) | 0x37, // lui x5, 0xfffff000
        i(0x7ff, 5, 2, 6, 0x03),          // lw x6, 2047(x5)
        jal(0, 0),
    ];
    let mut m = Maquina::desde_palabras(&prog, 1000);
    assert_eq!(m.correr(), Veredicto::Trampa(Causa::MemoriaFueraDeRango));
}

/// Escribir fuera de rango tampoco envuelve. Se prueba aparte porque el camino de
/// escritura es otro `match` y una correccion se puede aplicar a la mitad.
#[test]
fn c6_escribir_fuera_de_rango_es_trampa() {
    let prog = vec![
        (MEM >> 12) << 12 | (5 << 7) | 0x37,
        // sw x6, 0(x5) — tipo S
        (0 << 25) | (6 << 20) | (5 << 15) | (2 << 12) | (0 << 7) | 0x23,
        jal(0, 0),
    ];
    let mut m = Maquina::desde_palabras(&prog, 1000);
    assert_eq!(m.correr(), Veredicto::Trampa(Causa::MemoriaFueraDeRango));
}

/// El pc fuera del texto es trampa y no un indice a un arreglo de al lado.
#[test]
fn c6_el_pc_fuera_del_texto_es_trampa() {
    let prog = vec![jal(0, 4096)];
    let mut m = Maquina::desde_palabras(&prog, 1000);
    assert_eq!(m.correr(), Veredicto::Trampa(Causa::PcFueraDelTexto));
}

// =========================================================================== //
// La regresion que sostiene todo lo demas
// =========================================================================== //

/// **La maquina endurecida no movio ni un paso la semantica del arnes.**
///
/// `steps_per_verify` de Test 2 es 3.339.364 y es el unico numero de aquella
/// medicion que ninguna contaminacion puede tocar. Si los chequeos de rango, el
/// techo y la admision por secciones hubieran cambiado la semantica, este numero
/// se moveria — y con el se caeria todo el techo de §6.6, que se deriva de ahi.
#[test]
fn la_semantica_reproduce_test2_paso_a_paso() {
    let (mut m, syms) = admitir(vm::GUEST_RV, u64::MAX).expect("admitir");
    m.arrancar();
    let prepare = *syms.get("prepare").expect("prepare");
    let run = *syms.get("run").expect("run");
    m.llamar(prepare, &[0]); // ML-DSA-44

    let p0 = m.pasos;
    m.llamar(run, &[0, 10]);
    let d10 = m.pasos - p0;
    let p1 = m.pasos;
    m.llamar(run, &[0, 20]);
    let d20 = m.pasos - p1;

    assert_eq!((d20 - d10) / 10, 3_339_364, "steps_per_verify de Test 2");
}

/// Y una verificacion entra en los dos techos del ruleset inicial, con el margen
/// que Genesis eligio. Si esto falla, el bloque 0 no se puede escribir.
#[test]
fn una_verificacion_entra_en_los_dos_techos() {
    let (mut m, syms) = admitir(vm::GUEST_RV, u64::MAX).expect("admitir");
    m.arrancar();
    m.llamar(*syms.get("prepare").unwrap(), &[0]);

    m.borrar_paginas();
    let base = m.pasos;
    m.techo = base + vm::TECHO_INICIAL;
    m.techo_paginas = PAGINAS_INICIALES;
    let v = m.llamar(*syms.get("run").unwrap(), &[0, 1]);

    assert!(matches!(v, Veredicto::Retorno(_)), "termino en {:?}", v);
    let pasos = m.pasos - base;
    assert!(
        (vm::TECHO_INICIAL as f64) / (pasos as f64) >= 2.0,
        "margen de pasos {:.2}x, Genesis eligio 2x",
        (vm::TECHO_INICIAL as f64) / (pasos as f64)
    );
    assert!(m.paginas_usadas <= PAGINAS_INICIALES, "{} paginas", m.paginas_usadas);
    let _ = TEXT_BASE;
}

/// **El segundo número medido de la máquina, y el que cerró el piso de §8.5.**
///
/// Un SHA-256 escrito a mano, compilado a RV32IM y corrido acá: 4.898 pasos por
/// compresion. Se fija como regresion por la misma razon que `steps_per_verify` — de ese
/// numero cuelga el piso de permanencia, y si la semantica de la maquina se moviera sin
/// que nadie lo note, el piso quedaria mal calibrado y no habria forma de saberlo.
#[test]
fn el_costo_de_un_sha256_no_se_mueve() {
    let (mut m, syms) = admitir(vm::GUEST_SHA, u64::MAX).expect("admitir guest-sha");
    m.arrancar();
    let comprimir = *syms.get("comprimir").expect("simbolo comprimir");

    let base = m.pasos;
    m.llamar(comprimir, &[100]);
    let p100 = m.pasos - base;
    let base = m.pasos;
    m.llamar(comprimir, &[200]);
    let p200 = m.pasos - base;

    assert_eq!((p200 - p100) / 100, 4_898, "pasos por compresion SHA-256");
}

/// Y la admision acepta un binario que produjo otro toolchain y otro repo.
///
/// C2 y C4 se probaron contra el guest de Test 2, que es de otro proyecto; este lo
/// produce el nuestro. **Un criterio verificado contra un solo binario prueba menos de
/// lo que parece**, y las dos correcciones que C2 necesito salieron justamente de chocar
/// contra un binario real.
#[test]
fn la_admision_acepta_un_segundo_binario_independiente() {
    let (m, syms) = admitir(vm::GUEST_SHA, u64::MAX).expect("guest-sha tiene que entrar");
    assert_eq!(m.pasos, 0);
    assert!(syms.contains_key("comprimir"));
}
