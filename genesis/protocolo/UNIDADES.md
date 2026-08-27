# Auditoría de unidades — qué pasa por debajo de las cinco invariantes

**Corrida el 22/8/2026, después de terminar el roadmap.** No es una fase: es una pregunta que
dejaron planteada las dos últimas correcciones y que conviene hacer de frente.

## La pregunta

Las Fases 4 y 6 encontraron cada una un defecto que **no violaba ninguna de las cinco
invariantes**:

| defecto | qué hacía | qué invariante lo veía |
|---|---|---|
| el techo de páginas era constante (C18) | excluía primitivas en vez de encarecerlas, contra la promesa de §6.6 | ninguna |
| el depósito estaba en byte-épocas (C20, B3) | una conmutación reinterpretaba lo que un depósito ya pagado había comprado | ninguna |

Los dos son la misma forma. **I3 protege los bytes; nada protege lo que los bytes significan.**
El estado cruzó íntegro las dos veces —el conmutador lo verifica por huella y por identidad de
objeto— y lo que cambió fue el valor de lo que cruzó.

De ahí la pregunta que se puede hacer mecánicamente:

> **Para cada cantidad que el protocolo guarda o declara: ¿su significado depende de un parámetro
> que una transición puede mover?**

Si depende, hay dos salidas —denominarla en algo que no dependa, o recalcularla en la
transición— y ninguna es gratis. Lo que no es una salida es no darse cuenta.

---

## El barrido

Los parámetros que una transición puede mover son los de `ESPACIO_INTERNO`: emisión por bloque,
tamaño de bloque, **tiempo de bloque**, fee de quema, **transacciones por bloque** y **páginas de
VM**. Los tres en negrita son los que redefinen unidades de otras cosas.

| cantidad | unidad | ¿la mueve un parámetro? | estado |
|---|---|---|---|
| `deposito` de permanencia | byte-segundos declarados | no, desde C20 | ✅ corregido |
| `L_MAX_SEGUNDOS` | segundos | no, desde C20 | ✅ corregido |
| `EPOCA_BLOQUES` | bloques → se convierte con el tiempo declarado | no, desde C20 | ✅ |
| techo de pasos | pasos | se **deriva** de tiempo de bloque, tx y páginas — a propósito | ✅ es la fórmula |
| techo de páginas | páginas | es parámetro y se paga en capacidad | ✅ desde C18 |
| `saldos`, `emitido`, `quemado` | unidades del token | el valor del token flota | ⚠️ §10.3, frontera declarada |
| `altura`, `indice` | contadores | no significan tiempo | ✅ |
| `VENTANA_FINALIDAD` | bloques | mide profundidad de reorganización, que es natural en bloques | ✅ |
| **`DELTA_POR_CLASE` (`Δ`)** | **bloques** | **sí — el tiempo de bloque lo mueve 60×** | ❌ **abierto** |
| `TOPE_DEMORA_LOCKIN` | bloques | acota espera de finalidad, natural en bloques | ✅ |

---

## Lo que encontró: `Δ`

`Δ` es la ventana de aviso entre lock-in y activación, y §10.1 dice para qué existe:

> **La ventana `Δ` compra seguridad de integración con tiempo de reacción.** Una ventana larga
> deja a la cadena corriendo bajo reglas que ya se sabe que no alcanzan; una corta le pasa el
> costo a todo el que integró.

**Compra tiempo de reacción.** Y está denominada en bloques, con estos valores:

| clase | `Δ` | bloque de 1 s | bloque de 6 s (Genesis) | bloque de 60 s |
|---|---:|---:|---:|---:|
| circulación | 64 bloques | 1,1 min | **6,4 min** | 64 min |
| criptográfica | 8 bloques | 8 s | **48 s** | 8 min |

Son **dos problemas y conviene no mezclarlos**:

### 1 · La unidad — el mismo defecto que B3

El aviso real varía **60×** según el tiempo de bloque, y el tiempo de bloque es un parámetro
interno. Peor: una transición puede cambiarlo **mientras otra está en vuelo**, con lo cual el
aviso ya anunciado se acorta o se alarga después de anunciado. Es exactamente lo que le pasaba
al depósito, en el mecanismo central en vez de en la permanencia.

**Y acá la corrección de C20 no se aplica igual**, y por eso queda abierto en vez de arreglado.
Denominar `Δ` en tiempo declarado y convertirlo a bloques al hacer lock-in preserva el aviso *en
el momento del lock-in*, pero no después: si el tiempo de bloque cambia entre el lock-in y la
activación, la altura ya anunciada da otro tiempo real. Y §3 es explícito en que la altura de
activación **se emite on-chain al hacer lock-in**, así que moverla después contradice el
mecanismo.

Las tres salidas, y ninguna es gratis:

- **recalcular la altura de activación** cuando cambia el tiempo de bloque. Preserva el aviso,
  que es lo que importa, pero la altura anunciada deja de ser fija — aunque se mueve de forma
  pública y determinística;
- **prohibir que un cambio de tiempo de bloque active mientras hay una transición en vuelo.**
  Angosto y chequeable, y no toca §3;
- **declararlo**, como una frontera más.

### 2 · La magnitud — y es lo más grande de los dos

Con los valores actuales, `Δ` da **6,4 minutos** para una transición de circulación y **48
segundos** para una criptográfica. Ningún integrador reacciona en seis minutos.

O sea que **la tensión que §10.1 describe no existe a estos números**: no hay un compromiso entre
la urgencia de la cadena y el tiempo de reacción del integrador, porque los dos valores están del
mismo lado —el de "ningún aviso"—. La perilla está descripta como un compromiso real y no está
sobre esa curva.

Y lo que de verdad protege al integrador es **I5**, no `Δ`: quien no llegó a soportar la
generación nueva sigue operando en la anterior y degrada en vez de detenerse (§4). Eso ya está
en el paper y es lo que hace que el número chico no sea catastrófico — pero entonces `Δ`
está haciendo mucho menos de lo que §10.1 le atribuye.

> **Los valores 64 y 8 nunca aparecieron en el paper.** Viven sólo en `protocolo/genesis.py`
> desde la Fase 1, donde alcanzaban para que las pruebas corrieran. El paper habla de *"`Δ`
> largo"* y *"`Δ` corto"* sin dar números, así que nadie los contrastó nunca contra lo que la
> sección dice que compran.

---

## Lo que esta auditoría no contesta

**Cuánto tiene que valer `Δ`.** Es una decisión de diseño sobre el mecanismo central y no sale de
ninguna cuenta: depende de a quién se le promete el aviso y de cuánto tarda ese alguien en
actualizar software. Lo que sí queda establecido es que **los valores actuales no están sobre la
curva que el paper describe**, y que el número tiene que decidirse mirando tiempo real y no
bloques.
