//! Test 2 — arnes de medicion.
//!
//! Mide el mismo verify ML-DSA en cinco motores:
//!   native   — codigo maquina, baseline
//!   ct-jit   — wasmtime/Cranelift, JIT optimizante
//!   pulley   — wasmtime/Pulley, interprete portable (escenario sin JIT, tipo iOS)
//!   wasmi    — interprete puro de registros (perfil "VM de cadena")
//!   rv32im   — interprete RV32IM propio (el ISA chico, 32 bits)
//!   rv64imac — el mismo interprete a 64 bits (el ISA chico, ancho correcto)
//!
//! Los tres ultimos son el grupo que decide la eleccion de maquina: los tres
//! son interpretes puros, asi que sus cocientes comparan ISA contra ISA. Y
//! rv32 contra rv64 aisla una sola variable —el ancho de registro— sobre el
//! mismo diseño de interprete.

mod rv32;
mod rv64;

use std::time::{Duration, Instant};

const WASM: &[u8] = include_bytes!("../../guest/guest.wasm");
const RVELF: &[u8] = include_bytes!("../../guest-rv/guest.elf");
const RV64ELF: &[u8] = include_bytes!("../../guest-rv64/guest.elf");

const TARGET: Duration = Duration::from_millis(1200);
const REPS: usize = 5;

/// Corre `f(iters)` subiendo iters hasta pasar TARGET; devuelve ns/op mediano.
fn measure(mut f: impl FnMut(u32)) -> f64 {
    let mut iters: u32 = 1;
    loop {
        let t = Instant::now();
        f(iters);
        let e = t.elapsed();
        if e >= TARGET || iters >= 1 << 24 {
            break;
        }
        let grow = (TARGET.as_secs_f64() / e.as_secs_f64().max(1e-9)).min(8.0);
        iters = ((iters as f64 * grow).ceil() as u32).max(iters + 1);
    }
    let mut samples = Vec::with_capacity(REPS);
    for _ in 0..REPS {
        let t = Instant::now();
        f(iters);
        samples.push(t.elapsed().as_secs_f64() / iters as f64 * 1e9);
    }
    samples.sort_by(|a, b| a.partial_cmp(b).unwrap());
    samples[REPS / 2]
}

// ---------- motores ----------

fn bench_native(lvl: pqcore::Level, mode: u32) -> f64 {
    let fx = pqcore::make_fixture(lvl);
    measure(|n| {
        let ok = if mode == 0 {
            pqcore::bench_decode_verify(lvl, &fx, n)
        } else {
            pqcore::bench_verify_only(lvl, &fx, n)
        };
        assert_eq!(ok, n, "verificacion fallida");
    })
}

#[cfg(feature = "jit")]
fn bench_wasmtime(level: u32, mode: u32, pulley: bool) -> (f64, f64) {
    let mut cfg = wasmtime::Config::new();
    cfg.cranelift_opt_level(wasmtime::OptLevel::Speed);
    if pulley {
        cfg.target("pulley64").expect("target pulley64");
    }
    let engine = wasmtime::Engine::new(&cfg).expect("engine");

    let t = Instant::now();
    let module = wasmtime::Module::new(&engine, WASM).expect("module");
    let compile_ms = t.elapsed().as_secs_f64() * 1e3;

    let mut store = wasmtime::Store::new(&engine, ());
    let inst = wasmtime::Instance::new(&mut store, &module, &[]).expect("instance");
    let prepare = inst
        .get_typed_func::<u32, u32>(&mut store, "prepare")
        .expect("prepare");
    let run = inst
        .get_typed_func::<(u32, u32), u32>(&mut store, "run")
        .expect("run");
    prepare.call(&mut store, level).expect("prepare call");

    let ns = measure(|n| {
        let ok = run.call(&mut store, (mode, n)).expect("run call");
        assert_eq!(ok, n, "verificacion fallida");
    });
    (ns, compile_ms)
}

