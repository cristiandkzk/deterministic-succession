//! Interprete RV64IMAC — el sexto motor del arnes.
//!
//! Mismo diseño que `rv32.rs` (predecodifica una vez, despacha por match), asi
//! que el par RV32/RV64 aisla una sola variable: el ancho de registro. Es lo
//! que mide cuanto cuesta que Keccak trabaje en carriles de 64 bits sobre una
//! maquina de 32.
//!
//! Cubre mas que RV32IM porque no queda opcion: el unico target bare-metal de
//! 64 bits que trae Rust precompilado es `riscv64imac`, y el `core` que viene
//! con el ya esta compilado con instrucciones comprimidas. Asi que:
//!
//!   - **C** — se expanden a su equivalente de 32 bits al predecodificar, de
//!     modo que el bucle de ejecucion no las distingue; solo cambia cuanto
//!     avanza el pc.
//!   - **A** — semantica monohilo: LR es un load, SC siempre tiene exito, los
//!     AMO son lectura-modificacion-escritura sin contencion posible.
//!
//! Vale notar para la decision de maquina: RV64IM "puro" son ~59 instrucciones.
//! Las otras dos extensiones entran aca por una limitacion del toolchain, no
//! porque la spec de la cadena tenga que incluirlas.

use std::collections::BTreeMap;

/// Debe coincidir con MEM_SIZE / STACK en `guest-rv64/src/main.rs`.
pub const MEM_SIZE: usize = 64 * 1024 * 1024;
const PAD: usize = 8;
const MASK: u64 = (MEM_SIZE as u64) - 1;
const TEXT_BASE: u64 = 0x1000;
const STACK_TOP: u64 = MEM_SIZE as u64;
const SENTINEL: u64 = 0xFFFF_FFFF_FFFF_FFF0;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
#[repr(u8)]
enum Op {
    Lui, Auipc, Jal, Jalr,
    Beq, Bne, Blt, Bge, Bltu, Bgeu,
    Lb, Lh, Lw, Lbu, Lhu, Lwu, Ld,
    Sb, Sh, Sw, Sd,
    Addi, Slti, Sltiu, Xori, Ori, Andi, Slli, Srli, Srai,
    Add, Sub, Sll, Slt, Sltu, Xor, Srl, Sra, Or, And,
    Addiw, Slliw, Srliw, Sraiw,
    Addw, Subw, Sllw, Srlw, Sraw,
    Mul, Mulh, Mulhsu, Mulhu, Div, Divu, Rem, Remu,
    Mulw, Divw, Divuw, Remw, Remuw,
    /// `imm` lleva el funct5; el ancho va en el propio opcode.
    AmoW, AmoD,
    Ecall, Nop, Illegal,
}

#[derive(Clone, Copy)]
struct Insn {
    op: Op,
    rd: u8,
    rs1: u8,
    rs2: u8,
    imm: i32,
    /// 2 para comprimida, 4 para completa. Es lo unico que sobrevive de C.
    len: u8,
}

const ILLEGAL: Insn = Insn { op: Op::Illegal, rd: 0, rs1: 0, rs2: 0, imm: 0, len: 2 };

#[inline(always)]
fn sext(v: u32, bits: u32) -> i32 {
    ((v << (32 - bits)) as i32) >> (32 - bits)
}

fn mk(op: Op, rd: u8, rs1: u8, rs2: u8, imm: i32, len: u8) -> Insn {
    Insn { op, rd, rs1, rs2, imm, len }
}

// ---------- instrucciones de 32 bits ----------

