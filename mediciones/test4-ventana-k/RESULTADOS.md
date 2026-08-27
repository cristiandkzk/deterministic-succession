# Test 4 · La ventana de `k`

> Estado: **cerrado. No pasa.** Corregido el 17/8/2026 — ver §2.
> La emisión neta y la ganancia del autotratante son **la misma cantidad**, así que
> no hay ningún `k` que cree dinero nuevo sin crear exactamente esa oportunidad de
> farmeo. En el máximo `k` seguro, todo el aparato de emisión y quema equivale a un
> mercado de fees sin emisión ni quema. Y hay un segundo problema, independiente de
> `k`: el lazo no puede arrancar.

Lo que pide §12: *"simular si existe algún `k > 0` donde auto-pagarse no sea rentable
y el subsidio todavía sea significativo para un operador honesto"*. Es el test con doble
función: decide a la vez si la moneda es sana (§7.1) y si la etapa 1 de adopción es
viable (§9).

Reproducible con `python simulacion.py`. No hay datos externos: es aritmética sobre el
modelo que el propio paper escribe.

---

## 1. El modelo, tomado literal del paper

§7.1 da la fórmula:

```
E(t) = min( curva_temporal(t),  k · W(t) )
```

`W(t)` es el trabajo liquidado y verificado, medido **en tokens pagados** — es lo único
que el protocolo puede contar sin juzgar utilidad (§7.1, regla 1). Entonces `k` es
adimensional: subsidio por token de trabajo pagado. El subsidio se reparte a prorrata,
así que la tasa efectiva por token es `r = E/W = min(curva/W, k)`.

**El autotratante** (§9: *"un agente que se paga a sí mismo"*). Cicla `W` tokens: los
deposita en escrow y los cobra él mismo, así que el pago neto es cero. Sus costos:

- el fee del protocolo, `φ·W`, del cual se quema una fracción `β` y el resto va a los
  nodos PoD (§6.1);
- si además corre nodos PoD, recupera una fracción `s` de esa parte no quemada
  (`s = 1` es el atacante verticalmente integrado);
- el trabajo en sí: elige el predicado más barato que §6.2 admita. Ese costo es **fijo
  por liquidación, no proporcional a `W`**, así que escalando `W` lo diluye a cero.

```
costo por ciclo = φ · (1 − s·(1−β)) · W        ganancia = r · W
```

**El operador honesto** cobra `W` de un cliente real, gasta cómputo real, paga el mismo
fee y recibe **el mismo `r`**. El protocolo no puede distinguirlo del autotratante: no
es una omisión, es la regla 1 de §7.1 funcionando como fue escrita.

**"Significativo"** se mide como fracción del ingreso bruto del operador,
`r/(1+r)`, contra un umbral `σ`. `σ = 10%` significa *"el subsidio es al menos el 10%
de lo que factura"*.

---

## 2. Corrección: quién cobra la emisión

**El error.** La primera corrida midió la significancia del subsidio contra la
facturación del nodo que hace el trabajo. §6.1 dice lo contrario, textual: el ingreso
del nodo de cómputo es *"el pago del pedido que ejecutaron, **no la emisión del
protocolo**"*. El paper no dice en ningún lado quién sí cobra `E(t)`; por descarte, los
nodos PoD. Rehecho en `correccion-destinatario.py`.

**El techo no se mueve.** El autotratante corre su propio nodo PoD para capturar la
emisión sobre el trabajo que él mismo fabrica, y §6.1 hace esa entrada barata *a
propósito* — *"un nodo que entra en un teléfono"*. Así que la integración vertical deja
de ser el peor caso y pasa a ser el caso normal: `s = 1`, techo `k ≤ β·φ`.

**Lo que sí cambia es que el resultado se vuelve una identidad.** Por unidad de trabajo
liquidado:

```
emisión creada        k·W
quema                 β·φ·W
─────────────────────────────────
emisión neta          (k − β·φ)·W
ganancia autotratante (k − β·φ)·W        ← la misma expresión
```

> **El teorema.** `emisión neta > 0` ⟺ `auto-pagarse es rentable`. No son dos
> condiciones que haya que hacer entrar en una ventana: son **la misma cantidad**. Todo
> peso de dinero nuevo que el protocolo crea es, exactamente, un peso de ganancia
> disponible para quien fabrique trabajo.

De ahí sale la forma más nítida del veredicto. En `k* = β·φ`, que es el máximo seguro:

| | con emisión y quema | sin emisión ni quema |
|---|---|---|
| emisión neta | 0 | 0 |
| ingreso de los nodos PoD | `(1−β)φW + kW = φW` | `φW` |

