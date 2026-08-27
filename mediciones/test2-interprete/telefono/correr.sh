#!/data/data/com.termux/files/usr/bin/bash
# Test 2 — presupuesto del interprete. Correr en Termux (Android, aarch64).
#
#   pkg install -y rust
#   bash correr.sh            # solo interprete (wasmi) + baseline nativo  (~3 min de compilacion)
#   bash correr.sh jit        # agrega Cranelift JIT y Pulley             (~20 min de compilacion)
#
# La salida es CSV; guardarla y pegarla de vuelta.
set -e
cd "$(dirname "$0")/host"

if ! command -v cargo >/dev/null 2>&1; then
  echo "falta cargo: correr 'pkg install -y rust'" >&2
  exit 1
fi

echo "# dispositivo: $(getprop ro.product.model 2>/dev/null || echo desconocido)"
echo "# soc:        $(getprop ro.board.platform 2>/dev/null || echo desconocido)"
echo "# rustc:      $(rustc --version)"
echo

if [ "$1" = "jit" ]; then
  cargo run --release --features jit
else
  cargo run --release
fi