fn decode32(w: u32) -> Insn {
    let opc = w & 0x7f;
    let rd = ((w >> 7) & 0x1f) as u8;
    let f3 = (w >> 12) & 7;
    let rs1 = ((w >> 15) & 0x1f) as u8;
    let rs2 = ((w >> 20) & 0x1f) as u8;
    let f7 = w >> 25;
    let i_imm = sext(w >> 20, 12);
    let m = |op: Op, imm: i32| mk(op, rd, rs1, rs2, imm, 4);

    match opc {
        0x37 => m(Op::Lui, sext(w & 0xffff_f000, 32)),
        0x17 => m(Op::Auipc, sext(w & 0xffff_f000, 32)),
        0x6f => {
            let imm = ((w >> 31) & 1) << 20
                | ((w >> 12) & 0xff) << 12
                | ((w >> 20) & 1) << 11
                | ((w >> 21) & 0x3ff) << 1;
            m(Op::Jal, sext(imm, 21))
        }
        0x67 if f3 == 0 => m(Op::Jalr, i_imm),
        0x63 => {
            let imm = ((w >> 31) & 1) << 12
                | ((w >> 7) & 1) << 11
                | ((w >> 25) & 0x3f) << 5
                | ((w >> 8) & 0xf) << 1;
            let imm = sext(imm, 13);
            match f3 {
                0 => m(Op::Beq, imm),
                1 => m(Op::Bne, imm),
                4 => m(Op::Blt, imm),
                5 => m(Op::Bge, imm),
                6 => m(Op::Bltu, imm),
                7 => m(Op::Bgeu, imm),
                _ => ILLEGAL,
            }
        }
        0x03 => match f3 {
            0 => m(Op::Lb, i_imm),
            1 => m(Op::Lh, i_imm),
            2 => m(Op::Lw, i_imm),
            3 => m(Op::Ld, i_imm),
            4 => m(Op::Lbu, i_imm),
            5 => m(Op::Lhu, i_imm),
            6 => m(Op::Lwu, i_imm),
            _ => ILLEGAL,
        },
        0x23 => {
            let imm = sext(((w >> 25) << 5) | ((w >> 7) & 0x1f), 12);
            match f3 {
                0 => m(Op::Sb, imm),
                1 => m(Op::Sh, imm),
                2 => m(Op::Sw, imm),
                3 => m(Op::Sd, imm),
                _ => ILLEGAL,
            }
        }
        // OP-IMM: en RV64 el shamt es de 6 bits y funct6 separa SRLI de SRAI.
        0x13 => {
            let shamt = ((w >> 20) & 0x3f) as i32;
            let f6 = w >> 26;
            match f3 {
                0 => m(Op::Addi, i_imm),
                2 => m(Op::Slti, i_imm),
                3 => m(Op::Sltiu, i_imm),
                4 => m(Op::Xori, i_imm),
                6 => m(Op::Ori, i_imm),
                7 => m(Op::Andi, i_imm),
                1 if f6 == 0x00 => m(Op::Slli, shamt),
                5 if f6 == 0x00 => m(Op::Srli, shamt),
                5 if f6 == 0x10 => m(Op::Srai, shamt),
                _ => ILLEGAL,
            }
        }
        // OP-IMM-32
        0x1b => {
            let shamt = ((w >> 20) & 0x1f) as i32;
            match (f3, f7) {
                (0, _) => m(Op::Addiw, i_imm),
                (1, 0x00) => m(Op::Slliw, shamt),
                (5, 0x00) => m(Op::Srliw, shamt),
                (5, 0x20) => m(Op::Sraiw, shamt),
                _ => ILLEGAL,
            }
        }
        0x33 => match (f7, f3) {
            (0x00, 0) => m(Op::Add, 0),
            (0x20, 0) => m(Op::Sub, 0),
            (0x00, 1) => m(Op::Sll, 0),
            (0x00, 2) => m(Op::Slt, 0),
            (0x00, 3) => m(Op::Sltu, 0),
            (0x00, 4) => m(Op::Xor, 0),
            (0x00, 5) => m(Op::Srl, 0),
            (0x20, 5) => m(Op::Sra, 0),
            (0x00, 6) => m(Op::Or, 0),
            (0x00, 7) => m(Op::And, 0),
            (0x01, 0) => m(Op::Mul, 0),
            (0x01, 1) => m(Op::Mulh, 0),
            (0x01, 2) => m(Op::Mulhsu, 0),
            (0x01, 3) => m(Op::Mulhu, 0),
            (0x01, 4) => m(Op::Div, 0),
            (0x01, 5) => m(Op::Divu, 0),
            (0x01, 6) => m(Op::Rem, 0),
            (0x01, 7) => m(Op::Remu, 0),
            _ => ILLEGAL,
        },
        // OP-32
        0x3b => match (f7, f3) {
            (0x00, 0) => m(Op::Addw, 0),
            (0x20, 0) => m(Op::Subw, 0),
            (0x00, 1) => m(Op::Sllw, 0),
            (0x00, 5) => m(Op::Srlw, 0),
            (0x20, 5) => m(Op::Sraw, 0),
            (0x01, 0) => m(Op::Mulw, 0),
            (0x01, 4) => m(Op::Divw, 0),
            (0x01, 5) => m(Op::Divuw, 0),
            (0x01, 6) => m(Op::Remw, 0),
            (0x01, 7) => m(Op::Remuw, 0),
            _ => ILLEGAL,
        },
        // AMO — el funct5 viaja en imm.
        0x2f => {
            let f5 = (w >> 27) as i32;
            match f3 {
                2 => m(Op::AmoW, f5),
                3 => m(Op::AmoD, f5),
                _ => ILLEGAL,
            }
        }
        0x0f => m(Op::Nop, 0),
        0x73 => m(Op::Ecall, 0),
        _ => ILLEGAL,
    }
}

