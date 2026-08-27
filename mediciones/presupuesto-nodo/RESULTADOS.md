# El presupuesto del nodo, y qué margen pide el lazo

**Corrido el 18/8/2026.** Reproducir con `python medicion.py`. Sin datos externos.

**La pregunta.** `θ*` se iba a fijar sobre tres supuestos sumados a ojo —128 B de
entrada + 32 B de árbol + 16 B de índice = 176 B— y sobre una simulación de
estabilidad. Se pidió medir antes de fijarlo.

**La respuesta corta: bien pedido.** Dos de los tres supuestos de bytes estaban
mal, y la simulación de C7.13 estaba mal de una forma que invalida su conclusión.
**La ley de control, corregida, no converge** — y la causa no es de sintonía sino
económica.

---

## Supuestos, todos declarados

| supuesto | valor | por qué |
|---|---|---|
| hash | 32 B | direcciones y punteros a metadata son hashes: con firmas post-cuánticas la clave pública no se guarda |
| hash en el teléfono | 100 MB/s | conservador para la capa liviana |
| presupuesto de firma | ~640 tx/s | §6.1, medido en Test 2 |
| presupuesto de disco | 2 / 4 / 8 GB | barrido |

---

## A · El layout: hay dos clases de entrada, no una

| OBJETO (el activo) | B | | SALDO (un tenedor) | B |
|---|---|---|---|---|
| dueño (hash de clave pública) | 32 | | dueño | 32 |
| identificador del activo | 8 | | identificador del activo | 8 |
| puntero a metadata (hash) | 32 | | monto | 8 |
| depósito de permanencia | 8 | | depósito de permanencia | 8 |
| bloque de creación | 8 | | bloque de creación | 8 |
| supply | 8 | | | |
| divisibilidad + flags | 4 | | | |
| **suma → alineado** | **100 → 112** | | **suma → alineado** | **64 → 64** |

Los 128 B eran correctos para el objeto. **Para un saldo sobran: son 64 B**, y esa
distinción no estaba hecha en ninguna medición anterior.

## B · El árbol: el overhead no es un dato, es una perilla

Se suponía guardar todos los nodos internos (32 B por entrada). No hace falta: se
guardan los niveles por encima de un corte `d` y se recomputa el subárbol de `2^d`
hojas. **El tope que muerde es actualizar, no probar** — actualizar pasa en cada
transacción.

| corte `d` | B por entrada | hash por operación | % del presupuesto de hash |
|---|---|---|---|
| 1 (guardar todo) | 32,0 | 0,4 KB | 0,2% |
| **6** | **1,0** | 12 KB | **7,9%** |
| 9 | 0,125 | 96 KB | 62,9% |
| 12 | 0,016 | 768 KB | 503% |

> **El árbol no cuesta 32 B por entrada: cuesta ~1 B con el corte en `d=6`**, y el
> precio son 8 puntos del presupuesto de hash del nodo. Es una decisión de
> implementación que hay que tomar, no un costo que se sufre.

> **Nota del 22/8/2026 — la tabla de bytes se reprodujo exacta, y la última frase no.**
> Construido el árbol (`genesis/estado/arbol.py`), los bytes por entrada dan
> 32,0 / 1,0 / 0,125 / 0,016 igual que acá. Lo que no se sostiene es *"decisión de
> implementación"*: **el piso de permanencia de §8.5 se deriva del costo de actualizar
> el árbol, y el piso se quema**, así que dos nodos con `d` distinto no coincidirían
> sobre cuánto se quemó al crear una entrada. `d` pasó a ser constante de Genesis
> (`CORTE_ARBOL`).
>
> Y aparece una tercera moneda que esta medición no miraba: **con `d=6` el piso es el
> 77% del depósito máximo, y con `d=7` lo supera.** El margen es más fino de lo que se
> veía mirando sólo disco y hash. Desarrollo en `genesis/estado/RESULTADOS-ARBOL.md`.

## C · El índice de desalojo

Heap binario de `(vencimiento, id)`: 16 B por entrada. **Baldes por época de
vencimiento: 8 B** —el vencimiento queda implícito en el balde, sólo se guarda el
id— y además el desalojo pasa a ser O(k) sobre los k que vencen.

## D · La capacidad real

| | entrada | árbol | índice | total |
|---|---|---|---|---|
| objeto activo | 112 | 1 | 8 | **121 B** |
| saldo de tenedor | 64 | 1 | 8 | **73 B** |

**31% menos que los 176 B supuestos.**

| presupuesto | objetos | saldos | supuesto viejo |
|---|---|---|---|
| 2 GB | 17,7 M | 29,4 M | 12,2 M |
| **4 GB** | **35,5 M** | **58,8 M** | 24,4 M |
| 8 GB | 71,0 M | 117,7 M | 48,8 M |

