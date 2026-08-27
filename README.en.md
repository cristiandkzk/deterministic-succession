# Deterministic rule succession

[![invariantes](https://github.com/cristiandkzk/deterministic-succession/actions/workflows/invariantes.yml/badge.svg)](https://github.com/cristiandkzk/deterministic-succession/actions/workflows/invariantes.yml)

**A chain that carries, written into its genesis block, the rule by which its own rules
change — and executes that change with no vote, no political fork, and no human in the
decision loop.**

*[Versión en español](README.md) · the long-form material is in Spanish; this page and the
two debate documents are in English.*

> **This is not a pitch. It is a request that you break it.**
>
> The design survived every attack that was run against it, and **every one of them was run
> by the person who wrote it** — which is precisely the kind of evidence that doesn't count.
> This repository exists so that stops being true.
>
> If you only have time for one thing: **[where to hit first](docs/open-problems.en.md)**.

---

## The part worth reading first

**The design was finished and there was not one line of code.** Then it was built — the six
phases of the roadmap, each with its pass/fail criteria written *before* the phase ran.

**Building it corrected the paper seven times.** Not seven bugs in the code: seven places
where the design was wrong and only running it showed that.

| what the paper said | what building it found | where |
|---|---|---|
| invariant I2 ruled out triggers nobody can foresee | I2 was **written wrong in both directions**: it excluded §6.6's own canary, and it let through a back door — *"when address X receives 1 wei"* has monotone progress and a publishable distance too | [`genesis/LEEME.md`](genesis/LEEME.md) |
| the VM step ceiling is a constant to choose | it is **not a number, it is a calculation** — and the same move worked three times on three different parameters | [`predicado/RESULTADOS.md`](genesis/predicado/RESULTADOS.md) |
| a step budget bounds verification cost | **a step is not a step.** The worst instruction mix runs **23× slower**, and weighting opcodes cannot fix it: `lw` costs the same as `addi` with the data in cache and 23× more without — same opcode. Hence a second ceiling, on **pages touched** | [`predicado/RESULTADOS.md`](genesis/predicado/RESULTADOS.md) |
| the page ceiling is a constant | written as a constant it **excluded primitives instead of pricing them** — the three ML-DSA primitives touch 26, 40 and 65 pages, so the first number chosen (48) locked the third one out forever, against what §6.6 promises | [`predicado/RESULTADOS.md`](genesis/predicado/RESULTADOS.md) |
| §8.5's storage floor buys ~16 hours | off by two orders of magnitude — and then wrong again when the tree got built: 26 hashes was the tree the design had discarded | [`estado/RESULTADOS.md`](genesis/estado/RESULTADOS.md) |
| state crosses a transition intact (I3), so a paid deposit is safe | a deposit denominated in byte-**epochs** got **reinterpreted by a switch without anyone touching it**: the bytes crossed identical, what changed was what they were worth. **No invariant was watching** | [`devnet/RESULTADOS.md`](genesis/devnet/RESULTADOS.md) |
| the tree's cut `d` is an implementation detail | it enters consensus through the floor | [`estado/RESULTADOS-ARBOL.md`](genesis/estado/RESULTADOS-ARBOL.md) |

That list is the reason this repository exists in the shape it does. **A design document that
was never executed is a hypothesis about itself.**

---

## Check it in thirty seconds

No dependencies outside the standard library. Python 3.11+.

```sh
cd genesis
python verificar.py            # 296 criteria: I1-I5 and every phase's pass criteria
python herramientas/demo.py    # the switch running, on one screen
python herramientas/mutar.py   # 39 deliberate breakages, all caught
```

That last one is the one that matters. **A criterion only ever run against working code
cannot tell a predicate from a `return true`.** `mutar.py` breaks the engine on purpose in 39
ways the paper declares impossible and verifies the suite catches each one. It has already
found three criteria that existed, had names, and proved nothing.

The Rust machine has its own:

```sh
cd genesis/predicado/vm && cargo test --release   # 20 criteria
```

---

## The mechanism, on one screen

The piece that makes this not a disguised fork is that **the node is not replaced, it is
switched**: same process, same in-memory state, executing different rules from a given block
onward.

```
   +-------- ruleset A --------+ +- F -+ +---- D ----+ +--- ruleset B ---+
                                                     |
   ---#---#---#---#---#---#---#---#---#---#---#---#--|--#---#---#---#--->
                              ^       ^              |
                          block N   N final      activation
                       TRANSITION_    LOCK-IN    switch takes effect
                        RULE -> TRUE  irrevocable
                        (advisory)    params on-chain

   the SAME node . the SAME state . no migration, no bridge, no snapshot
```

**There are three times, not two:**

1. **Trigger.** At block `N`, `TRANSITION_RULE` returns TRUE. Nothing is committed: it is
   advisory, and a reorg can undo it.
2. **Lock-in.** Once `N` is final, the trigger becomes irrevocable. Lock-in emits the full
   parameter set and the activation height **on-chain**.
3. **Activation.** `Δ` blocks after lock-in — not after the trigger, so the notice is exactly
   `Δ` regardless of how long finality took.

---

## The evidence is of two classes, and mixing them would be dishonest

| half | what it is | evidence |
|---|---|---|
| **parameter succession** (§3) | the chain changes its own internal parameters with no vote | **a client found in the wild**: Ethereum recalibrates `blobSchedule` by hand (EIP-7892), the gas limit by schedule (EIP-8261), and the difficulty bomb was delayed by fork six times |
| **the currency, the interpreter, §6.6** | own economy, deterministic VM, chainable cryptographic evolution | **self-evidence only** — it survived every attack, and the author ran all of them |

The replay harness ([`genesis/herramientas/`](genesis/herramientas/)) is the only thing here
that produces evidence the author did not write: it runs a deterministic rule against
Ethereum's real history and compares it to what humans actually decided. Verdict, including
where it fails, in [`herramientas/RESULTADOS.md`](genesis/herramientas/RESULTADOS.md).

---

## If you have a machine, you can close an open problem today

The design assumes the light layer is the binding constraint. **Measured, that is false for
adversarial memory patterns:**

| pages touched | aarch64 (phone) | x86-64 (desktop) | worst case |
|---:|---:|---:|---|
| 48 | 86.2 | 122.2 | phone |
| 96 | 80.8 | 78.9 | **desktop** |
| 512 | 77.6 | 40.6 | **desktop, by 1.9×** |

*(M steps/s, worst-case instruction mix.)*

Above 96 pages the desktop runs the worst mix **slower than the phone**, and the desktop's
dispersion is 44–79 M steps/s depending on when you run it, against 1.6% on the phone.

**Two machines are not enough to fix a hardware floor, and closing it needs more machines,
not more analysis.** If you run the harness and post your numbers in an issue, that is a
declared open problem getting closed. See [`genesis/predicado/vm/LEEME.md`](genesis/predicado/vm/LEEME.md).

---

## What is deliberately not here

**No network transport** — no sockets, no peer discovery, no gossip. Nodes pass blocks as
objects in one process. What is proved is the *separation between producing and validating*,
which is the protocol property; transport is engineering and moves no invariant.

**No compute node, no work market, and no market test** — and that last one is what the paper
itself calls the dominant risk. Nobody has ever been asked whether they would pay for this.
It is [attack A](docs/open-problems.en.md#a--is-the-verifiable-work-subset-an-economy-or-a-niche).

**Everything here is disposable by declaration.** The parameters are toy parameters: nobody
knows yet what space genesis has to anticipate, so these numbers exist to make the mechanism
run, not to be inherited.

---

## How this is organized

| where | what |
|---|---|
| [`docs/paper.md`](docs/paper.md) | the full design, 12 sections. Source of truth — `§X.Y` always cites this |
| [`docs/open-problems.en.md`](docs/open-problems.en.md) | **the debate agenda**: where to hit first, the declared open problems, and what needs measurement rather than analysis |
| [`docs/roadmap.en.md`](docs/roadmap.en.md) | glossary, module structure, and each phase with its pass criteria |
| [`docs/build-log.en.md`](docs/build-log.en.md) | what already died, and why. Worth checking before proposing |
| [`genesis/`](genesis/) | **the implementation.** Start at [`genesis/LEEME.md`](genesis/LEEME.md) |
| [`mediciones/`](mediciones/) | the four falsification tests and five measurements that predate the implementation |

Each phase has its `CRITERIOS.md` (written before the phase ran, untouched afterwards) next to
its `RESULTADOS.md` (what it gave, including what failed). **Adding criteria was allowed;
softening them was not.**

---

## Licence

Code (`genesis/`, `mediciones/`) under [MIT](LICENSE). Prose (`docs/`, `README*`,
`CONTRIBUTING*`, every `RESULTADOS.md`) under [CC BY 4.0](LICENSE-DOCS).

How to contribute — and specifically how to attack this: [CONTRIBUTING.en.md](CONTRIBUTING.en.md).