// ---------- instrucciones comprimidas ----------

/// Registro de 3 bits de las formas comprimidas: mapea a x8..x15.
#[inline(always)]
fn rp(v: u32) -> u8 {
    ((v & 7) + 8) as u8
}

/// Expande una comprimida a su equivalente de 32 bits. Devuelve `len = 2`.
fn decode16(h: u16) -> Insn {
    let w = h as u32;
    let f3 = (w >> 13) & 7;
    let q = w & 3;
    let c = |op: Op, rd: u8, rs1: u8, rs2: u8, imm: i32| mk(op, rd, rs1, rs2, imm, 2);

    match q {
        // ---- cuadrante 0 ----
        0 => {
            let rdp = rp(w >> 2);
            let rs1p = rp(w >> 7);
            match f3 {
                // C.ADDI4SPN → addi rd', x2, nzuimm
                0 => {
                    let imm = ((w >> 11) & 3) << 4
                        | ((w >> 7) & 0xf) << 6
                        | ((w >> 6) & 1) << 2
                        | ((w >> 5) & 1) << 3;
                    if imm == 0 {
                        return ILLEGAL; // reservada
                    }
                    c(Op::Addi, rdp, 2, 0, imm as i32)
                }
                // C.LW / C.SW
                2 | 6 => {
                    let imm = (((w >> 10) & 7) << 3 | ((w >> 6) & 1) << 2 | ((w >> 5) & 1) << 6) as i32;
                    if f3 == 2 {
                        c(Op::Lw, rdp, rs1p, 0, imm)
                    } else {
                        c(Op::Sw, 0, rs1p, rdp, imm)
                    }
                }
                // C.LD / C.SD
                3 | 7 => {
                    let imm = (((w >> 10) & 7) << 3 | ((w >> 5) & 3) << 6) as i32;
                    if f3 == 3 {
                        c(Op::Ld, rdp, rs1p, 0, imm)
                    } else {
                        c(Op::Sd, 0, rs1p, rdp, imm)
                    }
                }
                _ => ILLEGAL, // 1/5 son FLD/FSD: no existen en imac
            }
        }

        // ---- cuadrante 1 ----
        1 => {
            let rd = ((w >> 7) & 0x1f) as u8;
            let imm6 = sext(((w >> 12) & 1) << 5 | ((w >> 2) & 0x1f), 6);
            match f3 {
                // C.NOP / C.ADDI
                0 => c(Op::Addi, rd, rd, 0, imm6),
                // C.ADDIW
                1 => {
                    if rd == 0 {
                        return ILLEGAL;
                    }
                    c(Op::Addiw, rd, rd, 0, imm6)
                }
                // C.LI → addi rd, x0, imm
                2 => c(Op::Addi, rd, 0, 0, imm6),
                // C.ADDI16SP (rd==2) / C.LUI
                3 => {
                    if rd == 2 {
                        let imm = ((w >> 12) & 1) << 9
                            | ((w >> 6) & 1) << 4
                            | ((w >> 5) & 1) << 6
                            | ((w >> 3) & 3) << 7
                            | ((w >> 2) & 1) << 5;
                        if imm == 0 {
                            return ILLEGAL;
                        }
                        c(Op::Addi, 2, 2, 0, sext(imm, 10))
                    } else {
                        let imm = ((w >> 12) & 1) << 17 | ((w >> 2) & 0x1f) << 12;
                        if imm == 0 || rd == 0 {
                            return ILLEGAL;
                        }
                        c(Op::Lui, rd, 0, 0, sext(imm, 18))
                    }
                }
                // MISC-ALU
                4 => {
                    let rdp = rp(w >> 7);
                    let f2 = (w >> 10) & 3;
                    let shamt = (((w >> 12) & 1) << 5 | ((w >> 2) & 0x1f)) as i32;
                    match f2 {
                        0 => c(Op::Srli, rdp, rdp, 0, shamt),
                        1 => c(Op::Srai, rdp, rdp, 0, shamt),
                        2 => c(Op::Andi, rdp, rdp, 0, imm6),
                        _ => {
                            let rs2p = rp(w >> 2);
                            let hi = (w >> 12) & 1;
                            let sub = (w >> 5) & 3;
                            let op = match (hi, sub) {
                                (0, 0) => Op::Sub,
                                (0, 1) => Op::Xor,
                                (0, 2) => Op::Or,
                                (0, 3) => Op::And,
                                (1, 0) => Op::Subw,
                                (1, 1) => Op::Addw,
                                _ => return ILLEGAL,
                            };
                            c(op, rdp, rdp, rs2p, 0)
                        }
                    }
                }
                // C.J → jal x0, imm
                5 => {
                    let imm = ((w >> 12) & 1) << 11
                        | ((w >> 11) & 1) << 4
                        | ((w >> 9) & 3) << 8
                        | ((w >> 8) & 1) << 10
                        | ((w >> 7) & 1) << 6
                        | ((w >> 6) & 1) << 7
                        | ((w >> 3) & 7) << 1
                        | ((w >> 2) & 1) << 5;
                    c(Op::Jal, 0, 0, 0, sext(imm, 12))
                }
                // C.BEQZ / C.BNEZ
                6 | 7 => {
                    let rs1p = rp(w >> 7);
                    let imm = ((w >> 12) & 1) << 8
                        | ((w >> 10) & 3) << 3
                        | ((w >> 5) & 3) << 6
                        | ((w >> 3) & 3) << 1
                        | ((w >> 2) & 1) << 5;
                    let op = if f3 == 6 { Op::Beq } else { Op::Bne };
                    c(op, 0, rs1p, 0, sext(imm, 9))
                }
                _ => ILLEGAL,
            }
        }

        // ---- cuadrante 2 ----
        2 => {
            let rd = ((w >> 7) & 0x1f) as u8;
            let rs2 = ((w >> 2) & 0x1f) as u8;
            match f3 {
                // C.SLLI
                0 => {
                    let shamt = (((w >> 12) & 1) << 5 | ((w >> 2) & 0x1f)) as i32;
                    c(Op::Slli, rd, rd, 0, shamt)
                }
                // C.LWSP
                2 => {
                    let imm = (((w >> 12) & 1) << 5 | ((w >> 4) & 7) << 2 | ((w >> 2) & 3) << 6) as i32;
                    c(Op::Lw, rd, 2, 0, imm)
                }
                // C.LDSP
                3 => {
                    let imm = (((w >> 12) & 1) << 5 | ((w >> 5) & 3) << 3 | ((w >> 2) & 7) << 6) as i32;
                    c(Op::Ld, rd, 2, 0, imm)
                }
                // C.JR / C.MV / C.EBREAK / C.JALR / C.ADD
                4 => {
                    let hi = (w >> 12) & 1;
                    match (hi, rd, rs2) {
                        (0, _, 0) => c(Op::Jalr, 0, rd, 0, 0),
                        (0, _, _) => c(Op::Add, rd, 0, rs2, 0),
                        (1, 0, 0) => c(Op::Ecall, 0, 0, 0, 0), // C.EBREAK
                        (1, _, 0) => c(Op::Jalr, 1, rd, 0, 0),
                        (1, _, _) => c(Op::Add, rd, rd, rs2, 0),
                        _ => ILLEGAL,
                    }
                }
                // C.SWSP
                6 => {
                    let imm = (((w >> 9) & 0xf) << 2 | ((w >> 7) & 3) << 6) as i32;
                    c(Op::Sw, 0, 2, rs2, imm)
                }
                // C.SDSP
                7 => {
                    let imm = (((w >> 10) & 7) << 3 | ((w >> 7) & 7) << 6) as i32;
                    c(Op::Sd, 0, 2, rs2, imm)
                }
                _ => ILLEGAL, // 1/5 son FLDSP/FSDSP
            }
        }

        _ => ILLEGAL,
    }
}

