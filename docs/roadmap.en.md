# Roadmap

*[Versión en español](roadmap.md)*

**For whoever joins the project.** This says where the project stands, what the words you'll see
in file names mean, and in what order things get built.

> **Citation convention.** `§X.Y` always refers to the **[paper](paper.md)**, which is the source
> of truth. The [summary](resumen.md) has **its own numbering** — 10 sections against the paper's
> 12 — so numbers do not match between the two documents. If a `§` doesn't line up, you're looking
> at the wrong file. *Both are in Spanish.*

---

## 0. Where the project stands

**All six phases have been run.** The reference implementation runs 246 executable criteria with
31 mutations caught, plus a deterministic VM in Rust with 18 criteria of its own, also run on
aarch64. *That implementation is not in this repository* — what is here is the design, the
measurements, and the record of what building it corrected.

What remains at the end is **not design: it is external measurement**. See
[open problems](open-problems.en.md).

And the project splits into two halves with **different classes of evidence**, which is the first
thing to understand:

| half | what it is | evidence |
|---|---|---|
| **parameter succession** (§3 + I2 over a finite space) | the chain changes its own internal parameters without a vote | **taker found in the wild**: Ethereum recalibrates `blobSchedule` by hand (EIP-7892), the gas limit by schedule (EIP-8261), the difficulty bomb was delayed by fork six times |
| **the currency + the interpreter + §6.6** | its own economics, a deterministic VM, chainable cryptographic evolution | **self-generated evidence only**: it survived every attack run against it, and every one was run by whoever wrote the design |

> **The top half gets built first, and that is not a preference: it is where the evidence is.**
> The bottom half pays the most expensive boundaries in §10.1 and still has no case found in the
> wild.

**What this roadmap deliberately does not cover:** the block-0 launch. It depends on two things
that are not code — finding a buyer for the verifiable work of §6.2, and closing the open problems
of §10.3 — and the claim is **non-repeatable**, so launching early spends the only distribution
event that exists.

---

## 1. Glossary: the words to have before opening a file

In the order you need them, not alphabetical.

**Generation.** A version of the ruleset. The chain does not branch into generations: **it is one
chain that changes rules.** Generation 3 is the same chain as generation 1, with different
parameters.

**Ruleset.** The parameter set in force in a generation: issuance, fees, block size, timings,
formats. It is *data*, not code — that is the whole difference from a hard fork.

**Switching (*conmutación*).** The act of changing ruleset. **Same process, same in-memory state,
executing different rules from a given block on.** No restart, no migration, no snapshot, no
bridge. If your implementation needs to restart the node, it is not switching: it is a fork under
another name.

**`TRANSITION_RULE`.** The trigger condition. Computed **from chain state alone** (I2). It reads
no prices, no oracles, no votes, and nobody's clock.

**The three times.** Never conflate them, and there are three, not two:

1. **Trigger** — `TRANSITION_RULE` returns TRUE at block `N`. **It commits nothing**: it is
   advisory and a reorg undoes it.
2. **Lock-in** — once `N` is final, the trigger becomes **irrevocable** and the full new ruleset is
   emitted on-chain with the activation height. Waiting for finality is not ceremony: `H0_B`
   commits the state that fired, and committing earlier would leave the checkpoint pointing at a
   state a reorg can remove from the chain.
3. **Activation** — `Δ` blocks **after lock-in**, not after the trigger. That way the integrator's
   notice is exactly `Δ` and does not depend on how long finality took.

**`Δ` (delta).** The notice window, fixed at genesis **per transition class**. A circulation
transition tolerates a long `Δ`; an urgent cryptographic migration needs a short one.

**Lineage / `H0_B`.** `H0_B = H( H0_A || state_trigger || new_params )`. It is not the genesis of a
new chain: it is a **generational checkpoint marker** inside the same chain. It makes lineage
verifiable with a hash from any generation backward. Genesis A does not know B's hash — it cannot
— but it knows how it will be computed.

**The five invariants (I1–I5).** The hard frame. Each eliminates a way of putting the human back
in the loop. **In the implementation they are not documentation: they are executable assertions
every phase must keep passing** (see Phase 0).