**Son idénticos.** En el máximo `k` seguro, todo el aparato monetario de §7.1 hace
exactamente lo que haría un mercado de fees sin emisión ni quema. No hay tercera región:
o la emisión es un no-op, o es un subsidio al farmeo del tamaño exacto de la emisión
neta.

**Y la pregunta de la significancia se disuelve en vez de contestarse.** En `k*` el
"subsidio" *es* el fee, así que preguntar si alcanza para un nodo PoD es una pregunta de
mercado de fees, no de política monetaria. La respuesta, con nodos que cuestan un
teléfono (US$ 100/año amortizado) y entrada libre hasta beneficio cero:

| trabajo liquidado anual | φ=0,1% | φ=0,3% | φ=1,0% |
|---|---|---|---|
| US$ 1 M | 10 nodos | 30 | 100 |
| US$ 100 M | 1 000 | 3 000 | 10 000 |
| US$ 1 000 M | 10 000 | 30 000 | 100 000 |

Con US$ 100 M anuales liquidados y fee del 0,3%, la red banca ~3 000 nodos PoD — del
orden de los nodos de ejecución de Ethereum. **El mercado de fees sí sostiene una capa
liviana grande.** Lo que no hace falta para eso es la emisión: esos números salen del
fee, no de `k`.

### 2.1 El arranque en frío (independiente de `k`)

`W(t)` se mide en tokens pagados, y §7.1 dice *"no hay preminado, ni tesorería, ni
asignación de equipo. Toda unidad que existe nació contra trabajo entregado."*

En el bloque 0 no existe ningún token. Entonces nadie puede pagar, entonces `W = 0`,
entonces `E = min(curva, k·0) = 0`, y el circulante sigue en cero para siempre. **El
lazo es cerrado y arranca en cero.** Emitir la primera unidad exige una emisión inicial
que no dependa de `W`, que es exactamente lo que la misma sección prohíbe.

No es un problema de calibración de `k`: ningún valor de `k` lo mueve. Es una
contradicción entre dos frases de §7.1, y no la habíamos visto porque la primera
simulación tomaba `W_h` como dato exógeno.

### 2.2 Qué queda en pie de §3 a §5

Las tablas de §3 a §5 se calcularon con el destinatario equivocado, así que **los números
de significancia contra la facturación del operador de cómputo (0,15%, 334×–2001×) ya no
describen nada del diseño** y no hay que citarlos. Lo que sobrevive intacto:

- el techo `k ≤ φ·(1−s(1−β))` y su forma normal `k ≤ β·φ` (§2, §3);
- que arriba del umbral `k` deja de ser variable de control y la entrada libre clava la
  tasa efectiva en el costo del autotratante (§3);
- la escapatoria del piso de costo real `γ` y su precio (§5);
- el corolario del fee *ad valorem* (§6).

---

## 3. El resultado principal: la ventana se reduce a una desigualdad

Como el subsidio y el costo del autotratante **escalan los dos con `W`**, la
rentabilidad del autotrato es invariante de escala: no depende del capital, ni del
volumen, ni de la curva. Todo el test colapsa a comparar dos tasas:

```
no farmear   ⟺   k ≤ φ · (1 − s·(1−β))          ← techo de seguridad
ser goloso   ⟺   k ≥ σ / (1 − σ)                ← piso de adopción
```

**La ventana existe si y solo si `σ ≲ φ_efectivo`.** Ni la curva temporal, ni el tamaño
de la red, ni el precio del token entran en la condición.

| φ | β | s | techo de `k` | σ=1% | σ=5% | σ=10% | σ=20% |
|---|---|---|---|---|---|---|---|
| 0,1% | 0,50 | 1 | 0,00025 | · | · | · | · |
| 0,3% | 0,50 | 1 | 0,00150 | · | · | · | · |
| 0,3% | 1,00 | 0 | 0,00300 | · | · | · | · |
| 1,0% | 1,00 | 0 | 0,01000 | · | · | · | · |
| 3,0% | 1,00 | 0 | 0,03000 | **sí** | · | · | · |
| 10,0% | 1,00 | 0 | 0,10000 | **sí** | **sí** | · | · |

La ventana recién se abre —y solo para el umbral más laxo, 1%— cuando el protocolo
cobra **3% por liquidación**. §6.1 pide *"un fee chico"*. Stripe cobra 2,9%.

