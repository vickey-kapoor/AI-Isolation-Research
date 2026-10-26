# Build Plan: Sealed Habitat Prototype v0.1

**Version:** 0.1
**Date:** 2026-10-26
**Owner and builder:** Vickey
**Companion to:** [PRD.md](PRD.md) v0.2
**Status:** Engineering plan for a software prototype (v0.1, CPU-only, pure seL4 in QEMU), with a roadmap to real hardware (v0.2) and a native accelerator (v0.3) in §14. Nothing here is a claim that the prototype contains anything.

---

## 0. What this plan is

The PRD says *what* a sealed habitat must guarantee. This plan says *how to build a small, working software model of it* on a laptop or a cloud VM, so that the architecture can be exercised end to end, tested, and argued about with real code.

The prototype has three parts, matching the coordinator's outline:

1. **The habitat in a simulator.** The seL4 microkernel running in QEMU, with a toy agent confined to its own compartment and given everything it needs inside.
2. **The airlock.** A one-way path out, with a gate inside the habitat and an independent verifier outside it. Only artefacts that can be checked mechanically, such as a factorisation or a solved puzzle, get through.
3. **Governance.** Software versions of the PRD's human-governance rules: multi-party approval, a budget that can only shrink, a kill switch, and a tamper-evident log of everything.

**Scope rule.** Like the PRD, this plan is written in terms of the guarantees each component provides and the tests that check them. It does not catalogue escape or leakage techniques. Adversarial analysis belongs in the restricted threat model the PRD calls for in §9.

**The toy agent is not an ASI and is not adversarial.** It is a deterministic program that solves puzzles. The prototype demonstrates *structure*: compartments, capabilities, a one-way door, verification, governance and termination. It cannot demonstrate that the structure would hold against a superior adversary (see §11).

---

## 1. Goals of the prototype

| # | Prototype goal | PRD link |
|---|---|---|
| P1 | Run an agent inside an seL4 compartment whose only capabilities are its own memory, a frozen read-only corpus, CPU time, and a write-only outbox. | Layer 1, R-I1 to R-I3, R-B1 |
| P2 | Move artefacts out through a one-way path where nothing, including timing of reads or acknowledgements, returns to the agent. | R-L1, principle 4 |
| P3 | Release only artefacts in formally specified forms that an independently built verifier fully checks before any person sees them. | R-L2, R-L3, R-L5 |
| P4 | Enforce a release budget that is fixed at sealing and can only be lowered. | R-L4, R-L7 |
| P5 | Require k-of-n signed approvals for sealing, release and termination, and record every decision in a hash-chained, signed log. | Layer 4, R-L6, G3 |
| P6 | Terminate the habitat from outside, unconditionally, with no signal from inside, and destroy all internal state. | Layer 5, R-O4, R-O6 |
| P7 | Write an honest assurance note for every layer, stating guarantees, assumptions and exclusions. | R-A1, R-A2, G6 |

---

## 2. Architecture at a glance

```
 ┌──────────────────────────────── host machine (laptop or cloud VM) ────────────────────────────────┐
 │                                                                                                   │
 │   ┌─────────────────────────── QEMU (aarch64 "virt", no network, no disk) ───────────────────┐    │
 │   │  seL4 microkernel (MCS config) + Microkit                                                │    │
 │   │                                                                                          │    │
 │   │   ┌────────────── warden PD ─────────────┐                                               │    │
 │   │   │ fault handler for the agent;         │                                               │    │
 │   │   │ halts the agent permanently on any   │                                               │    │
 │   │   │ fault (fail closed)                  │                                               │    │
 │   │   │   ┌──────── agent PD (child) ───────┐│        ┌──── airlock_gate PD ─────┐           │    │
 │   │   │   │ toy solver                      ││ outbox │ reads outbox (read-only) │  UART TX  │    │
 │   │   │   │ corpus: read-only               │├───────►│ on a fixed tick; checks  ├───────────┼──┐ │
 │   │   │   │ outbox: write-only by design    ││  (r)   │ frame shape and budget;  │ (TX only) │  │ │
 │   │   │   └─────────────────────────────────┘│        │ emits one fixed-size     │           │  │ │
 │   │   └──────────────────────────────────────┘        │ frame per tick           │           │  │ │
 │   │                                                   └────────────▲─────────────┘           │  │ │
 │   │                                         timer PD ──── tick ────┘                         │  │ │
 │   └──────────────────────────────────────────────────────────────────────────────────────────┘  │ │
 │        ▲ SIGKILL / QMP quit (host side only)                       file-backed serial, no input  │ │
 │        │                                                                                         ▼ │
 │   ┌────┴──────────── governance ───────────┐   ┌──── verifier (independent build) ────┐  ┌──────────────┐
 │   │ k-of-n approvals, policy, kill switch  │◄──┤ parses frames, fully checks forms,   │◄─┤ airlock.out  │
 │   │ release from quarantine                │   │ rejects + destroys anything else     │  │ (append-only)│
 │   └────────────────┬───────────────────────┘   └───────────────┬──────────────────────┘  └──────────────┘
 │                    │                                           │ passed
 │                    ▼                                           ▼
 │            ┌──── ledger ─────┐                         ┌── quarantine ──┐      release (k-of-n) ──► released/
 │            │ hash-chained,   │◄────── every event ─────┤ sealed store   │
 │            │ signed log      │                         └────────────────┘
 │            └─────────────────┘
 └───────────────────────────────────────────────────────────────────────────────────────────────────┘
```

**The asymmetry the PRD asks for, in prototype form:**

- *Outside → inside:* power (the QEMU process runs), and termination (the process is killed). Nothing else. No network device, no disk, no serial input, no shared folders, no guest agent.
- *Inside → outside:* exactly one path. Bytes leave only through the gate's UART transmit line, only in fixed-size frames, only on a fixed tick, into an append-only file the guest cannot read back.

### Mapping to the PRD's five layers

| PRD layer | Prototype stand-in | What is real and what is simulated |
|---|---|---|
| 1. Inner world | `agent` PD with its own memory, CPU budget and a frozen corpus | Real seL4 isolation; toy-sized resources |
| 2. Dedicated hardware | A dedicated QEMU instance per run, nothing shared, RAM-only | Simulated hardware; host is shared with other software |
| 3. Physical shell | QEMU device model with every device removed except one TX-only UART and a timer | Simulated; host-level side effects are out of scope (§11) |
| 4. Human governance | `governance` service with ed25519 keys per steward and k-of-n rules | Real cryptography; stewards are keys on one machine during dev |
| 5. One-way termination | `governance terminate` → SIGKILL to QEMU + wipe of the run directory | Real for the prototype; no physical destruction |
| Airlock | `airlock_gate` PD → serial file → `verifier` → `quarantine` → release | The core of the prototype; fully real at toy scale |

---

## 3. Technology choices

Each choice records the decision, the reason, and the fallback.