fn bench_wasmi(level: u32, mode: u32) -> (f64, f64) {
    let engine = wasmi::Engine::default();
    let t = Instant::now();
    let module = wasmi::Module::new(&engine, WASM).expect("module");
    let compile_ms = t.elapsed().as_secs_f64() * 1e3;

    let mut store = wasmi::Store::new(&engine, ());
    let linker = wasmi::Linker::<()>::new(&engine);
    let inst = linker
        .instantiate_and_start(&mut store, &module)
        .expect("instantiate");
    let prepare = inst
        .get_typed_func::<u32, u32>(&store, "prepare")
        .expect("prepare");
    let run = inst
        .get_typed_func::<(u32, u32), u32>(&store, "run")
        .expect("run");
    prepare.call(&mut store, level).expect("prepare call");

    let ns = measure(|n| {
        let ok = run.call(&mut store, (mode, n)).expect("run call");
        assert_eq!(ok, n, "verificacion fallida");
    });
    (ns, compile_ms)
}

/// Devuelve (ns por verify, ms de carga+predecodificacion, pasos por verify).
///
/// Los pasos salen de la diferencia entre correr 20 y 10 iteraciones, asi el
/// costo fijo de entrar y salir de `run` no entra en la cuenta marginal.
fn bench_rv32(level: u32, mode: u32) -> (f64, f64, u64) {
    let t = Instant::now();
    let (mut vm, syms) = rv32::Rv32::load(RVELF).expect("cargar ELF del guest");
    let load_ms = t.elapsed().as_secs_f64() * 1e3;

    let prepare = *syms.get("prepare").expect("simbolo prepare");
    let run = *syms.get("run").expect("simbolo run");

    vm.boot().expect("boot del guest");
    vm.call(prepare, &[level]).expect("prepare");

    let s0 = vm.steps;
    let n10 = vm.call(run, &[mode, 10]).expect("run 10");
    let s10 = vm.steps - s0;
    assert_eq!(n10, 10, "verificacion fallida");
    let s1 = vm.steps;
    let n20 = vm.call(run, &[mode, 20]).expect("run 20");
    let s20 = vm.steps - s1;
    assert_eq!(n20, 20, "verificacion fallida");
    let steps_per_verify = (s20 - s10) / 10;

    let ns = measure(|n| {
        let ok = vm.call(run, &[mode, n]).expect("run");
        assert_eq!(ok, n, "verificacion fallida");
    });
    (ns, load_ms, steps_per_verify)
}

/// Igual que `bench_rv32` pero sobre el interprete de 64 bits.
fn bench_rv64(level: u32, mode: u32) -> (f64, f64, u64) {
    let t = Instant::now();
    let (mut vm, syms) = rv64::Rv64::load(RV64ELF).expect("cargar ELF del guest rv64");
    let load_ms = t.elapsed().as_secs_f64() * 1e3;

    let prepare = *syms.get("prepare").expect("simbolo prepare");
    let run = *syms.get("run").expect("simbolo run");

    vm.boot().expect("boot del guest");
    vm.call(prepare, &[level as u64]).expect("prepare");

    let s0 = vm.steps;
    let n10 = vm.call(run, &[mode as u64, 10]).expect("run 10");
    let s10 = vm.steps - s0;
    assert_eq!(n10, 10, "verificacion fallida");
    let s1 = vm.steps;
    let n20 = vm.call(run, &[mode as u64, 20]).expect("run 20");
    let s20 = vm.steps - s1;
    assert_eq!(n20, 20, "verificacion fallida");
    let steps_per_verify = (s20 - s10) / 10;

    let ns = measure(|n| {
        let ok = vm.call(run, &[mode as u64, n as u64]).expect("run");
        assert_eq!(ok, n as u64, "verificacion fallida");
    });
    (ns, load_ms, steps_per_verify)
}

/// Filtros de linea de comando.
///
///   host                         la matriz completa (comportamiento previo)
///   host 87                      solo ML-DSA-87
///   host 87 decode+verify        solo esa celda
///   host --pausa 45              la matriz completa, con 45 s de enfriamiento
///                                antes de cada bloque
///
/// La pausa existe porque el telefono termaliza. El SoC es 2x Cortex-A78 +
/// 6x Cortex-A55, y en una corrida larga los bloques tardios terminan en el
/// cluster chico: salen ~4x inflados. Se detecta comparando compile_ms entre
/// bloques, o mirando ns por paso en los motores RISC-V, que es invariante
/// porque steps_per_verify es determinista.
struct Filtros {
    nivel: Option<u32>,
    modo: Option<u32>,
    pausa: Duration,
}

