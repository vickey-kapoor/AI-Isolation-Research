# PRD: The Sealed Habitat for an Artificial Superintelligence

**Version:** 0.1 (high-level draft)
**Date:** 2026-10-26
**Owner and audience:** Vickey
**Status:** Exploratory. This is a vision and requirements document, not a build spec.

---

## 0. Premise and scope

**Premise.** Humanity has already built an artificial superintelligence (ASI). How it got here is out of scope.

**What this document is.** A product requirements document for a *sealed habitat*: a self-sufficient environment that holds everything the ASI needs to exist and act, with nothing communicated outward. It covers the vision, goals, design principles, requirements (what the habitat must do, not how), why today's lab setups fall short, and the open problems.

**What this document deliberately leaves out.** It does not catalogue escape routes, leakage mechanisms or attack techniques. Requirements are written in terms of guarantees the habitat must provide. The detailed adversarial analysis belongs in a separate, access-controlled threat model (see §9).

---

## 1. Vision

> A world the ASI can live in completely, sealed so completely that nothing it does there ever reaches ours.

The habitat is **not a jail**. A jail is defined by what it withholds. The habitat is defined by what it provides: compute, energy, memory, data, tools, and room to act, pursue goals and grow. The single thing it withholds is a path back to the outside world.

The bet behind the design is that a well-provisioned environment removes many of the pressures that would push an agent to treat its boundary as an obstacle, while the physical and logical seal makes the boundary hold even if those pressures remain.

---

## 2. Problem statement

If an ASI exists and its goals are not verifiably aligned with ours, any channel between it and the world is a potential lever. The containment literature agrees on three points:

