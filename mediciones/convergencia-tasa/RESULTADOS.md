# ¿Se borra el nivel inicial? — resultados

**Corrida el 28/8/2026.** Criterios en [`CRITERIOS.md`](CRITERIOS.md), escritos antes del código
y sin ablandar. Reproducir: `python convergencia.py`.

| criterio | veredicto |
|---|---|
| **C1** con demanda exógena `c = 1` | **aprobado** — `D` no se mueve en 500 pasos |
| **C2** `c` empírico = `c` analítico | **aprobado al tercer intento**, 0,00% de error. Las tres fallas fueron del instrumento |
| **C3** hay un lado inestable | **aprobado** — aparece exactamente en `e > 2k/target` |
| **C4** el piso no se cuenta como convergencia | **aprobado** — se detecta y se informa aparte |
| **C5** el entregable es un número | **aprobado** — `e_min(N)`, y su valor al `L_MAX` real |

---

## C1 · El operador no contrae solo, y esto es lo primero que hay que saber

Con `e = 0` —demanda que no responde al precio— dos estados iniciales separados por 10
siguen separados por **exactamente 10** después de 500 pasos.

La razón es de una línea. El exceso es un acumulador:

```
x_{n+1}^a − x_{n+1}^b = (x_n^a + q_n − target) − (x_n^b + q_n − target) = x_n^a − x_n^b
```

**Un integrador no es una contracción.** `c = 1`, y no aproximadamente.

> **O sea que la convergencia de EIP-1559/4844/7999 no está en la regla de actualización.**
> Está en que `q_n` no es exógeno: es demanda respondiendo al precio. La contracción la aporta
> **la curva de demanda**, no el operador. Que 7999 no especifique el nivel inicial no es porque
> la regla lo borre — es porque hay alguien del otro lado que reacciona.

## C2 · La tasa de contracción, y por qué el criterio falló tres veces

Linealizando en el punto fijo, con `p(x) = p_min·exp(x/k)` y demanda de elasticidad constante:

```
F′(x*) = 1 − e · target / k        →        c(e) = |1 − e · target / k|
```

Con la normalización de 7999 —el precio se mueve 12,5% por paso a uso pleno, o sea
`k = target/ln(1,125) = 8,4902`— eso da `c(e) = |1 − 0,117783·e|`. Medido:

| `e` | `c` empírico | `c` analítico | error |
|---:|---:|---:|---:|
| 0,5 | 0,941109 | 0,941108 | 0,00% |
| 1,0 | 0,882218 | 0,882217 | 0,00% |
| 2,0 | 0,764434 | 0,764434 | 0,00% |
| 4,0 | 0,528868 | 0,528868 | 0,00% |
| 8,0 | 0,057736 | 0,057736 | 0,00% |
| 12,0 | 0,413395 | 0,413396 | 0,00% |

**Las tres fallas previas valen más que la tabla**, porque las tres eran el instrumento
midiendo otra cosa:

1. **ventana fija de promediado** (pasos 20–120): con `e` grande `D` ya había colapsado a
   epsilon antes del paso 20, así que se promediaba ruido de punto flotante. Error 2,18%;
2. **promediar donde `D > 1e-9`, con `δ = 10`**: eso incorpora el **transitorio no lineal**. El
   precio es exponencial en el exceso, y `δ = 10` sobre `x* = 50` mueve el precio 3,2×. `c` es
   una propiedad **local** del punto fijo y hay que medirla con perturbación infinitesimal.
   Error 398%;
3. **`δ = 1e-4` con piso 1e-13**: con `x* ≈ 50` la precisión absoluta del double es ~7e-15, así
   que la cola del promedio estaba a diez veces del ruido. Error 2,55%.

> **El criterio nunca estuvo mal; la medición sí, tres veces.** Es la misma lección que ya
> aparece dos veces en la bitácora: *una medición tiene que declarar qué está midiendo, y
> verificarlo al terminar.* Acá lo que se declaraba era «la tasa asintótica» y lo que se medía
> era, sucesivamente, ruido de máquina, el transitorio, y ruido otra vez.

## C3 · Es una banda, no un umbral

`c < 1` exige `0 < e·target/k < 2`. El lado de arriba es sobrecorrección:

| `e` | `c` analítico | `max|D|` en la cola |
|---:|---:|---:|
| 14,0 | 0,649 | 0,0000 |
| 16,0 | 0,885 | 0,0000 |
| **16,98** | **1,000** | **0,0194** |
| 18,0 | 1,120 | 0,2432 |
| 22,0 | 1,591 | 0,6481 |

**El lazo contrae si y sólo si `0 < e < 2k/target = 16,98`.** Demasiada elasticidad tampoco
converge: el controlador persigue su propia corrección.

## C4 · El piso fusiona sin contraer, y se ve igual desde afuera

Con uso 0,2 contra target 1 y `e = 0`, dos trayectorias que arrancan en 5 y en 30 llegan a
`x = 0` y **se fusionan exactamente en el paso 38**. `D → 0` con `c = 1`.

Si el estudio no separara este caso, informaría convergencia donde no hay ninguna: lo único que
pasó es que las dos tocaron el `max(0, ·)`. **Es un criterio de la familia de los tres que ya
aparecieron vacíos en este proyecto** — mide algo que se *parece* al resultado buscado.

## C5 · El número, que es el entregable

Cuánta elasticidad hace falta para borrar una diferencia inicial de 10 hasta 0,01:

| horizonte `N` | `c` requerido | `e` mínima |
|---:|---:|---:|
| 10 | 0,501 | **4,24** |
| **25** | 0,759 | **2,05** ← `L_MAX_EPOCAS` del diseño |
| 50 | 0,871 | 1,10 |
| 100 | 0,933 | 0,57 |
| 500 | 0,986 | 0,12 |

---

## Veredicto: el problema no se cierra, se reubica — y eso estaba declarado de antemano

`CRITERIOS.md` decía que el problema **no** se cierra si `e_min` cae donde la respuesta depende
de conocer la demanda real. Ahí cayó.

**`L_MAX_EPOCAS = 25` es el parámetro que manda**, porque es la vida máxima comprable: dentro de
la vida de un depósito, el nivel inicial se borra sólo si la elasticidad de la demanda de
guardado supera **2,05**. Eso es una demanda muy elástica —1% más caro, 2% menos guardado—, y
para almacenamiento de estado no es una suposición barata.

**Lo que sí cambió, y es una mejora real:**

> El problema abierto pasa de *«Genesis tiene que conocer el precio»*, que la cadena no puede
> resolver ni en principio, a *«la demanda de guardado tiene que tener elasticidad mayor a 2,05
> en 25 épocas»*, **que es una pregunta empírica sobre un mercado**.

Una frontera que no se puede cruzar se convirtió en una medición que alguien puede hacer. Es la
misma jugada que cerró el techo dos veces, con una diferencia importante: **el techo tenía sus
dos lados contables por la cadena y éste no.** El número no lo puede producir el protocolo.

## Los dos límites de este estudio, declarados

- **La forma de la demanda es un supuesto, no un dato.** Elasticidad constante es la forma más
  simple; otra forma da otro `e_min`. El [ROADMAP §4](../../docs/roadmap.md) ya tiene la cicatriz
  de esto: la primera ley de control no la tumbó un ataque, la tumbó **corregir el modelo con el
  que se la había probado**.
- **Es el operador de 4844/7999, no la tasa de permanencia.** Se mide el lazo que este diseño
  tomaría prestado, con la normalización de 7999. Trasladarlo exige que la tasa se escriba con
  esa misma forma, y eso todavía no está decidido.