/// Marca de slot sin instruccion (direccion par que cae en medio de una).
const NO_IDX: u32 = u32::MAX;

pub struct Rv64 {
    mem: Box<[u8; MEM_SIZE + PAD]>,
    x: [u64; 32],
    pc: u64,
    /// Instrucciones reales en orden de direccion, sin huecos. El sucesor de
    /// `code[i]` en caida libre es `code[i + 1]`, asi que el camino secuencial
    /// —que es la enorme mayoria— nunca toca la tabla de direcciones.
    code: Vec<Insn>,
    /// (addr - text_lo) / 2 -> indice en `code`. Solo se consulta cuando el
    /// control salta: rama tomada, jal o jalr.
    slots: Vec<u32>,
    text_lo: u64,
    text_hi: u64,
    entry: u64,
    pub steps: u64,
}

enum Halt {
    Returned,
    Ecall,
}

impl Rv64 {
    #[inline(always)]
    fn r8(&self, a: u64) -> u8 {
        self.mem[(a & MASK) as usize]
    }
    #[inline(always)]
    fn r16(&self, a: u64) -> u16 {
        let i = (a & MASK) as usize;
        u16::from_le_bytes([self.mem[i], self.mem[i + 1]])
    }
    #[inline(always)]
    fn r32(&self, a: u64) -> u32 {
        let i = (a & MASK) as usize;
        u32::from_le_bytes([self.mem[i], self.mem[i + 1], self.mem[i + 2], self.mem[i + 3]])
    }
    #[inline(always)]
    fn r64(&self, a: u64) -> u64 {
        let i = (a & MASK) as usize;
        u64::from_le_bytes([
            self.mem[i], self.mem[i + 1], self.mem[i + 2], self.mem[i + 3],
            self.mem[i + 4], self.mem[i + 5], self.mem[i + 6], self.mem[i + 7],
        ])
    }
    #[inline(always)]
    fn w8(&mut self, a: u64, v: u8) {
        self.mem[(a & MASK) as usize] = v;
    }
    #[inline(always)]
    fn w16(&mut self, a: u64, v: u16) {
        let i = (a & MASK) as usize;
        self.mem[i..i + 2].copy_from_slice(&v.to_le_bytes());
    }
    #[inline(always)]
    fn w32(&mut self, a: u64, v: u32) {
        let i = (a & MASK) as usize;
        self.mem[i..i + 4].copy_from_slice(&v.to_le_bytes());
    }
    #[inline(always)]
    fn w64(&mut self, a: u64, v: u64) {
        let i = (a & MASK) as usize;
        self.mem[i..i + 8].copy_from_slice(&v.to_le_bytes());
    }
    #[inline(always)]
    fn set(&mut self, rd: u8, v: u64) {
        if rd != 0 {
            self.x[(rd & 31) as usize] = v;
        }
    }

