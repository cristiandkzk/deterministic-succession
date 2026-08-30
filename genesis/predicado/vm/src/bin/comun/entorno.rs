#![allow(dead_code)]

//! Procedencia de la maquina, para las salidas que se pegan afuera.
//!
//! Lo comparten `mezclas` y `conjunto` por `#[path]`, y vive en `src/bin/comun/`
//! —no en el lib— por dos razones: nada de esto es la maquina que I1 congela, y
//! lee `/proc`, el registro de Windows y `git`, que es justo lo que no puede
//! aparecer en la pieza de consenso. El directorio no tiene `main.rs`, asi que
//! cargo no lo toma como un binario mas.
//!
//! **El bloque se imprime en ingles, y es a proposito.** Es la unica salida del
//! crate escrita para alguien que no trabaja en el proyecto: la pide un hilo en
//! ingles, la completa a mano quien corre el benchmark en su maquina, y la pega
//! de vuelta ahi. Un dato que falta se nombra en vez de omitirse, para que el
//! hueco se vea; un numero sin procedencia no sirve para fijar un piso de
//! hardware, que es para lo que se juntan estas corridas.

use std::process::Command;

const FALTA: &str = "unknown — please fill in";

/// Corre un comando y devuelve su stdout si salio bien y dijo algo.
fn salida(cmd: &str, args: &[&str]) -> Option<String> {
    let s = Command::new(cmd).args(args).output().ok()?;
    if !s.status.success() {
        return None;
    }
    let t = String::from_utf8_lossy(&s.stdout).trim().to_string();
    if t.is_empty() {
        None
    } else {
        Some(t)
    }
}

/// El valor de `clave:` en un archivo estilo `/proc`.
#[cfg(any(target_os = "linux", target_os = "android"))]
fn campo(texto: &str, clave: &str) -> Option<String> {
    for linea in texto.lines() {
        if let Some((k, v)) = linea.split_once(':') {
            if k.trim() == clave && !v.trim().is_empty() {
                return Some(v.trim().to_string());
            }
        }
    }
    None
}

// ── cpu ──────────────────────────────────────────────────────────────────────

#[cfg(any(target_os = "linux", target_os = "android"))]
fn cpu() -> Option<String> {
    let info = std::fs::read_to_string("/proc/cpuinfo").ok()?;
    // En x86 la marca esta en `model name`. En Android suele no estar, y hay que
    // caer al SoC, que es el dato que de verdad identifica la maquina.
    for clave in ["model name", "Hardware", "Processor", "cpu model"] {
        if let Some(v) = campo(&info, clave) {
            return Some(v);
        }
    }
    for ruta in ["/sys/devices/soc0/machine", "/proc/device-tree/model"] {
        if let Ok(v) = std::fs::read_to_string(ruta) {
            let v = v.trim_end_matches(char::from(0)).trim().to_string();
            if !v.is_empty() {
                return Some(v);
            }
        }
    }
    None
}

#[cfg(target_os = "windows")]
fn cpu() -> Option<String> {
    // El registro y no `wmic`: wmic ya no viene en Windows 11 reciente.
    salida(
        "reg",
        &[
            "query",
            r"HKLM\HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            "/v",
            "ProcessorNameString",
        ],
    )
    .and_then(|s| s.split("REG_SZ").nth(1).map(|x| x.trim().to_string()))
    .filter(|s| !s.is_empty())
    .or_else(|| std::env::var("PROCESSOR_IDENTIFIER").ok())
}

#[cfg(target_os = "macos")]
fn cpu() -> Option<String> {
    salida("sysctl", &["-n", "machdep.cpu.brand_string"])
}

#[cfg(not(any(
    target_os = "linux",
    target_os = "android",
    target_os = "windows",
    target_os = "macos"
)))]
fn cpu() -> Option<String> {
    None
}

// ── cache ────────────────────────────────────────────────────────────────────
//
// Es el campo que mas pesa de todos: el desplome del barrido de `conjunto` cae
// donde el conjunto de trabajo deja de entrar en el ultimo nivel, asi que sin
// esto la corrida ajena no se puede leer.

#[cfg(any(target_os = "linux", target_os = "android"))]
fn cache() -> Option<String> {
    let mut niveles = Vec::new();
    for i in 0..10 {
        let base = format!("/sys/devices/system/cpu/cpu0/cache/index{i}");
        let leer = |q: &str| std::fs::read_to_string(format!("{base}/{q}")).ok();
        let (nivel, tipo, tam) = match (leer("level"), leer("type"), leer("size")) {
            (Some(n), Some(t), Some(s)) => (n, t, s),
            _ => continue,
        };
        let sufijo = match tipo.trim() {
            "Data" => "d",
            "Instruction" => "i",
            _ => "",
        };
        niveles.push(format!("L{}{} {}", nivel.trim(), sufijo, tam.trim()));
    }
    if niveles.is_empty() {
        None
    } else {
        Some(niveles.join(" · "))
    }
}

