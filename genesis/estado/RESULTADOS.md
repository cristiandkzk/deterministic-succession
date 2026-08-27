# Fase 5 — resultados

**Corrida el 21/8/2026.** Los criterios están en `CRITERIOS.md`, escritos antes de la primera
línea de mecanismo y sin tocar después.

| criterio | veredicto |
|---|---|
| **A1** el ciclo cierra completo | **aprobado**, y el objeto vuelve byte a byte |
| **A2** el acumulador es de cientos de bytes totales | **aprobado**, 232 bytes con un millón |
| **A3** cuánto cuesta mantener la prueba al día | **medido**: una vez por desalojo ajeno |
| **A4** doble reactivación sin nulificadores | **aprobado** |
| **A5** nadie compra permanencia perpetua | **aprobado** |
| **A6** la cuenta regresiva es pública | **aprobado** |
| **A7** desalojar no es confiscar | **aprobado** |
| **A8** el piso: ¿perilla o cuenta? | **REPROBADO contra el paper, por 9×** — y cerrado |
| **A9** la tasa: ¿por qué no se cierra igual? | **aprobado por la segunda vía** |

**A8 es el resultado de la fase**, y reprueba contra §8.5 y no contra el código.

---

## A8 · El piso es una cuenta, y la cuenta no da lo que el paper dice

§8.5 declara que el piso *"no es una perilla: es el costo fijo del ciclo crear + desalojar"* y
afirma un valor: **unas dieciséis horas de guardado, o sea el 0,2% de un año**. Nunca se escribió
la cuenta. Escrita, no da eso.

### La cuenta

Iguala dos fracciones del mismo nodo, y **las dos ya las declara Genesis**:

- **del cómputo** — el ciclo consume `C` pasos y el nodo dedica `f*` de su ritmo a verificar, así
  que gasta `C / (f* × R × duración_de_época)` del cómputo de una época;
- **del disco** — guardar la entrada una época ocupa `tamaño / presupuesto_de_estado`.

El piso es el cociente: **cuántas épocas de disco valen lo que el ciclo gasta de cómputo.**

> **No hay un número nuevo, pero sí un supuesto:** que las dos fracciones están igualmente
> ajustadas, o sea que el nodo satura las dos. Es lo que §6.1 construye a propósito al fijar
> ambas contra lo que tiene un teléfono. Si una sobrara, la cuenta se corre hacia la otra.

### Lo que da

| qué se mete en el ciclo | pasos | piso |
|---|---:|---:|
| firma + dos actualizaciones (como decía el paper) | 3.594.060 | **91,4 épocas** |
| **sólo las dos actualizaciones** | **254.696** | **6,03 épocas** |

§8.5 afirmaba **0,67 épocas**. La cuenta da **9× más**, y con la firma adentro daba 137×.

### Por qué la firma no va en el ciclo

**La firma ya la paga el fee ad valorem de §6.1**, como en cualquier transacción: cobrarla otra
vez en el piso es cobrarla dos veces. Y el error no era cosmético — con la firma adentro el piso
quedaba en **3,7× el depósito máximo** que `L_max` permite, o sea que casi todo el costo de una
entrada se pagaría al crearla. Es exactamente el cargo a la creación que §8.5 descarta dos
párrafos antes, y por el motivo que ella misma explica: *no reduce la creación, reduce la
registración de la creación.*

Sacada, el piso queda en el **24% del depósito máximo** y la estructura de §8.5 se sostiene.

### Y el insumo que faltaba, medido

El término dominante pasó a ser cuántos pasos cuesta un SHA-256, y estaba **estimado en 10.000**.

> **Ese estimado se había declarado inofensivo por una razón circular.** La primera versión de
> `permanencia.py` decía que no importaba *"porque la verificación de firma lo domina"*. Valía
> sólo mientras la firma estuviera adentro del ciclo — y sacarla es justamente la corrección.
> **El término descartado por chico pasó a ser el único que quedaba.**

Se midió igual que `steps_per_verify`: un SHA-256 escrito a mano, compilado a RV32IM
(`predicado/vm/guest-sha/`) y corrido en la máquina de §6.6, restando dos tandas para que el
marco de la llamada no entre.

| | |
|---|---:|
| **pasos por compresión SHA-256** | **4.898** |
| hashes por actualización del árbol | 26 |
| pasos del ciclo crear + desalojar | 254.696 |
| eso, contra una verificación de firma | 8% |

