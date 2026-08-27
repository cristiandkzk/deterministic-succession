"""§6.3 · La ventana de impugnación, y por qué la cola no satura.

Una interacción queda firme cuando pasa la ventana sin que nadie presente prueba de
conflicto. No hay quórum ni conjunto de validadores: **cualquiera puede impugnar y
cualquiera puede verificar**. Lo que impide que un atacante la sature es una
asimetría:

```
llenar  ≤ T                  serial: una impugnación no existe hasta entrar en un bloque
drenar  = N · h · T / γ      paralelo: los N nodos PoD verifican a la vez
margen  = N · h / γ
```

`cola-impugnaciones/` cerró esto en agosto de 2026 **como fórmula**, y predijo que
con `γ = 1` y `h = 0,10` alcanzan **diez nodos PoD**. Lo que esta implementación
agrega no es otra fórmula: es correrla con una cola de verdad, con los `N` nodos
eligiendo qué verificar, y ver si la predicción sobrevive.

> **Y ahí aparece lo que la fórmula daba por sentado: que los `N` nodos no se pisan.**
> El paralelismo de `drenar` supone que cada nodo toma impugnaciones **distintas**, y
> §6.3 no dice cómo se reparten — no puede, porque no hay conjunto de validadores y
> ningún nodo sabe cuántos son. La regla más natural, *la más vieja primero*, hace que
> los `N` nodos verifiquen exactamente la misma, y el desagüe colapsa al de **un solo
> nodo** por más nodos que haya. Se mide en `herramientas/cola.py`.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

#: Las tres formas de elegir qué verificar, y no son intercambiables.
MAS_VIEJA = "mas_vieja"      # natural, y colapsa el paralelismo
AZAR = "azar"                # sin coordinación, y funciona
POR_HASH = "por_hash"        # perfecta, y **exige saber cuántos nodos hay**

ESTRATEGIAS = (MAS_VIEJA, AZAR, POR_HASH)


@dataclass(frozen=True)
class Impugnacion:
    identidad: int
    llegada: int
    #: Una impugnación legítima señala un fraude real. El ataque de censura consiste
    #: en enterrarla entre basura para que no se procese dentro del tope.
    legitima: bool = False


@dataclass
class Cola:
    """Las impugnaciones esperando verificación, en orden de llegada."""

    pendientes: list[Impugnacion] = field(default_factory=list)
    verificadas: dict[int, int] = field(default_factory=dict)  # identidad → altura
    #: Trabajo duplicado: verificaciones que dos nodos hicieron sobre lo mismo.
    duplicadas: int = 0

    def encolar(self, impugnacion: Impugnacion) -> None:
        self.pendientes.append(impugnacion)

    @property
    def largo(self) -> int:
        return len(self.pendientes)

    def espera_de(self, identidad: int) -> int | None:
        """Bloques entre la llegada y la verificación. `None` si sigue esperando."""
        altura = self.verificadas.get(identidad)
        if altura is None:
            return None
        llegada = next(
            (i.llegada for i in self._historial if i.identidad == identidad), None
        )
        return None if llegada is None else altura - llegada

    _historial: list[Impugnacion] = field(default_factory=list)


@dataclass
class NodoVerificador:
    """Un nodo PoD verificando impugnaciones con el sobrante de su bloque.

    `headroom` es cuánto trabajo extra hace por bloque, medido en bloques: `0,10`
    significa que además de verificar el bloque entero le sobra un 10% de bloque. Test
    2 midió 640 tx/s con un cuarto de núcleo en un teléfono, así que 0,10 es
    conservador por varios múltiplos.
    """

    nombre: int
    headroom: float
    estrategia: str = AZAR
    azar: random.Random = field(default_factory=lambda: random.Random(0))

    def elegir(self, cola: Cola, cuantas: int, total_nodos: int) -> list[Impugnacion]:
        if not cola.pendientes or cuantas <= 0:
            return []
        if self.estrategia == MAS_VIEJA:
            return cola.pendientes[:cuantas]
        if self.estrategia == POR_HASH:
            mias = [
                i for i in cola.pendientes if i.identidad % total_nodos == self.nombre
            ]
            return mias[:cuantas]
        indices = self.azar.sample(
            range(len(cola.pendientes)), min(cuantas, len(cola.pendientes))
        )
        return [cola.pendientes[i] for i in indices]


@dataclass
class Ronda:
    altura: int
    llegaron: int
    verificadas: int
    duplicadas: int
    backlog: int


def simular(
    nodos: int,
    bloques: int,
    capacidad_bloque: int = 100,
    headroom: float = 0.10,
    gamma: float = 1.0,
    estrategia: str = AZAR,
    legitima_en: int | None = None,
    semilla: int = 20260819,
) -> tuple[list[Ronda], Cola]:
    """Un atacante llena la cola a `capacidad_bloque` por bloque; `N` nodos drenan.

    Devuelve la traza por bloque y la cola final. Determinístico: misma semilla,
    mismo resultado.
    """
    if estrategia not in ESTRATEGIAS:
        raise ValueError(f"estrategia desconocida: {estrategia}")

    cola = Cola()
    verificadores = [
        NodoVerificador(n, headroom, estrategia, random.Random(semilla + n))
        for n in range(nodos)
    ]
    por_nodo = int(headroom * capacidad_bloque / gamma)
    siguiente = 0
    traza: list[Ronda] = []

    for altura in range(bloques):
        # llenar: serial, un bloque por vez
        llegaron = capacidad_bloque
        for _ in range(llegaron):
            impugnacion = Impugnacion(
                identidad=siguiente,
                llegada=altura,
                legitima=(legitima_en is not None and siguiente == legitima_en),
            )
            cola.encolar(impugnacion)
            cola._historial.append(impugnacion)
            siguiente += 1

        # drenar: paralelo, y acá se ve si se pisan
        tomadas: dict[int, int] = {}
        for verificador in verificadores:
            for impugnacion in verificador.elegir(cola, por_nodo, nodos):
                tomadas[impugnacion.identidad] = tomadas.get(impugnacion.identidad, 0) + 1

        duplicadas = sum(veces - 1 for veces in tomadas.values())
        for identidad in tomadas:
            cola.verificadas[identidad] = altura
        cola.duplicadas += duplicadas
        cola.pendientes = [i for i in cola.pendientes if i.identidad not in tomadas]

        traza.append(
            Ronda(
                altura=altura,
                llegaron=llegaron,
                verificadas=len(tomadas),
                duplicadas=duplicadas,
                backlog=cola.largo,
            )
        )

    return traza, cola


def margen_teorico(nodos: int, headroom: float = 0.10, gamma: float = 1.0) -> float:
    """`N · h / γ`, la fórmula de `cola-impugnaciones/`. Arriba de 1 no satura."""
    return nodos * headroom / gamma


def margen_medido(traza: list[Ronda]) -> float:
    """Verificadas sobre llegadas, en la corrida real. Puede ser menor al teórico."""
    llegadas = sum(r.llegaron for r in traza)
    return sum(r.verificadas for r in traza) / llegadas if llegadas else 0.0


def satura(traza: list[Ronda], cola_de_gracia: int = 5) -> bool:
    """¿El backlog creció al final de **esta** corrida?

    **Ojo con esta función: depende del largo de la corrida y no alcanza sola.**
    Con selección al azar el backlog no crece indefinidamente: se estabiliza, porque
    a mayor cola menos se pisan los nodos y el desagüe efectivo sube hasta igualar a
    la canilla. Una corrida corta lo agarra antes del equilibrio y lo reporta como
    saturación. Para decidir si satura de verdad está `crece_sin_techo`.
    """
    if len(traza) < cola_de_gracia * 2:
        return traza[-1].backlog > traza[0].backlog
    return traza[-1].backlog > traza[-cola_de_gracia - 1].backlog


def crece_sin_techo(
    nodos: int,
    estrategia: str,
    corta: int = 250,
    larga: int = 500,
    tolerancia: float = 1.15,
    **opciones,
) -> bool:
    """¿El backlog sigue creciendo al duplicar el largo de la corrida?

    Ésta es la pregunta que importa y la otra es su aproximación barata. Si el
    backlog de `larga` no supera al de `corta` por más que la tolerancia, el sistema
    encontró equilibrio: la cola es larga pero **acotada**, y eso no es saturar.
    """
    primera, _ = simular(nodos=nodos, bloques=corta, estrategia=estrategia, **opciones)
    segunda, _ = simular(nodos=nodos, bloques=larga, estrategia=estrategia, **opciones)
    return segunda[-1].backlog > primera[-1].backlog * tolerancia


def nodos_criticos(estrategia: str, tope: int = 40, **opciones) -> int | None:
    """El `N` más chico cuyo backlog deja de crecer. `None` si no hay dentro del tope."""
    for nodos in range(1, tope + 1):
        if not crece_sin_techo(nodos, estrategia, **opciones):
            return nodos
    return None


def espera_media(backlog: int, llegadas_por_bloque: int) -> float:
    """Ley de Little: `W = L / λ`. Bloques que espera una impugnación cualquiera.

    Se calcula del backlog de equilibrio en vez de cronometrar una impugnación
    suelta: una sola muestra con semilla fija es anécdota, no medición.
    """
    return backlog / llegadas_por_bloque if llegadas_por_bloque else 0.0
