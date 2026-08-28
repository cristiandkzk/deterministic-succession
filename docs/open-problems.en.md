# What is missing, and where to hit first

*[Versión en español](problemas-abiertos.md)*

This document is the project's debate agenda. It has three parts:

- **[Part 1 · Where to hit first](#part-1--where-to-hit-first)** — eight attacks, ordered by how
  expensive each would be to discover late. If you have time for one thing, this is it.
- **[Part 2 · The declared open problems](#part-2--the-declared-open-problems)** — what the design
  knows it hasn't solved, with the reason each is still open.
- **[Part 3 · What needs measurement, not analysis](#part-3--what-needs-measurement-not-analysis)**
  — where the bottleneck is not more thinking.

**How to read this list.** Nothing here is buried in a footnote: it is all declared in the
[paper](paper.md), and several of these points **exist because an attempt to fix them failed and
got written down**. The [build log](build-log.en.md) has the index of what already died — worth
checking before proposing, not because a repeated proposal is forbidden, but because one that
doesn't answer the existing refutation doesn't advance.

---

## Part 1 · Where to hit first

### A · Is the verifiable-work subset an economy or a niche?

**This is the design's most expensive hypothesis, and the only one never taken out to be
falsified.**

All network revenue depends on the existence of requests with a cheap deterministic predicate:
*"deliver something that compiles and passes these tests."* Today most of the economic value of a
model lies in outputs **without** a cheap predicate.

**Concrete question, and it is a market question rather than a design one:** would you pay for
this, against a centralized provider that answers in seconds, with hours-long finality?

*What would close it:* a real buyer saying yes, or an analysis of why the set of tasks with a
cheap predicate is larger (or smaller) than the design assumes.

### B · Does the block-0 claim recruit operators, or claimants?

The optimal claimant is **a GPU fleet rented for the duration of the window and returned when it
closes**. The design proves the hardware **existed**, not that it **stays** — and since issuance
is decoupled from work, holding tokens gives no reason to keep working. The claim is also
**non-repeatable**.

### C · Is the reference task replayable?

If the instance is fixed and published at genesis, the first to solve it publishes the solution
and **the cost of the claim collapses to zero for everyone else**. It would be fixed by deriving
the instance from the claimant's key — *that is not written*.

### D · At `t = 0` every defense is denominated in a unit with no price

The fee is ad valorem; the floor and the deposit are nominal; and the rate's initial level is
[open problem 2](#2--the-permanence-rate-rule-and-the-level-it-starts-from). **In the window where
the chain is most fragile, the anti-spam is worth approximately nothing.**

### E · The dangerous scenario is success, not failure

If the currency appreciates — which is what happens if it is adopted — storage becomes
prohibitive in real terms and **state empties out**. What compensates is the rule that isn't
written, **and the first version of that rule already collapsed** (see [build log
2.5](build-log.en.md#25--a-control-law-that-seemed-to-close-and-didnt)).

### F · The canary installs consensus cryptography written by an anonymous bidder

With *"nobody broke a weakened instance within a fixed window"* as the only filter. **Is that
enough?**

*What is already settled here, so it isn't re-litigated:* the weakened instance is **derived**
from a public seed, not generated — if anyone generated it they would retain the trapdoor and the
canary would be theirs. That is closed ([build log
3.1](build-log.en.md#31--phases-0-and-1--the-engine-and-three-gaps-only-visible-when-running)).
What stays open is whether the window filter is enough as an admission criterion.

### G · The interpreter can never be patched

That is I1, and it is the invariant that makes everything else possible. **Is it realistic to
formally verify a complete deterministic VM, and what happens the day a bug appears?**

*Context that may help attack this:* building the machine found three amplification
vulnerabilities no correctness test would have found, and three criteria that existed and proved
nothing. That is the kind of thing I1 makes permanent.

### H · The design cannot correct a day-1 economic error

By construction. And a launch is exactly when you discover what you failed to anticipate. **Every
other chain fixes that through governance. Is this sustainable?**

---

## Part 2 · The declared open problems

### 1 · Which hardware is the worst case

The whole design assumes **the light layer is the binding constraint** — that is where cheap node
entry comes from, and it is load-bearing in two separate places: a blocking coalition cannot last
if entry is cheap, and the challenge queue doesn't saturate because eleven nodes suffice.

**Measured, the assumption is false** for adversarial memory patterns:

| | worst admissible program |
|---|---|
| mid-range phone | **80.8 M steps/s** |
| x86-64 desktop | **78.9 M steps/s** |

And with more memory the gap widens to double **in the phone's favor**. The two machines break in
different places: the ARM core doesn't pay for the unpredictable indirect branch that punishes the
x86 interpreter (327 vs 145 M steps/s on the shuffled mix), and the desktop can't take the page
dispersion the phone absorbs for free.

This doesn't invalidate the ceiling — it is calibrated against the hardware declared as reference
— but it does invalidate the sentence *the cheapest hardware is the worst case*, which had looked
obvious.

> **Two machines are not enough to set a floor, and closing it needs more machines, not more
> analysis.** See [part 3](#part-3--what-needs-measurement-not-analysis).

### 2 · The permanence-rate rule, and the level it starts from

That the rate cannot stay frozen is already established: **a fixed nominal price cannot ration a
real resource under a floating currency.** At 50% annual appreciation, storage costs 57× more in
real terms over ten years and state empties; under depreciation it becomes free and fills.

The only variable it can be indexed to without violating I2 is **state occupancy** — a fact of
state, not a market reading. What is missing is which rule gets written. **And something beyond
the shape is missing: the level it starts from**, which is a price the chain cannot read without
violating I2.

**Two things already known about this problem, which have to be answered to make progress:**

- **the first version of the control law already collapsed**, and not through tuning but for an
  economic reason: prepayment under a floating price is intertemporal arbitrage. See [build log
  2.5](build-log.en.md#25--a-control-law-that-seemed-to-close-and-didnt);
- **indexing to occupancy stops working once a price already rations the resource.** Measured on a
  second, independent parameter with third-party data: with Ethereum's base fee moving 650× over
  four years, mean occupancy stays at 50.9% and its correlation with the fee is **−0.02** over
  1,026 samples. Not weak: zero.

**And there is a statable reason why this doesn't yield to the move that closed the ceiling
twice:**

> The ceiling had both sides in the physical world — steps and seconds — and the chain can count
> both. **The rate has a physical side, bytes × epochs, and a monetary one, and no calculation
> crosses those two sides without reading a price.** It is not a calculation waiting to be
> written: it is a boundary.

That is where denominating the floor in storage epochs rather than token units came from — with
that, **what stays open is one number and not two**.

**Update, 2026-08-28 — the first external answer, and what it does to this boundary.**

Asked on [`ethereum/EIPs#12107`](https://github.com/ethereum/EIPs/pull/12107) why `CPSB` is
recalibrated through a new EIP rather than derived from the active gas limit, Maria Silva —
author of EIP-8037 — pointed at the design they consider the end game for this problem:

> **EIP-7999**, where **the base fee varies to hold the target state growth rate** instead of
> varying the gas cost itself.

EIP-7999 — *Unified multidimensional fee market*, by Anders Elowsson, Vitalik Buterin and Maria
Silva — **specifies the whole control law**: an exponential on excess relative to target, with
`BASE_FEE_UPDATE_FRACTION` **derived** from `GAS_NORMALIZATION_FACTOR / (2·ln(1.125))` rather
than picked. And it **does not specify the initial level** of the base fees at activation.

So there the problem splits exactly as it does here: **the form solved, the level not.** Two
consequences:

- **the form can be borrowed**, with the constant derived rather than chosen — which is
  precisely the move that closed the step ceiling twice;
- **the initial level is unsolved in Ethereum too**, with those three authors on it. That
  demotes it from a hole in this design to **a boundary of the field**.

**And it raises a doubt about how the boundary above is stated.** EIP-1559 does not read a
price: the base fee starts anywhere above `MIN_BASE_FEE_PER_GAS = 1` and the loop converges.
**The price is the loop's fixed point, not an input.** If that carries over, *"no calculation
crosses the two sides without reading a price"* is stated wrongly — you don't need to **know**
the price, you need a loop whose fixed point **is** the price.

> **Unverified.** This is a hypothesis, not a closure: it requires reading EIP-7999 in full
> against this problem. That is the next thing to do here, and if it holds, this open problem
> goes away.

### 3 · The notice window `Δ`: a unit and a magnitude

Found by the units audit, and **these are two distinct problems worth not conflating**.

**The units problem.** `Δ` is in blocks and block time is an internal parameter, so the real
notice varies **60×** across the space. And a transition can move it **while another is in
flight**, which shortens an already-announced notice after it has been announced. Three ways out,
none free:

1. **recompute the activation height** when block time changes — preserves the notice, but the
   announced height stops being fixed;
2. **forbid a block-time change from activating while a transition is in flight** — narrow,
   checkable, and doesn't touch the mechanism section;
3. **declare it** as one more boundary.

**The magnitude problem, which is the bigger one.** At current values `Δ` gives **6.4 minutes and
48 seconds**, and the paper describes that knob as a real tradeoff between the chain's urgency and
an integrator's reaction time — **at these numbers both values are on the same side, the side of
no notice at all.** The knob is described as a tradeoff and isn't on that curve.

What actually gives the integrator a tolerable failure mode is **I5**, not `Δ`. That makes the
small number non-catastrophic, and also shows **`Δ` does considerably less than the paper
attributes to it**.

### 4 · The burn channel: a declared boundary, with its reopening condition

If the rate is indexed to state occupancy, **an attacker who fills state accelerates third
parties' burn**, and burn enters the quantity the trigger reads. Which means **a transition can be
paid to arrive sooner**. The leverage is of order `1/ε`, with `ε` the elasticity of honest storage
demand:

| attacker's share of state | ε=0.25 | ε=0.5 | ε=1.0 | ε=2.0 |
|---|---|---|---|---|
| 5% | **3.52** | 1.85 | 0.95 | 0.48 |
| 50% | 0.94 | 0.75 | 0.50 | 0.29 |

With elastic demand the attacker never burns more of others' than of their own and the channel is
harmless. With **inelastic** demand the channel is real. And `ε` cannot be known before there is a
live network.

**The decision was to declare it as a boundary rather than close it by definition**, and the
argument matters because it is reusable: the alternative — excluding that burn from the count —
**pays a certain price for an uncertain risk**, and *the expensive thing is not the exception, it
is the first exception*: once one is written, every future burn channel has to argue whether it
counts.

**What makes it honest is that the boundary declares what measurement revokes it:** if with a live
network storage demand turns out markedly inelastic, the other choice becomes the right one.

### 5 · The limits the frame cannot cover

**None of these is a problem to solve: they are declared limits**, listed here so an attack doesn't
spend time rediscovering them.

- **writing the rule in advance doesn't eliminate the fork: it moves it to the case where the
  written rule is the wrong one.** With two real measured cases, and a *how* that came out of the
  second: the rule doesn't become wrong because the world changes, but **because the people who
  wrote it learn**;
- **the declared space can fall short.** The ceiling of what the chain can ever do may be bounded
  by a technology that didn't exist when the space was declared — and widening it is a fork.
  Measured on a real case;
- **the set of possible futures stops being auditable.** The flip side of the previous one;
- **the protocol can guarantee that an evicted asset *can* be revived. It cannot guarantee anyone
  will have what it takes;**
- **the five invariants cover what state *is*, not what it *means*.** Two real defects passed
  underneath all five. It cannot be covered without the protocol having a notion of what a quantity
  is worth, which is precisely what the design declares impossible;
- **the protocol has no notion of identity**, so every lever it moves it moves for everyone. See
  the two rules for reviewers in [build log 2.1](build-log.en.md#21--the-wall-four-fixes-one-cause).

---

## Part 3 · What needs measurement, not analysis

**This is the part where a stranger helps more than an argument does.**

### Run the benchmark on more machines

[Open problem 1](#1--which-hardware-is-the-worst-case) doesn't close by thinking: it closes with
more hardware. **The number that comes out of it is a genesis constant.**

What is needed is to run the adversarial mixes on anything available — another phone, a server ARM,
a laptop, a large x86 core — and see where the worst mix lands. The benchmark package is
self-contained and lives in
[`mediciones/test2-interprete/`](../mediciones/test2-interprete/RESULTADOS.md), with the procedure
written down *(in Spanish, but the commands and CSVs are language-independent)*.

One useful data point about dispersion: **the desktop gave between 44 and 79 M steps/s depending on
when it ran, against 1.6% variation on the phone.** Any new measurement must report the worst of
several runs, not the mean.

### External adversarial review

Everything the design survived was run by the person who wrote it. That is exactly the kind of
evidence that doesn't count, and the paper says so explicitly.

### The test that never ran

The buyer test: [attack A](#a--is-the-verifiable-work-subset-an-economy-or-a-niche). It isn't a
simulation — it is going out and asking.

---

## How to report

See **[CONTRIBUTING.en.md](../CONTRIBUTING.en.md)**. In one sentence: a useful attack says **which
invariant it targets** and **what observation would confirm or kill it**.