    pub fn load(elf: &[u8]) -> Result<(Self, BTreeMap<String, u64>), String> {
        let g64 = |o: usize| -> u64 {
            u64::from_le_bytes([
                elf[o], elf[o + 1], elf[o + 2], elf[o + 3],
                elf[o + 4], elf[o + 5], elf[o + 6], elf[o + 7],
            ])
        };
        let g32 = |o: usize| -> u32 {
            u32::from_le_bytes([elf[o], elf[o + 1], elf[o + 2], elf[o + 3]])
        };
        let g16 = |o: usize| -> u16 { u16::from_le_bytes([elf[o], elf[o + 1]]) };

        if elf.len() < 64 || &elf[0..4] != b"\x7fELF" || elf[4] != 2 || elf[5] != 1 {
            return Err("no es un ELF64 little-endian".into());
        }
        if g16(18) != 0xf3 {
            return Err(format!("e_machine {:#x}, se esperaba RISC-V (0xf3)", g16(18)));
        }

        let mut mem: Box<[u8; MEM_SIZE + PAD]> = vec![0u8; MEM_SIZE + PAD]
            .into_boxed_slice()
            .try_into()
            .map_err(|_| "no se pudo reservar la memoria del guest")?;

        // Cabecera ELF64: los offsets difieren de ELF32.
        let entry = g64(24);
        let phoff = g64(32) as usize;
        let shoff = g64(40) as usize;
        let phentsize = g16(54) as usize;
        let phnum = g16(56) as usize;
        let shentsize = g16(58) as usize;
        let shnum = g16(60) as usize;

        let mut top = TEXT_BASE;
        for i in 0..phnum {
            let p = phoff + i * phentsize;
            if g32(p) != 1 {
                continue; // solo PT_LOAD
            }
            let off = g64(p + 8) as usize;
            let vaddr = g64(p + 16);
            let filesz = g64(p + 32) as usize;
            let memsz = g64(p + 40);
            let dst = (vaddr & MASK) as usize;
            mem[dst..dst + filesz].copy_from_slice(&elf[off..off + filesz]);
            top = top.max(vaddr + memsz);
        }

        // Limites del codigo ejecutable: PROGBITS con SHF_EXECINSTR. Barrer
        // solo eso evita predecodificar .rodata/.data, que no solo es memoria
        // desperdiciada sino que desincronizaria el barrido lineal.
        let mut text_lo = u64::MAX;
        let mut text_hi = 0u64;
        for i in 0..shnum {
            let s = shoff + i * shentsize;
            if g32(s + 4) != 1 || g64(s + 8) & 0x4 == 0 {
                continue; // PROGBITS + ejecutable
            }
            let addr = g64(s + 16);
            let size = g64(s + 32);
            text_lo = text_lo.min(addr);
            text_hi = text_hi.max(addr + size);
        }
        if text_lo == u64::MAX {
            return Err("el ELF no tiene seccion ejecutable".into());
        }

        let mut syms = BTreeMap::new();
        for i in 0..shnum {
            let s = shoff + i * shentsize;
            if g32(s + 4) != 2 {
                continue; // SHT_SYMTAB
            }
            let symoff = g64(s + 24) as usize;
            let symsz = g64(s + 32) as usize;
            let strsec = shoff + g32(s + 40) as usize * shentsize;
            let stroff = g64(strsec + 24) as usize;
            // Entrada de simbolo ELF64: name(4) info(1) other(1) shndx(2) value(8) size(8)
            for k in 0..(symsz / 24) {
                let e = symoff + k * 24;
                let name_off = stroff + g32(e) as usize;
                let value = g64(e + 8);
                let end = elf[name_off..].iter().position(|&c| c == 0).unwrap_or(0);
                if end > 0 {
                    let name = String::from_utf8_lossy(&elf[name_off..name_off + end]).into_owned();
                    syms.insert(name, value);
                }
            }
        }

        // Barrido lineal del texto: en cada direccion se lee el largo real y se
        // avanza por el, asi que `code` queda con una entrada por instruccion y
        // sin huecos. `slots` mapea direccion -> indice y solo hace falta para
        // los saltos.
        let nslots = ((text_hi - text_lo) / 2) as usize;
        let mut slots = vec![NO_IDX; nslots];
        let mut code: Vec<Insn> = Vec::with_capacity(nslots);
        let mut a = text_lo;
        while a < text_hi {
            let i = (a & MASK) as usize;
            let lo = u16::from_le_bytes([mem[i], mem[i + 1]]);
            let ins = if lo & 3 == 3 {
                decode32(u32::from_le_bytes([mem[i], mem[i + 1], mem[i + 2], mem[i + 3]]))
            } else {
                decode16(lo)
            };
            slots[((a - text_lo) / 2) as usize] = code.len() as u32;
            code.push(ins);
            a += ins.len as u64;
        }
        code.shrink_to_fit();

        Ok((
            Rv64 {
                mem,
                x: [0; 32],
                pc: entry,
                code,
                slots,
                text_lo,
                text_hi,
                entry,
                steps: 0,
            },
            syms,
        ))
    }