**Solo la parte quemada acota.** Con `s = 1`, el techo baja de `φ` a `β·φ`: el atacante
que corre nodos PoD recicla la parte del fee que no se quema. El paper ya intuía esto
—§7.1 dice *"el fee quemado"*— pero la consecuencia no estaba escrita: **el techo de `k`
no es el fee, es el fee por la fracción de quema.**

---

## 4. Lo que rompe la afirmación de §9

§9 dice, textual:

> *"La ventana de arbitraje y la ventana de autotrato son la misma ventana. Lo único que
> las separa es `k`."*

**`k` no las separa, porque `k` entra idénticamente en las dos.** El autotratante y el
operador honesto reciben la misma tasa `r` sobre el mismo `W`, y tienen que recibirla:
distinguirlos exigiría que el protocolo juzgue si el trabajo era real, que es exactamente
lo que la regla 1 prohíbe. Lo que separa a los dos es `φ_efectivo` contra `σ` — dos
números que el diseño fija por otras razones y que `k` no puede mover.

Y hay una segunda consecuencia, más incómoda: **arriba del umbral, `k` deja de ser
variable de control.** Con entrada libre, los autotratantes entran hasta que la dilución
lleva `r` a su propio costo. Diez períodos con `k = 0,10` —67× el umbral— y demanda
orgánica creciendo 60% por período:

| período | `W_h` orgánico | `W_f` farmeado | `r` | captura | significancia |
|---|---|---|---|---|---|
| 1 | 10 000 | 66 656 667 | 0,00150 | 100,0% | 0,15% |
| 5 | 65 536 | 66 601 131 | 0,00150 | 99,9% | 0,15% |
| 10 | 687 195 | 65 979 472 | 0,00150 | 99,0% | 0,15% |

`r` no se mueve de `0,00150` = `β·φ`. **Subir `k` no le sube el subsidio al operador
honesto ni un punto básico**: solo determina cuántos autotratantes entran a diluirlo.
Y capturan entre el 99% y el 100% de la emisión.

De ahí sale el único `k` defendible:

> **`k* = φ · (1 − s·(1−β))`, exactamente.** Es el máximo que no invita al autotrato, y
> es también el máximo subsidio alcanzable. Por encima, el mercado lo devuelve a ese
> mismo valor cobrando el peaje de que la emisión se la lleven los farmers.

---

## 5. La intensidad, contra el ejemplo que §9 dice seguir

§9: *"el bootstrap previsto es el de Bitcoin"*. En Bitcoin 2009–2012 el subsidio fue
prácticamente el 100% del ingreso del minero; los fees eran ruido.

| φ | β | s | `k*` | subsidio / ingreso | vs. Bitcoin |
|---|---|---|---|---|---|
| 0,1% | 0,50 | 1 | 0,00050 | 0,05% | **2001×** más débil |
| 0,3% | 0,50 | 1 | 0,00150 | 0,15% | **668×** |
| 0,3% | 1,00 | 0 | 0,00300 | 0,30% | **334×** |
| 1,0% | 1,00 | 0 | 0,01000 | 0,99% | **101×** |
| 3,0% | 1,00 | 0 | 0,03000 | 2,91% | **34×** |

*(Medir contra el margen en vez de contra el ingreso bruto mejora estos números por el
inverso del margen — con margen del 10%, un subsidio del 0,3% del ingreso es 3% del
margen. Sigue siendo un orden de magnitud corto de "goloso", pero es la lectura más
favorable y corresponde declararla.)*

§9 dice que la etapa 1 *"es casi segura: todo yield farm de la historia lo demuestra"*.
Los yield farms ofrecían retornos de dos y tres dígitos. Acá el techo es **0,15%**.

---

## 6. La única escapatoria, y lo que cuesta

El techo es bajo porque fabricar trabajo falso es **gratis salvo el fee**. La única
forma estructural de subirlo es que producir un token de trabajo cueste algo real e
irreducible, `γ`, además del fee. El techo pasa a ser `φ_efectivo + γ`.

| σ | φ | β | s | techo actual | `γ` necesario |
|---|---|---|---|---|---|
| 1% | 0,3% | 0,50 | 1 | 0,00150 | 0,86% |
| 5% | 0,3% | 0,50 | 1 | 0,00150 | 5,11% |
| 10% | 0,3% | 0,50 | 1 | 0,00150 | **10,96%** |
| 10% | 1,0% | 1,00 | 0 | 0,01000 | 10,11% |

Para que el subsidio sea el 10% del ingreso del operador, el protocolo tiene que
garantizar que **fabricar trabajo cueste ~11% de su valor en recursos reales**.