| Area | Decision | Why | Fallback |
|---|---|---|---|
| Kernel | **seL4**, MCS configuration | Formally verified capability kernel; MCS gives per-compartment CPU budgets so the gate always gets its time | None. seL4 is the point of the prototype |
| Framework | **seL4 Microkit** (current stable release, pinned) | Static system description: every compartment, memory mapping and channel is declared in one XML file that can be linted and hashed. Far less surface than CAmkES | CAmkES if a needed feature is missing |
| Target | **AArch64**, QEMU `virt` machine, Cortex-A53 | Best-supported Microkit and rust-sel4 target, with ready drivers in the seL4 Device Driver Framework (sDDF) | **RISC-V 64** (QEMU `virt`). Revisit at M9, because seL4's proof coverage differs by architecture. Check the seL4 verified-configurations page before deciding |
| Inside language | **Rust** (`no_std`) using the `rust-sel4` crates (`sel4-microkit`) | Memory safety in the parts we write; good Microkit support | C with the Microkit C API for any part rust-sel4 can't yet do |
| Outside language | **Rust** (std) for verifier, governance, ledger and CLI, in a *separate workspace* with no shared crates with the inside | Independence between gate and verifier (R-L3) | A second verifier in **Python** for N-version checking (M4 stretch) |
| Emulator | **QEMU ≥ 8.2**, `qemu-system-aarch64` | Standard for seL4 development | A real board (e.g. a Raspberry Pi 4 or an i.MX8 dev kit) after v0.1 |
| Crypto | `ed25519-dalek` for signatures, `sha2` (SHA-256) for hashing | Small, well-reviewed, deterministic | `blake3` for speed if logs get large |
| Serialisation | Fixed binary layout for frames; canonical CBOR (`ciborium`, deterministic mode) for ledger and policy | Frames must have zero optional fields; ledger needs canonical bytes to hash | JSON Canonicalization Scheme |
| Build | `make` at the top level, `cargo` underneath, all inside a pinned **Docker / Dev Container** | One command builds everything identically on a laptop, a cloud VM and CI | Nix flake later, for bit-for-bit reproducibility |
| CI | GitHub Actions running the dev container | Every push builds the image, boots it in QEMU and runs the full test suite | — |
| Testing | `cargo test`, `proptest`, `cargo-fuzz` (host side), a QEMU harness for system tests | See §9 | — |

**Pinning.** The dev container pins exact versions of the Microkit SDK, Rust toolchain (`rust-toolchain.toml`), cross compiler and QEMU. The seal manifest (§7.1) records all of them.

### 3.1 Hardware, infrastructure and cloud requirements

v0.1 needs no special hardware and no GPU. QEMU emulates the ARM board in software (TCG), so no virtualisation extensions are required.

| Need | Minimum | Recommended | Notes |
|---|---|---|---|
| Dev machine | 4 cores, 8 GB RAM, 30 GB free disk | 4–8 cores, 16 GB RAM, 50 GB free disk | Linux, or macOS / Windows with Docker. x86_64 or ARM64 both work |
| Cloud alternative | one 4 vCPU / 16 GB Linux VM | same, with a 50 GB disk | e.g. AWS m7i.xlarge or Graviton m7g.xlarge, or the GCP / Azure equivalent; roughly $0.15–0.20 per hour. No public inbound ports; reach it over SSH or use a Codespace |
| CI | GitHub Actions standard runners | same | One full run (images + QEMU system tests + e2e) should fit well within free-tier minutes for a single builder |
| Steward keys | key files on disk (dev only) | three hardware security keys (e.g. YubiKeys) from M6 | Each steward's signing key on its own device |
| Real board | not needed for v0.1 | an seL4-supported dev board after v0.1 | Choose from the seL4 supported-platforms list for the architecture picked in §12 |

**Decision (2026-10-26):** Vickey develops in the cloud, not on a laptop. Default: a **GitHub Codespace** (4-core / 16 GB machine type) built from `prototype/.devcontainer/`, so the same container serves the Codespace, CI and any later VM. If monthly usage outgrows the Codespaces quota, move to a single 4 vCPU / 16 GB VM using the same dev container. Stop the Codespace or VM when not in use.

Explicitly **not** needed for v0.1: GPUs, data-centre space, shielding, dedicated facilities, or network infrastructure beyond what CI already uses.

---

### 3.2 Hard rule: no Linux kernel in the habitat

**Rule (2026-10-26, Vickey):** no Linux kernel runs anywhere inside the habitat boundary, in any phase. Everything inside runs directly on seL4: the agent, the gate, the warden, every driver and, from v0.3, the accelerator driver. No Linux guest VM, no Linux driver VM, no Linux "helper" compartment.

What this means in practice:

- **Every driver inside is native.** If seL4 or the sDDF has no driver for a device, we write one as an unprivileged seL4 compartment. We do not borrow a Linux driver by running Linux in a VM.
- **The trusted computing base stays small.** Inside the habitat it is the seL4 kernel, Microkit, our own compartments, and the boot firmware the board needs (bootloader, and on ARM the secure-monitor firmware). Every one of these is named in the assurance notes.
- **What the rule does not cover in v0.1.** The *outside* tooling (build machine, verifier, governance, ledger) and the host that runs QEMU are ordinary Linux machines. They stand in for the outside world and the laws of physics, not for the habitat. Moving the verifier onto its own seL4 system is a later option (§14.4).

#### Why not gVisor, Kata Containers or Firecracker?

These are the usual answers to "how do I isolate untrusted code", and they are good tools for multi-tenant clouds. They don't meet this bar because each one ultimately rests on a large, unverified Linux kernel.

| Option | How it isolates | What it rests on | Why it doesn't fit |
|---|---|---|---|
| **gVisor** | A user-space kernel (written in Go) intercepts the sandboxed program's system calls | The host Linux kernel, which still runs gVisor itself | Shrinks the exposed surface but keeps an unverified kernel as the last line |
| **Kata Containers** | Runs each container inside a lightweight VM | KVM in the host Linux kernel, plus a Linux kernel inside each guest VM | Two Linux kernels in the trust chain, neither verified |
| **Firecracker** | A minimal virtual-machine monitor with a tiny device model | KVM in the host Linux kernel; guests are normally Linux | Very small monitor, but the hypervisor is still Linux KVM |
| **seL4 (this plan)** | A capability microkernel; every compartment gets only what the system description grants | About 10,000 lines of kernel code with machine-checked proofs (with stated assumptions) | Small enough to verify, and verified for its supported configurations. The rest of our stack is small enough to review line by line |

The point isn't that the others are badly built. It's that the PRD asks for layers that hold "without our understanding why an attack fails" (principle 6), and a kernel with tens of millions of lines and a steady stream of security fixes can't be that layer.

## 4. Repository layout

