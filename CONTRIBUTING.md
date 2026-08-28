# Cómo debatir esto

*[English version](CONTRIBUTING.en.md)*

Este repositorio no busca contribuciones de código. **Busca que alguien rompa el diseño**, o
que demuestre que una parte no sirve para lo que dice servir.

Todo lo que el diseño sobrevivió hasta ahora lo corrió quien lo escribió, que es exactamente
el tipo de evidencia que no vale. Vos sos la parte que falta.

---

## Lo que hace útil a un ataque

**Un ataque útil dice contra qué invariante va, y qué observación lo confirmaría o lo
mataría.**

Las [cinco invariantes](docs/paper.md#4-invariantes-de-diseño) son el marco duro:

> **Un ataque que las respeta es un ataque contra el diseño. Uno que las viola es otro
> diseño.**

Las dos cosas sirven, pero no son lo mismo y conviene decir cuál estás haciendo. *"Esto se
arreglaría con un voto de tenedores"* es correcto y es otro diseño: I2 existe para prohibirlo,
y el proyecto entero es la apuesta de que se puede sin eso. *"Esto se rompe aunque respetes
las cinco"* es lo que más vale.

**Y decí qué lo mataría.** El diseño tiene la costumbre de declarar, junto a cada frontera,
qué medición la revoca. Un ataque con esa forma se puede cerrar; uno sin ella se discute para
siempre.

---

## Antes de abrir algo

**Mirá el [índice de lo que ya murió](docs/bitacora.md#índice-lo-que-ya-murió).** Hay
propuestas que ya tienen una refutación escrita. No están prohibidas — pero una propuesta que
no contesta la refutación existente no avanza, y vas a perder tu tiempo y el mío.

Tres reflejos que aparecieron cuatro veces cada uno y las cuatro fallaron por la misma razón:

- **un bono, un lockup, o un descuento por volumen.** *El protocolo no tiene noción de
  identidad, así que toda palanca que mueva la mueve para todos.* Antes de agregar capital
  como palanca, buscá el castigo que el mecanismo ya produce — cuatro veces ya estaba adentro;
- **"que el bueno pague menos".** Es una propuesta de introducir identidad;
- **"que se emita cuando hay demanda real".** También es una propuesta de introducir
  identidad, y falla por cuatro razones distintas a la vez.

**Y mirá si tu pregunta ya está contestada en el paper.** El [resumen](docs/resumen.md) tiene
~25 minutos de lectura y comprime el diseño a un tercio; el [paper](docs/paper.md) es la
fuente de verdad. Si algo está contestado en el paper y no se ve en el resumen, **eso es un
defecto del resumen y quiero saberlo** — abrilo como pregunta.

---

## Dónde va cada cosa

| | |
|---|---|
| **[Ataque](../../issues/new?template=ataque.yml)** | encontraste algo que se rompe, o una hipótesis que no se sostiene |
| **[Pregunta](../../issues/new?template=pregunta.yml)** | algo no se entiende, falta, o el resumen y el paper se contradicen |
| **[Discussions](../../discussions)** | ideas abiertas, encuadres alternativos, y todo lo que no cierra como issue |
| **Medición** | corriste el benchmark en una máquina nueva — abrilo como ataque contra el [problema abierto 1](docs/problemas-abiertos.md#1--cuál-hardware-es-el-peor-caso), con la salida cruda adjunta |

---

## Si venís a correr una medición

**Es la contribución de mayor valor que tiene el proyecto ahora mismo**, porque hay un
problema abierto que no se cierra pensando: cuál hardware es el peor caso. El paquete es
autocontenido y el procedimiento está en
[`mediciones/test2-interprete/RESULTADOS.md`](mediciones/test2-interprete/RESULTADOS.md).

Dos reglas que salieron de errores propios y que le pido a cualquier medición nueva:

- **informá la peor de varias corridas, no la media.** El escritorio medido dio entre 44 y
  79 M pasos/s según cuándo se corriera, contra 1,6% de variación en el teléfono;
- **decí qué máquina es**, con el modelo de CPU, la memoria y qué más estaba corriendo.

---

## Cómo respondo

- **Un ataque que da en el blanco se escribe al paper con su nombre y su fecha**, como se
  escribieron todos los anteriores. La [bitácora](docs/bitacora.md) es el registro de eso, y
  ahí están también los errores propios, con el mismo detalle.
- **Un ataque que no da en el blanco recibe la refutación por escrito**, no un "ya está
  contestado". Si la refutación no existía, la escribo.
- **Si el ataque muestra que una sección promete más de lo que cumple, la sección se corrige.**
  Ya pasó: una invariante estaba mal escrita y fallaba en las dos direcciones; una sección se
  contradecía entre dos de sus propias frases; y un techo prometía un presupuesto que no
  cumplía por 23×.

**El idioma no importa.** El material largo está en español y la portada en los dos idiomas;
escribí en el que te salga.

---

## Licencia de lo que aportes

Lo que abras acá queda bajo las mismas licencias del repositorio: [MIT](LICENSE) para código,
[CC BY 4.0](LICENSE-DOCS) para texto. Si citás el trabajo en otro lado, decí de dónde salió.
