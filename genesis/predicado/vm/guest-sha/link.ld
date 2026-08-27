/* Mismo mapa plano que el guest de Test 2: la maquina de §6.6 da 64 MiB desde 0 y el
   texto arranca en 0x1000 para dejar la pagina nula sin mapear. Sin heap: este guest
   no reserva memoria, asi que no hace falta allocator. */
ENTRY(_start)

SECTIONS {
  . = 0x1000;
  .text : {
    KEEP(*(.text._start))
    KEEP(*(.text.comprimir))
    *(.text .text.*)
  }
  .rodata : { *(.rodata .rodata.*) *(.srodata .srodata.*) }
  .data   : {
    __global_pointer$ = . + 0x800;
    *(.data .data.*) *(.sdata .sdata.*)
  }
  .bss    : { *(.bss .bss.*) *(.sbss .sbss.*) *(COMMON) }

  /DISCARD/ : { *(.eh_frame) *(.eh_frame_hdr) *(.comment) }
}
