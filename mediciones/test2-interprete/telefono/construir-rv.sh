#!/usr/bin/env bash
# Regenera los ELF de los guests RISC-V. Solo hace falta si se toca pqcore o
# los guests: guest.elf va versionado igual que guest.wasm.
#   rustup target add riscv32im-unknown-none-elf riscv64imac-unknown-none-elf
set -e
cd "$(dirname "$0")"
for g in guest-rv guest-rv64; do
  (cd "$g" && cargo build --release)
  cp "$g"/target/*/release/"$g" "$g"/guest.elf
  echo "$g/guest.elf: $(wc -c < "$g"/guest.elf) bytes"
done
