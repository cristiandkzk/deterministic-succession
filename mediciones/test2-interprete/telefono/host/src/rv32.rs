//! Interprete RV32IM — el quinto motor del arnes.
//!
//! Es un interprete puro, del mismo perfil que `wasmi`: predecodifica el texto
//! una vez y despues despacha por match. No hay JIT y no hay optimizacion de
//! traza. Se escribio a mano en vez de tomar un crate para que la comparacion
//! mida el ISA y no la calidad de un emulador de terceros — y porque el set
//! entero de RV32IM entra en un archivo, que es justamente la propiedad que se
//! esta evaluando.
//!
//! Lleva un contador exacto de instrucciones retiradas: es determinista,
//! independiente del hardware, y es la primitiva que pide el techo de pasos.

use std::collections::BTreeMap;

/// Debe coincidir con MEM_SIZE / STACK en `guest-rv/src/main.rs`.
pub const MEM_SIZE: usize = 64 * 1024 * 1024;
const PAD: usize = 8;
const MASK: u32 = (MEM_SIZE as u32) - 1;
const TEXT_BASE: u32 = 0x1000;
const STACK_TOP: u32 = MEM_SIZE as u32;
/// Direccion de retorno imposible: cuando el pc la alcanza, la llamada volvio.
const SENTINEL: u32 = 0xFFFF_FFF0;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
#[repr(u8)]
enum Op {
    Lui, Auipc, Jal, Jalr,
    Beq, Bne, Blt, Bge, Bltu, Bgeu,
    Lb, Lh, Lw, Lbu, Lhu,
    Sb, Sh, Sw,
    Addi, Slti, Sltiu, Xori, Ori, Andi, Slli, Srli, Srai,
    Add, Sub, Sll, Slt, Sltu, Xor, Srl, Sra, Or, And,
    Mul, Mulh, Mulhsu, Mulhu, Div, Divu, Rem, Remu,
    Ecall, Nop, Illegal,
}

#[derive(Clone, Copy)]
struct Insn {
    op: Op,
    rd: u8,
    rs1: u8,
    rs2: u8,
    imm: i32,
}

const ILLEGAL: Insn = Insn { op: Op::Illegal, rd: 0, rs1: 0, rs2: 0, imm: 0 };

#[inline(always)]
fn sext(v: u32, bits: u32) -> i32 {
    ((v << (32 - bits)) as i32) >> (32 - bits)
}

fn decode(w: u32) -> Insn {
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
                _ => ILLEGAL,
            }
        }
        0x03 => match f3 {
            0 => mk(Op::Lb, i_imm),
            1 => mk(Op::Lh, i_imm),
            2 => mk(Op::Lw, i_imm),
            4 => mk(Op::Lbu, i_imm),
            5 => mk(Op::Lhu, i_imm),
            _ => ILLEGAL,
        },
        0x23 => {
            let imm = sext(((w >> 25) << 5) | ((w >> 7) & 0x1f), 12);
            match f3 {
                0 => mk(Op::Sb, imm),
                1 => mk(Op::Sh, imm),
                2 => mk(Op::Sw, imm),
                _ => ILLEGAL,
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
            _ => ILLEGAL,
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
            _ => ILLEGAL,
        },
        0x0f => mk(Op::Nop, 0),
        0x73 => mk(Op::Ecall, 0),
        _ => ILLEGAL,
    }
}

pub struct Rv32 {
    mem: Box<[u8; MEM_SIZE + PAD]>,
    x: [u32; 32],
    pc: u32,
    code: Vec<Insn>,
    entry: u32,
    pub steps: u64,
}

enum Halt {
    Returned,
    Ecall,
}

impl Rv32 {
    #[inline(always)]
    fn r8(&self, a: u32) -> u8 {
        self.mem[(a & MASK) as usize]
    }
    #[inline(always)]
    fn r16(&self, a: u32) -> u16 {
        let i = (a & MASK) as usize;
        u16::from_le_bytes([self.mem[i], self.mem[i + 1]])
    }
    #[inline(always)]
    fn r32(&self, a: u32) -> u32 {
        let i = (a & MASK) as usize;
        u32::from_le_bytes([self.mem[i], self.mem[i + 1], self.mem[i + 2], self.mem[i + 3]])
    }
    #[inline(always)]
    fn w8(&mut self, a: u32, v: u8) {
        self.mem[(a & MASK) as usize] = v;
    }
    #[inline(always)]
    fn w16(&mut self, a: u32, v: u16) {
        let i = (a & MASK) as usize;
        self.mem[i..i + 2].copy_from_slice(&v.to_le_bytes());
    }
    #[inline(always)]
    fn w32(&mut self, a: u32, v: u32) {
        let i = (a & MASK) as usize;
        self.mem[i..i + 4].copy_from_slice(&v.to_le_bytes());
    }
    #[inline(always)]
    fn set(&mut self, rd: u8, v: u32) {
        if rd != 0 {
            self.x[(rd & 31) as usize] = v;
        }
    }

