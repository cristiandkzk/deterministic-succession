//! La maquina determinista de §6.2 — RV32IM, con techo y con trampas.
//!
//! Deriva del interprete de `test2-interprete/telefono/host/src/rv32.rs`, que ya
//! tenia lo caro: el set completo, el predecodificado y el conteo exacto de pasos
//! que reproduce byte a byte entre x86 y ARM. Lo que cambia es **quien escribe el
//! programa**. Aquel corria un guest propio; este corre el programa de la
//! contraparte de una impugnacion, que quiere que el nodo se cuelgue o se caiga.
//!
//! Tres diferencias, y las tres son de consenso y no de estilo:
//!
//! - **el techo corta.** El arnes cuenta pasos y no para nunca. Acá `pasos` es un
//!   presupuesto: al agotarse la maquina para en el paso exacto y devuelve un
//!   veredicto. Es lo que impide que exista una impugnacion mas cara de verificar
//!   que de crear;
//! - **fuera de rango es trampa, no envolver.** El arnes hace `dir & MASK`, que es
//!   determinista pero **depende del tamano de memoria**. Si el tamano fuera un
//!   parametro del espacio, el mismo programa daria distinto en dos generaciones y
//!   eso rompe I1 justo donde no se puede. Acá el tamano es constante de Genesis y
//!   toda direccion invalida es `Trampa`;
//! - **todo final es un veredicto, no un `Err`.** Las dos partes de una impugnacion
//!   tienen que leer el mismo resultado. Un error de ejecucion que cada nodo
//!   reporta como quiere no sirve: el final entra al hash del bloque.

/// Tamano de la memoria del guest. **Constante de Genesis, no parametro** (C6):
/// el resultado de un programa no puede depender de la generacion en la que corre.
pub const MEM: u32 = 64 * 1024 * 1024;
/// Donde arranca el texto. Tiene que coincidir con el `link.ld` del guest.
pub const TEXT_BASE: u32 = 0x1000;
/// Tope de pila al entrar a una llamada.
pub const PILA: u32 = MEM;
/// Direccion de retorno imposible: cuando el pc la alcanza, la llamada volvio.
pub const CENTINELA: u32 = 0xFFFF_FFF0;
/// Tamano de pagina para el segundo techo. **Constante de Genesis.**
pub const PAGINA: u32 = 4096;

/// Como termino una corrida. **Esto es dato de consenso**: entra al hash del
/// bloque y las dos partes de una impugnacion leen exactamente lo mismo.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Veredicto {
    /// Volvio al centinela. `a0` es el valor de retorno.
    Retorno(u32),
    /// Hizo `ecall`. El guest lo usa para senalar panic y para terminar `_start`.
    Ecall(u32),
    /// Se agoto el presupuesto de pasos. **No es un error: es un rechazo con causa.**
    TechoExcedido,
    /// Se agoto el presupuesto de **paginas distintas tocadas**. El segundo techo,
    /// el que Fase 4 tuvo que agregar: sin el, un paso miente por 23x.
    PaginasExcedidas,
    /// Acceso fuera de la memoria declarada, o pc fuera del texto.
    Trampa(Causa),
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Causa {
    /// Lectura o escritura fuera de `MEM`.
    MemoriaFueraDeRango,
    /// El pc salio del texto predecodificado.
    PcFueraDelTexto,
    /// Una palabra que no es RV32IM. **No deberia poder llegar acá**: la admision
    /// la rechaza antes (C2). Existe para que el caso no sea un `unreachable!`,
    /// que en consenso es un panic con otro nombre.
    InstruccionIlegal,
}

