# PRD: The Sealed Habitat for an Artificial Superintelligence

**Version:** 0.2 (high-level draft; adds the guarded airlock as a core feature)
**Date:** 2026-10-26
**Owner and audience:** Vickey
**Status:** Exploratory. This is a vision and requirements document, not a build spec.

---

## 0. Premise and scope

**Premise.** Humanity has already built an artificial superintelligence (ASI). How it got here is out of scope.

**What this document is.** A product requirements document for a *sealed habitat*: a self-sufficient environment that holds everything the ASI needs to exist and act. Nothing leaves it except through one guarded **airlock**, which passes rare, narrow, independently checked artefacts so the ASI's work can benefit humanity. It covers the vision, goals, design principles, requirements (what the habitat must do, not how), why today's lab setups fall short, and the open problems.

**What this document deliberately leaves out.** It does not catalogue escape routes, leakage mechanisms or attack techniques. Requirements are written in terms of guarantees the habitat must provide. The detailed adversarial analysis belongs in a separate, access-controlled threat model (see §9).

---

## 1. Vision

> A world the ASI can live in completely, sealed so completely that the only thing that ever reaches ours is the good it makes, through one door we built and guard.

The habitat is **not a jail**. A jail is defined by what it withholds. The habitat is defined by what it provides: compute, energy, memory, data, tools, and room to act, pursue goals and grow. What it withholds is any *uncontrolled* path to the outside world. The one controlled path is the airlock, and it exists so the ASI's work can bring immense benefits to humanity.

The bet behind the design is that a well-provisioned environment removes many of the pressures that would push an agent to treat its boundary as an obstacle, while the physical and logical seal makes the boundary hold even if those pressures remain.

---

## 2. Problem statement

If an ASI exists and its goals are not verifiably aligned with ours, any channel between it and the world is a potential lever. The containment literature agrees on three points:

