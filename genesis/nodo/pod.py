"""El nodo que aplica bloques, evalúa la regla y conmuta.

**En esta fase es sólo eso.** El nodo PoD de §6.1 verifica, liquida y cobra fee;
la liquidación es la Fase 3 y acá no hay ni oferta, ni lock, ni impugnación, ni
fees repartidas. Lo que sí hay es la parte que ninguna otra pieza puede probar:
que la conmutación ocurre **en el mismo proceso, sobre el mismo estado**.

Por eso `arranques` existe y por eso vale 1 para siempre. El criterio de aprobado
de la Fase 1 dice *"el nodo no se reinicia; si hace falta reiniciar, la fase no
está aprobada"*, y un contador es la forma más barata de que eso sea falsable en
vez de ser una promesa.

**El orden dentro del bloque no es arbitrario** y conviene leerlo una vez:

1. **activación**, antes que nada: el ruleset nuevo gobierna el bloque entero,
   incluida su emisión;
2. **estado**: emisión y transacciones;
3. **lock-ins que maduraron** — se publican on-chain *en este bloque*, que es lo
   que le da al integrador su aviso de `Δ`;
4. **distancias** al disparo de cada regla, también on-chain (I2);
5. **la raíz del estado**, que cierra el bloque;
6. **los disparos nuevos**, que commitean esa raíz como `state_trigger`.

El 3 va antes del 6 a propósito: así el `state_trigger` de un disparo es exacta y
literalmente la raíz de estado del bloque `N`, y no una foto a mitad de camino.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from estado.sintetico import EstadoSintetico
from protocolo import genesis as g
from protocolo import invariantes
from protocolo.generacion import Ruleset
from protocolo.linaje import Checkpoint
from protocolo.serializacion import huella
from sucesion import distancia as distancia_mod
from sucesion.conmutador import conmutar
from sucesion.cronograma import Cronograma, Disparo
from sucesion.distancia import Distancia
from sucesion.regla import ReglaTransicion


class ReorganizacionProfunda(RuntimeError):
    """Se pidió reorganizar por debajo de la finalidad. No es una opción."""


@dataclass(frozen=True)
class Bloque:
    altura: int
    padre: bytes
    transacciones: tuple
    raiz_estado: bytes

    def canonico(self) -> dict:
        return {
            "altura": self.altura,
            "padre": self.padre,
            "transacciones": [list(t) for t in self.transacciones],
            "raiz_estado": self.raiz_estado,
        }

    def hash(self) -> bytes:
        return huella(self.canonico(), dominio="bloque")


@dataclass
class Conmutacion:
    """Registro de una conmutación efectiva, para inspección y para las pruebas."""

    altura: int
    generacion: int
    huella_estado: bytes


class NodoPoD:
    """Un nodo. Se construye una vez y no se vuelve a construir."""

    def __init__(
        self,
        reglas: Iterable[ReglaTransicion] = (),
        estado: EstadoSintetico | None = None,
        ruleset: Ruleset = g.RULESET_INICIAL,
        ventana_finalidad: int = g.VENTANA_FINALIDAD,
        ventana_ritmo: int = distancia_mod.VENTANA_RITMO,
        revisar_invariantes: bool = True,
    ) -> None:
        self.arranques = 1
        self.estado = estado if estado is not None else EstadoSintetico()
        self.ruleset = ruleset
        self.ventana_finalidad = ventana_finalidad
        self.ventana_ritmo = ventana_ritmo
        self.revisar_invariantes = revisar_invariantes

        self.reglas: list[ReglaTransicion] = list(reglas)
        self.cronograma = Cronograma(ruleset)
        self.historial_rulesets: list[tuple[int, Ruleset]] = [(0, ruleset)]
        self.historial_progreso: dict[str, list[int]] = {
            r.nombre: [] for r in self.reglas
        }
        self.conmutaciones: list[Conmutacion] = []

        bloque_cero = Bloque(
            altura=0,
            padre=ruleset.h0,
            transacciones=(),
            raiz_estado=self.estado.huella(),
        )
        self.cadena: list[Bloque] = [bloque_cero]
        self.instantaneas: dict[int, dict] = {0: self.estado.instantanea()}

    # -- lecturas ---------------------------------------------------------- #

    @property
    def altura(self) -> int:
        return self.cadena[-1].altura

    @property
    def generacion(self) -> int:
        return self.ruleset.generacion

    @property
    def ruleset_comprometido(self) -> Ruleset:
        """El último ruleset **commiteado**, esté activo o todavía esperando `Δ`.

        Es la base de todo sucesor, y no el ruleset vigente. La diferencia sólo
        se nota con dos transiciones en vuelo; el porqué está en el docstring de
        `sucesion/cronograma.py` y en §3 del paper.
        """
        return self.cronograma.comprometido

    def distancia(self, nombre_de_regla: str) -> Distancia:
        """La distancia al disparo, **leída del estado** y no recalculada.

        Que salga del estado es el punto: es lo mismo que puede leer cualquiera
        con la cadena, sin correr la regla ni confiar en este nodo.
        """
        return self.estado.distancias[nombre_de_regla]

    def avisos_pendientes(self) -> list[Checkpoint]:
        """Transiciones con lock-in y todavía sin activar. Lo que ve el integrador."""
        return self.cronograma.pendientes_de_activar(self.altura)

    def es_final(self, altura: int) -> bool:
        return self.altura >= altura + self.ventana_finalidad

    # -- producción de bloques --------------------------------------------- #

    def producir_bloque(self, transacciones: Sequence[tuple] = ()) -> Bloque:
        altura = self.altura + 1

        # 1 · activación: el ruleset nuevo gobierna el bloque entero.
        for checkpoint in self.cronograma.activaciones(altura):
            self.ruleset = conmutar(self.estado, self.ruleset, checkpoint)
            self.historial_rulesets.append((altura, self.ruleset))
            self.conmutaciones.append(
                Conmutacion(altura, self.ruleset.generacion, self.estado.huella())
            )

        # 2 · estado.
        self.estado.altura = altura
        self.estado.emitir(self.ruleset)
        for transaccion in transacciones:
            self.estado.aplicar(transaccion, self.ruleset)

        # 3 · disparos maduros: lock-in o rechazo, publicados on-chain acá.
        #
        # Se publica **por altura**, no por "recién resuelto", y la diferencia
        # sólo se ve en una reorganización: si se deshace el bloque que contenía
        # el evento, el checkpoint sobrevive —es irrevocable— y el evento tiene
        # que volver a emitirse cuando esa altura se vuelve a producir. Publicar
        # sólo lo recién madurado dejaba un lock-in vigente sin rastro on-chain,
        # o sea un aviso que el integrador no puede leer.
        self.cronograma.promover(altura, self.ventana_finalidad)
        for checkpoint in self.cronograma.checkpoints:
            if checkpoint.altura_lockin == altura:
                self.estado.eventos.append({"tipo": "lock-in", **checkpoint.canonico()})
        for rechazo in self.cronograma.rechazos:
            if rechazo.altura == altura:
                self.estado.eventos.append(rechazo.canonico())

        # 4 · distancias al disparo (I2).
        previas = dict(self.estado.distancias)
        for regla in self.reglas:
            historial = self.historial_progreso[regla.nombre]
            # Una regla con transición en vuelo no se rearma hasta la activación:
            # la distancia no puede dar menos que lo que falta para eso.
            en_vuelo = self.cronograma.en_vuelo(regla.nombre, altura)
            piso = en_vuelo.altura_activacion - altura if en_vuelo else 0
            self.estado.distancias[regla.nombre] = distancia_mod.calcular(
                regla, self.estado, historial, self.ventana_ritmo, piso=piso
            )
            historial.append(regla.progreso(self.estado))

        # 5 · la raíz cierra el bloque.
        raiz = self.estado.huella()
        bloque = Bloque(
            altura=altura,
            padre=self.cadena[-1].hash(),
            transacciones=tuple(transacciones),
            raiz_estado=raiz,
        )
        self.cadena.append(bloque)

        # 6 · disparos nuevos, commiteando la raíz de este bloque.
        # El disparo se lleva el estado congelado, no los parámetros: el sucesor
        # se computa en el lock-in, sobre el ruleset comprometido de ese momento.
        hash_bloque = bloque.hash()
        congelado = None
        for regla in self.reglas:
            if regla.dispara(self.estado):
                # I2, la mitad con filo: una regla que se declara por aproximación
                # no puede disparar desde el reposo. El bloque anterior tenía que
                # haber publicado una distancia observable — si no, es un escalón
                # con disfraz de rampa, y un escalón hay que declararlo como tal.
                if regla.modo == invariantes.MODO_APROXIMACION:
                    invariantes.i2_se_vio_venir(regla, previas.get(regla.nombre))
                if congelado is None:
                    congelado = self.estado.congelar()
                self.cronograma.registrar_disparo(
                    Disparo(
                        regla=regla,
                        altura=altura,
                        hash_bloque=hash_bloque,
                        state_trigger=raiz,
                        estado=congelado,
                    ),
                    altura_cabeza=altura,
                )

        self.instantaneas[altura] = self.estado.instantanea()
        self._podar_instantaneas()

        if self.revisar_invariantes:
            invariantes.revisar_bloque(
                estado=self.estado,
                ruleset=self.ruleset,
                reglas=self.reglas,
                historial_progreso=self.historial_progreso,
                checkpoints=self.cronograma.checkpoints,
            )
        return bloque

    def producir(self, cantidad: int, transacciones: Sequence[tuple] = ()) -> None:
        """`cantidad` bloques seguidos, con las mismas transacciones en cada uno."""
        for _ in range(cantidad):
            self.producir_bloque(transacciones)

    # -- reorganización ---------------------------------------------------- #

    def reorganizar(
        self, altura_desde: int, bloques: Sequence[Sequence[tuple]] = ()
    ) -> list[Disparo]:
        """Deshace desde `altura_desde` y reaplica la rama nueva.

        Lo que **no** se puede: reorganizar un bloque ya final. La finalidad es
        la ventana de impugnación (§6.3), y si un bloque final pudiera deshacerse
        el lock-in no significaría nada. Un nodo que recibe una rama así no elige
        entre dos historias: la rechaza.

        Devuelve los disparos advisorios que la reorganización se llevó puestos.
        """
        if altura_desde < 1 or altura_desde > self.altura:
            raise ValueError(f"altura fuera de la cadena: {altura_desde}")
        if self.es_final(altura_desde):
            raise ReorganizacionProfunda(
                f"el bloque {altura_desde} es final (cabeza {self.altura}, ventana "
                f"{self.ventana_finalidad}): no se reorganiza"
            )

        descartados = self.cronograma.reorganizar(altura_desde)

        objetivo = altura_desde - 1
        self.estado.restaurar(self.instantaneas[objetivo])
        self.cadena = self.cadena[: objetivo + 1]
        self.instantaneas = {
            h: inst for h, inst in self.instantaneas.items() if h <= objetivo
        }
        for historial in self.historial_progreso.values():
            del historial[objetivo:]

        # El ruleset vuelve al que regía en el objetivo: una activación dentro de
        # la ventana también se deshace. El checkpoint no — se reactiva sola al
        # reaplicar, porque el lock-in sigue ahí.
        self.historial_rulesets = [
            (h, r) for h, r in self.historial_rulesets if h <= objetivo
        ]
        self.ruleset = self.historial_rulesets[-1][1]
        self.conmutaciones = [c for c in self.conmutaciones if c.altura <= objetivo]

        for transacciones in bloques:
            self.producir_bloque(transacciones)

        return descartados

    # -- interno ----------------------------------------------------------- #

    def _podar_instantaneas(self) -> None:
        """Sólo se guarda lo que se puede deshacer: la ventana de finalidad."""
        piso = self.altura - self.ventana_finalidad
        if piso <= 0:
            return
        for h in [h for h in self.instantaneas if h < piso]:
            del self.instantaneas[h]

    # -- diagnóstico ------------------------------------------------------- #

    def resumen(self) -> str:
        lineas = [
            f"altura {self.altura} · generación {self.generacion} · "
            f"arranques {self.arranques}",
            f"emitido {self.estado.emitido} · quemado {self.estado.quemado}",
            self.cronograma.resumen(),
        ]
        for nombre in sorted(self.estado.distancias):
            lineas.append(f"  {self.estado.distancias[nombre]}")
        return "\n".join(lineas)