impl Veredicto {
    /// La forma canonica que entra al hash. Un solo byte de clase y una palabra
    /// de dato: no hay texto, porque el texto es donde se cuelan las diferencias
    /// entre implementaciones.
    pub fn canonico(&self) -> [u8; 5] {
        let (clase, dato) = match self {
            Veredicto::Retorno(v) => (0u8, *v),
            Veredicto::Ecall(v) => (1, *v),
            Veredicto::TechoExcedido => (2, 0),
            Veredicto::PaginasExcedidas => (4, 0),
            Veredicto::Trampa(Causa::MemoriaFueraDeRango) => (3, 0),
            Veredicto::Trampa(Causa::PcFueraDelTexto) => (3, 1),
            Veredicto::Trampa(Causa::InstruccionIlegal) => (3, 2),
        };
        let b = dato.to_le_bytes();
        [clase, b[0], b[1], b[2], b[3]]
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
#[repr(u8)]
pub enum Op {
    Lui, Auipc, Jal, Jalr,
    Beq, Bne, Blt, Bge, Bltu, Bgeu,
    Lb, Lh, Lw, Lbu, Lhu,
    Sb, Sh, Sw,
    Addi, Slti, Sltiu, Xori, Ori, Andi, Slli, Srli, Srai,
    Add, Sub, Sll, Slt, Sltu, Xor, Srl, Sra, Or, And,
    Mul, Mulh, Mulhsu, Mulhu, Div, Divu, Rem, Remu,
    Ecall, Nop, Ilegal,
}

impl Op {
    /// Las cuatro clases con las que se mide C7. No son las clases del ISA: son
    /// las que se sospecha que tienen ritmos distintos.
    pub fn clase(self) -> Clase {
        use Op::*;
        match self {
            Mul | Mulh | Mulhsu | Mulhu => Clase::Multiplicacion,
            Div | Divu | Rem | Remu => Clase::Division,
            Lb | Lh | Lw | Lbu | Lhu | Sb | Sh | Sw => Clase::Memoria,
            Jal | Jalr | Beq | Bne | Blt | Bge | Bltu | Bgeu => Clase::Salto,
            _ => Clase::Aritmetica,
        }
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Clase {
    Aritmetica,
    Multiplicacion,
    Division,
    Memoria,
    Salto,
}

#[derive(Clone, Copy)]
pub struct Insn {
    pub op: Op,
    rd: u8,
    rs1: u8,
    rs2: u8,
    imm: i32,
}

pub const ILEGAL: Insn = Insn { op: Op::Ilegal, rd: 0, rs1: 0, rs2: 0, imm: 0 };

#[inline(always)]
fn sext(v: u32, bits: u32) -> i32 {
    ((v << (32 - bits)) as i32) >> (32 - bits)
}

/// El decodificador entero de RV32IM. **Acá se lee C2 de un vistazo: no hay una
/// sola rama de punto flotante.** Los opcodes 0x07 (`flw`), 0x27 (`fsw`), 0x43,
/// 0x47, 0x4b, 0x4f (fused multiply-add) y 0x53 (el resto de F y D) caen todos en
/// `Ilegal` por el `_` final — no porque se los rechace, sino porque nunca se los
/// escribio.
pub fn decodificar(w: u32) -> Insn {
    let opc = w & 0x7f;
    let rd = ((w >> 7) & 0x1f) as u8;
    let f3 = (w >> 12) & 7;
    let rs1 = ((w >> 15) & 0x1f) as u8;
    let rs2 = ((w >> 20) & 0x1f) as u8;
    let f7 = w >> 25;
    let i_imm = sext(w >> 20, 12);
    let mk = |op: Op, imm: i32| Insn { op, rd, rs1, rs2, imm };

    match opc {
        0x37 => mk(Op::Lui, (w & 0xffff_f000) as i32),
        0x17 => mk(Op::Auipc, (w & 0xffff_f000) as i32),
        0x6f => {
            let imm = ((w >> 31) & 1) << 20
                | ((w >> 12) & 0xff) << 12
                | ((w >> 20) & 1) << 11
                | ((w >> 21) & 0x3ff) << 1;
            mk(Op::Jal, sext(imm, 21))
        }
        0x67 if f3 == 0 => mk(Op::Jalr, i_imm),
        0x63 => {
            let imm = ((w >> 31) & 1) << 12
                | ((w >> 7) & 1) << 11
                | ((w >> 25) & 0x3f) << 5
                | ((w >> 8) & 0xf) << 1;
            let imm = sext(imm, 13);
            match f3 {
                0 => mk(Op::Beq, imm),
                1 => mk(Op::Bne, imm),
                4 => mk(Op::Blt, imm),
                5 => mk(Op::Bge, imm),
                6 => mk(Op::Bltu, imm),
                7 => mk(Op::Bgeu, imm),
                _ => ILEGAL,
            }
        }
        0x03 => match f3 {
            0 => mk(Op::Lb, i_imm),
            1 => mk(Op::Lh, i_imm),
            2 => mk(Op::Lw, i_imm),
            4 => mk(Op::Lbu, i_imm),
            5 => mk(Op::Lhu, i_imm),
            _ => ILEGAL,
        },
        0x23 => {
            let imm = sext(((w >> 25) << 5) | ((w >> 7) & 0x1f), 12);
            match f3 {
                0 => mk(Op::Sb, imm),
                1 => mk(Op::Sh, imm),
                2 => mk(Op::Sw, imm),
                _ => ILEGAL,
            }
        }
        0x13 => match f3 {
            0 => mk(Op::Addi, i_imm),
            2 => mk(Op::Slti, i_imm),
            3 => mk(Op::Sltiu, i_imm),
            4 => mk(Op::Xori, i_imm),
            6 => mk(Op::Ori, i_imm),
            7 => mk(Op::Andi, i_imm),
            1 if f7 == 0x00 => mk(Op::Slli, rs2 as i32),
            5 if f7 == 0x00 => mk(Op::Srli, rs2 as i32),
            5 if f7 == 0x20 => mk(Op::Srai, rs2 as i32),
            _ => ILEGAL,
        },
        0x33 => match (f7, f3) {
            (0x00, 0) => mk(Op::Add, 0),
            (0x20, 0) => mk(Op::Sub, 0),
            (0x00, 1) => mk(Op::Sll, 0),
            (0x00, 2) => mk(Op::Slt, 0),
            (0x00, 3) => mk(Op::Sltu, 0),
            (0x00, 4) => mk(Op::Xor, 0),
            (0x00, 5) => mk(Op::Srl, 0),
            (0x20, 5) => mk(Op::Sra, 0),
            (0x00, 6) => mk(Op::Or, 0),
            (0x00, 7) => mk(Op::And, 0),
            (0x01, 0) => mk(Op::Mul, 0),
            (0x01, 1) => mk(Op::Mulh, 0),
            (0x01, 2) => mk(Op::Mulhsu, 0),
            (0x01, 3) => mk(Op::Mulhu, 0),
            (0x01, 4) => mk(Op::Div, 0),
            (0x01, 5) => mk(Op::Divu, 0),
            (0x01, 6) => mk(Op::Rem, 0),
            (0x01, 7) => mk(Op::Remu, 0),
            _ => ILEGAL,
        },
        0x0f => mk(Op::Nop, 0),
        0x73 => mk(Op::Ecall, 0),
        _ => ILEGAL,
    }
}

/// El estado de la maquina. Se construye desde `admision::admitir`.
pub struct Maquina {
    mem: Box<[u8]>,
    x: [u32; 32],
    pc: u32,
    codigo: Box<[Insn]>,
    /// Pasos retirados. **Determinista e independiente del hardware** — es la
    /// propiedad que vuelve admisible un techo en pasos y no en tiempo (I2).
    pub pasos: u64,
    /// Presupuesto. Al llegar a cero la corrida termina en `TechoExcedido`.
    pub techo: u64,
    /// `e_entry` del ELF. No tiene por que ser `TEXT_BASE`.
    pub entrada: u32,
    /// Un bit por pagina de 4 KiB tocada. **Esto no es instrumentacion: es el
    /// segundo techo**, y por eso no tiene interruptor. Un chequeo de consenso que
    /// se puede apagar es una bifurcacion esperando a que dos nodos elijan distinto.
    pub paginas: Vec<u64>,
    /// Cuantas paginas distintas se tocaron.
    pub paginas_usadas: u32,
    /// Presupuesto de paginas. Ver `PAGINAS_INICIALES`.
    pub techo_paginas: u32,
}

impl Maquina {
    pub fn nueva(mem: Box<[u8]>, codigo: Box<[Insn]>, techo: u64, entrada: u32) -> Self {
        let bits = (mem.len() / 4096 + 63) / 64;
        Maquina {
            mem,
            x: [0; 32],
            pc: entrada,
            codigo,
            pasos: 0,
            techo,
            entrada,
            paginas: vec![0u64; bits],
            paginas_usadas: 0,
            techo_paginas: u32::MAX,
        }
    }

    /// Una maquina con el texto puesto a mano, sin pasar por ELF. **Solo para la
    /// medicion**: las mezclas de C7 son programas sinteticos que no tiene sentido
    /// compilar. Un predicado real siempre entra por `admision::admitir`.
    pub fn desde_palabras(palabras: &[u32], techo: u64) -> Self {
        let mut mem = vec![0u8; MEM as usize].into_boxed_slice();
        let base = TEXT_BASE as usize;
        for (k, w) in palabras.iter().enumerate() {
            mem[base + k * 4..base + k * 4 + 4].copy_from_slice(&w.to_le_bytes());
        }
        let codigo: Vec<Insn> = palabras.iter().map(|w| decodificar(*w)).collect();
        Maquina::nueva(mem, codigo.into_boxed_slice(), techo, TEXT_BASE)
    }

    /// Lee una palabra de la memoria del guest. Solo para el arnes: el protocolo
    /// mueve datos por la region de entrada/salida, no leyendo memoria a mano.
    pub fn leer32(&self, a: u32) -> Option<u32> {
        let i = a as usize;
        if i + 4 > self.mem.len() {
            return None;
        }
        Some(u32::from_le_bytes([
            self.mem[i], self.mem[i + 1], self.mem[i + 2], self.mem[i + 3],
        ]))
    }

    /// Escribe bytes en la memoria del guest antes de correr. Es como entra la
    /// clave publica y la firma de una transaccion.
    pub fn escribir(&mut self, a: u32, datos: &[u8]) -> bool {
        let i = a as usize;
        match i.checked_add(datos.len()) {
            Some(fin) if fin <= self.mem.len() => {
                self.mem[i..fin].copy_from_slice(datos);
                true
            }
            _ => false,
        }
    }

    #[inline(always)]
    fn set(&mut self, rd: u8, v: u32) {
        if rd != 0 {
            self.x[(rd & 31) as usize] = v;
        }
    }

    /// Huella del estado observable: los 32 registros y una ventana de memoria.
    ///
    /// **Es el instrumento de C3.** Comparar solo el conteo de pasos dejaria pasar
    /// una diferencia de semantica que no cambie cuantas instrucciones se retiran
    /// —un `sra` que desplaza sin signo, un `divu` que trata el cero distinto—, y
    /// esas son justamente las que bifurcan una cadena sin que nadie las vea.
    pub fn huella_estado(&self, base: u32, largo: u32) -> u64 {
        let mut h: u64 = 0xcbf2_9ce4_8422_2325;
        let comer = |b: u8, h: &mut u64| {
            *h ^= b as u64;
            *h = h.wrapping_mul(0x0000_0100_0000_01b3);
        };
        for r in &self.x {
            for b in r.to_le_bytes() {
                comer(b, &mut h);
            }
        }
        let (i, f) = (base as usize, (base + largo) as usize);
        if f <= self.mem.len() {
            for b in &self.mem[i..f] {
                comer(*b, &mut h);
            }
        }
        h
    }

    /// Cuantas paginas distintas de 4 KiB toco hasta ahora.
    pub fn paginas_tocadas(&self) -> u32 {
        self.paginas.iter().map(|w| w.count_ones()).sum()
    }

    /// Borra el mapa. **Solo para medir un tramo**: dentro de una corrida el mapa
    /// no se borra nunca, porque el techo es sobre el total de la verificacion.
    pub fn borrar_paginas(&mut self) {
        for w in self.paginas.iter_mut() {
            *w = 0;
        }
        self.paginas_usadas = 0;
    }

    /// Corre `_start` y devuelve donde paro. El guest bare-metal fija `gp`,
    /// declara el heap y termina en `ecall`.
    pub fn arrancar(&mut self) -> Veredicto {
        self.pc = self.entrada;
        self.x[2] = PILA;
        self.correr()
    }

    /// Llama a `dir` con la ABI de C y corre hasta el veredicto.
    pub fn llamar(&mut self, dir: u32, args: &[u32]) -> Veredicto {
        self.pc = dir;
        self.x[1] = CENTINELA;
        self.x[2] = PILA;
        for (i, a) in args.iter().enumerate().take(8) {
            self.x[10 + i] = *a;
        }
        self.correr()
    }

    /// El lazo. Devuelve **siempre** un veredicto: no hay camino que haga `panic`
    /// ni que devuelva un error de texto libre (C4, C5).
    pub fn correr(&mut self) -> Veredicto {
        let largo = self.mem.len();
        loop {
            if self.pc == CENTINELA {
                return Veredicto::Retorno(self.x[10]);
            }
            if self.pc < TEXT_BASE || (self.pc & 3) != 0 {
                return Veredicto::Trampa(Causa::PcFueraDelTexto);
            }
            let idx = ((self.pc - TEXT_BASE) >> 2) as usize;
            let ins = match self.codigo.get(idx) {
                Some(i) => *i,
                None => return Veredicto::Trampa(Causa::PcFueraDelTexto),
            };
            // El techo se chequea **antes** de retirar el paso, para que el corte
            // caiga en el paso exacto y no en el siguiente: dos nodos que cuentan
            // distinto por uno leen veredictos distintos.
            if self.pasos >= self.techo {
                return Veredicto::TechoExcedido;
            }
            self.pasos += 1;

            let a = self.x[(ins.rs1 & 31) as usize];
            let b = self.x[(ins.rs2 & 31) as usize];
            let mut sig = self.pc.wrapping_add(4);

            // Direccion efectiva de las de memoria, chequeada una sola vez. El
            // ancho se suma con `checked_add` porque una direccion cerca de 2^32
            // envolveria y volveria a caer dentro del rango.
            macro_rules! dir {
                ($ancho:expr) => {{
                    let d = a.wrapping_add(ins.imm as u32) as usize;
                    match d.checked_add($ancho) {
                        Some(f) if f <= largo => {
                            let pg = d >> 12;
                            let (w, bit) = (pg >> 6, 1u64 << (pg & 63));
                            if self.paginas[w] & bit == 0 {
                                if self.paginas_usadas >= self.techo_paginas {
                                    return Veredicto::PaginasExcedidas;
                                }
                                self.paginas[w] |= bit;
                                self.paginas_usadas += 1;
                            }
                            d
                        }
                        _ => return Veredicto::Trampa(Causa::MemoriaFueraDeRango),
                    }
                }};
            }

            match ins.op {
                Op::Lui => self.set(ins.rd, ins.imm as u32),
                Op::Auipc => self.set(ins.rd, self.pc.wrapping_add(ins.imm as u32)),
                Op::Jal => {
                    self.set(ins.rd, sig);
                    sig = self.pc.wrapping_add(ins.imm as u32);
                }
                Op::Jalr => {
                    let t = a.wrapping_add(ins.imm as u32) & !1;
                    self.set(ins.rd, sig);
                    sig = t;
                }
                Op::Beq => if a == b { sig = self.pc.wrapping_add(ins.imm as u32) },
                Op::Bne => if a != b { sig = self.pc.wrapping_add(ins.imm as u32) },
                Op::Blt => if (a as i32) < (b as i32) { sig = self.pc.wrapping_add(ins.imm as u32) },
                Op::Bge => if (a as i32) >= (b as i32) { sig = self.pc.wrapping_add(ins.imm as u32) },
                Op::Bltu => if a < b { sig = self.pc.wrapping_add(ins.imm as u32) },
                Op::Bgeu => if a >= b { sig = self.pc.wrapping_add(ins.imm as u32) },

                Op::Lb => { let i = dir!(1); let v = self.mem[i] as i8 as i32 as u32; self.set(ins.rd, v) }
                Op::Lbu => { let i = dir!(1); let v = self.mem[i] as u32; self.set(ins.rd, v) }
                Op::Lh => {
                    let i = dir!(2);
                    let v = u16::from_le_bytes([self.mem[i], self.mem[i + 1]]) as i16 as i32 as u32;
                    self.set(ins.rd, v)
                }
                Op::Lhu => {
                    let i = dir!(2);
                    let v = u16::from_le_bytes([self.mem[i], self.mem[i + 1]]) as u32;
                    self.set(ins.rd, v)
                }
                Op::Lw => {
                    let i = dir!(4);
                    let v = u32::from_le_bytes([
                        self.mem[i], self.mem[i + 1], self.mem[i + 2], self.mem[i + 3],
                    ]);
                    self.set(ins.rd, v)
                }
                Op::Sb => { let i = dir!(1); self.mem[i] = b as u8 }
                Op::Sh => {
                    let i = dir!(2);
                    self.mem[i..i + 2].copy_from_slice(&(b as u16).to_le_bytes());
                }
                Op::Sw => {
                    let i = dir!(4);
                    self.mem[i..i + 4].copy_from_slice(&b.to_le_bytes());
                }

                Op::Addi => self.set(ins.rd, a.wrapping_add(ins.imm as u32)),
                Op::Slti => self.set(ins.rd, ((a as i32) < ins.imm) as u32),
                Op::Sltiu => self.set(ins.rd, (a < ins.imm as u32) as u32),
                Op::Xori => self.set(ins.rd, a ^ ins.imm as u32),
                Op::Ori => self.set(ins.rd, a | ins.imm as u32),
                Op::Andi => self.set(ins.rd, a & ins.imm as u32),
                Op::Slli => self.set(ins.rd, a << (ins.imm & 31)),
                Op::Srli => self.set(ins.rd, a >> (ins.imm & 31)),
                Op::Srai => self.set(ins.rd, ((a as i32) >> (ins.imm & 31)) as u32),

                Op::Add => self.set(ins.rd, a.wrapping_add(b)),
                Op::Sub => self.set(ins.rd, a.wrapping_sub(b)),
                Op::Sll => self.set(ins.rd, a << (b & 31)),
                Op::Slt => self.set(ins.rd, ((a as i32) < (b as i32)) as u32),
                Op::Sltu => self.set(ins.rd, (a < b) as u32),
                Op::Xor => self.set(ins.rd, a ^ b),
                Op::Srl => self.set(ins.rd, a >> (b & 31)),
                Op::Sra => self.set(ins.rd, ((a as i32) >> (b & 31)) as u32),
                Op::Or => self.set(ins.rd, a | b),
                Op::And => self.set(ins.rd, a & b),

                Op::Mul => self.set(ins.rd, a.wrapping_mul(b)),
                Op::Mulh => self.set(ins.rd, (((a as i32 as i64) * (b as i32 as i64)) >> 32) as u32),
                Op::Mulhsu => self.set(ins.rd, (((a as i32 as i64) * (b as i64)) >> 32) as u32),
                Op::Mulhu => self.set(ins.rd, (((a as u64) * (b as u64)) >> 32) as u32),
                // Semantica de RV32M: sin trampas, con casos definidos para el
                // divisor cero y el overflow de INT_MIN/-1. **En consenso esto no
                // es un detalle**: si la division por cero fuera una trampa, dos
                // implementaciones podrian discrepar sobre si el programa fallo.
                Op::Div => self.set(ins.rd, if b == 0 { u32::MAX }
                    else if a == 0x8000_0000 && b == u32::MAX { a }
                    else { ((a as i32).wrapping_div(b as i32)) as u32 }),
                Op::Divu => self.set(ins.rd, if b == 0 { u32::MAX } else { a / b }),
                Op::Rem => self.set(ins.rd, if b == 0 { a }
                    else if a == 0x8000_0000 && b == u32::MAX { 0 }
                    else { ((a as i32).wrapping_rem(b as i32)) as u32 }),
                Op::Remu => self.set(ins.rd, if b == 0 { a } else { a % b }),

                Op::Nop => {}
                Op::Ecall => return Veredicto::Ecall(self.x[10]),
                Op::Ilegal => return Veredicto::Trampa(Causa::InstruccionIlegal),
            }
            self.pc = sig;
        }
    }
}