fn parse_filtros() -> Filtros {
    let mut f = Filtros {
        nivel: None,
        modo: None,
        pausa: Duration::ZERO,
    };
    let args: Vec<String> = std::env::args().skip(1).collect();
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "44" => f.nivel = Some(0),
            "65" => f.nivel = Some(1),
            "87" => f.nivel = Some(2),
            "d" | "decode+verify" => f.modo = Some(0),
            "v" | "verify_only" => f.modo = Some(1),
            "--pausa" => {
                i += 1;
                f.pausa =
                    Duration::from_secs(args.get(i).and_then(|s| s.parse().ok()).unwrap_or(0));
            }
            otro => {
                eprintln!("argumento no reconocido: {otro}");
                eprintln!("uso: host [44|65|87] [decode+verify|verify_only] [--pausa SEGUNDOS]");
                std::process::exit(2);
            }
        }
        i += 1;
    }
    f
}

fn main() {
    let filtros = parse_filtros();
    let arch = std::env::consts::ARCH;
    let os = std::env::consts::OS;
    println!("# Test 2 — presupuesto del interprete");
    println!(
        "# host: {}-{}  wasm: {} B  rv32im-elf: {} B  rv64imac-elf: {} B",
        arch,
        os,
        WASM.len(),
        RVELF.len(),
        RV64ELF.len()
    );
    println!(
        "# filtro: nivel={} modo={} pausa={}s",
        match filtros.nivel {
            Some(0) => "44",
            Some(1) => "65",
            Some(2) => "87",
            _ => "todos",
        },
        match filtros.modo {
            Some(0) => "decode+verify",
            Some(1) => "verify_only",
            _ => "todos",
        },
        filtros.pausa.as_secs()
    );
    println!();
    println!(
        "engine,level,mode,ns_per_verify,verifies_per_sec,slowdown_vs_native,compile_ms,steps_per_verify"
    );

    for (lname, lv) in [("ML-DSA-44", 0u32), ("ML-DSA-65", 1), ("ML-DSA-87", 2)] {
        if filtros.nivel.is_some_and(|n| n != lv) {
            continue;
        }
        for (mname, mode) in [("decode+verify", 0u32), ("verify_only", 1)] {
            if filtros.modo.is_some_and(|m| m != mode) {
                continue;
            }
            // A stderr, para no ensuciar el CSV que va por stdout.
            if !filtros.pausa.is_zero() {
                eprintln!(
                    "# enfriando {}s antes de {} {}",
                    filtros.pausa.as_secs(),
                    lname,
                    mname
                );
                std::thread::sleep(filtros.pausa);
            }
            let lvl = pqcore::Level::from_u32(lv);
            let nat = bench_native(lvl, mode);
            let (wmi, wmi_c) = bench_wasmi(lv, mode);
            let (rv, rv_c, rv_steps) = bench_rv32(lv, mode);
            let (rv64, rv64_c, rv64_steps) = bench_rv64(lv, mode);
            #[allow(unused_mut)]
            let mut rows: Vec<(&str, f64, f64, Option<u64>)> = vec![
                ("native", nat, f64::NAN, None),
                ("wasmi", wmi, wmi_c, None),
                ("rv32im", rv, rv_c, Some(rv_steps)),
                ("rv64imac", rv64, rv64_c, Some(rv64_steps)),
            ];
            #[cfg(feature = "jit")]
            {
                let (jit, jit_c) = bench_wasmtime(lv, mode, false);
                let (pul, pul_c) = bench_wasmtime(lv, mode, true);
                rows.insert(1, ("wasmtime-cranelift", jit, jit_c, None));
                rows.insert(2, ("wasmtime-pulley", pul, pul_c, None));
            }
            for (eng, ns, cms, steps) in rows {
                println!(
                    "{},{},{},{:.0},{:.0},{:.2},{},{}",
                    eng,
                    lname,
                    mname,
                    ns,
                    1e9 / ns,
                    ns / nat,
                    if cms.is_nan() {
                        "-".to_string()
                    } else {
                        format!("{:.1}", cms)
                    },
                    match steps {
                        Some(s) => s.to_string(),
                        None => "-".to_string(),
                    }
                );
            }
        }
    }
}
