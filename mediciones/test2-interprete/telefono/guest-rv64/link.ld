/* Mapa plano: el emulador del host da 64 MiB de RAM desde 0.
   El texto arranca en 0x1000 para dejar la pagina nula sin mapear.
   El tope de la RAM lo ocupa el stack (1 MiB); el heap va del final
   de .bss hasta ahi. */
ENTRY(_start)

SECTIONS {
  . = 0x1000;
  .text : {
    KEEP(*(.text._start))
    KEEP(*(.text.prepare))
    KEEP(*(.text.run))
    *(.text .text.*)
  }
  .rodata : { *(.rodata .rodata.*) *(.srodata .srodata.*) }
  .data   : {
    __global_pointer$ = . + 0x800;
    *(.data .data.*) *(.sdata .sdata.*)
  }
  .bss    : { *(.bss .bss.*) *(.sbss .sbss.*) *(COMMON) }
  . = ALIGN(16);
  __heap_start = .;

  /DISCARD/ : { *(.eh_frame) *(.eh_frame_hdr) *(.comment) }
}
