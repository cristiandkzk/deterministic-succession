# Build log: how it was built, and what fell apart along the way

*[Versión en español](bitacora.md)*

This document is not a record of progress. **It is a record of what was discarded and why.**

The [paper](paper.md) says what was arrived at; this says how, what died on the way, and
which attack each piece survived. It exists for two reasons:

- **for whoever comes to break the design** — so you don't spend your time proposing
  something already tried and failed. At the end there is an [index of what already
  died](#index-what-already-died);
- **because it is the expensive thing to re-derive.** A result can be re-checked in a minute;
  the reasoning that produced it cannot.

It is in chronological order, and each stretch says what it corrected in the paper.

---

## Contents

- [0 · Method, which is half the result](#0--method-which-is-half-the-result)
- [1 · Four falsification tests, before building anything](#1--four-falsification-tests-before-building-anything)
- [2 · The monetary redesign, and the identity wall](#2--the-monetary-redesign-and-the-identity-wall)
- [3 · Construction: six phases, and what reading had not corrected](#3--construction-six-phases-and-what-reading-had-not-corrected)
- [4 · The units audit: what passes underneath all five](#4--the-units-audit-what-passes-underneath-all-five)
- [5 · Method lessons that hold outside this project](#5--method-lessons-that-hold-outside-this-project)
- [Index: what already died](#index-what-already-died)

---

## 0 · Method, which is half the result

Three rules governed everything that follows, and it is worth having them before the results,
because they are what decides whether a result means anything.

**1 · Pass criteria are written before anything runs, and never softened afterward.** Every
phase has its criteria file, written before the first line of code, and it was not edited
after seeing results. **Adding criteria is allowed; softening them is not.** In one case the
measured number would have permitted raising a constant to 140 and it was left at 120 —
precisely because raising it after seeing a favorable result is what the rule forbids.

**2 · A test has to be seen failing once.** Three times in two days a criterion turned up that
existed, had a name, and proved nothing: a floating-point check written with a mis-escaped
pattern that never matched; the revalidation of a cryptographic proof that could be deleted
entirely without any test failing; and the traversal order of the active set, which could be
switched to a non-deterministic one with no visible consequence.

> **A test that doesn't test is worse than no test, because it also grants confidence.**

Hence the tool that most paid for itself: a mutation harness that breaks the engine on
purpose, in ways the design declares impossible, and verifies the suite catches them. Without
it, *"246 criteria pass"* does not distinguish a predicate from a `return true`.

**3 · Every measurement declares what it is measuring.** This came out of the worst error in
the project (§3.4), where one measurement degenerated into a different one without warning and
**nothing failed**: it kept reporting a number — plausible and wrong — on which two written
conclusions already rested.

---

## 1 · Four falsification tests, before building anything

The paper was written with a closing section on how to falsify it **before building
anything**. All four ran. Detail is under [`mediciones/`](../mediciones/); here is what they
produced.

**Test 1 — does the mechanism have a taker in the wild?** Yes, and this is the only half of
the project with third-party evidence. See §2 below and section 4 of the
[README](../README.en.md).

**Test 2 — the interpreter's budget on real hardware.** It measured that one ML-DSA
verification costs the same, **byte for byte, on x86 and on ARM**: 3,339,364 steps for
ML-DSA-44. That result is what makes it possible for the protocol ceiling to be denominated in
*steps* — in wall-clock time it would be an oracle. It also found the iOS/Android asymmetry of
15×, which weakened the decentralization-by-entry-cost argument and forced its replacement
with a better one (§2).

**Test 4 — the `k` window.** It looked for a calibration that made self-dealing unprofitable
without punishing the honest user. **The window turned out to be empty**, and that was the most
productive result in the project: it forced the entire monetary redesign in part 2.

---

## 2 · The monetary redesign, and the identity wall

All of this came from Test 4 returning negative. The economics were redesigned wholesale, and
the central result was not a mechanism but **a limit of the design**.

### 2.1 · The wall: four fixes, one cause

Four attempts to fix four different things died for the same reason:

| attempt | how it died |
|---|---|
| `k` as a calibration lever | enters identically for the self-dealer and the honest user |
| locking up the subsidy | discounts both equally |
| splitting the benefit by role | arbitraged by whoever occupies both roles |
| superlinear challenge bond | punishes the honest challenger alongside the attacker |

> **The protocol has no notion of identity, so every lever it moves, it moves for everyone.**
> This is not bad luck four times: it is a property of the design, and it explains all four
> results at once.

It is declared in the paper as an inherent limit, with **two rules for reviewers** that exist
so four different people don't propose the same four levers:

> Any proposal of the form **"make the good actor pay less"** is a proposal to introduce
> identity.
>
> Any proposal of the form **"issue when there is real demand"** is also a proposal to
> introduce identity.

**The way out was to stop trying to distinguish.** The redesign doesn't ask *"is this external
demand?"*; it makes the closed circuit **lose**. The arithmetic doesn't need to know who anyone
is. Measured: the self-dealing attack loses **even when it is 100% of the network** (−0.000600
per cycle). And burning turned out to be the one irreplaceable piece — at 0% burn the attacker
breaks even and the attack becomes free.

### 2.2 · Day-1 distribution, and the theorem that closed it

Four mechanisms were proposed and died before the surviving one appeared:

- **give the pool to the first to produce work** — at block 0 there is no real demand by
  definition, so *"the first to work"* is whoever fabricates work fastest. And it is **once and
  uncorrectable**: no later dilution fixes it;
- **split among all nodes existing after some time `T`** — pure Sybil (a node costs a phone, on
  purpose), and something worse: **the chain cannot observe that a node exists, only what it
  does**. Bitcoin can measure hashing because a hash evidences itself; *"a node was online"*
  does not;
- **a free claim on the initial pool** — saying "hello" is a signature, and at block 0 there
  are no tokens to charge a fee against and no stake to demand. The pool goes to whoever
  generates the most keypairs;
- **the block-0 certificate as a license to earn fees** — actively bad: it makes the number of
  nodes artificially scarce and builds exactly the capital moat the design exists to avoid.

> **The theorem, in final form.** A distribution of new tokens indexed to an action yields **at
> most what that action costs, or it is farmable**. If the pool pays less than the cost, nobody
> claims it; if it pays more, it gets farmed. Bitcoin could because the action was hashing —
> external, physical, impossible to fake — and because it lasted years rather than an instant.

And a framing discovery that closed the question entirely: an attempt was made to frame block 0
as a fork of a prior generation. But I3 says *state is preserved intact across the transition*,
which means **a transition preserves the distribution, it does not create it** — and the
regress never terminates.

> **Day-1 distribution is by definition outside the mechanism.** There is no mechanism to look
> for here: there is **a decision to make**, which is a different kind of work.

What survived: **a claim paid in computation**, with the unclaimed remainder burned. And the
property that justifies it: if the claim costs and the unclaimed burns, then **the initial
supply is not set by the creator — it is set by how much real capacity showed up**. *Declared
honestly: it is still an auction paid in compute. Whoever has more GPUs takes more. It is not
egalitarian distribution and must not be sold as such — it is open, which is a different
thing.*

### 2.3 · The withdraw/add asymmetry

> **Activity already determines how much circulating supply is WITHDRAWN. What it cannot
> determine is how much is ADDED.**

Withdrawing needs no recipient: burning is a fact of state, self-verifying, and the burner
loses. It is a lever that **only harms whoever pulls it**, so it can be left open to anyone.
Adding does need a recipient, and choosing one is either a human decision or an indexation to
an action — and there the theorem returns.

### 2.4 · Creating assets: where the charge goes, and why not on creation

A charge on asset creation was proposed, importing another chain's *rent* model. It was
rejected, and the argument that closed it came from outside crypto — Argentina's construction
levy, paid when the permit is requested **in addition to** the recurring property tax:

> **A charge on creation does not reduce creation — it reduces the *registration* of
> creation.**

Transferred: if creating on the native layer carries its own charge, people don't create less,
they create **outside**, and there you lose exactly what the design argues for across an entire
section. The asymmetry, which is one of *enforceability* and not only of incentives:

| | charge on creation | permanence mechanism |
|---|---|---|
| distorts? | yes — taxes production | no |
| evadable? | **yes, by creating outside** | **no — state that exists is seen by every node** |

The form that closes is a **prepaid deposit consumed by burning**, and its sentence: *you don't
pay to create — you pay for how long you want the network to keep it for you.*

**Discarded along the way, with reasons:**

- **auctioning the abandoned asset.** It jams on two things that don't depend on price. First:
  nobody buys garbage — that's why it's garbage — so the only thing that actually sells is what
  did have value, and a valuable abandoned asset almost always belongs to someone who lost
  access or died. **The mechanism selects valuable property from people without access, not
  garbage.** Second: what expiration recovers is **disk**, not supply, and against the real sink
  this is noise;
- **debt against the network.** There is no debtor: the owner is a key, and against an empty
  account there is nothing to seize. The only enforceable thing is the object, so the debt isn't
  a mechanism, it's the trigger for a forced sale — and a forced sale requires appraisal, i.e.
  reading an on-chain market price, which is forbidden and manipulable in the obvious direction;
- **warning the last owner before acting.** *The chain has no outbound channel.* The owner is a
  key, not a person;
- **a volume discount as a power rule** (`r(D) = r0·(D0/D)^α`). It drives the price per year to
  zero, and it doesn't cheapen just anything: it cheapens **the one operation that buys lifetime
  in bulk**, which is filling every node's state and never letting go. The form that keeps the
  intuition without the defect is a two-part tariff, where what falls as you buy more lifetime is
  the fixed floor spread over more time — **and it never drops below the real cost of storage**.

### 2.5 · A control law that seemed to close, and didn't

A control law over state occupancy was simulated — the EIP-1559 shape applied to disk rather
than gas — and it looked excellent: it absorbed a 3× demand shock without oscillating. **The
result was an artifact of the model.** The simulation recomputed every cohort's lifetime each
epoch, meaning that raising the price **retroactively shortened terms already paid for**. With
terms honored, the loop **does not converge at any gain**.

The cause is not tuning, it is economic:

> **Prepayment under a floating price is intertemporal arbitrage: buy long when it's cheap.**
> Those slots stay taken for centuries at bargain rates, and the loop cannot recover them
> because they're paid for and evicting early would be confiscation.

The fix was a cap on lifetime purchasable at once, with top-ups at the price of the day — and
with that the cap **stopped being an economic recommendation and became a stability condition
of the mechanism**.

> This episode is cited in the paper as a demonstration of how fragile self-generated evidence
> is: **the first version of the rule looked stable, and what knocked it down was correcting
> the model it had been tested with.**

---

## 3 · Construction: six phases, and what reading had not corrected

Up to this point the mechanism was prose that had survived imagined attacks. It was built in
six phases, each with its pass criteria written first.

**Building corrected five things reading had not**, and all five are now in the paper.

> **Careful not to read too much into this.** That the mechanism runs is not evidence that it
> is useful: it remains self-generated evidence with self-chosen parameters. What changed is
> smaller and real: **the mechanism section stopped being prose.**

### 3.1 · Phases 0 and 1 — the engine, and three gaps only visible when running

The five invariants were written as executable predicates, with a case that **must** fail for
each. The switch runs for real: same process, same state object, `starts == 1` end to end.

And three gaps appeared that the paper did not have. None was a bug in the code.

**Gap 1 — more than one transition in flight at once.** *It fell out on its own, with nobody
forcing the case.* Between lock-in and activation the chain keeps running the old rules even
though the new ones are already committed, so an accumulation rule keeps evaluating TRUE in
there and fires again. Four decisions, with what was discarded in each:

- **the rule re-arms at activation, not at lock-in.** If it could fire in between it would be
  measuring a state that doesn't reflect the change it just committed: **a control loop with
  dead time**. There is a real counter-case — Bitcoin Cash's EDA, 2017: an automatic rule
  written in advance, reacting faster than its own effect became visible, which oscillated and
  had to be replaced by a human fork three months later — and it **entered the paper through
  this gap**, in the place where it argues rather than merely illustrates;
- **the wait is per-rule, not global.** *Discarded — blocking all triggers while one is in
  flight:* that puts an urgent cryptographic migration behind a circulation transition **before
  it has even committed**;
- **activations go in lock-in order.** This was not obvious and appeared while writing the proof
  of the previous point: with different notice windows per class, a transition committed *later*
  came due *earlier*. The reason is I1: new parameters are **a complete point in the space, not
  an increment**, so generations are a totally ordered sequence and not a set of commutable
  patches;
- **parameters are computed at lock-in, which verifies before committing.** That opened a new
  question: *what if the successor is not a point in the space?* A checkpoint is irrevocable, so
  committing it would leave the node reaching activation unable to switch — **a halted chain**.
  It is verified first, with on-chain rejection. *Discarded — clamping the successor to the edge
  of the space: it changes the rule silently, which is exactly what I2 exists to prevent.*

**Gap 2 — lock-in is state, not an announcement.** And here **the initial diagnosis was
wrong**, which is the part that matters. It was filed as a *readability* problem: the
integrator loses the notice if a reorg takes the block. On writing it up, the severity turned
out to be different:

> **The state root diverges** between the node that reorged and the node that didn't. It is not
> an unreadable notice: it is a **fork**, and of the worst kind, because the two nodes agree on
> absolutely everything else and neither has any reason to suspect.

A documentation gap became a consensus rule. And it isn't proven by looking at one node: the
test runs **two nodes with the same history** — one reorgs the lock-in block, the other doesn't
— and requires they end with the same state root; a third resyncs from scratch and must reach
the same checkpoint.

**Gap 3 — I2 was written wrong, and failed in both directions.** This was the first time an
invariant was touched. The framing was that the cryptographic canary fails I2 because it can't
be seen coming. Examined closely, the problem was the invariant's:

- **it excluded what has to be included.** A primitive break does not approach: it happens;
- **it admitted what it exists to exclude.** *"When address X receives 1 wei"* is computed from
  state alone, has monotone progress and a publishable distance — and it is a gate with an
  owner. **The shape of the curve does not distinguish the two: both are steps.**

> **What separates the canary from the backdoor is not how visible it is coming, but who can
> produce the fact and what it costs them.**

And out of that came a condition the paper did not have, which is the most important thing from
that day: if genesis **generates** the weakened instance of the primitive, **whoever generated
it retains the trapdoor** and can claim the canary whenever they like. It would be the same
governance the design eliminates, but far harder to see, and signed by the author of block 0.

> **A canary that cannot be re-derived from its seed is not a canary: it belongs to someone.**

The limit of the second form is **proven as a limit, not hidden**: there is a test that runs the
very same backdoor declared under demonstrated capability and **lets it through**, with its
declaration in plain sight.

### 3.2 · Phase 2 — replay against Ethereum's real history

The only phase that can be shown to outsiders without asking anyone to believe anything: run
the deterministic rule against decisions humans already made, and compare. Three cases, with
data pulled from public endpoints without an API key.

**Case 1 · the difficulty bomb.** The six forks happened with the bomb term between `2^37` and
`2^41` — **it varied 16×**. There was no consistent human threshold. With a fixed threshold the
rule reproduces all six decisions within 37 days, mean 20, one of them exactly. But the
difficulty series answered an open question **against** the design: measured against adjustment
capacity, the real dispersion is **41×, not 16×**, and **only one of the six forks happened with
the bomb actually biting** — the other five were preventive, and there is a temporal trend. *The
humans learned to act earlier and earlier.*

> **The calculation has an external validation that wasn't sought.** One fork was an emergency
> because block times climbed to ~17 s. The model, which knows nothing of that history and was
> not calibrated against it, gives **17.2 s**.

The finding: the number that reproduces the history **is only knowable looking backward**, and a
threshold written at the start would have been wrong at both ends. *A written rule doesn't become
wrong because the world changes, but because **the people who wrote it learn**.*

**Case 2 · the blob schedule.** Where the constraint was demand, the rule wins by a lot:
occupancy hit 80% of target **37 days** after the fork that introduced it, stayed saturated 64%
of the time and peaked at 129%; Ethereum took **383 days** to respond. *That is the cost of
coordination, measured.* But where the constraint was **not** demand, the rule is blind: two
target raises happened at 43% and 31% occupancy, responding to a new technology rather than to
demand. A demand rule would have raised nothing, and would have been right by its own criterion
and wrong for the network.

And from that came a boundary the paper did not have:

> Could the rule have raised the target at the time? Only if that value was inside the space
> declared at genesis **and was safe** — and it wasn't safe until the enabling technology existed.
> **The ceiling of the descendant space was bounded by a technology that did not exist when the
> space was declared.** It is not that the rule may be the wrong one: it is that the **space** may
> fall short, and I1 freezes it at genesis.

**Case 3 · the gas limit — the only case where the rival is not a fork.** The gas limit is already
voted block by block: here the mechanism competes against lightweight, decentralized, fork-free
coordination **that already works**. It is the hardest rival, and the result is that **for this
parameter there is no admissible trigger**, with all three possible forms closed and each with a
number:

- **quantity — empty by construction.** The fee market pins the target at half the limit and
  moves the price until usage returns there. With the base fee moving **650×**, mean occupancy
  stays at 50.9% and its correlation with the fee is **−0.02** over 1,026 samples. Not weak: zero;
- **nominal price — expires.** The median fee fell from 36.4 to 0.056 gwei;
- **dimensionless price — ratchets.** It fires where it matters (fourteen months before the
  humans moved) but loses the notion of *expensive*: with no absolute reference, *expensive* is
  only *more than just now*.

> The problem is not the data's provenance nor the trigger's shape: **the only observable carrying
> information about this resource is a price, and no nominal price works as a long-run setpoint.**

**The honest close of the phase:** three of three passed as *explained difference*, and the phase
**produced no evidence that the design is better**. Two of three produced findings against it and
the third is a tie with an asterisk. What it produced is the three exact places where the mechanism
breaks against the real world. After this, the paper section that described its own status opened
with *"Nothing built"*, which was already false — and it was rewritten **putting the replay first,
saying two of its three cases went against the design**.

**And a data lesson that holds for anyone:** sampling one block every N gives a terrible estimate
of a rate (29% of samples read zero). The way out was not to download more blocks but to **read the
accumulator the chain already maintains**. *Find the accumulator before averaging the sample.* With
an asterisk that appeared later: **an on-chain accumulator is the right observable until someone
changes its formula** — and that isn't visible in the data, it's visible in the EIP.

### 3.3 · Phase 3 — ordering and settlement, and a contradiction inside one section

The criterion said: *if a hundred nodes are needed, the paper's prediction is wrong and it has to
be said*. **A hundred aren't needed: one more is, or infinitely many.**

The earlier calculation had closed this as a formula, and the formula assumed something nobody had
written down: **that the nodes don't collide**.

| how each node picks | critical N | steady state |
|---|---|---|
| partition by hash | 10 = the formula | no backlog |
| at random | **11** | backlog **stable** at ~424, mean wait 4.2 blocks |
| **oldest first** | **never** | growing backlog: 50 nodes verify what 1 verifies |

> **And the gap was inside the section, between two of its own sentences.** It said *draining is
> done by all nodes at once* and also *first-come, first-served* — and if everyone takes **from the
> head** of a FIFO queue, everyone takes the same one. **The contradiction isn't visible reading;
> it's visible running.**

The new rule requires no coordination and no knowledge of how many nodes there are: each walks the
queue in a pseudorandom order derived from its identity. The exact alternative — partitioning the
queue among the `N` — nails ten but **requires knowing how many there are**, which is precisely what
a design without a validator set does not have.

Two more things came out of this phase:

- **the correction from 13 to 11.** The first measurement used 80-block runs and gave 13. It was an
  artifact: at 80 blocks the system hadn't reached equilibrium, so a backlog that was going to
  stabilize read as one that was growing. **Every saturation measurement compares two run lengths**,
  and that is now written into the code. The 13 was in the paper for a few minutes;
- **a mutation escaped because the default wasn't tested.** Every test passed the strategy
  explicitly, and the default *is* the design decision — it's what whoever didn't read the section
  gets. *When a mutation changes a default and escapes, the mutation isn't superfluous: the
  criterion is missing.*

### 3.4 · Phase 4 — the machine, and the ceiling that overpromised by 23×

Six criteria passed, one failed. **The failure is what made the phase worth it.**

**A step is not a step.** The declared hardware rate came from dividing one verification's cost by
how long it took. **That is the rate of one specific instruction mix.** Measured against six mixes
chosen to be slow, the worst — pointer chasing across 63 MiB — runs at **11.3 M steps/s**: the
ceiling promised 22 ms per transaction and that mix took **596**.

**And it isn't fixed by weighting instructions**, which is the obvious way out and the one gas
takes. The mix that opens the gap is a memory load, and that instruction runs at 207 M steps/s when
the data is cached and 11 when it isn't: **it's the same opcode**. A per-class weight would have to
charge every load the price of the worst one, and then the real primitive — which is full of loads
that do hit — would stop fitting.

The way out was to count **distinct pages touched**, and the number wasn't chosen: it was read off
the crossing of two curves. Three things were measured because they weren't obvious and **all three
could have sunk the approach**: what dispersing the pages costs, what counting them costs (14%, to
close a 23× hole), and whether text size was a second lever.

> **This is the best evidence that it was worth making the ceiling a formula.** One input was
> corrected by 2.5× and **the mechanism didn't change a line**: a parameter changed. Had the ceiling
> been the number the paper asked for, the correction would have been a design change.

**Three holes that weren't about performance, and how they surfaced.** No correctness test would
have found them. **They were found because a sweep took minutes**, which is worth remembering next
time a slow test looks like just a slow test: a 64 MiB allocation before validating a header; an
altered section header that could force 128 MiB of predecoding; and the fact that an ELF's segment
flags **do not distinguish code from constants**, because the linker merges both into the same
segment.

**The worst error in the whole project, and nothing failed.** One measurement mix loaded its base
address wrong — a twelve-bit signed immediate that subtracted instead of adding — so the pointer
chain started one page earlier, read a zero, and from there **read the same address forever, always
in L1**. It reported a plausible number. It was caught because **it ran at exactly the speed of a
different mix that had to differ**, when two tools that should have agreed didn't. Two written
conclusions already rested on that number.

What was put in place, and it is rule 3 of the method:

> **Every mix declares how many pages it must touch, and it is verified on completion. A
> measurement has to declare what it is measuring.**

**Three ways to measure wrong, all of the same type.** The whole calculation is **a ratio between
two rates**, so measuring one worse than the other corrupts it — and all three times the bias pushed
toward the unsafe side: the reference measured with a single short call; the reference measured
last, after seconds of full load (~20% slower); and a comparison against a rate from a different
execution, which reported a 1.20× penalty that was **entirely noise** (the real one: 1.01×).

> A number compared against another is measured in the same run, with the same method, and the one
> serving as reference is measured **first and cold**. And when a bias has a safe side and an unsafe
> side, **you have to know in advance which is which.**

Three more things were found by looking at tests rather than code: a genesis constant duplicated
across two files (*a constant in two files is a fork waiting for someone to edit one of them*); a
test that proved nothing due to a mis-escaped pattern; and a counter that still had an off switch
from when it was instrumentation (*a check that can be turned off is a fork waiting for two nodes to
choose differently*).

**The problem the phase opened and left open:** which hardware is the worst case is unknown, and the
design assumed it was known. The two machines measured break in different places — the ARM core
doesn't pay for the unpredictable indirect branch that punishes the x86 interpreter, and the desktop
can't take the page dispersion the phone absorbs for free. **Two machines are not enough.**

### 3.5 · The page-ceiling wall — the same move, a second time

The paper promises **no walls, only prices**: a more expensive primitive doesn't get excluded, it
enters by paying capacity. The step ceiling complies, because it derives from capacity. **The page
ceiling, written as a constant, could not**: there is no price a primitive can pay to get more
memory. It can only exclude.

And it wasn't hypothetical. The three primitives in the family touch 26, 40 and 65 pages: with the
ceiling at 48, the third **was excluded forever** and no calculation flagged it. It was saved by two
pages of luck when the ceiling moved to 96, and the next primitive might not have that luck.

> **For one day the protocol contained exactly the thing its central section says does not exist.**

The fix was the same one that had closed the first ceiling: **freeze the curve, not the point.** The
declared rate stops being a number and becomes a measured table; asking for more pages lowers the
rate, and that is paid in capacity.

**And the objection that had to be answered was wrong — written by me the day before**: that the
budget couldn't be a parameter because the same program would behave differently across two
generations. It conflated two things:

> **Does it change what the program computes, or only whether it fits?** The first is semantics and
> gets frozen; the second is a budget and can be a parameter. The step ceiling **already worked that
> way from day one** and nobody thought it broke I1.

What the curve charges couldn't be anticipated: from 96 to 512 pages memory is nearly free — 4% of
rate — and **the next step divides capacity by seven**. That is the reference core's TLB cliff, and
the mechanism charges for it without anyone declaring it.

> **The same move worked twice on the same ceiling.** Both times the symptom was identical — a number
> that had to be chosen and no choice was good — and the way out was identical: **the number isn't
> chosen, it's derived; what gets frozen is the calculation.**
>
> Worth keeping as a standing suspicion: **a parameter you have to eyeball is usually a calculation
> waiting to be written.**

### 3.6 · Phase 5 — a floor wrong by two orders of magnitude

The paper claimed a certain floor worked out to *"about sixteen hours of storage"*. **Written out,
it doesn't:** with the signature inside the cycle it is ~91 epochs against the 0.67 claimed —
**137×** — and since the purchasable-lifetime cap is 25 epochs, the floor exceeded the maximum
deposit several times over. Which means nearly the entire cost of an entry would be paid at
creation, **which is exactly the charge-on-creation the section rejects two paragraphs earlier**.

The correction: the signature is already paid by the ordinary fee, and charging it again in the
floor is charging it twice.

**And there the interesting part appeared.** With the signature removed, the dominant term became a
number that was **estimated, not measured** — and that estimate had been declared harmless for a
circular reason: *"it doesn't matter because signature verification dominates"*. True only while the
signature was inside the cycle.

> **The term discarded for being small became the only one left.**

It was measured (4,898 steps per compression; the estimate was 2× high, in the conservative
direction) and the number is now asserted because both its inputs are measured.

**And the phase separated two problems that looked like one.** The previous section's suspicion — *a
number you eyeball is usually a calculation waiting to be written* — was run against the permanence
rate, and it does not yield:

> **The ceiling closed twice because both its sides were physical**: steps on one, seconds on the
> other, and the chain can count both without asking anyone. **The rate has a physical side — bytes ×
> epochs — and a monetary one, and no calculation crosses that without reading a price.**

And it isn't rhetoric: **it shows up in the types.** Everything the module computes is in byte-epochs
or epochs, and no monetary unit appears anywhere. The day one does, it arrives with an oracle beside
it.

> **The rule that remains:** anything expressible as a fraction of the node's budget gets derived;
> anything requiring a monetary unit stays on the other side of the wall.

From that came a form decision that shrank the open problem: **the floor is denominated in storage
epochs, not in token units.** In token units it would be a *second* price to set alongside the rate,
with the same problem and none of its defenses. With that, what stays open is **one number and not
two**.

### 3.7 · Phase 6 — the devnet, and what no invariant was watching

The phase was deliberately narrowed: of the four questions assigned to it, two had already been
answered by earlier phases. *Re-running what is already measured adds no evidence, and does add the
temptation to stare at the number until it comes out right.*

**The finding, invisible to all five invariants.** The permanence deposit was carried in
byte-**epochs**; an epoch is counted in blocks; and block time is an internal parameter a transition
can move:

```
6,000 ms block  ->  240 hours of real storage
12,000 ms block ->  480 hours, on the SAME deposit
```

> **The uncomfortable part: I3 held.** State crossed intact — the bytes are identical and the
> switcher verifies by digest and by object identity. What changed was not the state but **what that
> state is worth**, and none of the five invariants looks at that.

The correction is the same move a third time: denominate the deposit in **declared time**, not in
epochs. And the fine point, so it isn't confused with an I2 violation: **block time is not a clock
reading, it is a parameter the ruleset declares.** The chain doesn't measure time — it uses the
number it set itself.

> **The rule, now with three cases:** when a mechanism needs a physical magnitude, use **the declared
> one, not the derived one and not the measured one.**

And the mutation harness found the third empty criterion in two days: the active set could be walked
**in hash order** during eviction and no test failed. That is a fork, and it hides well, because
dictionary traversal by hash **looks deterministic within one process and isn't across two**.

---

## 4 · The units audit: what passes underneath all five

Two consecutive phases each found a defect that **violated none of the five invariants** — the
constant page ceiling, and the deposit in epochs. Both are the same shape:

> **I3 protects the bytes; nothing protects what the bytes mean.**

From that came a question that can be asked mechanically, and must be re-asked every time the
parameter space grows:

> **For every quantity the protocol stores or declares: does its meaning depend on a parameter a
> transition can move?**

The full sweep is written down, with a test that **fails the day someone adds a parameter to the
space without redoing the sweep**.

**What it found, still open:** the notice window `Δ` is in blocks, and block time is an internal
parameter, so the real notice varies **60×** across the space. And there is a second problem, larger
than the units one: at current values `Δ` gives 6.4 minutes and 48 seconds, and the paper describes
that knob as a real tradeoff between the chain's urgency and an integrator's reaction time — **at
these numbers both values are on the same side, the side of no notice at all.**

> **The values never appeared in the paper.** They lived in the code since the first phase, where
> they were enough for tests to run, and the paper speaks of *"long Δ"* and *"short Δ"* without giving
> numbers. **Nobody ever checked them against what the section claims they buy** — which is exactly
> the gap this audit exists to close.

What actually gives the integrator a tolerable failure mode is **I5**, not `Δ`: whoever didn't manage
to support the new generation keeps operating on the previous one. That makes the small number
non-catastrophic, and also shows **`Δ` does considerably less than the paper attributes to it**.

The tests in this part **assert the defect**: they fail the day it is decided, and that failure is
the signal to rewrite them, not a bug.

---

## 5 · Method lessons that hold outside this project

- **Building corrects what reading doesn't.** Five things, none of them a bug in the code: they were
  things the design didn't say, visible only when the mechanism executes. One was a contradiction
  between two sentences of the same section.
- **A number you have to eyeball is usually a calculation waiting to be written** — and when it
  isn't, there is a statable reason why (a physical side and a monetary side don't cross without
  reading a price).
- **Freeze the curve, not the point.** A mechanism that freezes a formula survives its input being
  corrected by 2.5×; one that freezes a number does not.
- **When a mechanism needs a physical magnitude, use the declared one** — not the measured one and
  not the derived one. Measuring it is an oracle; deriving it gets reinterpreted when a parameter
  moves.
- **A measurement has to declare what it is measuring**, and verify it on completion. A measurement
  that degenerated into another one doesn't fail: it keeps reporting a plausible number.
- **A number compared against another is measured in the same run**, and when the bias has a safe
  side and an unsafe side, you must know in advance which is which.
- **Any test meant to forbid something has to be seen failing once.** Three empty criteria appeared
  in two days, and all three had names.
- **When a mutation changes a default and escapes, the mutation isn't superfluous: the criterion is
  missing.** The default is part of the mechanism, not a convenience.
- **A slow test may not be just a slow test.** Three amplification vulnerabilities were found because
  a sweep took minutes.
- **Find the accumulator before averaging the sample** — and remember an on-chain accumulator is the
  right observable until someone changes its formula.
- **Before adding capital as a lever, find the penalty the mechanism already produces.** Four times
  the reflex was a bond or a lockup, and four times the penalty was already built in.

---

## Index: what already died

Before proposing something on this list, look at where it died. **These aren't forbidden: they
already have a written refutation, and a proposal that doesn't answer it doesn't advance.**

| proposal | where the reason is |
|---|---|
| calibrate a parameter so the attacker pays more than the honest user | [2.1](#21--the-wall-four-fixes-one-cause) — the identity wall |
| superlinear bond against queue flooding | [2.1](#21--the-wall-four-fixes-one-cause) |
| lock up the subsidy against farming | [2.1](#21--the-wall-four-fixes-one-cause) |
| split the benefit by role | [2.1](#21--the-wall-four-fixes-one-cause) |
| issue when there is real demand | [2.1](#21--the-wall-four-fixes-one-cause) and [2.3](#23--the-withdrawadd-asymmetry) |
| give the initial pool to the first to work | [2.2](#22--day-1-distribution-and-the-theorem-that-closed-it) |
| split among nodes existing after time `T` | [2.2](#22--day-1-distribution-and-the-theorem-that-closed-it) — the chain cannot observe that a node exists |
| a free claim on the initial pool | [2.2](#22--day-1-distribution-and-the-theorem-that-closed-it) |
| the block-0 certificate as a license to earn | [2.2](#22--day-1-distribution-and-the-theorem-that-closed-it) |
| charge a fee for creating an asset | [2.4](#24--creating-assets-where-the-charge-goes-and-why-not-on-creation) |
| auction the abandoned asset | [2.4](#24--creating-assets-where-the-charge-goes-and-why-not-on-creation) |
| let the deposit go into debt | [2.4](#24--creating-assets-where-the-charge-goes-and-why-not-on-creation) |
| warn the owner before eviction | [2.4](#24--creating-assets-where-the-charge-goes-and-why-not-on-creation) — the chain has no outbound channel |
| volume discount on the deposit (power rule) | [2.4](#24--creating-assets-where-the-charge-goes-and-why-not-on-creation) |
| pay a node to archive | [2.2](#22--day-1-distribution-and-the-theorem-that-closed-it) — same family: passive state, no on-chain evidence |
| block all triggers while a transition is in flight | [3.1](#31--phases-0-and-1--the-engine-and-three-gaps-only-visible-when-running) |
| activate transitions out of lock-in order | [3.1](#31--phases-0-and-1--the-engine-and-three-gaps-only-visible-when-running) |
| clamp the successor to the edge of the space | [3.1](#31--phases-0-and-1--the-engine-and-three-gaps-only-visible-when-running) |
| derive the lock-in event without storing it in state | [3.1](#31--phases-0-and-1--the-engine-and-three-gaps-only-visible-when-running) |
| have genesis generate the canary's weakened instance | [3.1](#31--phases-0-and-1--the-engine-and-three-gaps-only-visible-when-running) — whoever generated it keeps the trapdoor |
| weight instructions per class, gas-style | [3.4](#34--phase-4--the-machine-and-the-ceiling-that-overpromised-by-23) |
| the page budget as a constant | [3.5](#35--the-page-ceiling-wall--the-same-move-a-second-time) |
| index the rate to occupancy with no cap on purchasable lifetime | [2.5](#25--a-control-law-that-seemed-to-close-and-didnt) |