    /// Direccion -> indice en `code`. Solo se llama en saltos.
    #[inline]
    fn idx_of(&self, addr: u64) -> Result<usize, String> {
        if addr < self.text_lo || addr >= self.text_hi {
            return Err(format!("salto fuera del texto: {:#x}", addr));
        }
        match self.slots[((addr - self.text_lo) / 2) as usize] {
            NO_IDX => Err(format!("salto al medio de una instruccion: {:#x}", addr)),
            s => Ok(s as usize),
        }
    }

    pub fn boot(&mut self) -> Result<(), String> {
        self.pc = self.entry;
        self.x[2] = STACK_TOP;
        match self.exec()? {
            Halt::Ecall => Ok(()),
            Halt::Returned => Err("_start volvio en vez de hacer ecall".into()),
        }
    }

    pub fn call(&mut self, addr: u64, args: &[u64]) -> Result<u64, String> {
        self.pc = addr;
        self.x[1] = SENTINEL;
        self.x[2] = STACK_TOP;
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
        /// Marca de "no hubo salto": distinta de SENTINEL y de toda direccion.
        const NO_JUMP: u64 = u64::MAX;

        if self.pc == SENTINEL {
            return Ok(Halt::Returned);
        }
        let mut idx = self.idx_of(self.pc)?;
        loop {
            let ins = match self.code.get(idx) {
                Some(i) => *i,
                None => return Err(format!("se cayo del final del texto en {:#x}", self.pc)),
            };
            self.steps += 1;

            let a = self.x[(ins.rs1 & 31) as usize];
            let b = self.x[(ins.rs2 & 31) as usize];
            let imm = ins.imm as i64 as u64;
            let mut jump = NO_JUMP;

            match ins.op {
                Op::Lui => self.set(ins.rd, imm),
                Op::Auipc => self.set(ins.rd, self.pc.wrapping_add(imm)),
                Op::Jal => {
                    let link = self.pc.wrapping_add(ins.len as u64);
                    self.set(ins.rd, link);
                    jump = self.pc.wrapping_add(imm);
                }
                Op::Jalr => {
                    let t = a.wrapping_add(imm) & !1;
                    let link = self.pc.wrapping_add(ins.len as u64);
                    self.set(ins.rd, link);
                    jump = t;
                }
                Op::Beq => if a == b { jump = self.pc.wrapping_add(imm) },
                Op::Bne => if a != b { jump = self.pc.wrapping_add(imm) },
                Op::Blt => if (a as i64) < (b as i64) { jump = self.pc.wrapping_add(imm) },
                Op::Bge => if (a as i64) >= (b as i64) { jump = self.pc.wrapping_add(imm) },
                Op::Bltu => if a < b { jump = self.pc.wrapping_add(imm) },
                Op::Bgeu => if a >= b { jump = self.pc.wrapping_add(imm) },

                Op::Lb => { let v = self.r8(a.wrapping_add(imm)) as i8 as i64 as u64; self.set(ins.rd, v) }
                Op::Lh => { let v = self.r16(a.wrapping_add(imm)) as i16 as i64 as u64; self.set(ins.rd, v) }
                Op::Lw => { let v = self.r32(a.wrapping_add(imm)) as i32 as i64 as u64; self.set(ins.rd, v) }
                Op::Ld => { let v = self.r64(a.wrapping_add(imm)); self.set(ins.rd, v) }
                Op::Lbu => { let v = self.r8(a.wrapping_add(imm)) as u64; self.set(ins.rd, v) }
                Op::Lhu => { let v = self.r16(a.wrapping_add(imm)) as u64; self.set(ins.rd, v) }
                Op::Lwu => { let v = self.r32(a.wrapping_add(imm)) as u64; self.set(ins.rd, v) }
                Op::Sb => self.w8(a.wrapping_add(imm), b as u8),
                Op::Sh => self.w16(a.wrapping_add(imm), b as u16),
                Op::Sw => self.w32(a.wrapping_add(imm), b as u32),
                Op::Sd => self.w64(a.wrapping_add(imm), b),

                Op::Addi => self.set(ins.rd, a.wrapping_add(imm)),
                Op::Slti => self.set(ins.rd, ((a as i64) < ins.imm as i64) as u64),
                Op::Sltiu => self.set(ins.rd, (a < imm) as u64),
                Op::Xori => self.set(ins.rd, a ^ imm),
                Op::Ori => self.set(ins.rd, a | imm),
                Op::Andi => self.set(ins.rd, a & imm),
                Op::Slli => self.set(ins.rd, a << (ins.imm & 63)),
                Op::Srli => self.set(ins.rd, a >> (ins.imm & 63)),
                Op::Srai => self.set(ins.rd, ((a as i64) >> (ins.imm & 63)) as u64),

                Op::Add => self.set(ins.rd, a.wrapping_add(b)),
                Op::Sub => self.set(ins.rd, a.wrapping_sub(b)),
                Op::Sll => self.set(ins.rd, a << (b & 63)),
                Op::Slt => self.set(ins.rd, ((a as i64) < (b as i64)) as u64),
                Op::Sltu => self.set(ins.rd, (a < b) as u64),
                Op::Xor => self.set(ins.rd, a ^ b),
                Op::Srl => self.set(ins.rd, a >> (b & 63)),
                Op::Sra => self.set(ins.rd, ((a as i64) >> (b & 63)) as u64),
                Op::Or => self.set(ins.rd, a | b),
                Op::And => self.set(ins.rd, a & b),

                // Las variantes W operan en 32 bits y extienden el signo a 64.
                Op::Addiw => self.set(ins.rd, (a as u32).wrapping_add(imm as u32) as i32 as i64 as u64),
                Op::Slliw => self.set(ins.rd, ((a as u32) << (ins.imm & 31)) as i32 as i64 as u64),
                Op::Srliw => self.set(ins.rd, ((a as u32) >> (ins.imm & 31)) as i32 as i64 as u64),
                Op::Sraiw => self.set(ins.rd, ((a as i32) >> (ins.imm & 31)) as i64 as u64),
                Op::Addw => self.set(ins.rd, (a as u32).wrapping_add(b as u32) as i32 as i64 as u64),
                Op::Subw => self.set(ins.rd, (a as u32).wrapping_sub(b as u32) as i32 as i64 as u64),
                Op::Sllw => self.set(ins.rd, ((a as u32) << (b & 31)) as i32 as i64 as u64),
                Op::Srlw => self.set(ins.rd, ((a as u32) >> (b & 31)) as i32 as i64 as u64),
                Op::Sraw => self.set(ins.rd, ((a as i32) >> (b & 31)) as i64 as u64),

                Op::Mul => self.set(ins.rd, a.wrapping_mul(b)),
                Op::Mulh => self.set(ins.rd, (((a as i64 as i128) * (b as i64 as i128)) >> 64) as u64),
                Op::Mulhsu => self.set(ins.rd, (((a as i64 as i128) * (b as i128)) >> 64) as u64),
                Op::Mulhu => self.set(ins.rd, (((a as u128) * (b as u128)) >> 64) as u64),
                Op::Div => self.set(ins.rd, if b == 0 { u64::MAX }
                    else if a == 1 << 63 && b == u64::MAX { a }
                    else { ((a as i64).wrapping_div(b as i64)) as u64 }),
                Op::Divu => self.set(ins.rd, if b == 0 { u64::MAX } else { a / b }),
                Op::Rem => self.set(ins.rd, if b == 0 { a }
                    else if a == 1 << 63 && b == u64::MAX { 0 }
                    else { ((a as i64).wrapping_rem(b as i64)) as u64 }),
                Op::Remu => self.set(ins.rd, if b == 0 { a } else { a % b }),

                Op::Mulw => self.set(ins.rd, (a as u32).wrapping_mul(b as u32) as i32 as i64 as u64),
                Op::Divw => {
                    let (x, y) = (a as i32, b as i32);
                    let r = if y == 0 { -1 } else if x == i32::MIN && y == -1 { x } else { x.wrapping_div(y) };
                    self.set(ins.rd, r as i64 as u64)
                }
                Op::Divuw => {
                    let (x, y) = (a as u32, b as u32);
                    let r = if y == 0 { u32::MAX } else { x / y };
                    self.set(ins.rd, r as i32 as i64 as u64)
                }
                Op::Remw => {
                    let (x, y) = (a as i32, b as i32);
                    let r = if y == 0 { x } else if x == i32::MIN && y == -1 { 0 } else { x.wrapping_rem(y) };
                    self.set(ins.rd, r as i64 as u64)
                }
                Op::Remuw => {
                    let (x, y) = (a as u32, b as u32);
                    let r = if y == 0 { x } else { x % y };
                    self.set(ins.rd, r as i32 as i64 as u64)
                }

                // Extension A con semantica monohilo: no hay contencion posible,
                // asi que SC siempre tiene exito y los AMO son read-modify-write.
                Op::AmoW => {
                    let old = self.r32(a) as i32;
                    let src = b as u32 as i32;
                    let new = match ins.imm {
                        0x02 => { self.set(ins.rd, old as i64 as u64); None } // LR.W
                        0x03 => { self.w32(a, src as u32); self.set(ins.rd, 0); None }                                      // SC.W
                        0x01 => Some(src),
                        0x00 => Some(old.wrapping_add(src)),
                        0x04 => Some(old ^ src),
                        0x0c => Some(old & src),
                        0x08 => Some(old | src),
                        0x10 => Some(old.min(src)),
                        0x14 => Some(old.max(src)),
                        0x18 => Some(((old as u32).min(src as u32)) as i32),
                        0x1c => Some(((old as u32).max(src as u32)) as i32),
                        _ => return Err(format!("AMO.W desconocido: funct5={:#x}", ins.imm)),
                    };
                    if let Some(v) = new {
                        self.w32(a, v as u32);
                        self.set(ins.rd, old as i64 as u64);
                    }
                }
                Op::AmoD => {
                    let old = self.r64(a) as i64;
                    let src = b as i64;
                    let new = match ins.imm {
                        0x02 => { self.set(ins.rd, old as u64); None }              // LR.D
                        0x03 => { self.w64(a, src as u64); self.set(ins.rd, 0); None } // SC.D
                        0x01 => Some(src),
                        0x00 => Some(old.wrapping_add(src)),
                        0x04 => Some(old ^ src),
                        0x0c => Some(old & src),
                        0x08 => Some(old | src),
                        0x10 => Some(old.min(src)),
                        0x14 => Some(old.max(src)),
                        0x18 => Some(((old as u64).min(src as u64)) as i64),
                        0x1c => Some(((old as u64).max(src as u64)) as i64),
                        _ => return Err(format!("AMO.D desconocido: funct5={:#x}", ins.imm)),
                    };
                    if let Some(v) = new {
                        self.w64(a, v as u64);
                        self.set(ins.rd, old as u64);
                    }
                }

                Op::Nop => {}
                Op::Ecall => return Ok(Halt::Ecall),
                Op::Illegal => {
                    return Err(format!("instruccion ilegal en pc={:#x}", self.pc))
                }
            }
            // Caida libre: el sucesor es la entrada siguiente del arreglo, sin
            // tocar `slots`. Solo un salto paga la traduccion de direccion.
            if jump == NO_JUMP {
                self.pc = self.pc.wrapping_add(ins.len as u64);
                idx += 1;
            } else {
                self.pc = jump;
                if jump == SENTINEL {
                    return Ok(Halt::Returned);
                }
                idx = self.idx_of(jump)?;
            }
        }
    }
}