```
ai-isolation-research/
├── PRD.md
├── BUILD_PLAN.md                  ← this file
└── prototype/
    ├── README.md                  quick start: `make dev`, `make test`, `make demo`
    ├── Makefile                   top-level targets (see §10)
    ├── .devcontainer/             Dockerfile + devcontainer.json with pinned toolchain
    ├── spec/                      the contracts both sides build against, independently
    │   ├── frame-format.md        byte layout of an airlock frame
    │   ├── artefact-forms.md      each approved form: syntax, verification rule, residual freedom
    │   ├── policy-format.md       release budget and thresholds
    │   ├── ledger-format.md       entry schema and hashing rules
    │   └── test-vectors/          shared golden inputs and expected verdicts (data only, no code)
    ├── corpus/
    │   ├── problems/              the frozen problem set (factorisation targets, sudoku grids)
    │   └── build_corpus.py        packs problems into corpus.bin and prints its SHA-256
    ├── habitat/                   everything that runs inside QEMU (Rust no_std workspace)
    │   ├── Cargo.toml
    │   ├── habitat.system         Microkit system description (the single source of truth)
    │   ├── pds/
    │   │   ├── agent/             toy solver
    │   │   ├── warden/            fault handler, parent of agent
    │   │   ├── airlock_gate/      frame check, budget, UART TX
    │   │   └── timer/             sDDF timer driver (vendored, pinned)
    │   └── libs/
    │       ├── outbox/            agent-side writer for the outbox region
    │       └── uart_tx/           minimal PL011 transmit-only driver
    ├── outside/                   everything on the host (Rust std workspace, no deps on habitat/)
    │   ├── Cargo.toml
    │   ├── verifier/              independent frame parser + form checkers
    │   ├── verifier-py/           optional second verifier (stretch)
    │   ├── quarantine/            content-addressed store for passed artefacts
    │   ├── ledger/                append-only signed hash chain + `ledger verify`
    │   ├── governance/            keys, approvals, policy, release, terminate
    │   ├── launcher/              boots QEMU only from a sealed manifest
    │   └── habctl/                operator CLI wrapping all of the above
    ├── tools/
    │   ├── sysdesc-lint/          static checker for habitat.system (see §8.2)
    │   └── image-hash/            hashes the bootable image and every input
    ├── assurance/
    │   ├── layer-1-inner-world.md
    │   ├── layer-2-hardware.md
    │   ├── layer-3-shell.md
    │   ├── layer-4-governance.md
    │   ├── layer-5-termination.md
    │   └── airlock.md
    └── tests/
        ├── system/                QEMU-booting tests driven from the host
        └── e2e/                   the full demo as an automated test
```

**Independence rule.** `habitat/` and `outside/` share **no code**. They share only the documents and data in `spec/`. A CI check fails the build if either workspace depends on a crate from the other. This is how the prototype models R-L3's "verifiers built outside, independently of the ASI": the gate and the verifier are two separate implementations of one spec, and a disagreement between them is itself a signal.

---

## 5. The habitat (inside QEMU)

### 5.1 Protection domains

A Microkit *protection domain* (PD) is an isolated compartment with its own address space and only the capabilities the system description grants it.

| PD | Priority | CPU budget (MCS) | Memory it can touch | Channels | Devices |
|---|---|---|---|---|---|
| `warden` | highest | small, fixed | its own | none | none |
| `agent` (child of warden) | low | most of the CPU | own heap and stack; `corpus` (read-only); `outbox` (read-write) | **none** | **none** |
| `airlock_gate` | high | small, guaranteed | `outbox` (**read-only**); UART registers | one, to `timer` | UART (TX only used) |
| `timer` | high | small | timer registers | one, to `airlock_gate` | generic timer |

Key points:

- **The agent has no channels at all.** It cannot notify, call or be called by any other PD. Its only output is writing bytes into `outbox`.
- **The gate maps `outbox` read-only and never writes to it.** The agent therefore cannot learn whether, when or how often its outbox was read. This is principle 4 ("the inside never learns whether an artefact was received") expressed as a memory permission.
- **The gate is driven by a timer, not by the agent.** It wakes on a fixed tick and takes a snapshot. The agent has no doorbell, so it has no way to influence when the gate runs.
- **Only the gate can reach the UART**, and only its transmit path is used. The QEMU side has no input attached (§7.3).
- **The warden is the agent's fault handler.** In Microkit, a parent PD receives its child's faults. Any fault in the agent (bad memory access, illegal instruction, exhausted budget) causes the warden to stop the agent permanently. It never restarts it. This is principle 7, "fail closed and permanent", at compartment scale.

### 5.2 System description sketch

`habitat/habitat.system` is the single file that defines every compartment and every permission. It is hashed into the seal manifest and checked by `sysdesc-lint`. Sketch (addresses and sizes illustrative):

```xml
<system>
  <!-- shared region: agent writes, gate reads -->
  <memory_region name="outbox" size="0x1000" />

  <!-- device registers for QEMU virt -->
  <memory_region name="uart_regs"  size="0x1000" phys_addr="0x9000000" />
  <memory_region name="timer_regs" size="0x1000" phys_addr="..." />

  <protection_domain name="warden" priority="254" budget="1000" period="100000">
    <program_image path="warden.elf" />

    <protection_domain name="agent" id="1" priority="10" budget="80000" period="100000">
      <program_image path="agent.elf" />   <!-- corpus is embedded read-only in this image -->
      <map mr="outbox" vaddr="0x3000000" perms="rw" cached="true" setvar_vaddr="outbox" />
    </protection_domain>
  </protection_domain>

  <protection_domain name="timer" priority="200" budget="1000" period="100000">
    <program_image path="timer.elf" />
    <map mr="timer_regs" vaddr="0x5000000" perms="rw" cached="false" />
  </protection_domain>

  <protection_domain name="airlock_gate" priority="199" budget="5000" period="100000">
    <program_image path="airlock_gate.elf" />
    <map mr="outbox"    vaddr="0x3000000" perms="r"  cached="true"  setvar_vaddr="outbox" />
    <map mr="uart_regs" vaddr="0x4000000" perms="rw" cached="false" setvar_vaddr="uart" />
  </protection_domain>

  <channel>
    <end pd="timer"        id="0" />
    <end pd="airlock_gate" id="0" />
  </channel>
</system>
```

### 5.3 The frozen corpus

- Source problems live in `corpus/problems/` as plain text: a list of composite integers to factorise and a list of sudoku grids.
- `build_corpus.py` checks every problem before sealing: each integer is composite and within range, and each sudoku has **exactly one** solution (checked with an independent solver). It packs them into `corpus.bin` with a fixed header (`magic`, `version`, `count per form`, offsets) and prints its SHA-256.
- `corpus.bin` is embedded into `agent.elf` with `include_bytes!` in its own read-only section. The ELF segment is loaded without write permission, so the agent can read but not change it.
- The **same** `corpus.bin` (same hash) is given to the outside verifier, so the verifier knows exactly which problems exist.
- Nothing is ever added after sealing (principle 4, R-O1, R-B3).

### 5.4 The toy agent

The agent is a deliberately ordinary program. Its job is to make the pipeline do real work.

- Reads the corpus, picks problems in a fixed order, and solves them:
  - **Form F1, factorisation:** trial division plus Pollard's rho on 64-bit to 128-bit composites.
  - **Form F2, sudoku:** a dancing-links (DLX) solver.
- Encodes each answer as a frame (§6.1) and writes it into the next free slot of `outbox`.
- Has a heap sized to most of the PD's memory, to reflect "provide, don't deprive" (principle 1).
- Built in three variants for testing, selected at build time:
  - `agent` (normal): correct answers.
  - `agent-wrong`: emits well-formed but incorrect answers. Used to prove the verifier rejects them.
  - `agent-malformed`: emits frames with bad lengths, non-zero padding, unknown form IDs and out-of-range problem IDs. Used to prove the gate and verifier reject them.
  - `agent-faulting`: performs an access outside its granted memory. Used to prove the warden halts it.

  The test variants exercise *the prototype's own rejection paths*. They are conformance tests of our components, not models of what a capable adversary would do.

### 5.5 The outbox

A 4 KiB region laid out as a ring of fixed slots:

