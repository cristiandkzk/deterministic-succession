"""Codificación canónica: la única forma de convertir datos en bytes para hashear.

Todo hash del protocolo —el linaje de I4, la huella de estado de I3, el hash de
bloque— pasa por acá. Que dos nodos calculen el mismo hash sobre los mismos datos
es una precondición de todo lo demás, así que la codificación tiene tres reglas
que no son de estilo:

- **No hay flotantes.** Ni siquiera se aceptan para codificarlos: `codificar`
  levanta `FlotanteProhibido`. La Fase 4 exige que el flotante esté prohibido o
  canonicalizado *antes* de que el guante corra por primera vez, y una condición
  sobre Genesis no se levanta después. Prohibirlo desde el primer archivo es más
  barato que descubrir en la Fase 4 que se coló uno en un acumulador.
- **Toda codificación es autodelimitada.** Cada valor lleva etiqueta de tipo y
  largo. Sin eso, `("ab", "c")` y `("a", "bc")` tendrían la misma imagen y dos
  estados distintos podrían compartir huella.
- **El orden no lo elige quien llama.** Los diccionarios se recorren por clave
  ordenada y los conjuntos por su codificación ordenada. Un `dict` de Python
  conserva el orden de inserción; si ese orden entrara al hash, el mismo estado
  daría huellas distintas según en qué orden se construyó.

Un objeto que quiera hashearse expone `canonico()` y devuelve datos ya
codificables (dicts, listas, enteros, strings, bytes).
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping

_PREFIJO = b"genesis/"


class FlotanteProhibido(TypeError):
    """Se intentó codificar un flotante. Ver el docstring del módulo."""


class NoCodificable(TypeError):
    """Tipo sin codificación canónica definida."""


def codificar(valor: object) -> bytes:
    """Bytes canónicos de `valor`. Determinístico entre procesos y arquitecturas."""
    if isinstance(valor, float):
        raise FlotanteProhibido(
            "los flotantes no entran a ningún hash del protocolo: usá enteros "
            "(partes por millón, satoshis, bloques) en vez de fracciones"
        )
    if isinstance(valor, bool):  # antes que int: bool es subclase de int
        return b"T" if valor else b"F"
    if valor is None:
        return b"n"
    if isinstance(valor, int):
        return b"i" + str(valor).encode("ascii") + b";"
    if isinstance(valor, str):
        crudo = valor.encode("utf-8")
        return b"s" + str(len(crudo)).encode("ascii") + b":" + crudo
    if isinstance(valor, (bytes, bytearray)):
        return b"b" + str(len(valor)).encode("ascii") + b":" + bytes(valor)

    metodo = getattr(valor, "canonico", None)
    if callable(metodo):
        return codificar(metodo())

    if isinstance(valor, Mapping):
        claves = list(valor)
        if any(not isinstance(clave, str) for clave in claves):
            raise NoCodificable("las claves de un mapa canónico son strings")
        cuerpo = b"".join(codificar(c) + codificar(valor[c]) for c in sorted(claves))
        return b"d" + str(len(claves)).encode("ascii") + b":" + cuerpo
    if isinstance(valor, (set, frozenset)):
        elementos = sorted(codificar(e) for e in valor)
        return b"S" + str(len(elementos)).encode("ascii") + b":" + b"".join(elementos)
    if isinstance(valor, (list, tuple)):
        elementos = [codificar(e) for e in valor]
        return b"l" + str(len(elementos)).encode("ascii") + b":" + b"".join(elementos)

    raise NoCodificable(f"sin codificación canónica para {type(valor).__name__}")


def huella(valor: object, dominio: str) -> bytes:
    """SHA-256 de `valor` bajo un dominio de separación.

    El dominio evita que la imagen de un estado pueda hacerse pasar por la de un
    bloque o por la de un checkpoint generacional: son espacios distintos y no
    tienen por qué no colisionar por accidente.
    """
    return hashlib.sha256(
        _PREFIJO + dominio.encode("utf-8") + b"\x00" + codificar(valor)
    ).digest()


def corto(h: bytes) -> str:
    """Primeros 8 bytes en hexa. Sólo para mensajes y logs, nunca para comparar."""
    return h.hex()[:16]
