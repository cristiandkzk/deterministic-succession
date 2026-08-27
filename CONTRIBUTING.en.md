# How to debate this

*[Versión en español](CONTRIBUTING.md)*

This repository is not looking for code contributions. **It is looking for someone to break the
design**, or to show that a part of it doesn't do what it claims to do.

Everything the design has survived so far was run by the person who wrote it, which is exactly the
kind of evidence that doesn't count. You are the missing part.

---

## What makes an attack useful

**A useful attack says which invariant it targets, and what observation would confirm or kill
it.**

The [five invariants](README.en.md#the-five-invariants) are the hard frame:

> **An attack that respects them is an attack on the design. One that violates them is a different
> design.**

Both are useful, but they are not the same thing and it helps to say which one you're doing.
*"This would be fixed with a holder vote"* is correct and is a different design: I2 exists to
forbid it, and the entire project is the bet that it can be done without. *"This breaks even if
you respect all five"* is what's worth the most.

**And say what would kill it.** The design has a habit of declaring, alongside each boundary, what
measurement would revoke it. An attack with that shape can be closed; one without it gets argued
forever.

---

## Before you open anything

**Check the [index of what already died](docs/build-log.en.md#index-what-already-died).** Some
proposals already have a written refutation. They aren't forbidden — but a proposal that doesn't
answer the existing refutation doesn't advance, and you'll waste your time and mine.

Three reflexes that each appeared four times and failed all four for the same reason:

- **a bond, a lockup, or a volume discount.** *The protocol has no notion of identity, so every
  lever it moves it moves for everyone.* Before adding capital as a lever, look for the penalty the
  mechanism already produces — four times it was already there;
- **"make the good actor pay less."** That is a proposal to introduce identity;
- **"issue when there is real demand."** Also a proposal to introduce identity, and it fails for
  four distinct reasons at once.

**And check whether your question is already answered in the paper.** The
[summary](docs/resumen.md) is ~25 minutes and compresses the design to a third; the
[paper](docs/paper.md) is the source of truth. *Both are in Spanish.* If something is answered in
the paper and invisible in the summary, **that is a defect in the summary and I want to know** —
open it as a question.

---

## Where things go

| | |
|---|---|
| **[Attack](../../issues/new?template=ataque.yml)** | you found something that breaks, or a hypothesis that doesn't hold |
| **[Question](../../issues/new?template=pregunta.yml)** | something is unclear, missing, or the summary and the paper contradict each other |
| **[Discussions](../../discussions)** | open-ended ideas, alternative framings, anything that doesn't close as an issue |
| **A measurement** | you ran the benchmark on a new machine — open it as an attack on [open problem 1](docs/open-problems.en.md#1--which-hardware-is-the-worst-case), with the raw output attached |

---

## If you're here to run a measurement

**It is the highest-value contribution the project has right now**, because there is an open
problem that doesn't close by thinking: which hardware is the worst case. The package is
self-contained and the procedure is in
[`mediciones/test2-interprete/RESULTADOS.md`](mediciones/test2-interprete/RESULTADOS.md).

Two rules that came out of my own mistakes, and that I'd ask of any new measurement:

- **report the worst of several runs, not the mean.** The desktop measured gave between 44 and
  79 M steps/s depending on when it ran, against 1.6% variation on the phone;
- **say what machine it is**, with CPU model, memory, and what else was running.

---

## How I respond

- **An attack that lands gets written into the paper with your name and the date**, the way every
  previous one was. The [build log](docs/build-log.en.md) is the record of that, and my own errors
  are in there at the same level of detail.
- **An attack that doesn't land gets a written refutation**, not a "that's already answered." If
  the refutation didn't exist, I write it.
- **If the attack shows a section promises more than it delivers, the section gets corrected.** It
  has happened: an invariant was written wrong and failed in both directions; a section contradicted
  itself between two of its own sentences; and a ceiling promised a budget it missed by 23×.

**Language doesn't matter.** The long-form material is in Spanish and the debate documents are in
both; write in whichever comes easiest.

---

## License of what you contribute

Whatever you open here falls under the repository's licenses: [MIT](LICENSE) for code, [CC BY
4.0](LICENSE-DOCS) for prose. If you cite the work elsewhere, say where it came from.