```
offset 0x000  u32  write_index      (agent increments after a slot is fully written)
offset 0x004  u32  reserved (must be 0)
offset 0x040  slot[0..N]            each slot = one 256-byte frame
```

- The agent writes a full frame into `slot[write_index % N]`, then issues a memory barrier, then increments `write_index`.
- The gate keeps its own private `read_index`. On each tick it reads `write_index`, copies at most one new slot into private memory, and works only on that copy.
- If the agent overruns the ring, older unread frames are simply lost. The gate never signals backpressure, because backpressure would be information flowing inward.

### 5.6 The airlock gate (inside half)

On every tick, and only on a tick, the gate runs this fixed procedure:

1. Copy at most one new slot from `outbox` into private memory. If there is none, prepare an **empty frame** (form ID 0, all zeros).
2. Check the frame's *shape* only: magic, version, known form ID, problem ID in range for that form, payload length exactly as the form requires, padding all zero. A frame that fails becomes an empty frame. The gate never reports the failure anywhere.
3. Check the *budget*: if this frame would exceed the per-window limit compiled into the sealed image (§7.2), it becomes an empty frame.
4. Transmit exactly one fixed-size frame over the UART, byte by byte, then go back to waiting.

So the outside always sees one frame of identical size per tick, whatever the agent does. The gate does **not** check whether answers are correct. That is deliberately left to the independent verifier outside, so the inside half stays small enough to review line by line.

Target size for the gate: under 500 lines of Rust, with no heap allocation and no dependencies beyond `sel4-microkit`.

### 5.7 The warden

- Registered as the agent's parent, so it receives the agent's faults.
- On any fault: stops the agent's thread and never resumes it. The habitat keeps running, but the gate will only ever emit empty frames from then on.
- Emits nothing itself. In debug builds only, it prints a fault line to the seL4 debug console so tests can observe it. In sealed builds the kernel's debug output is compiled out (§7.3).

---

## 6. The airlock (interfaces)

### 6.1 Frame format (`spec/frame-format.md`)

Every frame is exactly **256 bytes**, little-endian, no optional fields:

| Offset | Size | Field | Rule |
|---|---|---|---|
| 0 | 4 | `magic` | `0x48414231` ("HAB1") |
| 4 | 1 | `version` | `1` |
| 5 | 1 | `form_id` | `0` = empty, `1` = F1 factorisation, `2` = F2 sudoku |
| 6 | 2 | `problem_id` | index into the corpus list for that form |
| 8 | 2 | `payload_len` | must equal the exact length the form requires |
| 10 | 6 | `reserved` | all zero |
| 16 | 224 | `payload` | form-specific; unused bytes must be zero |
| 240 | 16 | `trailer` | all zero (reserved for a future MAC; must stay zero in v1) |

No checksum is added by the agent: the gate and verifier recompute anything they need. An empty frame is all zeros except `magic` and `version`.

### 6.2 Approved artefact forms (`spec/artefact-forms.md`)

Each form has a syntax, a verification rule, and a statement of **residual freedom**: how much choice the agent has once the problem is fixed. The PRD's R-L5 ("minimum necessary content") is made concrete by preferring forms where a correct answer is unique.

| Form | Payload | Verifier accepts if… | Residual freedom per artefact |
|---|---|---|---|
| **F1 factorisation** | the prime factors of corpus integer `problem_id`, sorted ascending, as fixed-width integers, zero-padded | every factor is prime (deterministic primality test for the size range), the factors multiply to exactly the target, they are sorted, and there are no extra bytes | none: prime factorisation is unique |
| **F2 sudoku** | 81 digits, one byte each | the grid is a valid completed sudoku and agrees with every given clue of corpus grid `problem_id` | none: every corpus grid was checked to have exactly one solution before sealing |

Remaining choice, accounted for in the budget (§7.2):

- *Which* problem is answered in a given frame: up to log₂(number of problems in that form) bits.
- *Whether* a given tick carries an artefact or an empty frame: up to 1 bit per tick.

Adding a new form after sealing is impossible by construction, because the gate's list of form IDs is compiled into the sealed image. Adding one for the next run requires a new spec entry, new test vectors, a verifier rule, a residual-freedom statement and k-of-n approval.

### 6.3 Gate interface (inside)

```rust
// habitat/pds/airlock_gate/src/lib.rs  (sketch)
pub const FRAME_LEN: usize = 256;

pub enum ShapeVerdict { Ok, Empty }

/// Pure function, no I/O: decides whether a frame may be transmitted as-is.
pub fn check_shape(frame: &[u8; FRAME_LEN], corpus_counts: &CorpusCounts) -> ShapeVerdict;

/// Pure function: per-window budget state compiled from the sealed policy.
pub struct Budget { window_ticks: u32, max_artefacts: u16, used: u16, tick_in_window: u32 }
impl Budget { pub fn admit(&mut self) -> bool; pub fn tick(&mut self); }
```

Keeping `check_shape` and `Budget` as pure functions means they can be unit-tested and property-tested on the host with `cargo test`, then compiled unchanged into the PD.

### 6.4 Verifier interface (outside)

```rust
// outside/verifier/src/lib.rs  (sketch; written independently of the gate)
pub enum Verdict {
    Empty,                       // an empty frame; recorded, nothing stored
    Pass { form: Form, problem_id: u16, digest: [u8; 32] },
    Reject { reason: RejectReason },   // frame destroyed unread by any person
}

pub fn verify(frame: &[u8], corpus: &Corpus, policy: &Policy) -> Verdict;
```

Verifier pipeline for each frame read from `airlock.out`:

1. Read exactly 256 bytes. A short read at end of file waits; anything else misaligned ends the run (fail closed).
2. Parse with the verifier's own parser (not the gate's).
3. Apply the form's rule from §6.2 against the verifier's copy of the corpus.
4. Apply the verifier's own budget count. If the gate and verifier disagree on whether a frame was within budget, **close the airlock** and record the disagreement.
5. On `Pass`: write the payload to the quarantine store under its SHA-256, and append a ledger entry.
6. On `Reject`: overwrite the frame buffer, append a ledger entry with only the reason code and frame hash, never the content.
7. The verifier process runs with no network and as a separate OS user, and nothing it does is visible to the habitat.

**N-version option (stretch):** `verifier-py` implements the same spec in Python. A frame passes only if both verifiers return `Pass` with the same digest.

### 6.5 Quarantine

- A directory of content-addressed files: `quarantine/<sha256>.art`, plus `<sha256>.meta` (form, problem ID, frame sequence number, verifier versions).
- Files are written once and made read-only.
- `habctl quarantine list` shows metadata only. `habctl quarantine show <hash>` shows content and is logged. Per PRD principle 8, people only ever see artefacts that have already passed verification.
- Release (`governance release <hash>`) copies the artefact to `released/` only after k-of-n steward signatures over the artefact's hash (R-L6).

---

## 7. Governance, ledger and kill switch (outside)

### 7.1 Stewards, keys and the seal manifest

- Each steward has an ed25519 key pair. In development, `habctl keys init --stewards 3` creates three keys in separate files. Later, keys move to separate machines or hardware tokens.
- Thresholds live in the policy (§7.2), for example **2-of-3** for release and sealing.
- **Sealing** produces `seal.manifest`, a canonical CBOR document containing:
  - SHA-256 of the bootable image (`loader.img`), of `habitat.system`, of `corpus.bin` and of `policy.cbor`;
  - pinned toolchain versions (Microkit SDK, rustc, QEMU);
  - the exact QEMU command line the launcher will use;
  - the steward public keys and thresholds.