#[cfg(target_os = "macos")]
fn cache() -> Option<String> {
    let mut niveles = Vec::new();
    for (etiqueta, clave) in [
        ("L1d", "hw.l1dcachesize"),
        ("L2", "hw.l2cachesize"),
        ("L3", "hw.l3cachesize"),
    ] {
        if let Some(b) = salida("sysctl", &["-n", clave]).and_then(|s| s.parse::<u64>().ok()) {
            if b > 0 {
                niveles.push(format!("{etiqueta} {}K", b / 1024));
            }
        }
    }
    if niveles.is_empty() {
        None
    } else {
        Some(niveles.join(" · "))
    }
}

#[cfg(not(any(target_os = "linux", target_os = "android", target_os = "macos")))]
fn cache() -> Option<String> {
    // Windows no lo expone sin llamar a la API de Win32, y meter FFI en un
    // binario de medicion cuesta mas de lo que devuelve: el modelo de CPU de
    // arriba ya identifica los tamanos.
    None
}

// ── ram ──────────────────────────────────────────────────────────────────────

#[cfg(any(target_os = "linux", target_os = "android"))]
fn ram() -> Option<String> {
    let info = std::fs::read_to_string("/proc/meminfo").ok()?;
    let v = campo(&info, "MemTotal")?;
    let kib: f64 = v.split_whitespace().next()?.parse().ok()?;
    Some(format!("{:.1} GiB", kib / 1024.0 / 1024.0))
}

#[cfg(target_os = "macos")]
fn ram() -> Option<String> {
    let b: f64 = salida("sysctl", &["-n", "hw.memsize"])?.parse().ok()?;
    Some(format!("{:.1} GiB", b / 1024.0 / 1024.0 / 1024.0))
}

#[cfg(not(any(target_os = "linux", target_os = "android", target_os = "macos")))]
fn ram() -> Option<String> {
    None
}

// ── toolchain y arbol ────────────────────────────────────────────────────────

/// `release` y `host` de `rustc -vV`.
fn rustc() -> (Option<String>, Option<String>) {
    let v = match salida("rustc", &["-vV"]) {
        Some(v) => v,
        None => return (None, None),
    };
    let campo = |clave: &str| {
        v.lines()
            .find_map(|l| l.strip_prefix(clave))
            .map(|s| s.trim().to_string())
    };
    (campo("release:"), campo("host:"))
}

/// El commit, y si el crate esta tocado respecto de el.
///
/// Se mira solo `.` —el crate— y no el repo entero: lo que hay que declarar es
/// si el arnes que produjo estos numeros es el publicado. El propio post pide
/// levantar el techo de paginas para una fila, asi que esa corrida **tiene** que
/// salir marcada.
fn commit() -> Option<String> {
    let h = salida("git", &["rev-parse", "--short=7", "HEAD"])?;
    let sucio = salida("git", &["status", "--porcelain", "--", "."]).is_some();
    Some(if sucio {
        format!("{h} (MODIFIED — please say what you changed)")
    } else {
        format!("{h} (clean)")
    })
}

// ── el bloque ────────────────────────────────────────────────────────────────

/// Imprime la procedencia de la corrida. Va antes que cualquier medicion.
pub fn imprimir() {
    let (version, triple) = rustc();
    let nucleos = std::thread::available_parallelism()
        .map(|n| n.get().to_string())
        .unwrap_or_else(|_| FALTA.to_string());
    let arch = format!(
        "{} ({}-bit){}",
        std::env::consts::ARCH,
        usize::BITS,
        triple.map(|t| format!(" · target {t}")).unwrap_or_default()
    );
    // `--release` apaga debug_assertions. Una corrida en debug es varias veces
    // mas lenta y no compara con nada, asi que se dice fuerte y no como un campo
    // mas de la lista.
    let perfil = if cfg!(debug_assertions) {
        "DEBUG — not comparable, rebuild with --release"
    } else {
        "release"
    };

    println!("# ── environment ── please paste this block with the table below ──");
    println!("# cpu       {}", cpu().unwrap_or_else(|| FALTA.into()));
    println!("# cores     {nucleos} (logical)");
    println!("# cache     {}", cache().unwrap_or_else(|| FALTA.into()));
    println!("# ram       {}", ram().unwrap_or_else(|| FALTA.into()));
    println!("# arch      {arch}");
    println!("# os        {}", std::env::consts::OS);
    println!("# rustc     {}", version.unwrap_or_else(|| FALTA.into()));
    println!("# profile   {perfil}");
    println!("# commit    {}", commit().unwrap_or_else(|| FALTA.into()));
    println!("# ────────────────────────────────────────────────────────────────");
    println!();
}