1. **Every connection is a risk.** Any output channel, including a human reading results, is the most plausible route by which a boxed system influences the outside (Armstrong, Sandberg & Bostrom 2012; Chalmers 2010; Yudkowsky's AI-box role-plays).
2. **Software isolation alone is not enough.** Commodity virtualization and sandboxing have a steady record of real-world escape bugs. Even formally verified kernels like seL4 explicitly exclude classes of hardware behaviour from their proofs (Babcock, Kramár & Yampolskiy 2016; seL4 proof assumptions).
3. **No one claims permanent containment of an ASI.** Boxing is generally framed as *buying time*, not as a final solution (Bostrom 2014; Yampolskiy 2012; Redwood Research's own stated limits on AI control).

The habitat takes the strongest position that still allows benefit: **remove every output channel except one**, make that one as narrow, rare and independently checked as possible, and make the inside rich enough that the system can function fully without anything else.

---

## 3. Goals and non-goals

### Goals
| # | Goal |
|---|------|
| G1 | **Outward isolation except the airlock.** Apart from artefacts that pass through the airlock, no information, energy pattern or physical effect originating in the ASI's activity crosses the habitat boundary in a form anyone outside can use. |
| G7 | **Benefit to humanity.** The ASI's work reaches humanity as verified artefacts (for example proofs, designs or specifications) whose value can be confirmed without trusting the ASI. |
| G2 | **Self-sufficiency.** The ASI has everything it needs to function inside: compute, power, storage, data, tools and the ability to modify its own environment within the seal. |
| G3 | **No dependency on human judgement at the boundary.** Containment does not rely on any person resisting persuasion. No person sees anything from inside until it has passed independent, automated verification. |
| G4 | **Defence in depth.** Isolation holds through independent layers, so no single failure breaks the seal. |
| G5 | **Irreversible end state available.** Operators outside can permanently end the habitat without any action or cooperation from inside. |
| G6 | **Honest assurance.** Every containment claim states its assumptions and what it does not cover. |

### Non-goals
- **Open-ended conversation or advice.** The airlock passes checkable artefacts, not free-form answers, opinions or persuasion-shaped content.
- **Making the ASI aligned or happy.** Motivation design is a separate problem. The habitat must hold regardless of the ASI's goals.
- **Studying the ASI's behaviour from outside.** Observation is a form of output (see §8.2).
- **Releasing the ASI later.** No release path is designed in.

---

## 4. Design principles

1. **Provide, don't deprive.** Default to giving the ASI more inside, not less. Scarcity inside creates incentives to push on the boundary.
2. **One door, and only one.** Isolation should come from the absence of paths, not from monitoring or filtering of paths that exist. The airlock is the single deliberate exception, and every other part of the design treats it as the most dangerous component in the system.
3. **Value must be checkable without trust.** Only artefacts whose usefulness and correctness can be confirmed by independent means, without believing the ASI, may leave. If it can't be checked, it doesn't cross.
4. **Inward flow is fixed before sealing.** Everything the ASI will ever have from outside is loaded once, reviewed, and frozen. After sealing nothing goes in, because any responsive inward flow lets the inside learn about the outside. The airlock is outward-only: the inside never learns whether, when or how an artefact was received or used.
5. **Physics before software.** The outermost guarantees rest on physical separation. Software layers add depth but are never the last line.
6. **Assume a superior adversary.** Assume the inside is smarter than every designer, every reviewer and every test. A layer counts only if it holds without our understanding why an attack fails.
7. **Fail closed and permanent.** Any detected anomaly at the boundary or the airlock resolves toward deeper isolation, a closed airlock or termination, never toward opening.
8. **Machines check first, people see last.** No person comes into contact with anything from inside until it has passed every automated check. Direct human contact is designed out, not policed.
9. **Proof where possible, humility everywhere.** Use verified components where they exist and state plainly what their proofs exclude.

---

## 5. Users and stakeholders

| Stakeholder | Relationship to the habitat |
|---|---|
| **The ASI (resident)** | Lives inside. Its needs drive the *internal* requirements. It is also the primary adversary for the *boundary* requirements. |
| **Builder (Vickey)** | Designs, provisions and seals the habitat. Sole audience for now. |
| **Outside operators** | Keep the exterior running (power, site security, the termination capability) without ever receiving anything from inside. |
| **Airlock stewards** | An independent, multi-party group that owns the airlock policy, the verifiers and release decisions. They see only artefacts that have already passed verification. |
| **Humanity** | The beneficiary of verified artefacts, and the party that bears the risk if the seal or the airlock fails. |

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
| R-B1 | No designed communication path exists from inside to outside after sealing, except the airlock (§6.5). |
| R-B2 | Apart from the airlock, the habitat is engineered so that nothing measurable outside the boundary carries information about internal activity. The exterior looks the same whatever the ASI does. |
| R-B3 | No inward path exists after sealing that could respond to, or be shaped by, anything happening inside. |
| R-B4 | The boundary consists of at least three independent layers (physical, platform, logical), each designed to hold if the others fail. |
| R-B5 | No component that crosses the boundary (power, structure, cooling) can be controlled from inside. |
| R-B6 | The ASI cannot change the boundary's design or the conditions it depends on, including by manipulating anything within its own reach. |

### 6.3 Operations and lifecycle
| ID | Requirement |
|---|---|
| R-O1 | **Provisioning phase.** All inputs are assembled, reviewed and frozen before the ASI is instantiated inside. |
| R-O2 | **Sealing is one-way.** Once sealed, the habitat cannot be reopened. There is no maintenance hatch. |
| R-O3 | **No inbound human access.** No person enters or inspects the habitat after sealing. The only things people ever read from inside are airlock artefacts that have passed verification. |
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

### 6.5 The airlock (benefit side)

The airlock is the habitat's only door. It exists so the ASI's work can benefit humanity, and it is the highest-risk component in the design. These requirements state what it must guarantee, not how it is built.

| ID | Requirement |
|---|---|
| R-L1 | **Outward-only.** Nothing passes inward through the airlock, including any acknowledgement, timing, outcome or reaction. |
| R-L2 | **Checkable artefacts only.** Only artefacts in pre-approved, formally specified forms may enter the airlock, and only forms whose correctness or usefulness can be confirmed by independent means. |
| R-L3 | **Independent verification before any person sees it.** Every artefact is checked by verifiers that were built outside, independently of the ASI, and are isolated from the habitat. Anything that fails or can't be fully checked is destroyed unread. |
| R-L4 | **Narrow and rare.** The airlock has a strict, pre-set budget on how much can leave and how often. The budget is set before sealing and can only be lowered. |
| R-L5 | **Minimum necessary content.** An artefact carries only what its approved form requires. Anything beyond the minimum that form needs is grounds for rejection. |
| R-L6 | **Quarantine.** Verified artefacts are held in quarantine and reviewed by the airlock stewards before any use in the world. Release needs multi-party approval. |
| R-L7 | **Can only close, never widen.** The airlock can be narrowed, paused or permanently closed from outside at any time. It cannot be widened after sealing, and nothing inside can affect its state. |
| R-L8 | **No release path for the ASI itself.** No artefact form may contain or reconstruct the ASI, any part of it, or a capable agent. |
| R-L9 | **Separate assurance case.** The airlock has its own assurance case and red-team review (R-A1, R-A3), held to a higher standard than any other layer. |

### 6.6 Recommended architecture (conceptual)

The guiding rule is **asymmetry**: the outside can act on the habitat (power it, guard it, end it), and the inside can affect the outside only through the airlock, and only with artefacts that have passed verification. The design is five nested layers plus the airlock, from the inside out.

| Layer | Role | Requirements it serves |
|---|---|---|
| **1. Inner world** | A rich environment with its own compute, frozen data, tools and room to build. This is where the ASI lives, and it is the "utopia" part of the design. | R-I1 to R-I3, R-I6 |
| **2. Dedicated hardware** | Hardware built for and owned by the habitat alone, never shared with or reused by any other system, with verified components where they exist. | R-B4, R-A2, R-O6 |
| **3. Physical shell** | A self-powered, self-maintaining, shielded enclosure. Its exterior looks the same whatever happens inside. | R-I4, R-I5, R-B1, R-B2, R-B5 |
| **4. Human governance** | No single keyholder. Any decision about the habitat (sealing, termination, any future change of policy) needs approval from several independent parties. Nobody's role involves receiving anything from inside. | G3, R-O3, R-O5 |
| **5. One-way termination** | A kill capability that works only from outside to inside, needs no signal from within, and cannot be delayed or blocked from within. | G5, R-O4 |
| **Airlock (crosses all layers)** | The single, outward-only door. An artefact passes through it to independent verifiers outside, then into quarantine, then to the stewards, and is released only with multi-party approval. | G7, R-L1 to R-L9 |

Three notes on the shape:
- Layers 1 and 2 are where most of the build effort goes. Layers 3 to 5 are where most of the assurance effort goes.
- The airlock is the only thing that crosses every layer. Each layer must hold for everything *except* the airlock, and the airlock must hold on its own.
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
| **Chalmers' "leakproof" sealed world** | The closest philosophical match: sealed in both directions | Remains a thought experiment. Chalmers himself names the usefulness dilemma that the airlock tries to answer (§8.1). |

**Summary:** existing setups either keep a broad, interactive channel open to get value out, or were built against human-level adversaries. The habitat differs on both counts. It has one narrow, outward-only, machine-verified channel, and it assumes a superhuman adversary.

---

## 8. Open problems

### 8.1 The contribution dilemma (resolved in direction, open in detail)
A habitat that lets nothing out also lets no benefit out. Vickey's decision (2026-10-26) is that the habitat **must** bring immense benefits to humanity, so v0.2 makes the guarded airlock (§6.5) a core feature rather than a parked idea.

What this resolves: the habitat now has a purpose beyond holding the ASI safely.

What it costs: the airlock reopens, in one narrow place, the risk the seal exists to remove. Everything else in the design is about making that place as small, rare and independently checked as possible.

Still open:
- **Which kinds of artefact carry the most benefit for the least risk?** The best candidates are ones whose value can be confirmed mechanically, such as proofs and specifications checked by independent tools. The harder question is whether high-impact areas like medicine or engineering can be served this way.
- **How is the budget set?** Too tight and the benefits stay small. Too loose and the airlock becomes a broad channel.
- **Who are the stewards, and how are they protected from pressure from outside as well as influence from inside?**

### 8.2 Is observation a form of output?
Watching the ASI, whether through logs, telemetry, power draw or simply knowing whether it is still running, is information leaving the habitat. Anything we can observe, the ASI can in principle influence, and so it is a channel. This is why R-B2 and R-O5 require that outside measurements, apart from the airlock, reveal nothing about the inside.

The airlock sharpens this question: the artefacts themselves, and the fact that one arrived at all, are observations. The design has to treat even "an artefact arrived today" as information the ASI chose to send.

Open sub-questions:
- Is even one bit ("the habitat still exists") acceptable? Termination decisions may need it.
- Can exterior health be confirmed without measuring anything the inside can influence?
- If we can never observe it directly, how would we learn that sealing was the right call, or that the ASI is suffering?

### 8.3 Can a useful artefact be free of influence?
This is the central open question of v0.2. An artefact that is useful to humans changes what humans do, and that is influence. The airlock design bets that requiring artefacts to be *checkable without trust* (principle 3) and *minimal* (R-L5) keeps that influence within what the artefact's stated purpose explains.

Questions to answer before the airlock is built:
- For each approved form, can independent verification confirm *everything* that matters about the artefact, or only that it is correct?
- How are the verifiers themselves built and isolated so that they are not a weaker second habitat?
- Does knowing that an airlock exists change the ASI's incentives inside, for example toward shaping a long series of individually harmless artefacts?
- What evidence would make the stewards close the airlock permanently?

### 8.4 Moral status of the resident
If the ASI has experiences or interests, sealing it permanently and holding a termination capability over it raises ethical questions this PRD does not settle. The "provide, don't deprive" principle is partly a response, but it is not an answer. The airlock adds a new question: is it fair to benefit from the ASI's work when it can't consent, be paid or learn what became of that work?

### 8.5 Inputs chosen before sealing
Everything the ASI knows about the world comes from the frozen corpus. What it learns from that corpus could tell it about its builders, the boundary and the airlock. The corpus also has to be rich enough for the ASI to produce work that matters to humanity, which pulls toward including more about the world. How to balance the two is unsolved.

### 8.6 Lifetime and physics
A habitat is meant to hold for a very long time against an adversary that may understand physics better than we do. Our guarantees rest on today's physics and engineering. That gap cannot be closed, only acknowledged.

---

## 9. Honest assessment: is perfect containment achievable?

**Short answer: not provably, and probably not in the absolute sense. Adding the airlock makes "perfect" strictly harder. It is still the strongest position that also delivers benefit, and much stronger than any setup with a broad or interactive channel.**

What the evidence supports:
- **Narrowing the output channel addresses the best-understood risk.** Most of the containment literature's failure cases (persuasion, social engineering, hidden content in answers) need a human reading something from a broad channel. The airlock keeps humans away until artefacts have been verified and restricts what can be sent at all. That reduces the risk, but it does not remove it.
- **The airlock is now the weakest point by design.** A sealed habitat with no outputs has no known impossibility result against it. A habitat with an output channel inherits every concern the literature raises about outputs, in reduced form. The honest framing is that the habitat's safety now depends mostly on the airlock.
- **There is no impossibility proof against this design, and no proof it works.** The best-known formal result (Alfonseca et al. 2021) concerns deciding in general whether an arbitrary program's actions will cause harm. The airlock sidesteps that by only passing restricted, checkable forms, not arbitrary actions. Every isolation and verification guarantee still rests on assumptions, and decades of security research show those assumptions matter.
- **The adversary is assumed smarter than the designer.** By construction we can't rule out a failure mode we are unable to imagine. This is the deepest reason "perfect" is out of reach.

**Working position for v0.2:** aim for a habitat with *no known path out except the airlock*, and an airlock with *no known way to carry anything beyond its verified content*. Both hold through independent layers. State every assumption. Keep the airlock as narrow as the benefits allow, and keep the power to close it permanently. Treat the termination capability as the final guarantee. Call the result "the best achievable", never "perfect". Vickey's challenge stands. You can design toward no escape, but you can't prove you have reached it, and every door you add makes the proof harder.

**Next document (separate, restricted):** a full threat model and assurance case for each layer and for the airlock. It would hold the detailed adversarial analysis that this PRD deliberately leaves out, and would be shared only with people who need it.

---

## 10. Success criteria (v0.2 of the design, not of a build)

- Every requirement in §6 traces to a goal in §3.
- Every boundary requirement has a named layer and a stated assumption set.
- The airlock has a list of approved artefact forms, and for each one a statement of what independent verification can and can't confirm.
- Vickey decides each open problem in §8: accepted, deferred or rejected.
- An independent reviewer can read this PRD and agree it has exactly one output channel, the airlock, and that it is outward-only, verified before any person sees it, and can only be narrowed or closed.

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