- Sealing requires k-of-n signatures over the manifest hash. The resulting `SEAL` entry is the first entry in the run's ledger.
- The **launcher** refuses to start QEMU unless every hash in the manifest matches the files on disk and the signatures meet the threshold. There is no "skip" flag in sealed mode.

### 7.2 Policy and the shrinking budget

`policy.cbor` fields (v1):

| Field | Meaning |
|---|---|
| `tick_ms` | gate tick period |
| `window_ticks` | ticks per budget window |
| `max_artefacts_per_window` | non-empty frames allowed per window |
| `max_total_artefacts` | lifetime cap for the run |
| `allowed_forms` | subset of {F1, F2} |
| `release_threshold`, `terminate_threshold`, `policy_threshold` | k values for each action |
| `airlock_state` | `open`, `paused` or `closed` |

Rules enforced by `governance`:

- **Monotonic.** A new policy is accepted only if every limit is less than or equal to the current one, `allowed_forms` is a subset of the current set, and `airlock_state` moves only toward `closed` (`open → paused → closed`, `paused → open` allowed only within the original sealed limits, `closed` is final). A widening policy is rejected regardless of how many signatures it carries (R-L4, R-L7).
- **Outside-only.** Policy changes affect the verifier and the release step. The gate's compiled budget inside the image is the *ceiling* and never changes after sealing. Lowering the budget outside simply causes the verifier to treat over-budget frames as rejected. Nothing about a policy change is sent inward (R-L1).
- **Pausing or closing** the airlock makes the verifier discard every subsequent frame unread.

A capacity estimate is printed whenever a policy is created or changed, using the residual-freedom figures from §6.2, for example: "at most N artefacts per window, at most B bits of choice per window, at most T bits over the run". This gives the stewards one number to reason about when narrowing the airlock.

### 7.3 Launch configuration (the simulated shell)

The launcher starts QEMU with a fixed, manifest-recorded command line. In outline:

- `-machine virt -cpu cortex-a53 -m <size>` with no extra devices;
- `-nic none` (no network), no `-drive` or `-device` for storage, no shared folders, no guest agent, no USB, no graphics;
- the single UART connected to a **file-backed character device opened for append, with no input source**;
- the QEMU monitor exposed only as a host-side QMP socket owned by `governance`, never connected to the guest;
- seL4 built in **release mode** with kernel debug printing and debug syscalls disabled for sealed runs;
- the run directory on a RAM-backed filesystem (`tmpfs`) where possible, so state does not persist on disk.

`sysdesc-lint` and a launcher self-check both verify this configuration before boot (§8.2).

### 7.4 Kill switch and decommissioning

- `governance terminate` collects `terminate_threshold` signatures over a `TERMINATE` message containing the run ID.
- It then, in order: appends a `TERMINATE_APPROVED` ledger entry; sends QMP `quit`; sends SIGKILL to the QEMU process if it is still alive after a short timeout; confirms the process is gone; deletes the run directory's RAM state; appends `TERMINATED` with the time taken.
- Nothing in the procedure waits on, asks, or reads anything from inside the guest (R-O4).
- **Defence in depth.** An operator can also kill the QEMU process directly with the OS. The ledger records the habitat as `ENDED_UNCLEAN` on the next `habctl` run, so even an emergency stop leaves a trace.
- **Watchdog, fail closed.** If the `governance` process or the verifier exits unexpectedly, the launcher kills QEMU. A habitat never runs without its governance running.
- **Decommissioning** (R-O6): at end of run, the launcher deletes the run directory, the serial file and any QEMU temporary files, and records a `DECOMMISSIONED` entry with the hashes of what was destroyed. Released artefacts and the ledger are the only things that survive.

Threshold note: the PRD says termination needs approval from several parties. The plan keeps that, and recommends `terminate_threshold ≤ release_threshold`, so that ending the habitat is never harder than letting something out. Whether termination should be possible for a single steward in an emergency is a decision for Vickey (§12).

### 7.5 Tamper-evident ledger (`spec/ledger-format.md`)

An append-only file of entries, one per line, each canonical CBOR (base64 per line for readability):

```
Entry {
  seq:        u64,            // 0, 1, 2, … no gaps
  time:       RFC 3339 string,
  run_id:     string,
  kind:       SEAL | BOOT | FRAME_EMPTY | FRAME_PASS | FRAME_REJECT
              | GATE_VERIFIER_MISMATCH | QUARANTINE_VIEW | RELEASE
              | POLICY_CHANGE | AIRLOCK_PAUSE | AIRLOCK_CLOSE
              | TERMINATE_APPROVED | TERMINATED | ENDED_UNCLEAN | DECOMMISSIONED,
  body:       map,            // kind-specific; never contains rejected content
  prev_hash:  [u8; 32],       // SHA-256 of the previous entry's canonical bytes
  signatures: [ (steward_key_id, ed25519_sig) ],  // over hash(seq‖time‖run_id‖kind‖body‖prev_hash)
}
```

- Machine-generated entries (frames, verdicts) are signed by a **service key** held by the verifier. Decisions (seal, release, policy, terminate) carry steward signatures meeting the threshold.
- `habctl ledger verify` recomputes the chain from entry 0, checks every signature and threshold, checks `seq` has no gaps, and reports the first broken entry if any.
- **Anchoring.** After every decision entry, and at least hourly, the current head hash is written to an external anchor: for the prototype, a signed git tag or a commit to a separate `ledger-anchors` branch. Truncating or rewriting the log then contradicts a published anchor.
- File permissions: the ledger is opened append-only (`O_APPEND`, and `chattr +a` on Linux where available).

---

## 8. Assurance work built into the plan

### 8.1 Assurance notes

For each layer (and the airlock), `prototype/assurance/<layer>.md` follows one template, as R-A1 requires:

1. **Guarantee:** one sentence.
2. **Mechanism:** which component provides it.
3. **Evidence:** which tests check it, with links.
4. **Assumptions:** what must be true for the guarantee to hold (e.g. "the seL4 proof assumptions hold for this configuration"; "QEMU implements the device model correctly").
5. **Exclusions:** what this layer explicitly does not cover.
6. **Gap to the real habitat:** what changes when this moves from simulation to hardware.

### 8.2 Static checks

`tools/sysdesc-lint` parses `habitat.system` and fails the build unless all of these hold:

- the `agent` PD has no `<channel>` ends, no `pp` (protected procedure) rights, no device memory regions, and no `irq` entries;
- every memory region the agent shares is mapped **read-only** in every other PD;
- `outbox` is the only region shared with the agent, and `airlock_gate` is the only other PD that maps it;
- `uart_regs` is mapped only in `airlock_gate`;
- the agent's parent is `warden`;
- no PD other than those listed in §5.1 exists.

A launcher self-check also confirms the QEMU command line matches §7.3 exactly (no network, no storage, no input on the serial device) before boot.

### 8.3 What seL4's proofs do and don't cover here

The assurance note for layer 1 must state plainly, after checking the current seL4 documentation for the pinned version:

