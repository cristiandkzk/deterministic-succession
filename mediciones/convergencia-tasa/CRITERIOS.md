# Criterios — ¿el nivel inicial se borra?

**Escritos el 28/8/2026, antes de la primera línea de código.** No se ablandan después;
agregar criterios está permitido.

## La pregunta

El [problema abierto 2](../../docs/problemas-abiertos.md#2--la-regla-de-la-tasa-de-permanencia-y-el-nivel-del-que-parte)
son dos mitades: la regla que mueve la tasa, y **el nivel del que parte**. Leer EIP-7999 dejó la
hipótesis de que la segunda mitad no existe:

> Si el lazo converge desde cualquier nivel inicial, `x₀` no es necesario y el problema abierto
> pasa a ser uno solo.

La formulación correcta no es *"¿cuál es el nivel inicial?"* sino: **¿el operador de transición
tiene un atractor que borra a `x₀`?** Formalmente, con `Dₙ = max_{a,b} |Fⁿ(a) − Fⁿ(b)|`,
buscamos si existe `c < 1` con `Dₙ₊₁ ≤ c·Dₙ`.

## El operador que se mide

El de EIP-4844 que EIP-7999 generaliza — el que este diseño tomaría prestado:

```
x_{n+1} = max(0, x_n + q_n − target)          # exceso: acumulador
p_n     = p_min · exp(x_n / k)                # precio: exponencial del exceso
```

y la demanda con elasticidad constante `e`, que es **el supuesto del estudio y no un hecho
medido**:

```
q_n = min(limit, q_ref · (p_n / p_ref)^(−e))
```

## Criterios

**C1 · El caso exógeno tiene que dar `c = 1`.** Con `e = 0` —demanda que no responde al
precio— la diferencia entre dos estados iniciales **no** debe decaer. **Aprobado** si
`Dₙ = D₀` para todo `n` dentro del error de máquina. **Reprobado** si decae: querría decir que
el operador contrae solo, y entonces todo el análisis de abajo está mal planteado.

> Este criterio existe para que el estudio pueda fallar. Si el test no puede producir un `c = 1`,
> no está midiendo contracción: está midiendo otra cosa.

**C2 · Con demanda elástica, `c` medido tiene que coincidir con el analítico.** La linealización
en el punto fijo da `F′(x*) = 1 − e·target/k`, o sea `c = |1 − e·target/k|`. **Aprobado** si el
`c` empírico coincide dentro del 1%. **Reprobado** si no: significaría que la dinámica tiene algo
que el análisis no ve, y hay que encontrarlo antes de concluir nada.

**C3 · Tiene que haber un lado inestable.** Si `e·target/k > 2`, el lazo sobrecorrige y oscila
sin converger. **Aprobado** si se encuentra ese régimen y se reporta dónde empieza. **Reprobado**
si no aparece — sería evidencia de que el modelo está amortiguado por algo no declarado.

**C4 · El piso `max(0, ·)` no debe contarse como convergencia.** Dos trayectorias que tocan
fondo se fusionan **exactamente**, y eso se vería como `D → 0` sin que haya contracción alguna.
**Aprobado** si el estudio detecta e informa por separado las corridas donde la fusión ocurre por
el piso. **Reprobado** si las mezcla con las que contraen de verdad.

> Es el criterio que más importa, y es de la familia de los tres criterios vacíos que ya
> aparecieron en este proyecto: mide algo que *parece* el resultado buscado y no lo es.

**C5 · El entregable es un número, no un sí/no.** El estudio tiene que devolver **cuánta
elasticidad hace falta** para que `x₀` se borre a una tolerancia dada en un horizonte dado.
**Aprobado** si sale una cota `e_min(N, tol)` instanciable. **Reprobado** si la conclusión es
"converge" o "no converge" sin cuantificar.

## Qué cerraría el problema abierto, y qué no

- **Lo cierra** sólo si la elasticidad requerida es lo bastante baja como para ser plausible sin
  medirla — y aun así queda declarado como supuesto, no como hecho.
- **No lo cierra** si `e_min` cae en un rango donde la respuesta depende de conocer la demanda
  real de guardado: ahí el problema no se resolvió, **se reubicó** de *"hay que saber el precio"*
  a *"hay que saber la elasticidad"*, y eso hay que escribirlo tal cual.