- **I1** — the interpreter lives in genesis and **never changes**. A transition selects a point in
  a space the node already knows how to execute; it introduces no node code.
- **I2** — the trigger is computed from state alone, **and nobody picks the moment**. Computable is
  not enough: *"address X received 1 wei"* is computed from state and is a gate with an owner. There
  are two ways to satisfy it and every rule declares which: by **observable approximation** — it
  publishes *how many blocks remain at the current rate* and cannot fire from rest — or by
  **demonstrated capability** — there is no approximation and there cannot be, and producing the fact
  requires exactly the capability the transition reacts to: the canary of §6.6. *(Reformulated
  2026-08-19: the previous wording excluded the canary itself. See the [build
  log](build-log.en.md#31--phases-0-and-1--the-engine-and-three-gaps-only-visible-when-running).)*
- **I3** — state crosses the transition **intact**. No migration, no reassignment.
- **I4** — every generation commits to its ancestor.
- **I5** — transitions are **additive at the interface**. Formats can be added, never removed, and
  every object carries a generation tag from block 0.

**PoD node.** Verifies and settles, charges a fee whenever two contracts interact. Runs on any
hardware — verification reproduces bit for bit on x86-64, ARM64 and a phone. **This is the
consensus layer.**

**Compute node.** GPU and RAM, hosts the models that do the requested work. **Does not participate
in consensus.** Its revenue is payment for the request it executed.

**Acceptance predicate.** Every work request carries one: deterministic and cheap to run on the
light layer. Inference **is not verified** — what is verified is that the output satisfies the
predicate. Whatever cannot be expressed that way, the network cannot settle.

**The predicate's two ceilings.** Beyond passing the vectors, verification must happen under a cap
on **steps executed** and touching fewer than a cap of **4 KiB pages** (never wall-clock time — a
clock would be an oracle). **These are security conditions, not performance ones:** they are what
prevents a challenge that is more expensive to verify than to create.

The step cap **is not a chosen number: it is a calculation** — `f* × block_time × R_declared /
tx_per_block` — and what genesis freezes is the formula, not the value. *(Closed 2026-08-20; it was
the first open problem in §10.3.)*

The page cap **is also derived**, since 2026-08-21: it is a ruleset parameter — 96 pages of 4 KiB
at genesis — and what genesis freezes is the **curve** of rate against memory. **Phase 4 added it
and it was not in the design:** a step cap alone assumes a step is a step, and the worst instruction
mix runs 23× slower than the real load. It isn't fixed by weighting instructions — a load costs the
same as an add with the data in cache and 23× more without it, **it's the same opcode** — so you have
to count the only thing visible while running: the distinct pages it touches.

**And that was the phase's most important correction, because it touched the core:** a derived cap
*charges* — an expensive primitive enters by lowering `tx_per_block` — while a constant one **can
only exclude**. The three primitives in the ML-DSA family touch 26, 40 and 65 pages, so the first
number chosen (48) shut the third out forever. **In this design, a number you have to choose is
usually a calculation waiting to be written** — it happened twice with the same ceiling.

**Challenge window.** How finality works: an interaction becomes firm when the window passes with
nobody presenting proof of conflict. There is no quorum and no validator set. What keeps it from
saturating is an asymmetry: **filling is serial — you have to get into a block — and draining is
parallel — every PoD node does it at once.**

**Lock.** Committing funds to a contract removes them from the available balance. That is what
eliminates contention: they cannot be committed twice.

**Directed vs. open offer.** Every transfer is **bilateral** (Alice offers, Bob accepts). An
ordinary transfer names the recipient; **a work request names nobody** and is taken by whichever
node can fulfill it. It is *pull*, not *push*: **nobody assigns requests.**

**Epoch.** The time unit for permanence charging (§8.5). Not to be confused with a generation,
which runs in years.

**Permanence / eviction.** Every state entry pays to keep existing: a **floor** burned at creation,
plus a **deposit** consumed by burning, linear in size × time. When it runs out the entry is
**evicted** — it leaves the active set, it is not destroyed — and is revived with a proof. **Holding
a balance stops being free**, and that includes native-token accounts.

**Claim.** The day-1 distribution: claiming tokens **is paid for by demonstrating the capability
being claimed**. It happens once, at block 0, and afterward no action creates units.

---

## 2. If you come from Bitcoin or Ethereum, this differs in five points

This is the section that saves the most time, because these are five assumptions you arrive with
that do not hold here.

1. **There is no proof of work in consensus.** No mining, no difficulty, no block nonce, no
   hashrate. The only computation with an external cost appears **once**, in the block-0 claim, and
   it is not hashing but the reference task. **If you write a `proof_of_work.py` inside
   `consenso/`, you are building a different protocol.**
2. **There is no global order.** Each account carries its own sequence. Two interactions that share
   no collateral **have no relative order**, and that is different from having an undefined one. The
   "longest chain" is nobody's criterion.
3. **Finality is by challenge window**, not by quorum or confirmations. It is measured in minutes or
   hours, and it is a declared boundary, not a defect to optimize away.
4. **There is no unilateral send.** You cannot pay someone who is offline. The recipient signs to
   accept, and that is why *"waiting for finality"* stops being a discipline and becomes structure:
   there is no transaction until they signed.
5. **Forking is not resolved, it is prevented by construction.** The standard client switches on its
   own, so **not switching requires actively modifying the software**. Whoever stays on the old rules
   is not preserving the original chain: they are diverging from genesis, and that is verifiable with
   a hash. No "pick the good branch" logic is needed.

---

## 3. Structure

**Why the generic proposal doesn't work.** The one in the tutorials (`core/ consensus/ network/
api/` with PoW and a mempool) models a different protocol: it puts mining at the center, fork
resolution in `blockchain.py`, and has no place for **the one thing that makes this project** —
succession. A developer who opens `consensus/proof_of_work.py` has already misunderstood the
system.

The structure follows the paper's pieces, so the document ↔ code mapping is direct:

```
genesis/
├── protocolo/            # what genesis freezes and never changes (I1)
│   ├── genesis.py          # block 0: initial ruleset, descendant space,
│   │                       #   Δ per transition class, θ*, L_max
│   ├── invariantes.py      # I1-I5 as executable assertions -- not comments
│   ├── generacion.py       # generation tag on every object (I5), ruleset in force
│   └── linaje.py           # H0_B = H(H0_A || state_trigger || params) and its Verify (I4)
│
├── sucesion/             # §3 -- the core, and the first thing built
│   ├── regla.py            # TRANSITION_RULE evaluated against state (I2)
│   ├── distancia.py        # "how many blocks remain at the current rate" -- I2 requires it
│   ├── cronograma.py       # trigger -> lock-in (awaits finality) -> activation (+Δ)
│   └── conmutador.py       # the hot ruleset change: same process, same state
│
├── estado/               # I3: what crosses intact
│   ├── cuentas.py          # per-account queue, index, balance
│   ├── entradas.py         # every entry pays permanence: objects and balances alike
│   ├── arbol.py            # tree with cut depth d; the binding cost is updating, not proving
│   ├── permanencia.py      # floor, deposit, rate, L_max, epoch
│   └── desalojo.py         # append-only accumulator and revival with proof
│
├── liquidacion/          # §6.3-6.5: how an interaction closes
│   ├── oferta.py           # bilateral; directed vs. open (pull); declared timeout
│   ├── lock.py             # committing removes from available -- eliminates contention
│   ├── impugnacion.py      # window, flat bond, arrival order, parallel drain
│   └── doble_firma.py      # nonce = f(index): signing twice publishes the private key
│
├── predicado/            # §6.2 -- what the network can pay for
│   ├── aceptacion.py       # vectors + step ceiling
│   └── vm/                 # the deterministic machine. Rust, not Python -- see §5
│
├── nodo/
│   ├── pod.py              # verifies, settles, charges fees. This is the consensus layer
│   └── computo.py          # accepts requests, executes, delivers. Outside consensus
│
├── red/
│   ├── p2p.py              # node transport
│   └── sync.py             # validation and sync: the first node that does not produce
│
├── api/
│   └── server.py           # HTTP: query state, publish requests, read distance to trigger
│
└── herramientas/
    └── replay.py           # the harness against Ethereum's real history (Phase 2)
```

**Two decisions worth knowing are decisions:**

- **Module names are in Spanish** because each maps to a concept defined in a Spanish-language
  paper, and the onboarding cost here is the doc ↔ code mapping, not the language. **If this ever
  opens to the public, translating them is worthwhile** — and the sooner, the cheaper.
- **`api/` is a development convenience, not a protocol piece.** A real node speaks p2p. Don't put
  protocol logic in there.

---

## 4. The principle governing every phase

> **Every phase declares its pass and fail criteria BEFORE running.**

This is not bureaucracy, it is the most expensive lesson already paid for in this project: the
first control law for the permanence rate looked stable and absorbed a 3× shock. What knocked it
down was not an attack — it was **correcting a detail in the model it had been tested with**. A
criterion written after seeing the result accommodates itself to the result.

And its corollary, which applies to everything that follows:

> **A devnet with free tokens answers software questions, not economic ones.** With valueless
> tokens there is no revenue, no hoarding, no way to measure storage-demand elasticity, and the
> anti-spam is untested. Worse: fabricated activity is indistinguishable from real demand — and
> there it is also free. **Everything built here is disposable by declaration**, and has to be
> rewritten once it is known what parameter space genesis must anticipate.

---

## 5. The phases

### Phase 0 · Scaffolding and executable invariants

**Goal.** That I1–I5 stop being prose. Before the first line of mechanism.

The five are built as predicates that run against any state and any transition, plus the test
harness and CI that executes them on every commit.

**Pass:** every later phase keeps passing them with no exceptions and no *skips*. The day one has
to be marked as an exception, you stop and discuss the design, not the test.

### Phase 1 · The succession engine

**This is the half with a taker found; it needs no token, no VM and no economics, and does not
depend on either open problem in §10.3.**

**Pass — written before running:**

- a chain with synthetic state switches and **the state crosses bit-for-bit identical** (I3);
- `Verify(H0_B, H0_A, state_trigger, params)` returns TRUE across the whole generation chain, and
  fails if any of the three inputs is altered (I4);
- a reorg **before** lock-in undoes the trigger; **after**, it does not;
- the notice between lock-in and activation is exactly `Δ`, **independent** of how long finality
  took;
- distance to the trigger is queryable and **monotone** in the approach (I2);
- **the node does not restart.** If a restart is needed, the phase has not passed.

### Phase 2 · The replay harness — the only external evidence code produces

**Goal.** Answer with third-party data: *if the blob schedule had been a `TRANSITION_RULE` written
in advance, what would have happened?*

Real history is replayed: Ethereum's blob parameters, the gas limit of EIP-8261, and the difficulty
bomb with its six delays. The deterministic rule is run against historical state and compared with
what the humans actually decided.

**Pass:** for each case, either the rule reproduces the human decision, or it is written down
**exactly where it differs and whether that difference was better or worse**. A tie counts as a
pass; what does not count is being unable to explain the difference.

> **This phase is worth the most per unit of work in the entire roadmap**, because it is the only
> one that produces evidence the design's author did not write. It is also the one that can be
> shown to outsiders without asking anyone to believe anything.

### Phase 3 · Ordering and settlement

**Pass:**

- double-spend impossible via the lock, with no global order;
- **double-signing publishes the private key** and anyone can sweep the balance — verified with two
  signatures and a subtraction;
- under adversarial load with `N` nodes, the queue **drains faster than it fills**, and the measured
  margin is compared against the ten PoD nodes §6.3 predicts. If a hundred are needed, the paper's
  prediction is wrong and it has to be said.

### Phase 4 · The VM and the predicate

**Here the language changes, deliberately.** The deterministic machine **is not written in Python**:
the six-engine Rust harness from `test2-interprete/telefono` already exists, with `steps_per_verify`
measured identical across architectures. It gets reused.

**Pass:**

- the interpreter's budget fits **under real block load**, not in an isolated benchmark;
- floating point is forbidden or canonicalized **before the challenge runs for the first time** — it
  is a condition on genesis and cannot be lifted afterward;
- step counting reproduces bit for bit between x86-64 and ARM64.

**Run 2026-08-20, six criteria passed and the seventh failed** — and the failure is what made the
phase worth it. Four criteria were added to the roadmap's three upon reading the interpreter to be
reused: the Test 2 harness runs a trusted guest and this runs an adversary's program. Adding
criteria is allowed; softening them is not.

> **The finding:** the step ceiling promised a budget it missed **by 23×**, because a step is not a
> step. Out of that came a second ceiling on pages touched, `R_declared` going from 300 to 70 M
> steps/s, and initial capacity from 67 to 15 tx per block. Plus two amplification holes in the
> loader that no correctness test would have found — they were found because a sweep took minutes.

**Closed 2026-08-21**, with all seven criteria resolved: the vectors reproduce bit for bit between
x86-64 and aarch64, and the block-load criterion is measured on the reference hardware (354 ms out
of 1,500, margin 4.24×).

> **And it left an open problem the paper did not have:** which hardware is the worst case. The
> design assumes the light layer is the binding constraint, and measured that is false for
> adversarial memory patterns. **Two machines are not enough to set a hardware floor** — closing it
> needs more machines, not more analysis.

### Phase 5 · State with a cost

**Pass:** the create → pay → exhaust → evict → revive cycle closes completely; the accumulator stays
in the order of hundreds of bytes **in total** rather than per object; and it is measured what it
actually costs to keep a revival proof current, which is the archival dependency §10.2 declares and
cannot guarantee.

**Run 2026-08-21**, with eight criteria passed and one failed — and the failure was **against the
paper**: §8.5 claimed the floor worked out to sixteen hours of storage, and the calculation, once
written, gives a different order of magnitude.

**Still blocked where it was:** the rule that moves the rate is not chosen and there is nothing to
calibrate it against. What did close is **why that is not a calculation waiting to be written but a
boundary** — the ceiling had both sides physical and the rate has one monetary side, and no
calculation crosses that without reading a price. From that came denominating the floor in storage
epochs, which turned **the open problem into one number instead of two**.

### Phase 6 · The disposable devnet

Only here does everything come together and a token appear — **with the warning from section 4 in
writing and a reset date declared in advance.**

**What it is for:** closing the four mechanism questions nothing else answers — real switching under
load, the queue with a real `N`, the budget under real blocks, the eviction cycle.

**What it is not for, and don't get confused:** knowing whether anyone leaves a GPU running, what
the elasticity of storage demand is, whether the currency gets hoarded, or whether the anti-spam
holds. **That needs real money or external review, and goes down a different track.**

**Run 2026-08-21, narrowed to two of the four questions** — the queue with a real `N` was answered by
Phase 3 and the budget under real blocks by Phase 4, and re-running what is already measured adds no
evidence but does add the temptation to stare at the number until it comes out right.

> **The finding:** the permanence deposit was bought in byte-**epochs**, an epoch is counted in
> blocks, and block time is an internal parameter — so a switch that moved it made **an
> already-paid deposit buy twice the storage**. I3 held: the bytes crossed identical. What changed
> was what they were worth, and **none of the five invariants looks at that.** Corrected by
> denominating in declared byte-seconds.

---

## 6. What runs in parallel and is not code

Two things that decide more than any phase above, and that arrive too late if they wait for the
code:

- **Find a buyer for the verifiable work of §6.2.** It is the design's most expensive hypothesis and
  the only one never taken out to be falsified: the four tests measure the succession half and none
  asks whether anyone would buy this. **It needs no protocol** — a manual broker with real payment
  is enough. Ten real transactions say more than ten thousand on a devnet.
- **External adversarial review.** The design survived only the attacks of whoever wrote it. It is
  cheap and comes back fast, and this repository is built for it: see [open
  problems](open-problems.en.md), which opens with where to hit first.