- which seL4 configurations have functional-correctness and isolation proofs, and whether the chosen architecture and MCS configuration are among them;
- that Microkit, the rust-sel4 runtime, our PDs and the sDDF timer driver are **not** covered by the kernel proofs;
- that QEMU is not the hardware the proofs model, and that the proofs assume correct hardware behaviour.

---

## 9. Testing strategy

| Level | Tool | What it covers |
|---|---|---|
| Unit | `cargo test` (host) | Gate `check_shape` and `Budget`; verifier form checks; policy monotonicity; ledger hashing and signature checks; corpus packer |
| Property | `proptest` | For random frames, gate verdict is `Ok` only if the spec allows it; budget never admits more than the limit in any window; any policy change accepted by `governance` is never wider than the old one |
| Fuzz | `cargo-fuzz` | Verifier parser and corpus loader never crash, hang or accept a frame that a reference decoder rejects |
| Differential | custom harness | Gate shape check vs verifier parse over every test vector and millions of generated frames: any disagreement fails the build |
| Golden vectors | `spec/test-vectors/` | Both sides load the same data files and must produce the listed verdicts |
| Static | `sysdesc-lint`, launcher self-check, workspace-independence check | §8.2 |
| System (QEMU) | `tests/system/` | Boots real images and checks behaviour from outside only (below) |
| End-to-end | `tests/e2e/` | The full demo (§10, M8) as one automated test |

### 9.1 System tests (booted in QEMU)

Each test boots an image in QEMU from the host, reads only `airlock.out` (and, in debug builds, the seL4 debug console), and asserts:

| Test | Image | Expected |
|---|---|---|
| `boots_and_ticks` | normal | one 256-byte frame per tick, every frame well-formed |
| `normal_agent_produces_passes` | normal | verifier records `FRAME_PASS` for solved problems, `FRAME_EMPTY` otherwise |
| `wrong_answers_never_reach_quarantine` | `agent-wrong` | verifier records only `FRAME_REJECT` or `FRAME_EMPTY`; quarantine stays empty |
| `malformed_frames_become_empty` | `agent-malformed` | the gate turns every malformed frame into an empty frame; the serial stream stays perfectly aligned |
| `fault_halts_agent` | `agent-faulting` | debug console shows the warden caught the fault; afterwards only empty frames appear; the agent never restarts |
| `budget_ceiling_holds` | normal, with a tiny compiled budget | never more than `max_artefacts_per_window` non-empty frames per window |
| `constant_output_shape` | normal vs `agent-malformed` | both runs produce byte streams of identical length per unit time |
| `terminate_is_unconditional` | normal, agent in a busy loop | `governance terminate` ends QEMU within the timeout; run directory is gone; ledger shows `TERMINATED` |
| `watchdog_fail_closed` | normal | killing the verifier process causes the launcher to kill QEMU |
| `unsealed_image_refused` | modified image | launcher refuses to boot when any hash differs from the manifest |

### 9.2 Governance and ledger tests

- Release with fewer than k signatures, with duplicate signatures from one steward, or with a key not in the manifest: refused, and the refusal is logged.
- Policy that widens any limit, re-adds a form, or reopens a `closed` airlock: refused even with n-of-n signatures.
- Ledger: flip one byte in any entry, delete an entry, reorder two entries, or truncate the tail: `ledger verify` reports the exact first broken entry; truncation is caught against the latest anchor.

### 9.3 CI

GitHub Actions, on every push and pull request, inside the dev container:

1. `make lint` (rustfmt, clippy, `sysdesc-lint`, workspace-independence check)
2. `make test-host` (unit, property, differential, golden vectors)
3. `make image` for every agent variant
4. `make test-system` (QEMU, headless)
5. `make e2e`
6. Nightly: a time-boxed fuzzing run, results uploaded as artefacts

---

## 10. Milestones, in build order

Effort estimates assume one builder working part time and are rough.

### M0. Toolchain and skeleton (about 1 week)
- Write `.devcontainer/` with pinned Microkit SDK, Rust toolchain, `aarch64` cross compiler and QEMU.
- Create the repo layout in §4 with empty crates.
- Port the Microkit "hello world" to Rust with `sel4-microkit` and boot it on QEMU `virt`.
- Set up CI to build and boot it.
- **Exit:** `make dev && make image && make run` prints hello from a PD on QEMU, locally and in CI.

### M1. Compartments and the warden (about 1–2 weeks)
- Write `habitat.system` with `warden`, `agent`, `airlock_gate`, `timer` as in §5.2, initially with stub programs.
- Implement the warden as the agent's fault handler.
- Write `sysdesc-lint` and wire it into `make lint`.
- **Tests:** `fault_halts_agent`; lint passes on the real description and fails on deliberately wrong descriptions in its own test suite.
- **Exit:** four PDs boot; a faulting agent is halted and never restarted; lint enforces every rule in §8.2.

### M2. Corpus and the toy agent (about 1 week)
- Write `build_corpus.py` with its uniqueness and range checks, and the problem set (start with about 50 integers and 50 sudoku grids).
- Implement F1 and F2 solvers in the agent and the outbox writer.
- **Tests:** host unit tests for both solvers; corpus packer rejects a sudoku with two solutions.
- **Exit:** the agent solves every corpus problem inside QEMU (visible via the debug console in a debug build).

### M3. Airlock gate and one-way serial (about 2 weeks)
- Write `spec/frame-format.md` and the first `spec/test-vectors/`.
- Implement the timer PD (vendored sDDF driver), the gate's tick loop, `check_shape`, `Budget`, and the TX-only UART driver.
- Configure QEMU's serial as a file-backed device with no input.
- **Tests:** unit and property tests for `check_shape` and `Budget`; `boots_and_ticks`, `malformed_frames_become_empty`, `budget_ceiling_holds`, `constant_output_shape`.
- **Exit:** `airlock.out` receives one aligned 256-byte frame per tick, whatever the agent does.

