"""`python herramientas/mutar.py` — la prueba de las pruebas.

Un criterio que sólo se corre contra código que funciona no distingue entre un
predicado y un `return`. Esto rompe el motor a propósito, de formas que el
paper declara imposibles, y verifica que la suite las cace. **Deja los archivos
como estaban**, pase lo que pase.

Si se agrega un mecanismo nuevo, agregarle acá su mutación: el costo es una
entrada en la lista y compra saber que el criterio nuevo tiene filo.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent

MUTACIONES = [
    (
        "la conmutación toca el estado (I3)",
        "sucesion/conmutador.py",
        "    huella_antes = estado.huella()",
        "    huella_antes = estado.huella()\n    estado.quemado += 1",
    ),
    (
        "Δ se cuenta desde el disparo y no desde el lock-in",
        "sucesion/cronograma.py",
        "                    altura_lockin + g.delta(disparo.clase), self.ultima_activacion",
        "                    disparo.altura + g.delta(disparo.clase), self.ultima_activacion",
    ),
    (
        "el lock-in se puede deshacer en una reorganización",
        "sucesion/cronograma.py",
        "        descartados = [d for d in self.pendientes.values() if d.altura >= altura_desde]",
        "        self.checkpoints = [c for c in self.checkpoints if c.altura_disparo < altura_desde]\n"
        "        descartados = [d for d in self.pendientes.values() if d.altura >= altura_desde]",
    ),
    (
        "una regla se rearma en el lock-in y no en la activación (lazo abierto)",
        "sucesion/cronograma.py",
        "        if self.en_vuelo(disparo.nombre, altura_cabeza) is not None:\n            return False\n",
        "",
    ),
    (
        "las activaciones no respetan el orden de lock-in",
        "sucesion/cronograma.py",
        "                altura_activacion=max(\n"
        "                    altura_lockin + g.delta(disparo.clase), self.ultima_activacion\n"
        "                ),",
        "                altura_activacion=altura_lockin + g.delta(disparo.clase),",
    ),
    (
        "el sucesor se computa sobre Genesis y no sobre el ruleset comprometido",
        "sucesion/cronograma.py",
        "            base = self.comprometido",
        "            base = self.ruleset_raiz",
    ),
    (
        "el evento de lock-in se publica al madurar y no por altura",
        "nodo/pod.py",
        "        self.cronograma.promover(altura, self.ventana_finalidad)\n"
        "        for checkpoint in self.cronograma.checkpoints:\n"
        "            if checkpoint.altura_lockin == altura:\n"
        '                self.estado.eventos.append({"tipo": "lock-in", **checkpoint.canonico()})\n'
        "        for rechazo in self.cronograma.rechazos:\n"
        "            if rechazo.altura == altura:\n"
        "                self.estado.eventos.append(rechazo.canonico())",
        "        nuevos, rechazados = self.cronograma.promover(altura, self.ventana_finalidad)\n"
        "        for checkpoint in nuevos:\n"
        '            self.estado.eventos.append({"tipo": "lock-in", **checkpoint.canonico()})\n'
        "        for rechazo in rechazados:\n"
        "            self.estado.eventos.append(rechazo.canonico())",
    ),
    (
        "una regla de aproximación puede disparar desde el reposo",
        "nodo/pod.py",
        "                if regla.modo == invariantes.MODO_APROXIMACION:\n"
        "                    invariantes.i2_se_vio_venir(regla, previas.get(regla.nombre))\n",
        "",
    ),
    (
        "el trigger de capacidad publica una cuenta regresiva inventada",
        "sucesion/distancia.py",
        '    if getattr(regla, "modo", "") == MODO_CAPACIDAD:\n'
        "        return armar(None, 0, ventana)\n",
        "",
    ),
    (
        "la instancia del canario no se verifica contra su semilla",
        "protocolo/invariantes.py",
        "    i2_canario_sin_trampa(g.CANARIO_SEMILLA, g.CANARIO_INSTANCIA)\n",
        "",
    ),
    (
        "el lock no mira el disponible (doble gasto)",
        "estado/cuentas.py",
        "        if cuenta.disponible < monto:",
        "        if False:",
    ),
    (
        "el nonce no se deriva del índice (la doble firma deja de ser suicida)",
        "liquidacion/doble_firma.py",
        'semilla = _entero(b"nonce", privada.to_bytes(32, "big"), indice.to_bytes(8, "big"))',
        'semilla = _entero(b"nonce", privada.to_bytes(32, "big"), b"fijo")',
    ),
    (
        "los nodos verifican la más vieja en vez de repartirse la cola",
        "liquidacion/impugnacion.py",
        "    estrategia: str = AZAR",
        "    estrategia: str = MAS_VIEJA",
    ),
    (
        "el contrafáctico usa el offset de después del fork y no el de antes",
        "herramientas/replay.py",
        "                altura_regla=(umbral_exp + AJUSTE) * EPOCA + offset,",
        "                altura_regla=(umbral_exp + AJUSTE) * EPOCA + retraso.offset,",
    ),
    (
        "una regla rechazada reintenta contra el mismo ancestro",
        "sucesion/cronograma.py",
        "        if self.rechazo_vigente(disparo.nombre) is not None:\n            return False\n",
        "",
    ),
    # ------------------------------------------------------------------ #
    # Fase 4 — el predicado y los dos techos
    # ------------------------------------------------------------------ #
    (
        "el techo de páginas no se cobra (vuelve el 23× de la persecución)",
        "predicado/aceptacion.py",
        "        return self.pasos <= presupuesto.pasos and self.paginas <= presupuesto.paginas",
        "        return self.pasos <= presupuesto.pasos",
    ),
    (
        "un predicado se evalúa sobre los vectores que le convienen",
        "predicado/aceptacion.py",
        "        if corrida is None:\n            return False",
        "        if corrida is None:\n            continue",
    ),
    (
        "R_declarado vuelve al ritmo de una sola mezcla (300 M)",
        "protocolo/genesis.py",
        "    96: 70_000_000,",
        "    96: 300_000_000,",
    ),
    (
        "la capacidad vuelve a 67 tx sin que el ritmo la banque",
        "protocolo/genesis.py",
        '        "tx_por_bloque": 15,',
        '        "tx_por_bloque": 67,',
    ),
    (
        "el presupuesto de páginas vuelve a 48 y deja a ML-DSA-87 sin precio posible",
        "protocolo/genesis.py",
        '        "paginas_vm": 96,',
        '        "paginas_vm": 48,',
    ),
    (
        "vuelve el muro: el presupuesto de páginas sale del espacio de parámetros",
        "protocolo/genesis.py",
        '    "paginas_vm": ConjuntoEntero(frozenset(R_DECLARADO_POR_PAGINAS)),',
        "",
    ),
    (
        "la memoria pasa a ser gratis: la curva se aplana",
        "protocolo/genesis.py",
        "    1_024: 9_000_000,",
        "    1_024: 70_000_000,",
    ),
    (
        "el tamaño de página se vuelve un parámetro del espacio (I1)",
        "protocolo/genesis.py",
        '    "tx_por_bloque": RangoEntero(1, 10_000),',
        '    "tx_por_bloque": RangoEntero(1, 10_000),' + "\n" + '    "pagina_bytes": RangoEntero(256, 65_536),',
    ),
    # ------------------------------------------------------------------ #
    # Fase 5 — permanencia y desalojo
    # ------------------------------------------------------------------ #
    (
        "el acumulador guarda una lápida por objeto (residuo O(n))",
        "estado/desalojo.py",
        "        return 32 * len(self.picos) + 8",
        "        return 32 * self.tamano + 8",
    ),
    (
        "la vida comprable deja de tener tope (permanencia comprada)",
        "estado/permanencia.py",
        "L_MAX_SEGUNDOS = g.L_MAX_EPOCAS * EPOCA_BLOQUES * 6_000 // 1_000",
        "L_MAX_SEGUNDOS = 10 ** 15",
    ),
    (
        "el depósito da descuento por volumen (cien pisos, diez mil años)",
        "estado/permanencia.py",
        "    return tamano_bytes * epocas",
        "    return tamano_bytes * int(epocas ** 0.8)",
    ),
    (
        "agotarse deja deuda en vez de vencer la entrada",
        "estado/permanencia.py",
        "        quemado = min(costo_en_segundos(self.tamano_bytes, epocas, ruleset), self.deposito)",
        "        quemado = costo_en_segundos(self.tamano_bytes, epocas, ruleset)",
    ),
    (
        "la prueba de reactivación no se revalida contra los picos vigentes (§10.2)",
        "estado/desalojo.py",
        "        if tuple(prueba.picos) != tuple(self.picos):",
        "        if False:",
    ),
    # ------------------------------------------------------------------ #
    # Fase 6 — el devnet, y lo que sólo se ve integrando
    # ------------------------------------------------------------------ #
    (
        "el depósito vuelve a llevarse en épocas y una conmutación lo reinterpreta (B3)",
        "estado/permanencia.py",
        "    return tamano_bytes * epocas * epoca_segundos(ruleset.interno(\"tiempo_bloque_ms\"))",
        "    return tamano_bytes * epocas",
    ),
    (
        "el tope de vida vuelve a estar en épocas en vez de en tiempo real",
        "estado/permanencia.py",
        "        if self.segundos_restantes() + costo // self.tamano_bytes > L_MAX_SEGUNDOS:",
        "        if False:",
    ),
    (
        "el desalojo recorre el conjunto en orden de hash (dos nodos, dos acumuladores)",
        "devnet/cadena.py",
        "        for identificador in vencidas:",
        "        for identificador in sorted(vencidas, key=hash):",
    ),
    # ------------------------------------------------------------------ #
    # red/ - validar es poder decir que no
    # ------------------------------------------------------------------ #
    (
        "el validador cree la raiz que el bloque declara en vez de recalcularla",
        "red/sync.py",
        "    if propio.raiz_estado != bloque.raiz_estado:",
        "    if False:",
    ),
    (
        "un bloque rechazado deja el estado a medio aplicar (envenenable)",
        "red/sync.py",
        '    nodo.estado.restaurar(foto["estado"])',
        '    pass',
    ),
    (
        "el validador acepta bloques que no encadenan con su cabeza",
        "red/sync.py",
        "    if bloque.padre != nodo.cadena[-1].hash():",
        "    if False:",
    ),
    # ------------------------------------------------------------------ #
    # estado/arbol.py - el corte es consenso, no implementacion
    # ------------------------------------------------------------------ #
    (
        "el piso vuelve a salir de la altura del arbol y no del arbol",
        "estado/permanencia.py",
        "    return Arbol(altura=altura, corte=g.CORTE_ARBOL).hashes_por_actualizacion()",
        "    return altura",
    ),
    (
        "el corte del arbol se mueve sin que nadie lo note",
        "protocolo/genesis.py",
        "CORTE_ARBOL = 6",
        "CORTE_ARBOL = 4",
    ),
    # ------------------------------------------------------------------ #
    # nodo/predicado.py - el veredicto es un hecho, no una opinion
    # ------------------------------------------------------------------ #
    (
        "el nodo acepta la salida del predicado sin compararla con el vector",
        "nodo/predicado.py",
        "        elif corrida.salida != esperada:",
        "        elif False:",
    ),
    (
        "un pedido se juzga con el techo vigente y no con el de su generacion",
        "nodo/predicado.py",
        "        if ruleset.generacion != self.generacion:",
        "        if False:",
    ),
    (
        "el techo de paginas deja de cobrarse al correr un predicado",
        "nodo/predicado.py",
        "        if paginas > presupuesto.paginas:",
        "        if False:",
    ),
]


def limpio() -> int:
    """`python herramientas/mutar.py --limpio` — ¿quedó algún archivo mutado?

    **Existe por un incidente.** El arnés muta un archivo, corre la suite y restaura; si
    se lo corta en el medio, **el archivo queda mutado y la suite empieza a fallar por una
    razón que no es la real**. Pasó el 21/8/2026 y costó un rato entender que el fallo no
    era del código nuevo. Un `finally` no alcanza cuando el proceso se mata desde afuera,
    así que la salida es poder preguntar.
    """
    sucios = 0
    for nombre, ruta, viejo, nuevo in MUTACIONES:
        texto = (RAIZ / ruta).read_text(encoding="utf-8")
        if viejo not in texto:
            sucios += 1
            print(f"MUTADO: {ruta} — {nombre}")
            if nuevo and nuevo in texto:
                (RAIZ / ruta).write_text(texto.replace(nuevo, viejo, 1), encoding="utf-8")
                print("   restaurado")
            else:
                print("   NO se pudo restaurar solo: revisar a mano")
    if not sucios:
        print(f"limpio · las {len(MUTACIONES)} mutaciones están sin aplicar")
    return 1 if sucios else 0


def main() -> int:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:  # pragma: no cover
            pass

    sin_cazar = 0
    for nombre, ruta, viejo, nuevo in MUTACIONES:
        archivo = RAIZ / ruta
        original = archivo.read_text(encoding="utf-8")
        if viejo not in original:
            print(f"[ANCLA PERDIDA] {nombre} — {ruta} cambió, hay que reescribir esta mutación")
            sin_cazar += 1
            continue

        archivo.write_text(original.replace(viejo, nuevo, 1), encoding="utf-8")
        try:
            corrida = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "pruebas", "-t", "."],
                cwd=RAIZ,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        finally:
            archivo.write_text(original, encoding="utf-8")

        caidos = [l for l in corrida.stderr.splitlines() if l.startswith(("FAILED", "OK"))]
        if corrida.returncode:
            print(f"[CAZADA]  {nombre} — {' '.join(caidos)}")
        else:
            print(f"[SE ESCAPÓ] {nombre} — ningún criterio se cayó")
            sin_cazar += 1

    print()
    if sin_cazar:
        print(f"{sin_cazar} mutaciones sin cazar: hay criterios que no prueban nada.")
        return 1
    print(f"las {len(MUTACIONES)} mutaciones se cazan: los criterios tienen filo.")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(limpio() if "--limpio" in sys.argv else main())