    /// Carga un ELF32 RISC-V estatico y devuelve la tabla de simbolos.
    pub fn load(elf: &[u8]) -> Result<(Self, BTreeMap<String, u32>), String> {
        let g32 = |o: usize| -> u32 {
            u32::from_le_bytes([elf[o], elf[o + 1], elf[o + 2], elf[o + 3]])
        };
        let g16 = |o: usize| -> u16 { u16::from_le_bytes([elf[o], elf[o + 1]]) };

        if elf.len() < 52 || &elf[0..4] != b"\x7fELF" || elf[4] != 1 || elf[5] != 1 {
            return Err("no es un ELF32 little-endian".into());
        }
        if g16(18) != 0xf3 {
            return Err(format!("e_machine {:#x}, se esperaba RISC-V (0xf3)", g16(18)));
        }

        let mut mem: Box<[u8; MEM_SIZE + PAD]> = vec![0u8; MEM_SIZE + PAD]
            .into_boxed_slice()
            .try_into()
            .map_err(|_| "no se pudo reservar la memoria del guest")?;

        let entry = g32(24);
        let phoff = g32(28) as usize;
        let phentsize = g16(42) as usize;
        let phnum = g16(44) as usize;

        let mut top = TEXT_BASE;
        for i in 0..phnum {
            let p = phoff + i * phentsize;
            if g32(p) != 1 {
                continue; // solo PT_LOAD
            }
            let off = g32(p + 4) as usize;
            let vaddr = g32(p + 8);
            let filesz = g32(p + 16) as usize;
            let memsz = g32(p + 20);
            let dst = (vaddr & MASK) as usize;
            mem[dst..dst + filesz].copy_from_slice(&elf[off..off + filesz]);
            // El resto de memsz (.bss) ya esta en cero.
            top = top.max(vaddr + memsz);
        }

        // Tabla de simbolos: hace falta para llamar prepare/run por nombre.
        let shoff = g32(32) as usize;
        let shentsize = g16(46) as usize;
        let shnum = g16(48) as usize;
        let mut syms = BTreeMap::new();
        for i in 0..shnum {
            let s = shoff + i * shentsize;
            if g32(s + 4) != 2 {
                continue; // SHT_SYMTAB
            }
            let symoff = g32(s + 16) as usize;
            let symsz = g32(s + 20) as usize;
            let strsec = shoff + g32(s + 24) as usize * shentsize;
            let stroff = g32(strsec + 16) as usize;
            for k in 0..(symsz / 16) {
                let e = symoff + k * 16;
                let name_off = stroff + g32(e) as usize;
                let value = g32(e + 4);
                let end = elf[name_off..].iter().position(|&c| c == 0).unwrap_or(0);
                if end > 0 {
                    let name = String::from_utf8_lossy(&elf[name_off..name_off + end]).into_owned();
                    syms.insert(name, value);
                }
            }
        }

        // Predecodifica todo el texto una sola vez, igual que wasmi traduce el
        // modulo al instanciarlo. Indexado por (pc - TEXT_BASE) / 4.
        let words = ((top.saturating_sub(TEXT_BASE) + 4) / 4) as usize;
        let mut code = Vec::with_capacity(words);
        for k in 0..words {
            let a = TEXT_BASE + (k as u32) * 4;
            let i = (a & MASK) as usize;
            code.push(decode(u32::from_le_bytes([
                mem[i], mem[i + 1], mem[i + 2], mem[i + 3],
            ])));
        }

        Ok((
            Rv32 { mem, x: [0; 32], pc: entry, code, entry, steps: 0 },
            syms,
        ))
    }

    /// Corre `_start`, que fija `gp` y declara el heap, y termina en `ecall`.
    pub fn boot(&mut self) -> Result<(), String> {
        self.pc = self.entry;
        self.x[2] = STACK_TOP;
        match self.exec()? {
            Halt::Ecall => Ok(()),
            Halt::Returned => Err("_start volvio en vez de hacer ecall".into()),
        }
    }