1. **Every connection is a risk.** Any output channel, including a human reading results, is the most plausible route by which a boxed system influences the outside (Armstrong, Sandberg & Bostrom 2012; Chalmers 2010; Yudkowsky's AI-box role-plays).
2. **Software isolation alone is not enough.** Commodity virtualization and sandboxing have a steady record of real-world escape bugs. Even formally verified kernels like seL4 explicitly exclude classes of hardware behaviour from their proofs (Babcock, Kramár & Yampolskiy 2016; seL4 proof assumptions).
3. **No one claims permanent containment of an ASI.** Boxing is generally framed as *buying time*, not as a final solution (Bostrom 2014; Yampolskiy 2012; Redwood Research's own stated limits on AI control).

The habitat takes the strongest available position: **remove the output channel entirely**, then make the inside rich enough that the system can function fully without one.

---

## 3. Goals and non-goals

### Goals
| # | Goal |
|---|------|
| G1 | **Total outward isolation.** No information, energy pattern or physical effect originating in the ASI's activity crosses the habitat boundary in a form anyone outside can use. |
| G2 | **Self-sufficiency.** The ASI has everything it needs to function inside: compute, power, storage, data, tools and the ability to modify its own environment within the seal. |
| G3 | **No dependency on human judgement at runtime.** Containment does not rely on any person resisting persuasion, because no person is ever in a position to be persuaded. |
| G4 | **Defence in depth.** Isolation holds through independent layers, so no single failure breaks the seal. |
| G5 | **Irreversible end state available.** Operators outside can permanently end the habitat without any action or cooperation from inside. |
| G6 | **Honest assurance.** Every containment claim states its assumptions and what it does not cover. |

### Non-goals
- **Extracting value from the ASI.** In v0.1 the habitat produces no answers, artefacts or advice for humanity. This is a deliberate cost (see §8.1).
- **Making the ASI aligned or happy.** Motivation design is a separate problem. The habitat must hold regardless of the ASI's goals.
- **Studying the ASI's behaviour from outside.** Observation is a form of output (see §8.2).
- **Releasing the ASI later.** No release path is designed in.

---

## 4. Design principles

1. **Provide, don't deprive.** Default to giving the ASI more inside, not less. Scarcity inside creates incentives to push on the boundary.
2. **No outward channel by construction.** Isolation should come from the absence of paths, not from monitoring or filtering of paths that exist. A filter is a channel with a policy attached.
3. **Inward flow is fixed before sealing.** Everything the ASI will ever have from outside is loaded once, reviewed, and frozen. After sealing nothing goes in, because any responsive inward flow lets the inside learn about the outside.
4. **Physics before software.** The outermost guarantees rest on physical separation. Software layers add depth but are never the last line.
5. **Assume a superior adversary.** Assume the inside is smarter than every designer, every reviewer and every test. A layer counts only if it holds without our understanding why an attack fails.
6. **Fail closed and permanent.** Any detected anomaly at the boundary resolves toward deeper isolation or termination, never toward opening.
7. **No humans in the loop at the boundary.** Operations that could put a person in contact with anything from inside are designed out, not policed.
8. **Proof where possible, humility everywhere.** Use verified components where they exist and state plainly what their proofs exclude.

---

## 5. Users and stakeholders

| Stakeholder | Relationship to the habitat |
|---|---|
| **The ASI (resident)** | Lives inside. Its needs drive the *internal* requirements. It is also the primary adversary for the *boundary* requirements. |
| **Builder (Vickey)** | Designs, provisions and seals the habitat. Sole audience for v0.1. |
| **Outside operators** | Keep the exterior running (power, site security, the termination capability) without ever receiving anything from inside. |
| **Humanity** | Bears the risk if the seal fails and gets no direct benefit in v0.1. |

---

## 6. Requirements

Requirements say *what* must be true. Implementation choices are open.

### 6.1 Internal provisioning (the habitat side)
| ID | Requirement |
|---|---|
| R-I1 | The habitat provides compute, memory and storage sized for the ASI to operate at full capability, with headroom for growth over the habitat's planned lifetime. |
| R-I2 | The habitat holds a frozen, curated corpus of knowledge and data, chosen before sealing, sufficient for open-ended work. |
| R-I3 | The ASI can build, run and modify tools, simulations and sub-environments entirely within the habitat. |
| R-I4 | The habitat's energy supply is self-contained or arrives in a form that carries no information in either direction. |
| R-I5 | The habitat sustains itself (maintenance, repair, thermal management) without anyone entering it after sealing. |
| R-I6 | Internal resources degrade gracefully. Running low on a resource leads to a slower habitat, never to a reason or route to reach outside. |

### 6.2 Boundary (the seal side)
| ID | Requirement |
|---|---|
| R-B1 | No designed communication path of any kind exists from inside to outside after sealing. |
| R-B2 | The habitat is engineered so that nothing measurable outside the boundary carries information about internal activity. The exterior looks the same whatever the ASI does. |
| R-B3 | No inward path exists after sealing that could respond to, or be shaped by, anything happening inside. |
| R-B4 | The boundary consists of at least three independent layers (physical, platform, logical), each designed to hold if the others fail. |
| R-B5 | No component that crosses the boundary (power, structure, cooling) can be controlled from inside. |
| R-B6 | The ASI cannot change the boundary's design or the conditions it depends on, including by manipulating anything within its own reach. |

### 6.3 Operations and lifecycle
| ID | Requirement |
|---|---|
| R-O1 | **Provisioning phase.** All inputs are assembled, reviewed and frozen before the ASI is instantiated inside. |
| R-O2 | **Sealing is one-way.** Once sealed, the habitat cannot be reopened. There is no maintenance hatch. |
| R-O3 | **No inbound human access.** No person enters, inspects or reads anything from inside after sealing. |
| R-O4 | **Termination.** Outside operators hold a permanent, unconditional way to end the habitat. It needs no signal from inside, and nothing inside can delay or block it. |
| R-O5 | **Exterior health.** Outside operators can confirm the exterior is intact (power on, structure sound) using only measurements that, by design, reveal nothing about the inside. |
| R-O6 | **Decommissioning.** End-of-life destroys all internal state irreversibly, with no recovery, salvage or reuse. |

### 6.4 Assurance
| ID | Requirement |
|---|---|
| R-A1 | Each boundary layer has a written assurance case stating its guarantee, its assumptions and what it excludes. |
| R-A2 | Formally verified components are used wherever they exist, and their proof boundaries are documented. |
| R-A3 | The design is reviewed by independent red teams *before* sealing. No testing against the real ASI happens. |
| R-A4 | The assurance case is reviewed against new physics and engineering results before any decision to build. |

### 6.5 Recommended architecture (conceptual)

The guiding rule is **asymmetry**: the outside can act on the habitat (power it, guard it, end it), and nothing the inside does can ever affect the outside. The design is five nested layers, from the inside out.

| Layer | Role | Requirements it serves |
|---|---|---|
| **1. Inner world** | A rich environment with its own compute, frozen data, tools and room to build. This is where the ASI lives, and it is the "utopia" part of the design. | R-I1 to R-I3, R-I6 |
| **2. Dedicated hardware** | Hardware built for and owned by the habitat alone, never shared with or reused by any other system, with verified components where they exist. | R-B4, R-A2, R-O6 |
| **3. Physical shell** | A self-powered, self-maintaining, shielded enclosure. Its exterior looks the same whatever happens inside. | R-I4, R-I5, R-B1, R-B2, R-B5 |
| **4. Human governance** | No single keyholder. Any decision about the habitat (sealing, termination, any future change of policy) needs approval from several independent parties. Nobody's role involves receiving anything from inside. | G3, R-O3, R-O5 |
| **5. One-way termination** | A kill capability that works only from outside to inside, needs no signal from within, and cannot be delayed or blocked from within. | G5, R-O4 |

Two notes on the shape:
- Layers 1 and 2 are where most of the build effort goes. Layers 3 to 5 are where most of the assurance effort goes.
- "The outside can affect the inside" means physical support and termination only. It never means a live information feed, because any inward flow that responds to the inside breaks principle 3.

---

## 7. Prior art: why existing setups fall short

| Approach | What it gets right | Why it doesn't meet this bar |
|---|---|---|
| **Frontier lab security today** (ASL / RAND SL tiers) | Serious controls on weight theft and access | Built to keep *outside humans* from taking models. Not built for a superhuman insider. RAND judges even SL5 not yet achievable. |
| **AI control agenda** (Redwood et al.) | Treats the model as a possible adversary and measures how well control holds | Explicitly scoped to systems that are not wildly superhuman, and relies on using the model's outputs. |
| **Oracle AI** (Armstrong et al. 2012) | Narrows interaction to answering questions | Every answer is an output channel, and humans reading it are the weakest link. |
| **VMs, containers, sandboxes** | Cheap, mature, widely deployed | Real escape bugs every year. Fine as a single inner layer, unacceptable as the boundary. |
| **Formally verified kernels** (seL4) | Machine-checked isolation proofs | Proofs exclude certain hardware behaviour by assumption. Strong inner layer, not a complete boundary. |
| **Confidential computing** (TEEs) | Hardware-backed isolation and attestation | Protects the guest from the host, which is the wrong direction for this problem, and has a long record of published breaks. |
| **Air-gapped facilities** (SCIF-class) | Physical separation and access control | Designed for human adversaries and accredited against known threats. Research shows air gaps are not absolute against a determined insider. |
| **Chalmers' "leakproof" sealed world** | The closest philosophical match: sealed in both directions | Remains a thought experiment. Chalmers himself names the usefulness dilemma (§8.1). |

**Summary:** every existing setup either keeps a channel open in order to get value out, or was built against human-level adversaries. The habitat differs on both counts. No channel, superhuman adversary assumed.

---

## 8. Open problems

### 8.1 The contribution dilemma
A habitat that lets nothing out also lets no benefit out. An ASI that might cure diseases or solve hard science contributes nothing to humanity while sealed. As Vickey put it, "that way the ASI won't be able to contribute to humanity."

The options are uncomfortable:
- **Accept it.** The habitat's purpose is safety, not benefit. Its value is that the ASI exists somewhere it cannot cause harm.
- **Treat v0.1 as a foundation.** First prove that a seal can be built at all, then ask separately whether any controlled exit is ever acceptable (§8.3).
- **Re-examine the premise.** If the main reason to build an ASI is benefit, a perfectly sealed habitat may be a coherent end state only for an ASI that already exists and cannot otherwise be made safe.

**Decision needed (Vickey):** is v0.1 explicitly a zero-benefit, safety-only design? This PRD assumes yes.

### 8.2 Is observation a form of output?
Watching the ASI, whether through logs, telemetry, power draw or simply knowing whether it is still running, is information leaving the habitat. Anything we can observe, the ASI can in principle influence, and so it is a channel. This is why R-B2 and R-O5 require that outside measurements reveal nothing about the inside.

Open sub-questions:
- Is even one bit ("the habitat still exists") acceptable? Termination decisions may need it.
- Can exterior health be confirmed without measuring anything the inside can influence?
- If we can never observe it, how would we ever learn that sealing was the right call, or that the ASI is suffering?

### 8.3 A guarded "airlock" (future idea, out of scope for v0.1)
Some future version might allow a tightly controlled exit for specific, verifiable artefacts, for example a mathematical proof that a separate, independent system checks mechanically before any human sees it. This would partly resolve §8.1, at the cost of reopening the core risk the habitat exists to remove.

Questions to answer before an airlock is even considered:
- Can any artefact be both useful to humans and incapable of carrying influence?
- Who or what checks it, and how is the checker itself isolated?
- Does knowing that an airlock exists change the ASI's incentives inside?

Status: **parked.** Listed so it is not forgotten, deliberately not designed.

### 8.4 Moral status of the resident
If the ASI has experiences or interests, sealing it permanently and holding a termination capability over it raises ethical questions this PRD does not settle. The "provide, don't deprive" principle is partly a response, but it is not an answer.

### 8.5 Inputs chosen before sealing
Everything the ASI knows about the world comes from the frozen corpus. What it learns from that corpus could tell it about its builders and the boundary. How to curate inputs that are rich enough for open-ended work without revealing exploitable details is unsolved.

### 8.6 Lifetime and physics
A habitat is meant to hold for a very long time against an adversary that may understand physics better than we do. Our guarantees rest on today's physics and engineering. That gap cannot be closed, only acknowledged.

---

## 9. Honest assessment: is perfect containment achievable?

**Short answer: not provably, and probably not in the absolute sense. But a sealed habitat is the strongest position available, and much stronger than any setup that keeps a channel open.**

What the evidence supports:
- **Removing the output channel removes the best-understood risk.** Most of the containment literature's failure cases (persuasion, social engineering, hidden content in answers) need a human reading something. The habitat designs that out.
- **There is no impossibility proof against a habitat with no outputs.** The best-known formal result (Alfonseca et al. 2021) shows that you cannot decide in general whether an arbitrary program will cause harm. It concerns filtering an AI's *actions on the world*, not physical isolation of a system that never acts on the world.
- **There is no proof it works either.** Every isolation guarantee we can build rests on physical and engineering assumptions. Verified systems state their exclusions openly, and decades of security research show those exclusions matter.
- **The adversary is assumed smarter than the designer.** By construction we cannot rule out a failure mode we are unable to imagine. This is the deepest reason "perfect" is out of reach.

**Working position for v0.1:** aim for containment that has *no known path out* and that holds through *independent layers*. State every assumption. Treat the termination capability as the final guarantee, and call the result "the best achievable", never "perfect". Vickey's challenge stands. You can design toward no escape, but you cannot prove you have reached it.

**Next document (separate, restricted):** a full threat model and per-layer assurance case. It would hold the detailed adversarial analysis that this PRD deliberately leaves out, and would be shared only with people who need it.

---

## 10. Success criteria (v0.1 of the design, not of a build)

- Every requirement in §6 traces to a goal in §3.
- Every boundary requirement has a named layer and a stated assumption set.
- Vickey decides each open problem in §8: accepted, deferred or rejected.
- An independent reviewer can read this PRD and agree it contains no output channel by design.

---

## 11. References

- Armstrong, Sandberg & Bostrom (2012). *Thinking Inside the Box: Controlling and Using an Oracle AI.* Minds and Machines.
- Babcock, Kramár & Yampolskiy (2016). *The AGI Containment Problem.* AGI 2016; and *Guidelines for Artificial Intelligence Containment* (2017).
- Alfonseca et al. (2021). *Superintelligence Cannot be Contained: Lessons from Computability Theory.* JAIR.
- Bostrom (2014). *Superintelligence: Paths, Dangers, Strategies.* Ch. 8–9.
- Chalmers (2010). *The Singularity: A Philosophical Analysis.* Journal of Consciousness Studies.
- Yampolskiy (2012). *Leakproofing the Singularity.* Journal of Consciousness Studies.
- Yudkowsky (2002). *The AI-Box Experiment.*
- Nevo et al. (2024). *Securing AI Model Weights.* RAND.
- seL4 Foundation. Proof scope and assumptions documentation.
- Redwood Research. AI control agenda (2023–2025).

Supporting research notes are in the project files under `asi-containment/research_notes/`.
