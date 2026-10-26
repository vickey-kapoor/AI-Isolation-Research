# Phase 0 plan: a learning baseline on today's isolation tech

**Status:** proposal for Vickey to agree before building
**Date:** 2026-10-26
**Comes before:** the seL4 build plan (`BUILD_PLAN.md`, draft PR #3). This plan does not change it.

---

## 1. Why Phase 0 exists

The PRD describes a sealed habitat with one door (the airlock). The seL4 plan builds that with a formally verified kernel and no Linux anywhere. That is the right end state, but it is a long road, and it is hard to learn on.

Phase 0 builds a small, working version of the same shape with tools that exist today and run on an ordinary cloud machine: **gVisor, Firecracker and Kata Containers**. It has two jobs:

1. **Learn.** Get hands-on with real isolation tech so that both of us understand, concretely, what a sandbox gives you and what it doesn't.
2. **Find what we'd otherwise miss.** Building the airlock, governance and kill switch for real, even around weaker sandboxes, will surface design questions the PRD and the seL4 plan haven't answered yet. Those findings feed back into both documents.

Phase 0 is explicitly **not** the habitat. Every one of these tools relies on the Linux host kernel, which is large and unverified. The PRD already says this class of tech is "fine as a single inner layer, unacceptable as the boundary" (PRD §7). Phase 0 measures how far short each one falls, so the seL4 work knows exactly what it has to do better.

---

## 2. The three technologies, in plain words

All three answer the same question: *how do you run a program you don't trust so it can't touch the rest of the machine?* They answer it at different layers.

| | **gVisor** | **Firecracker** | **Kata Containers** |
|---|---|---|---|
| **One-line idea** | A "fake kernel" written in Go that sits between the program and the real Linux kernel | A tiny virtual machine monitor that boots a minimal VM in about a tenth of a second | Runs each container inside its own lightweight VM, so it feels like Docker but is isolated like a VM |
| **Where the wall is** | Software: the program's system calls go to gVisor, not to Linux | Hardware virtualization: the CPU itself keeps the guest apart | Hardware virtualization, same as Firecracker |
| **Who made it** | Google (used in Cloud Run, GKE Sandbox) | AWS (used in Lambda and Fargate) | OpenInfra Foundation (Intel and Hyper.sh origins) |
| **Needs KVM?** | No. Runs almost anywhere | Yes | Yes |
| **What it still trusts** | The Linux host kernel (gVisor uses a small, filtered set of its system calls) | The Linux host kernel (KVM lives inside it) and the CPU | The Linux host kernel, the CPU, and a bigger VMM plus the container runtime stack |

A few terms you'll see throughout:

- **Kernel.** The core of an operating system. It controls memory, devices and every program. Whoever controls the kernel controls the machine.
- **System call (syscall).** How a program asks the kernel to do something (open a file, send a packet). Every syscall is a door into the kernel, so fewer doors means less to trust.
- **KVM.** The part of Linux that lets it use the CPU's built-in virtualization features to run whole virtual machines. Firecracker and Kata both sit on top of it.
- **VMM (virtual machine monitor).** The program that sets up a VM and pretends to be its hardware (disk, network card, clock). Firecracker is a VMM. Kata uses one (QEMU, Cloud Hypervisor or Firecracker).
- **TCB (trusted computing base).** Everything that must be bug-free for the isolation to hold. Smaller is better. A big theme of Phase 0 is writing down each option's TCB honestly.
- **Nested virtualization.** Running a VM inside a VM. Most cloud machines are already VMs, so to run Firecracker or Kata on them the cloud provider has to pass the CPU's virtualization feature through. Some do, some don't.

---

## 3. What we build

The same small system, three times, once per sandbox. Everything outside the sandbox is shared code.

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

### 3.1 The toy agent (stand-in for the resident)
A small program that solves puzzles and writes answers to its outbox. It uses the same two artefact forms as the seL4 plan so the work carries over:

- **F1 factorisation:** given a number, output its prime factors. Checking is easy (multiply them back).
- **F2 sudoku:** given a puzzle with one solution, output the filled grid. Checking is easy (rules plus matching the givens).

The agent is deliberately boring. Phase 0 tests the *walls and the door*, not the resident.

### 3.2 The one-way outbox
The agent writes into a fixed-size area that the outside reads on its own schedule. The inside never learns whether, when, or how often it was read (PRD R-L1, principle 4). How we provide this differs per sandbox (a dedicated virtual disk for the VMs, a single mounted file for gVisor), and that difference is itself something we compare. Each sandbox starts with **no network device at all**.

### 3.3 The airlock gate and verifier (outside)
Runs as its own process, ideally inside its own sandbox, separate from the habitat's.

1. Reads the outbox on a fixed timer, in fixed-size frames, whatever the agent did.
2. Rejects anything not in an approved form (R-L2).
3. Runs the independent checker for that form (R-L3). Failures are destroyed unread.
4. Rejects anything with more content than the form needs (R-L5).
5. Enforces a budget on count and size per period, set at start and only lowerable (R-L4, R-L7).
6. Moves passing artefacts into quarantine (R-L6).

### 3.4 Governance (outside)
- **k-of-n approval** with real signatures (for example 2-of-3 steward keys) for: releasing from quarantine, lowering the budget, closing the airlock, terminating.
- **Monotonic policy:** the code has no "widen" operation at all, not just a disabled one.
- **Tamper-evident ledger:** every decision is appended to a hash chain, so any later edit is detectable.

### 3.5 Kill switch (outside)
Terminates the sandbox and destroys its state without any message to, or cooperation from, the inside (R-O4, R-O6). We time it and check that nothing survives.

### 3.6 The comparison harness
One command runs the same agent and the same airlock against all three sandboxes and writes a report:

- **Practical numbers:** setup effort, start time, memory overhead, kill time.
- **TCB inventory:** what each one has to trust, and roughly how big it is (host syscalls allowed, virtual devices exposed, lines of code in the trusted parts).
- **PRD scorecard:** for each relevant requirement (R-B1, R-B3, R-B4, R-L1 to R-L7, R-O4, R-O6), "meets / partly / no", with one plain sentence on why. Gaps are written at the level of *"this relies on the unverified host kernel"*, not as attack recipes.
- **Opportunities log:** anything we notice that the PRD or seL4 plan should pick up.

---

## 4. Opportunities I expect to look at

These are hunches to test, not conclusions.

- **Stacking layers.** gVisor inside a Firecracker VM gives two different kinds of wall (software and hardware). That's a cheap, real instance of PRD R-B4 (independent layers) and worth measuring.
- **The outside code is reusable.** The gate, verifiers, governance and ledger live outside the habitat in the seL4 plan too. If we write them carefully now, much of Phase 0 carries straight into it.
- **Making the boundary boring.** The PRD wants the outside to look the same whatever the inside does (R-B2). Even in Phase 0 we can try fixed schedules and fixed-size frames and see what still varies. This is a design question, measured at a high level.
- **Free automated testing with KVM.** GitHub's standard Linux runners expose KVM, so the comparison harness can run in CI on every change without a paid machine.
- **What the PRD hasn't specified.** I expect gaps to show up around the verifier's own isolation, how stewards hold keys, and what "destroy state" means in practice.

---

## 5. Where to run it (Vickey's cloud setup)

gVisor runs almost anywhere. Firecracker and Kata need `/dev/kvm`, which ordinary Codespaces and most cheap cloud VMs don't expose. (The cloud machine I work in doesn't have it either, so I'll write and test the outside code here and the sandboxes run on your machine and in CI.)

| Option | KVM? | Rough cost | Verdict |
|---|---|---|---|
| **Google Cloud `n2-standard-4` with nested virtualization on, as a Spot VM** | Yes | Roughly $0.05 to $0.10 an hour; stop it when idle | **Recommended.** Cheapest on-demand option, one flag to enable, pay only while using it |
| Azure `D4s_v5` | Yes (nested virt supported on this family) | Roughly $0.20 an hour, less as Spot | Good if you already use Azure |
| Hetzner dedicated server (bare metal) | Yes, natively | Roughly €40 to €50 a month, flat | Best if you want it always on |
| GitHub Actions standard Linux runner | Yes | Free for public repos, included minutes for private | Great for the automated harness, not for hands-on poking |
| GitHub Codespaces | No | | Fine for gVisor and the outside code only |
| AWS bare metal (`*.metal`) | Yes | Several dollars an hour | Works but expensive for learning |

Prices are approximate and change. Check the provider's calculator before you start one. I'll write a setup script that turns a fresh Ubuntu VM into a working Phase 0 box.

---

## 6. Milestones

| # | Milestone | What you'll learn | Needs KVM? |
|---|---|---|---|
| P0.1 | Outside code: forms, verifiers, gate, budget, quarantine, ledger, k-of-n, with tests | How the airlock works as code, independent of any sandbox | No |
| P0.2 | gVisor backend: toy agent in `runsc`, no network, file outbox, kill switch | How a user-space kernel isolates a program | No |
| P0.3 | Firecracker backend: minimal VM, virtual-disk outbox, jailer, kill switch | How a microVM works and what KVM does | Yes |
| P0.4 | Kata backend: same agent via containerd | What you gain and pay for a container-friendly VM | Yes |
| P0.5 | Comparison harness and report, running in CI | Side-by-side numbers and the PRD scorecard | CI has it |
| P0.6 | Stacked layer (gVisor inside Firecracker) and findings write-up | Defence in depth in practice, and what to feed back into the PRD and seL4 plan | Yes |

Each milestone ends with a short plain-language note in `phase0/notes/` explaining what we built, why, and what surprised us.

Rough effort: P0.1 and P0.2 are a few days of my work; P0.3 to P0.6 depend on when your KVM machine is ready.

---

## 7. Decisions for Vickey

1. **Agree the plan** as written, or change its shape.
2. **Language.** I recommend **Python** for Phase 0: it's the easiest to read while learning, and the outside code is small. The seL4 plan uses Rust; we can port the parts worth keeping later.
3. **Cloud machine.** I recommend a Google Cloud Spot `n2-standard-4` with nested virtualization. You don't need it until P0.3.
4. **Toy agent.** I recommend the deterministic puzzle solver. A small local language model would be more realistic but adds a lot of setup without changing what we learn about the walls. We can swap it in later.

---

## 8. Ground rules

- Everything stays defensive and design-level. Gaps are described by what they rely on, not by how to exploit them.
- `BUILD_PLAN.md` is not rewritten. Findings that affect it are proposed separately.
- All Phase 0 work lives under `phase0/`.