    /// Llama a `addr` con la ABI de C y devuelve a0.
    pub fn call(&mut self, addr: u32, args: &[u32]) -> Result<u32, String> {
        self.pc = addr;
        self.x[1] = SENTINEL; // ra
        self.x[2] = STACK_TOP; // sp
        for (i, a) in args.iter().enumerate() {
            self.x[10 + i] = *a;
        }
        match self.exec()? {
            Halt::Returned => Ok(self.x[10]),
            Halt::Ecall => Err(format!(
                "el guest hizo ecall durante la llamada (a0={:#x}) — panic",
                self.x[10]
            )),
        }
    }

    fn exec(&mut self) -> Result<Halt, String> {
        loop {
            if self.pc == SENTINEL {
                return Ok(Halt::Returned);
            }
            if self.pc < TEXT_BASE {
                return Err(format!("pc fuera del texto: {:#x}", self.pc));
            }
            let idx = ((self.pc - TEXT_BASE) >> 2) as usize;
            let ins = match self.code.get(idx) {
                Some(i) => *i,
                None => return Err(format!("pc fuera del texto: {:#x}", self.pc)),
            };
            self.steps += 1;

            let a = self.x[(ins.rs1 & 31) as usize];
            let b = self.x[(ins.rs2 & 31) as usize];
            let mut next = self.pc.wrapping_add(4);

            match ins.op {
                Op::Lui => self.set(ins.rd, ins.imm as u32),
                Op::Auipc => self.set(ins.rd, self.pc.wrapping_add(ins.imm as u32)),
                Op::Jal => {
                    self.set(ins.rd, next);
                    next = self.pc.wrapping_add(ins.imm as u32);
                }
                Op::Jalr => {
                    let t = a.wrapping_add(ins.imm as u32) & !1;
                    self.set(ins.rd, next);
                    next = t;
                }
                Op::Beq => if a == b { next = self.pc.wrapping_add(ins.imm as u32) },
                Op::Bne => if a != b { next = self.pc.wrapping_add(ins.imm as u32) },
                Op::Blt => if (a as i32) < (b as i32) { next = self.pc.wrapping_add(ins.imm as u32) },
                Op::Bge => if (a as i32) >= (b as i32) { next = self.pc.wrapping_add(ins.imm as u32) },
                Op::Bltu => if a < b { next = self.pc.wrapping_add(ins.imm as u32) },
                Op::Bgeu => if a >= b { next = self.pc.wrapping_add(ins.imm as u32) },

                Op::Lb => { let v = self.r8(a.wrapping_add(ins.imm as u32)) as i8 as i32 as u32; self.set(ins.rd, v) }
                Op::Lh => { let v = self.r16(a.wrapping_add(ins.imm as u32)) as i16 as i32 as u32; self.set(ins.rd, v) }
                Op::Lw => { let v = self.r32(a.wrapping_add(ins.imm as u32)); self.set(ins.rd, v) }
                Op::Lbu => { let v = self.r8(a.wrapping_add(ins.imm as u32)) as u32; self.set(ins.rd, v) }
                Op::Lhu => { let v = self.r16(a.wrapping_add(ins.imm as u32)) as u32; self.set(ins.rd, v) }
                Op::Sb => self.w8(a.wrapping_add(ins.imm as u32), b as u8),
                Op::Sh => self.w16(a.wrapping_add(ins.imm as u32), b as u16),
                Op::Sw => self.w32(a.wrapping_add(ins.imm as u32), b),

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
                // Semantica de division de RV32M: sin trampas, con casos
                // definidos para divisor cero y para el overflow de INT_MIN/-1.
                Op::Div => self.set(ins.rd, if b == 0 { u32::MAX }
                    else if a == 0x8000_0000 && b == u32::MAX { a }
                    else { ((a as i32).wrapping_div(b as i32)) as u32 }),
                Op::Divu => self.set(ins.rd, if b == 0 { u32::MAX } else { a / b }),
                Op::Rem => self.set(ins.rd, if b == 0 { a }
                    else if a == 0x8000_0000 && b == u32::MAX { 0 }
                    else { ((a as i32).wrapping_rem(b as i32)) as u32 }),
                Op::Remu => self.set(ins.rd, if b == 0 { a } else { a % b }),

                Op::Nop => {}
                Op::Ecall => return Ok(Halt::Ecall),
                Op::Illegal => {
                    return Err(format!("instruccion ilegal en pc={:#x}", self.pc))
                }
            }
            self.pc = next;
        }
    }
}
