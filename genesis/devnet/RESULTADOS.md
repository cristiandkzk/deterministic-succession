# Fase 6 — resultados

**Corrida el 21/8/2026.** Los criterios están en `CRITERIOS.md`, escritos antes de la primera
línea del devnet.

> **Desechable por declaración.** Un devnet con tokens gratis contesta preguntas de software, no
> de economía. **Fecha de reset: el día que se elija la regla de la tasa de permanencia** (§10.3),
> porque ése es el número que cambia el espacio de parámetros que Genesis tiene que anticipar.

| criterio | veredicto |
|---|---|
| **B1** la conmutación bajo carga no rompe el estado | **aprobado** |
| **B2** el ciclo de desalojo a escala y a través de una conmutación | **aprobado** |
| **B3** un depósito vale lo mismo después de conmutar | **REPROBADO**, y corregido |
| **B4** desalojo y cola comparten presupuesto | **medido**: 3,01% del bloque |
| **B5** la conmutación no desaloja por sorpresa | **aprobado** |

**B3 es el resultado de la fase, y es exactamente lo que la fase existe para encontrar:** un
acople que ninguna prueba de módulo podía ver, porque hace falta que una conmutación pase
mientras hay depósitos vivos.

---

## B3 · El depósito se compraba en una unidad que el ruleset podía reinterpretar

El depósito se llevaba en **byte-épocas**. La época se cuenta en **bloques**. Y
`tiempo_bloque_ms` es un **parámetro interno**, o sea que una transición lo puede mover.

Medido, con una entrada que compró diez épocas:

```
bloque de  6.000 ms  ->  240 horas de guardado real
bloque de 12.000 ms  ->  480 horas, con el MISMO depósito
```

**El mismo depósito compraba el doble de guardado**, sin que nadie lo tocara.

### Lo incómodo es que ninguna invariante lo veía

**I3 se cumplía.** El estado cruzó íntegro: los bytes del depósito son exactamente los mismos
antes y después, y el conmutador lo verifica por huella y por identidad de objeto. Lo que cambió
no fue el estado sino **lo que ese estado vale** — y eso no lo mira ninguna de las cinco.

Es la misma clase de cosa que el techo de páginas (C18): el mecanismo hacía algo que el diseño
prohíbe, y lo hacía en silencio porque ninguna cuenta lo señalaba.

### La corrección, que es la de siempre en este diseño

**Denominar el depósito en byte-segundos declarados**, convirtiendo con `tiempo_bloque_ms`.

Y el punto fino es por qué eso no viola I2: **`tiempo_bloque_ms` no es una lectura de reloj, es
un parámetro que el ruleset declara.** La cadena no mide el tiempo — usa el número que ella misma
fijó, igual que usa `R_declarado` para el techo. Es el mismo movimiento por tercera vez: **usar
la cantidad declarada en vez de la derivada.**

Con eso:

| | antes | después |
|---|---|---|
| guardado real que compró un depósito | cambia con el tiempo de bloque | **no cambia** |
| cuenta regresiva en épocas | fija | **se ajusta**, porque las épocas duran otra cosa |
| `L_max` | 25 épocas | 25 días de tiempo real |

Que la cuenta regresiva en épocas **sí** cambie es correcto y hace falta: si los bloques tardan
el doble, la misma vida real son la mitad de épocas. Lo que no puede cambiar es la vida real.

`L_max` se movió por lo mismo: si estuviera en épocas, cambiar el tiempo de bloque cambiaría
cuánto se puede prepagar — y el tope existe justamente para que no se pueda apostar contra la
tasa.

---

## B4 · Lo que el desalojo le saca a la cola

La Fase 3 midió la cola sin permanencia corriendo; la Fase 5 midió la permanencia sin cola. **En
un nodo real las dos salen del mismo presupuesto.**

Peor caso: el estado lleno y nadie recarga, así que todo vence dentro de `L_max` y se desaloja el
conjunto entero cada 25 épocas.

| | |
|---|---:|
| desalojos por bloque en régimen | **99** |
| pasos por bloque | 12.661.007 |
| presupuesto del bloque | 420.000.000 |
| **fracción del bloque** | **3,01%** |

**Queda el 97%** para todo lo demás, contra el 10% de headroom que la Fase 3 midió que necesita
la cola para drenar con once nodos. No ata.

> El número sale de la medición de la Fase 5 —4.898 pasos por compresión SHA-256, 26 hashes por
> actualización del árbol— así que **no es una estimación**: se mueve solo si se mueve aquélla.

---

## B1, B2 y B5 · Lo que aguantó

- **el estado cruza con carga corriendo** y el conmutador sigue verificando I3 por huella e
  identidad de objeto;
- **ninguna entrada cambia de estado por el solo hecho de conmutar** — ni se desaloja ni se
  revive porque cambió el ruleset. Lo único que desaloja es que se agote el depósito;
- **el ciclo cierra para las 500**: ninguna se pierde, ninguna se desaloja antes de agotarse, y
  el acumulador sigue por debajo del kilobyte;
- **se revive después de la conmutación**, con la prueba contra el acumulador, y la doble
  reactivación falla contra el conjunto activo;
- **la cuenta regresiva publicada antes de conmutar se cumple después**, para todas.

---

## Y el arnés de mutaciones encontró otro criterio que no probaba nada

Se podía **recorrer el conjunto activo por orden de hash** al desalojar, y ningún test se caía.

Eso es una bifurcación: **dos nodos meterían los desalojados en el acumulador en órdenes
distintos y sus raíces no coincidirían.** Y es de las que se esconden bien, porque un recorrido
de diccionario por hash **parece determinístico dentro de un proceso** y no lo es entre dos.

Es la tercera vez en dos días que el arnés encuentra un criterio vacío —antes fueron el chequeo
de flotantes con el escape mal puesto (C17.7) y la revalidación de la prueba de reactivación
(C19.8)—. **Los tres eran criterios que existían, tenían nombre y no probaban nada.**

---

## Estado

**246 criterios en Python, 20 en Rust, 31 mutaciones, todas cazadas.**

## Cómo reproducir

```
cd genesis
python verificar.py fase6      # los criterios de esta fase
python verificar.py            # los 246
python herramientas/mutar.py   # 31 mutaciones
```