El estimado estaba **2× arriba**, o sea en la dirección conservadora. El conteo es exacto e
independiente de la arquitectura, y queda fijado como regresión en
`predicado/vm/tests/criterios.rs` por la misma razón que `steps_per_verify`: **de ese número
cuelga el piso**, y si la semántica de la máquina se moviera sin que nadie lo note, el piso
quedaría mal calibrado y no habría forma de saberlo.

> **De paso, el guest de SHA-256 es la segunda carga independiente que pasa por la admisión.**
> C2 y C4 se habían probado contra el guest de Test 2, que lo produjo otro repo; éste lo produce
> el nuestro. Un criterio verificado contra un solo binario prueba menos de lo que parece — y las
> dos correcciones que C2 necesitó salieron justamente de chocar contra un binario real.

---

## A9 · Por qué la tasa no se cierra con la misma jugada

La Fase 4 cerró **dos veces** el mismo techo con la misma jugada —*el número no se elige, se
deriva*— y de ahí salió la sospecha de C18.5. Corrida contra esta fase, separa los dos números
limpiamente, y **la razón es verificable y no una sensación**:

> **El techo de pasos se pudo cerrar porque sus dos lados eran físicos**: pasos de un lado,
> segundos del otro, y la cadena puede contar los dos sin preguntarle nada a nadie. **La tasa
> tiene un lado físico —bytes × épocas— y uno monetario —cuántos tokens vale eso—, y ninguna
> cuenta cruza esos dos lados sin leer un precio.** Leer un precio es exactamente lo que I2
> prohíbe, y es el mismo muro que §7.6 declara para el pool.

La prueba de que el argumento no es retórica es que **se ve en los tipos**: todo lo que
`permanencia.py` calcula está en byte-épocas o en épocas, y en ningún lado aparece una unidad
monetaria. El día que aparezca, aparece con un oráculo al lado.

### Y de ahí sale una decisión de forma que no estaba en el paper

**El piso se denomina en épocas de guardado, no en tokens.** Si estuviera en tokens sería un
**segundo** parámetro libre al lado de la tasa, y habría que elegir dos precios en vez de uno. En
épocas de guardado hereda la tasa que rija, sea cual sea, y deja de ser una decisión aparte.

Eso reduce el problema abierto de §10.3 a un solo número: **la tasa, y sólo su nivel.**

---

## A2 y A3 · El acumulador, y lo que cuesta el archivo

| desalojos | picos | bytes en el estado |
|---:|---:|---:|
| 10 | 2 | 72 |
| 10.000 | 5 | 168 |
| 1.000.000 | 7 | **232** |

Crece con el logaritmo. El contraste que lo justifica: **una lápida de 32 bytes por objeto serían
1 GB por nodo para siempre**, un cuarto del presupuesto de §10.1.

Y A3, sin umbral que pasar porque §10.2 no promete ninguno: **la prueba se vence en cada desalojo
ajeno, sin excepción.** Con la capacidad inicial —15 tx por bloque, 14.400 bloques por época— el
techo son **216.000 reconstrucciones por época**. Alcanza para un agente permanentemente online,
que es el público declarado, y no alcanza para una persona.

> **Este criterio existía y no probaba nada, y lo encontró el arnés de mutaciones.** Se podía
> borrar la revalidación contra los picos vigentes y ningún test se caía. Una prueba que no
> prueba es peor que no tenerla, porque además da confianza.

---

## Dos cosas que se arreglaron por ser lentas

1. **`desalojar` construía la prueba en cada inserción** — O(n) por objeto. Un millón de
   desalojos tardaban 32 segundos y volvieron incorrible el arnés de mutaciones. Pero el
   problema no era de rendimiento: **un nodo desaloja y no prueba nada**; construir la prueba es
   trabajo de quien archiva (§10.2). Sacado, el mismo millón tarda 2,9 s.
2. **El arnés de mutaciones deja archivos mutados si se lo corta.** Pasó, y la suite empezó a
   fallar por una razón que no era la real. Un `finally` no alcanza cuando el proceso se mata
   desde afuera, así que ahora se puede preguntar: `python herramientas/mutar.py --limpio`.

---

## Estado

**230 criterios, 20 en Rust y 28 mutaciones, todas cazadas.** Lo que queda de la fase, y es lo declarado en
el roadmap: la ley de control de la tasa no está elegida y no hay con qué calibrarla.

## Cómo reproducir

```
cd genesis
python verificar.py fase5           # los criterios de esta fase
python verificar.py                 # los 228
python herramientas/mutar.py        # 28 mutaciones
python herramientas/mutar.py --limpio   # ¿quedó algo mutado de una corrida cortada?
```