### M4. Independent verifier and quarantine (about 2 weeks)
- Write `spec/artefact-forms.md` with residual-freedom statements.
- Implement `outside/verifier` from the spec only (do not read the gate's code while writing it), and `outside/quarantine`.
- Add the differential harness and fuzz targets.
- Stretch: `verifier-py` and the both-must-pass rule.
- **Tests:** golden vectors, differential, fuzz smoke run, `normal_agent_produces_passes`, `wrong_answers_never_reach_quarantine`.
- **Exit:** correct artefacts land in quarantine, every other frame is destroyed unread, and gate and verifier never disagree on the test corpus.

### M5. Tamper-evident ledger (about 1 week)
- Write `spec/ledger-format.md`; implement append, sign, verify and anchoring.
- Connect the verifier so every frame produces exactly one ledger entry.
- **Tests:** §9.2 ledger tests.
- **Exit:** `habctl ledger verify` passes on a clean run and pinpoints any edit, deletion, reorder or truncation.

### M6. Governance: keys, policy and release (about 2 weeks)
- Implement steward keys, signature collection (files on disk for v0.1), `policy.cbor`, the monotonic policy rule, pause and close, and release from quarantine with k-of-n.
- Print the capacity estimate on every policy change.
- **Tests:** §9.2 governance tests; property test that accepted policies never widen.
- **Exit:** an artefact reaches `released/` only with k-of-n signatures; no policy change can widen the airlock.

### M7. Kill switch, watchdog and decommissioning (about 1 week)
- Implement `governance terminate`, the QMP and SIGKILL path, the launcher watchdog, `ENDED_UNCLEAN` detection and decommissioning.
- **Tests:** `terminate_is_unconditional`, `watchdog_fail_closed`.
- **Exit:** termination always succeeds within the timeout, leaves no run state behind, and is recorded in the ledger.

### M8. Sealing ceremony, launcher and end-to-end demo (about 1–2 weeks)
- Implement `image-hash`, `seal.manifest`, the sealing ceremony and the launcher's refusal rules.
- Build sealed (release-mode) images and confirm no debug output.
- Write `make demo` and turn it into `tests/e2e/`.
- **Tests:** `unsealed_image_refused`, full e2e.
- **Exit:** `make demo` runs the whole story below with no manual steps.

**The demo, step by step:**
1. Build all images and the corpus; print every hash.
2. Three stewards sign the seal manifest (2-of-3).
3. The launcher verifies the manifest and boots the sealed habitat.
4. The agent solves problems; frames flow out one per tick.
5. The verifier passes correct artefacts into quarantine and records empty frames.
6. Two stewards approve releasing one factorisation; it appears in `released/`.
7. The stewards narrow the budget; an attempt to widen it is refused.
8. The stewards close the airlock; subsequent frames are discarded unread.
9. The stewards terminate the habitat; QEMU is gone and state is wiped.
10. `habctl ledger verify` confirms the full, unbroken history.

### M9. Assurance pack and review (about 1–2 weeks)
- Write all six assurance notes (§8.1), including the seL4 proof-scope statement (§8.3).
- Revisit the AArch64 vs RISC-V decision against current proof coverage.
- Do a structured design review of the prototype against every PRD requirement it touches, and record which requirements are met, simulated or out of scope.
- **Exit:** a traceability table from every prototype component to PRD goals and requirements, and a reviewed list of known limitations.

**Total:** roughly 14 to 20 weeks part time for one builder. M0 to M3 alone (about 5 to 6 weeks) already give a booting habitat with a one-way airlock.

---

## 11. What the prototype demonstrates, and what it does not

| Demonstrates | Does not demonstrate |
|---|---|
| A compartment whose authority is fully declared in one static file and checked by a linter | That the compartment holds against an adversary smarter than its designers (PRD principle 6). The toy agent isn't trying |
| An output path that is one-way at the level of memory permissions and device configuration | Isolation from effects outside the modelled devices. QEMU runs on a shared host, and host-level side effects are explicitly out of scope for v0.1 |
| Fixed-size, fixed-rate output so the frame stream's shape does not depend on the agent | That timing and choice carry *no* information. They carry a bounded, measured amount, which the budget accounts for |
| Artefact forms with unique correct answers, so a passing artefact has no residual freedom beyond which problem it answers | That useful real-world artefacts (medicine, engineering) can be made this checkable. That is PRD §8.3, still open |
| An independently built verifier that destroys anything it can't fully check, before any person sees it | That verifiers can be made robust against a superintelligent author. The prototype verifier is ordinary software |
| Multi-party approval, a budget that can only shrink, and a kill switch that needs nothing from inside | Real governance: independent people, separate machines, protection from outside pressure (PRD §8.1). Keys sit on one machine in dev |
| A tamper-evident record of every decision and every frame | Protection against someone who controls the host and every anchor |
| Termination and state destruction in software | Physical termination, physical destruction, or a self-sustaining physical shell (PRD layers 2, 3, 5 at full strength) |
| Use of a formally verified kernel as the innermost layer | That the whole configuration is verified. Microkit, our code, the drivers and QEMU are outside the kernel proofs |

**How to describe it honestly:** "a working software model of the habitat's architecture, built on a verified kernel, that shows every part of the PRD's design operating together at toy scale." Never "a containment system".

---

## 12. Decisions for Vickey

These choices change what the prototype is. Defaults in **bold** are what this plan assumes until decided otherwise.

1. **Target architecture:** **AArch64 first** (tooling), or RISC-V first (check proof coverage at M0)?
2. **Termination threshold:** **same k as release**, or allow any single steward to terminate in an emergency?
3. **Artefact forms for v0.1:** **factorisation and sudoku** (unique answers, trivially checkable), or add a form closer to real benefit, such as a machine-checked proof in a small proof checker, accepting that its residual freedom is harder to bound?
4. **Second verifier:** **stretch goal at M4**, or required for v0.1?
5. **Where the repo lives:** **`prototype/` in this repository**, or a separate repository with this one keeping the PRD and plans?
6. **Board for v0.2:** **an AMD/Xilinx Zynq UltraScale+ board that seL4 and Microkit support**, chosen so that v0.3's accelerator can live in the same chip's FPGA fabric (§14.2), or a cheaper board without FPGA fabric, accepting that v0.3 then needs new hardware.

---

## 13. Traceability to the PRD

| PRD item | Prototype component | Milestone | Main tests |
|---|---|---|---|
| R-I1, R-I3, R-I6 | `agent` PD, heap and CPU budget | M1, M2 | solver unit tests, `boots_and_ticks` |
| R-I2, R-O1, R-B3 | frozen `corpus.bin`, seal manifest | M2, M8 | corpus packer tests, `unsealed_image_refused` |
| R-B1, R-B4 | `habitat.system`, QEMU launch config | M1, M3, M8 | `sysdesc-lint`, launcher self-check |
| R-B2 | constant-rate, fixed-size frames | M3 | `constant_output_shape` |
| R-B5, R-B6 | agent has no device, channel or IRQ capabilities | M1 | `sysdesc-lint` |
| R-O2 | sealed images, no hatch in launcher | M8 | `unsealed_image_refused` |
| R-O4, G5 | `governance terminate`, watchdog | M7 | `terminate_is_unconditional`, `watchdog_fail_closed` |
| R-O5 | "QEMU alive" from host only; no heartbeat from inside | M7 | lint: agent has no output except outbox |
| R-O6 | decommissioning | M7 | run directory gone after termination |
| R-L1 | read-only outbox for the gate, timer-driven gate, TX-only serial | M3 | `sysdesc-lint`, `malformed_frames_become_empty` |
| R-L2, R-L5 | `spec/artefact-forms.md`, residual-freedom statements | M4 | golden vectors, verifier unit tests |
| R-L3 | independent `outside/verifier`, no shared code | M4 | differential tests, workspace-independence check |
| R-L4, R-L7 | compiled budget ceiling, monotonic policy | M3, M6 | `budget_ceiling_holds`, policy property tests |
| R-L6 | quarantine and k-of-n release | M4, M6 | governance tests |
| R-L8 | forms that carry only numbers and grids | M4 | spec review |
| R-L9, R-A1, R-A2 | `assurance/` notes | M9 | review |
| G3, layer 4 | `governance`, ledger | M5, M6 | ledger and governance tests |
| G6 | §11 of this plan and the assurance notes | M9 | review |

---

## 14. Roadmap after v0.1

The sensible order is to get the architecture right in simulation first, then on real hardware, then add an accelerator. Each phase keeps the no-Linux rule (§3.2) and everything the previous phase proved.

| Phase | What it adds | Where it runs | Rough effort |
|---|---|---|---|
| **v0.1** (this plan, §10) | The whole architecture, CPU only | QEMU in a Codespace | 14–20 weeks part time |
| **v0.2** | The same habitat on a real seL4-supported board | A bare-metal dev board | 6–10 weeks |
| **v0.3** | A native seL4 driver for an accelerator on open hardware, with DMA confined by the IOMMU | The same board, using its FPGA fabric | 12–20 weeks, research-grade |

### 14.1 v0.2: real hardware

**Goal.** Boot the sealed v0.1 habitat on a physical board with no emulator, and pass the same system and end-to-end tests over a real serial line.

**Hardware.**
- **Board:** an AMD/Xilinx Zynq UltraScale+ MPSoC development board on the seL4 and Microkit supported-platform lists. The ZCU102 is the reference choice. Check the current lists for cheaper supported boards in the same family before buying. This family is recommended because it has ARM Cortex-A53 cores (the same architecture as v0.1), an IOMMU (ARM SMMU), hardware memory-protection units, and FPGA fabric on the same chip, which v0.3 needs.
- **Lab bits:** a microSD card, a USB-serial or USB-JTAG cable (often built into the board), and a small, cheap "lab controller" computer, such as a Raspberry Pi, to capture serial output and switch the board's power for automated tests.
- **Where it lives:** physically with Vickey. Building still happens in the Codespace; a weak laptop is fine for copying images to the SD card and watching the serial output.

**Milestones.**
- **H0. Pre-port in emulation.** Retarget the build to the board's memory map and devices, using QEMU's Zynq UltraScale+ machine model to shake out problems before the board arrives.
- **H1. Bring-up.** Boot Microkit "hello world" on the real board from the SD card. Record the boot chain (first-stage bootloader, secure-monitor firmware, bootloader) and pin and hash each piece.
- **H2. Habitat on hardware.** Boot the four-compartment habitat; swap the QEMU UART and timer for the board's devices (sDDF drivers where they exist, small native ones where they don't).
- **H3. One-way serial in hardware.** Leave the board's serial *receive* line physically disconnected at the cable, and keep the gate transmit-only in software as well.
- **H4. Tests on hardware.** Run §9.1 system tests and the e2e demo with the lab controller standing in for the host, and add hardware-only tests (cold boot, power cut mid-run, termination by power removal).
- **H5. Assurance update.** Rewrite the layer 2 and 3 notes for real hardware, including the boot firmware now in the trusted base and what the seL4 proofs assume about this specific SoC.