Y el umbral de §10.1 —creaciones por día que agotan el presupuesto en diez años—
vuelve a subir a **~9.700/día**, muy cerca del 9.200 original.

---

## E · La simulación corregida tumba el resultado de C7.13

La simulación de C7.13 recalculaba la vida de **todas** las cohortes en cada época:
al subir el precio, acortaba retroactivamente plazos ya pagados. Eso no puede
pasar — el que pagó tiene su plazo. Corregido, cada cohorte vence cuando compró
vencer. Shock ×3 sostenido, 4.000 épocas, vida de referencia 200 épocas:

| k | ε | pico | cola (min–max) | `r0` final |
|---|---|---|---|---|
| 0,05 | 1,0 | 1,98× | 0,00 – 1,97 | 3.338 |
| 0,125 | 1,0 | 2,04× | 1,19 – 1,97 | 9e19 |
| 0,25 | 1,0 | 2,08× | 0,00 – 2,08 | 2e17 |

> **No converge con ninguna ganancia.** La ocupación sigue oscilando entre casi
> cero y más del doble del objetivo después de 4.000 épocas, y `r0` se va a valores
> sin sentido. El *"absorbe un shock ×3 sin oscilar"* de C7.13 era un artefacto del
> modelo.

## F · Por qué no cierra, y no es culpa del controlador

Medido sobre esa misma corrida: **`r0` bajó hasta 0,22 y la vida máxima comprada
llegó a 897 épocas** contra 200 de referencia.

> Cuando el lazo abarata para llenar, la vida que se compra por el mismo
> presupuesto **se alarga** — y esos slots quedan tomados por siglos a precio de
> saldo. El lazo después no los recupera, porque están pagados y desalojar antes
> sería confiscación.

**No es un problema de sintonía: es arbitraje intertemporal.** Prepago con precio
flotante equivale a *comprar largo cuando está barato*. Y explica de paso el tiempo
muerto: mover el precio recién se nota cuando vencen las cohortes, y un controlador
proporcional con cientos de épocas de tiempo muerto oscila por construcción.

## G · El arreglo, y el techo que deja para `θ*`

Si la vida comprable **de una vez** está topeada en `L_max` —y para seguir vivo se
recarga al precio de entonces— el arbitraje desaparece y el tiempo muerto queda
acotado por `L_max`:

| `L_max` | ε | pico | cola (min–max) | ¿cierra? |
|---|---|---|---|---|
| 10 | 1,0 | 1,43× | 1,00 – 1,00 | **sí** |
| 25 | 0,5 | 1,25× | 1,00 – 1,00 | **sí** |
| 25 | 1,0 | 1,48× | 1,00 – 1,00 | **sí** |
| 50 | 1,0 | 1,88× | 0,17 – 1,88 | no |
| 100 | 1,0 | 2,04× | 0,00 – 2,04 | no |

Con `L_max` de 25 épocas o menos el lazo **aterriza exacto en el objetivo**; con 50
es marginal y con 100 vuelve a romperse. El umbral está en el orden de **un octavo
de la vida de referencia**.

> **El tope a la vida comprable deja de ser una recomendación económica y pasa a
> ser condición de estabilidad del mecanismo.**

Y recién con el lazo cerrando, `θ*` tiene un techo derivado. El peor pico entre las
configuraciones que cierran es **1,48×**:

| θ\* | pico de ocupación | ¿entra en el presupuesto? |
|---|---|---|
| 25% | 37% | sí |
| **50%** | **74%** | **sí** |
| 65% | 96% | sí, al filo |
| 75% | 111% | **no** |
| 90% | 134% | **no** |

> **`θ* ≤ 67%`**, y eso es un techo, no una recomendación. El margen entre θ\* y
> 100% no es holgura: es donde vive el pico del primer shock sostenido.

---

## Veredicto

1. **Los 176 B estaban mal por dos lados.** El árbol es ~1 B con `d=6`, no 32; el
   índice es 8 B con baldes, no 16. El layout de 128 B era correcto para el objeto,
   pero **un saldo son 64 B**. Capacidad real con 4 GB: **35,5 M objetos**.
2. **La ley de control de C7.13 no cierra**, y su resultado anterior era un
   artefacto de simulación.
3. **La causa es económica:** prepago con precio flotante es arbitraje
   intertemporal — se compran vidas de 897 épocas cuando el precio cae, y esos
   slots no se recuperan sin confiscar.
4. **El arreglo es `L_max`**, un tope a la vida comprable de una vez. Con 25 épocas
   el lazo aterriza exacto.
5. **`θ*` tiene techo derivado en ~67%**, y 50% deja margen real contra el error de
   estimación que esta misma medición acaba de demostrar que es posible.
