"""§6.4 · La equivocación no se prohíbe: se vuelve suicida.

El protocolo no impide firmar dos cosas distintas con el mismo índice de cuenta.
Lo que hace es que **hacerlo publique la clave privada**: el nonce se deriva del
índice, así que dos firmas en el mismo índice comparten nonce, y de dos firmas con
nonce compartido la clave sale con **una resta y una división**. Cualquiera que vea
las dos firmas puede barrer el saldo.

No hace falta detectar el fraude, ni juzgarlo, ni castigarlo: **el castigo lo
ejecuta cualquier tercero, movido por el botín.** Es el mismo patrón del canario de
§6.6 y del impugnador de §6.3 — el vigilante financiado por lo que se lleva.

> **Esto NO es criptografía de producción y no pretende serlo.** El grupo es de 134
> bits, elegido para que el mecanismo corra y se pueda leer. La primitiva real la
> elige Genesis (§6.6) y la Fase 4 reutiliza el arnés en Rust de `test2-interprete`.
> Lo que esta implementación sí demuestra es **la propiedad**, que es lo que la
> Fase 3 tiene que falsar: firmar dos veces publica la clave.

## El grupo, derivado y no elegido

Es la misma disciplina que el canario de §6.6 —*derivar, no generar*— aplicada acá,
y por el mismo motivo: si alguien **eligiera** los parámetros, habría que confiar en
que no se guardó nada.

```
q = 2**127 - 1                      primo de Mersenne
p = 2·j·q + 1                       con el j más chico que da p primo  → j = 57
g = h**((p-1)/q) mod p              con el h más chico que da g ≠ 1    → h = 2
```

Los tres pasos se rederivan en menos de un segundo y la prueba lo hace: no hay que
creerle a las constantes de abajo, hay que poder reconstruirlas.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

#: `2**127 - 1`, primo de Mersenne. El orden del subgrupo.
Q = 2**127 - 1

#: El `j` más chico tal que `2·j·Q + 1` es primo.
J = 57

#: El módulo.
P = 2 * J * Q + 1

#: El `h` más chico cuyo `h**((P-1)/Q) mod P` no es 1.
H = 2

#: El generador del subgrupo de orden `Q`.
G = pow(H, (P - 1) // Q, P)


class FirmaInvalida(ValueError):
    """La firma no verifica contra la clave declarada."""


def _entero(*partes: bytes) -> int:
    return int.from_bytes(hashlib.sha256(b"|".join(partes)).digest(), "big")


def clave_publica(privada: int) -> int:
    return pow(G, privada % Q, P)


def _nonce(privada: int, indice: int) -> int:
    """El nonce **se deriva del índice**, y ahí está todo el mecanismo.

    Determinístico a propósito: si fuera aleatorio, firmar dos veces en el mismo
    índice sería un accidente sin consecuencia y el fraude tendría que detectarse
    y castigarse desde afuera. Derivado, el castigo es automático y lo ejecuta
    cualquiera.
    """
    semilla = _entero(b"nonce", privada.to_bytes(32, "big"), indice.to_bytes(8, "big"))
    return semilla % Q or 1


@dataclass(frozen=True)
class Firma:
    """Schnorr: `(R, s)` con `R = g^k` y `s = k + e·x`."""

    r: int
    s: int
    indice: int

    def canonico(self) -> dict:
        return {"r": self.r, "s": self.s, "indice": self.indice}


def firmar(privada: int, mensaje: bytes, indice: int) -> Firma:
    k = _nonce(privada, indice)
    r = pow(G, k, P)
    e = desafio(r, mensaje)
    return Firma(r=r, s=(k + e * (privada % Q)) % Q, indice=indice)


def desafio(r: int, mensaje: bytes) -> int:
    return _entero(b"desafio", r.to_bytes(64, "big"), mensaje) % Q


def verificar(publica: int, mensaje: bytes, firma: Firma) -> bool:
    e = desafio(firma.r, mensaje)
    return pow(G, firma.s, P) == (firma.r * pow(publica, e, P)) % P


def recuperar_privada(
    mensaje_a: bytes, firma_a: Firma, mensaje_b: bytes, firma_b: Firma
) -> int | None:
    """La clave privada, de dos firmas en el mismo índice. **Una resta y una división.**

    ```
    s₁ = k + e₁·x        s₂ = k + e₂·x
    s₁ − s₂ = (e₁ − e₂)·x     →     x = (s₁ − s₂) / (e₁ − e₂)   (mod q)
    ```

    Devuelve `None` si no hay nada que recuperar: índices distintos —cada uno con su
    nonce—, o el mismo mensaje firmado dos veces, que no es doble firma sino la misma
    firma otra vez.
    """
    if firma_a.indice != firma_b.indice or firma_a.r != firma_b.r:
        return None
    if mensaje_a == mensaje_b:
        return None

    e_a = desafio(firma_a.r, mensaje_a)
    e_b = desafio(firma_b.r, mensaje_b)
    if (e_a - e_b) % Q == 0:
        return None  # colisión de desafío: no pasa, pero no se supone

    return ((firma_a.s - firma_b.s) * pow(e_a - e_b, -1, Q)) % Q


def derivacion_del_grupo() -> tuple[int, int, int]:
    """Rederiva `(J, P, G)` desde cero. La prueba corre esto, no confía en las constantes."""
    j = 1
    while True:
        p = 2 * j * Q + 1
        if _es_primo(p):
            break
        j += 1
    for h in range(2, 100):
        g = pow(h, (p - 1) // Q, p)
        if g != 1:
            return j, p, g
    raise RuntimeError("sin generador")  # pragma: no cover


def _es_primo(n: int, rondas: int = 24) -> bool:
    """Miller-Rabin determinístico para los primeros primos como testigos."""
    if n < 2:
        return False
    for pequeño in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % pequeño == 0:
            return n == pequeño
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for testigo in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)[:rondas]:
        x = pow(testigo, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True