Y ahí está el nudo: **garantizar un piso de costo es definir qué cuenta como trabajo.**
Es literalmente la regla 1 de §7.1 —*"el protocolo nunca decide qué trabajo es útil"*—
que existe para evitar convertirse en *"un banco central con un comité adentro"*.

> **El hallazgo estructural: la regla 1 de §7.1 y un subsidio significativo son
> incompatibles.** No es un problema de calibración de `k`: es que `k` no tiene autoridad
> sobre ninguna de las dos cantidades que deciden el resultado. Bitcoin puede pagar un
> subsidio del 100% porque el protocolo **sí** define el trabajo (hashear) y su costo es
> externo y físico. Este diseño renunció a eso a propósito, y el precio es el techo de
> §2.

Se buscaron formas de imponer el piso sin definir trabajo. Todas mueren en Sybil, porque
el protocolo no tiene noción de identidad: exigir que pagador y trabajador sean distintos
—identidades gratis—; topes por cuenta —se parte en cuentas—; fee superlineal por cuenta
—ídem—; bond o stake —el capital vuelve, el costo por ciclo es la tasa de interés por la
duración del escrow, ~0,001% con finalidad horaria.

---

## 7. Un corolario que el paper no tiene escrito

**El fee tiene que ser proporcional al valor del trabajo, no fijo por operación.**

Si el fee fuera una cantidad fija por liquidación, el autotratante infla `W` contra un
costo constante y el subsidio `k·W` supera cualquier fee para `W` suficientemente grande.
El techo desaparece y el autotrato es rentable para todo `k > 0`.

Todo este análisis supone fee *ad valorem*. El paper no lo dice en ningún lado —§6.1 solo
dice *"un fee chico cada vez que dos contratos interactúan"*, que suena a fee por
operación. Es una condición sobre Genesis, y como todas las de esa clase, es barata el
día uno.

---

## 8. Qué sobrevive

§12 anticipó este caso exacto: *"uno puede pasar y el otro no — y en ese caso lo que
sobrevive es la mitad correspondiente, no el conjunto."*

Con Test 1 pasado y Test 4 no:

- **Sobrevive el mecanismo:** sucesión determinista de parámetros internos con trigger
  desde el estado. Test 1 le encontró clientes reales y vivos, y ninguno de esos clientes
  necesita que la cadena tenga moneda propia — Ethereum ya tiene la suya.
- **No sobrevive la moneda tal como está especificada:** §7.1 (emisión indexada a trabajo
  pagado), §9 etapa 1 (farmear el subsidio) y, por dependencia, el argumento de §6.1 sobre
  quién paga a los nodos.

Eso es una decisión de alcance y es del autor, no del test. Las opciones que el resultado
deja abiertas, sin recomendar ninguna:

1. **Separar el mecanismo de la moneda.** Publicar la sucesión determinista como
   mecanismo aplicable a una cadena existente. Es donde Test 1 encontró la demanda.
2. **Cambiar la base de la emisión** a algo cuyo costo sea externo y físico, aceptando
   que eso reintroduce una definición de trabajo — o sea, revisar la regla 1 a sabiendas
   en vez de por accidente.
3. **Aceptar el subsidio débil** y buscar el bootstrap en otro lado que no sea §9 etapa 1.

---

## 9. Límites de la simulación

- **La métrica de significancia es una elección de modelado.** Medir contra el margen en
  vez de contra el ingreso mejora los números por el inverso del margen (§4). No cambia
  el orden de magnitud, pero corresponde decir que el número exacto depende de esa
  elección.
- **No se modela el precio del token.** Es la omisión más grande. Los autotratantes
  vendiendo la emisión hunden el precio, y eso sí acota el farmeo en la práctica — pero
  lo acota destruyendo el valor del token, que no es una defensa.
- **No se modela la quema de §8.4** sobre swaps. Sube el costo de *salir*, no el de
  farmear: el autotratante cicla sin tocar el AMM y solo paga esa quema cuando vende.
- **`ε = 0`** (costo de fabricar trabajo trivial). Es la hipótesis pesimista para el
  diseño, y está justificada porque el atacante escala `W` por liquidación. Si hubiera un
  tamaño máximo de liquidación, `ε` volvería a importar — y eso es, otra vez, un
  parámetro que define trabajo.
- **Entrada libre e instantánea.** En la realidad hay fricción y demoras, así que la
  captura del 99% es un límite, no un pronóstico del primer mes.
- **Un solo período de decisión.** No hay estrategia intertemporal ni acumulación.
