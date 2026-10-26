# Phase 0 plan: a learning baseline on today's isolation tech

**Status:** agreed with Vickey on 2026-10-26 (revision 2)
**Timebox:** three weeks, 2026-10-27 to 2026-11-16
**Comes before:** the seL4 build plan (`BUILD_PLAN.md`, draft PR #3). This plan does not change it.

**What changed in revision 2.** After a review of the first draft, four changes were agreed:
1. Kata Containers is dropped. It wraps the same kind of VM as Firecracker in container tooling, which adds setup work and teaches little new. We stack gVisor inside Firecracker instead.
2. The airlock is the centre of Phase 0, not the sandboxes. The PRD calls the airlock the weakest point, and none of it needs a sandbox to build.
3. Phase 0 has six written questions (§4) and a three-week timebox. It ends when the questions are answered.
4. A small seL4 taster runs alongside, so we don't learn only on Linux.

---

## 1. Why Phase 0 exists

The PRD describes a sealed habitat with one door (the airlock). The seL4 plan builds that with a formally verified kernel and no Linux anywhere. That is the right end state, but it is a long road, and it is hard to learn on.

Phase 0 builds a small, working version of the same shape with tools that exist today. It has two jobs:

1. **Learn.** Get hands-on with real isolation tech and a real airlock, so that both of us understand concretely what each piece gives you and what it doesn't.
2. **Find what we'd otherwise miss.** Building the airlock, governance and kill switch for real will surface design questions the PRD and the seL4 plan haven't answered yet. Those findings feed back into both documents.

Phase 0 is explicitly **not** the habitat. gVisor and Firecracker both rely on the Linux host kernel, which is large and unverified. The PRD already says this class of tech is "fine as a single inner layer, unacceptable as the boundary" (PRD §7). We don't expect the sandbox comparison to surprise us. We do it to measure the gap, not to discover it.

---

## 2. The technologies, in plain words

All of these answer the same question: *how do you run a program you don't trust so it can't touch the rest of the machine?* They answer it at different layers.

| | **gVisor** | **Firecracker** | **seL4 (taster only)** |
|---|---|---|---|
| **One-line idea** | A "fake kernel" written in Go that sits between the program and the real Linux kernel | A tiny virtual machine monitor that boots a minimal VM in about a tenth of a second | A small kernel whose isolation has been mathematically proved, given stated assumptions |
| **Where the wall is** | Software: the program's system calls go to gVisor, not to Linux | Hardware virtualization: the CPU itself keeps the guest apart | The kernel itself, with proofs; no Linux needed at all |
| **Who made it** | Google (used in Cloud Run, GKE Sandbox) | AWS (used in Lambda and Fargate) | Originally NICTA/Data61, now the seL4 Foundation |
| **Needs KVM?** | No | Yes | No, for the taster: it runs in the QEMU emulator |
| **What it still trusts** | The Linux host kernel (gVisor uses a small, filtered set of its system calls) | The Linux host kernel (KVM lives inside it) and the CPU | The hardware, plus what the proofs assume |

Kata Containers (dropped) runs each container inside its own lightweight VM, using a VMM such as Firecracker. It's a packaging layer over the same idea, so it adds little to what we learn.

A few terms you'll see throughout:

- **Kernel.** The core of an operating system. It controls memory, devices and every program. Whoever controls the kernel controls the machine.
- **System call (syscall).** How a program asks the kernel to do something (open a file, send a packet). Every syscall is a door into the kernel, so fewer doors means less to trust.
- **KVM.** The part of Linux that lets it use the CPU's built-in virtualization features to run whole virtual machines. Firecracker sits on top of it.
- **VMM (virtual machine monitor).** The program that sets up a VM and pretends to be its hardware (disk, clock). Firecracker is a VMM.
- **TCB (trusted computing base).** Everything that must be bug-free for the isolation to hold. Smaller is better. A big theme of Phase 0 is writing down each option's TCB honestly.
- **Nested virtualization.** Running a VM inside a VM. Most cloud machines are already VMs, so to run Firecracker on them the cloud provider has to pass the CPU's virtualization feature through. Some do, some don't.

---

## 3. What we build

```
        INSIDE (sandbox)                    OUTSIDE (host = "the world")
 ┌───────────────────────────┐
 │  toy agent                │
 │  solves puzzles, writes   │      fixed schedule,
 │  candidate answers to its │      read-only, no reply
 │  OUTBOX  ─────────────────┼──────────────▶  GATE ──▶ VERIFIER ──▶ QUARANTINE ──▶ k-of-n RELEASE
 │                           │                  │          │              │
 │  no network, no shared    │                  └──────────┴──────────────┴──▶ hash-chained LEDGER
 │  folders, no clock from   │
 │  outside                  │      KILL SWITCH (outside only, needs nothing from inside)
 └───────────────────────────┘
```

### 3.1 The airlock (the centre of Phase 0)
Runs outside, and doesn't care which sandbox the agent is in.

1. **Outbox.** A fixed number of fixed-size slots. The agent writes; the gate only ever reads. The gate never clears or marks a slot, because that would tell the inside something (PRD R-L1, principle 4).
2. **Gate.** Reads one slot per tick, on its own timer, whatever the agent did.
3. **Form check.** Only approved forms pass (R-L2). Each form has one canonical encoding, and unused space must be zero, so a valid frame carries nothing beyond its answer (R-L5).
4. **Verifier.** Independent checker per form (R-L3). Failures are destroyed unread.
5. **Budget.** Count per period, set at the start, can only be lowered (R-L4, R-L7).
6. **Quarantine.** Passing artefacts wait there for release (R-L6).

The two forms are the same as in the seL4 plan, so the work carries over:
- **F1 factorisation:** given a number from a frozen task list, output its prime factors. Checking is easy (they're prime, and they multiply back).
- **F2 sudoku:** given a puzzle with exactly one solution, output the grid. Checking is easy (rules plus matching the givens).

Both forms have exactly one correct answer per task. That matters: if there's only one right answer, a correct artefact has no room to carry anything else.

### 3.2 Governance
- **k-of-n approval** with real signatures (default 2-of-3 steward keys) for: release from quarantine, lowering the budget, closing the airlock, termination.
- **Close-only policy:** the code has no "widen" operation at all, not just a disabled one.
- **Tamper-evident ledger:** every decision goes into a hash chain, so any later edit is detectable.

### 3.3 Sandboxes
- **gVisor** (`runsc`): toy agent, no network device, outbox as one mounted file.
- **Firecracker:** minimal VM, outbox as a dedicated virtual disk, started with the `jailer`.
- **Stacked:** gVisor inside the Firecracker VM. Two different kinds of wall, a real instance of PRD R-B4 (independent layers).
- **Kill switch:** outside-only termination and state destruction for each. We time it and check nothing survives (R-O4, R-O6).

### 3.4 seL4 taster
A Microkit "hello world" on QEMU, then two protection domains that can't see each other. No KVM, no cost. The aim is to learn the end-state concepts (capabilities, protection domains, channels) early and to see how our gate maps onto them.

### 3.5 Comparison and findings
One command runs the same agent and airlock in each sandbox and writes a short report: start time, memory, kill time, a TCB inventory (what each one trusts and roughly how big it is), and a PRD scorecard. Gaps are written at the level of *"this relies on the unverified host kernel"*, not as attack recipes.

---

## 4. The six questions Phase 0 must answer

Phase 0 is done when each has a written answer in `phase0/notes/findings.md`, or when the timebox runs out, whichever comes first.

| # | Question | Answered by |
|---|---|---|
| Q1 | With canonical encodings, unique answers and a fixed reading schedule, **what freedom does the inside still have** in what reaches the outside? (For example, which tasks it answers and in what order.) | Airlock code and tests |
| Q2 | **How small can a verifier be**, and what would it take to isolate the verifier itself so it isn't a weaker second habitat? | Airlock code; stacked sandbox |
| Q3 | **What does governance actually need to do?** Which operations, which thresholds, and what does the PRD leave unspecified (key custody, a single-steward emergency stop)? | Governance code |
| Q4 | **What does each sandbox still trust**, measured rather than assumed? | gVisor, Firecracker, stacked |
| Q5 | **Can the kill switch destroy all state** with nothing from inside, and how do we confirm it from outside? | Kill switch per sandbox |
| Q6 | **What does seL4 change?** Which of our airlock design choices map cleanly onto seL4 concepts, and which need rethinking in `BUILD_PLAN.md`? | seL4 taster |

---

## 5. Where it runs

| Piece | Where |
|---|---|
| Airlock and governance code, tests | Anywhere with Python 3.11+, including Codespaces and my cloud machine |
| gVisor | Any Linux machine with Docker, including Codespaces |
| Firecracker and stacked | A machine with KVM: **Google Cloud Spot `n2-standard-4` with nested virtualization**, roughly $0.05 to $0.10 an hour (check the calculator; stop it when idle). GitHub's standard Linux runners also expose KVM, so the comparison can run in CI |
| seL4 taster | Anywhere (QEMU emulation, no KVM) |

My cloud machine has no KVM, but gVisor runs on it, so I can build and test P0.1 and P0.2 there directly. The Firecracker pieces I write as scripts that you run on the KVM machine, and that CI runs.

---

## 6. Milestones (three weeks)

| # | Week | Milestone | What you'll learn |
|---|---|---|---|
| P0.1 | 1 | **Airlock core:** forms, verifiers, outbox, gate, budget, quarantine, ledger, k-of-n governance, with tests and a runnable demo | How the airlock works as code, independent of any sandbox |
| P0.2 | 1–2 | **gVisor backend** and its kill switch | How a user-space kernel isolates a program |
| P0.S | 2 | **seL4 taster** on QEMU | Capabilities, protection domains and channels, hands-on |
| P0.3 | 2 | **Firecracker backend** and its kill switch | How a microVM works and what KVM does |
| P0.4 | 3 | **Stacked** gVisor in Firecracker, comparison report, CI | Defence in depth in practice |
| P0.5 | 3 | **Findings:** answers to Q1 to Q6, proposed changes to the PRD and seL4 plan | What Phase 0 taught us |

Each milestone ends with a short plain-language note in `phase0/notes/`.

---

## 7. Decisions taken

- **Language:** Python for Phase 0, for readability while learning. Parts worth keeping can be ported to Rust for the seL4 plan.
- **Toy agent:** a deterministic puzzle solver, not a language model. Phase 0 tests the walls and the door, not the resident.
- **Cloud machine:** Google Cloud Spot `n2-standard-4` with nested virtualization, needed from P0.3.

## 8. Ground rules

- Everything stays defensive and design-level. Gaps are described by what they rely on, not by how to exploit them.
- `BUILD_PLAN.md` is not rewritten. Findings that affect it are proposed separately.
- All Phase 0 work lives under `phase0/`.