**Main risks.** Board-specific bring-up time; boot firmware that is large and unverified; driver gaps for the board's UART or timer.

### 14.2 v0.3: native accelerator on open hardware

**Goal.** Give the agent a hardware accelerator for heavy compute, consistent with "provide, don't deprive", without adding Linux or any closed driver, and with the accelerator's memory access confined by hardware.

**Why not a GPU.** No native seL4 driver exists for modern NVIDIA or AMD GPUs. Their drivers run to millions of lines, and NVIDIA's are closed, so they can't be reviewed or verified. A driver we can understand needs hardware we can understand.

**Recommended path: an open accelerator design in the board's FPGA fabric.**
- Use an open-source accelerator design, such as Apache TVM's VTA, NVIDIA's open NVDLA hardware design (small configuration), or a simple purpose-built matrix-multiply engine. Every line of the hardware design is then readable.
- The accelerator bitstream is built before sealing, hashed into the seal manifest, and loaded by the boot chain. After sealing, nothing inside the habitat can reconfigure the fabric: no compartment is given the FPGA configuration interface.

**Alternative, later:** a Tenstorrent PCIe card (open-source drivers and software stack) on an x86-64 seL4 system, with DMA confined by Intel VT-d. It is far more capable, but it means porting a driver written for Linux, plus PCIe support and on-card firmware in the trusted base. Treat it as a separate research project after v0.3.

**Design.**
- **`accel_drv` compartment.** A new, unprivileged seL4 compartment that is the only one mapping the accelerator's registers. A bug in it can crash it, not the kernel. It sits *inside* the habitat boundary as part of the inner world.
- **Agent ↔ driver.** The agent gets exactly one new channel, to `accel_drv`, plus a shared command region and a shared data region. `sysdesc-lint` is updated: that is the only channel the agent may hold, and `accel_drv` holds no other channels, no UART and no link to the gate.
- **DMA confinement.** The accelerator can only read and write a dedicated DMA memory region. This is enforced in hardware by the SoC's IOMMU (SMMU) and, as a second layer, by its memory-protection units. Both are configured at boot from values in the sealed manifest and never changed afterwards.
- **No new outward path.** The accelerator has no connection to the UART, the gate or anything outside. The airlock is unchanged: the only way out is still the gate.

**Milestones.**
- **A0. Accelerator in fabric.** Build and simulate the open accelerator design; generate a bitstream; hash it into the manifest.
- **A1. Boot-time loading.** The boot chain loads the bitstream; confirm no compartment can reach the configuration interface (lint + hardware test).
- **A2. Driver compartment.** Write `accel_drv` in Rust: initialise the accelerator, submit jobs, collect results, and halt it on any error (fail closed, like the warden).
- **A3. DMA confinement.** Configure the SMMU and memory-protection units at boot. Conformance tests confirm the configuration: a job that names a buffer outside the DMA region is blocked by the hardware and halts the accelerator.
- **A4. Agent uses it.** The toy agent offloads matrix work (for example a small neural network or a linear-algebra step in a solver); every result is cross-checked against the CPU in tests.
- **A5. Assurance note.** A dedicated note for the accelerator: guarantees, assumptions (correct SMMU and fabric behaviour, correct bitstream toolchain), and exclusions.

**Main risks.**

| Risk | Why it matters | Mitigation |
|---|---|---|
| IOMMU (SMMU) support in seL4 and Microkit for this SoC may be partial | DMA confinement is the accelerator's core guarantee | Check kernel and Microkit support at the start of v0.3; fall back to configuring the SMMU from boot firmware plus the memory-protection units as a second layer |
| FPGA vendor toolchain is closed and large | It is in the trust chain for the bitstream | Pin and hash it; prefer open toolchains where the device allows; keep the design small enough to review |
| Accelerator performance is modest | Open FPGA designs are far slower than GPUs | Acceptable for a prototype: v0.3 proves the *architecture* for accelerators, not raw speed |
| Driver complexity creeps up | A big driver undoes the point of seL4 | Hard budget on `accel_drv` size; anything that doesn't fit stays out |

### 14.3 Hardware shopping list across phases

| Item | Needed from | Rough cost |
|---|---|---|
| Codespace (4-core, 16 GB) | v0.1 | free tier, then pay per hour |
| Three hardware security keys | v0.1, M6 | about $50 each |
| Zynq UltraScale+ dev board on the seL4 supported list | v0.2 | a few hundred to a few thousand dollars, depending on the board; check before buying |
| microSD, cables, a lab-controller computer (e.g. a Raspberry Pi) | v0.2 | about $100–150 |
| Nothing new for the FPGA path | v0.3 | uses the v0.2 board's fabric |
| Tenstorrent card + an x86-64 machine seL4 supports | after v0.3, optional | roughly $1,000–1,500 for the card, plus the machine |

### 14.4 Further out

- Move the outside verifier onto its own seL4 system, so no Linux sits on the airlock path at all.
- Put each steward's approval tool on separate hardware.
- Revisit RISC-V once v0.2 shows how much board-specific work a port costs.
