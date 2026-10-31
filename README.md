# ai-isolation-research

💻 AI Isolation v0.1 research

Design and prototype work for a **sealed habitat**: an environment built to hold an assumed artificial superintelligence (ASI). It holds everything the ASI needs to function, and lets work out only through one guarded, outward-only **airlock**. The premise is that ASI already exists. How it got here is out of scope.

**Nothing in this repository is an AI.** The prototypes run a small ordinary program as a stand-in, so that the walls and the airlock can be tested. See [Words we use](#words-we-use).

_Status as of 2026-10-27._

---

## Where things stand

| Piece | What it is | Status |
|---|---|---|
| [docs/PRD.md](docs/PRD.md) | The requirements: what the habitat must guarantee, why today's setups fall short, and the open problems. v0.2 adds the guarded airlock | Merged ([#1](https://github.com/vickey-kapoor/ai-isolation-research/pull/1), [#2](https://github.com/vickey-kapoor/ai-isolation-research/pull/2)) |
| [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md) | The long-term build plan on seL4, a formally verified kernel, with no Linux inside the habitat. It's staged: QEMU first, then a real board, then an accelerator | Merged ([#3](https://github.com/vickey-kapoor/ai-isolation-research/pull/3)), not started |
| [phase0/](phase0/) | **Phase 0**, a learning baseline built with today's isolation tools before the seL4 work. See the [plan](phase0/PLAN.md) | In progress, P0.1 to P0.4 done |
| [docs/STUDY_PLAN.md](docs/STUDY_PLAN.md) | A study plan for the tech this project uses, in the order it comes up: virtualization first, seL4 last. Each topic links to the files where it appears | Reference |

### Phase 0 progress

Phase 0 builds a small working version of the habitat's shape with gVisor and Firecracker, so we can learn hands-on and find gaps the PRD and the build plan haven't covered. It's timeboxed to three weeks (to 2026-11-16) and ends when six written questions are answered ([PLAN.md §4](phase0/PLAN.md)).

| Milestone | What it does | Status | Where it has run |
|---|---|---|---|
| **P0.1 Airlock core** | Fixed-size frames, a checker per answer type, a one-way outbox, a fixed-schedule gate, a budget that can only go down, quarantine, 2-of-3 signed approvals, and a tamper-evident log | Done ([note](phase0/notes/P0.1-airlock-core.md)) | Claude's cloud machine, GitHub's automated checks |
| **P0.2 gVisor** | The puzzle program runs under gVisor with no network, a read-only filesystem and the outbox as its only writable file. It has an outside-only kill switch and a leftover check | Done ([note](phase0/notes/P0.2-gvisor.md)) | Claude's cloud machine, GitHub's automated checks |
| **P0.3 Firecracker** | The puzzle program runs in a Firecracker virtual machine under the jailer. It has two disks (read-only inputs, and the outbox) and no network, console or shared folders | Done ([note](phase0/notes/P0.3-firecracker.md)) | GitHub's automated checks, and once on a Google Cloud VM created with the Terraform below (2026-10-26) |
| **P0.4 Stacked** | gVisor inside the Firecracker VM: two different kinds of wall in a row, and a side-by-side comparison of all three | Done ([note](phase0/notes/P0.4-stacked.md)) | GitHub's automated checks only. Not yet run on Google Cloud |
| **P0.S seL4 taster** | A small seL4 example on the QEMU emulator, to learn the end-state concepts early | Next | |
| **P0.5 Findings** | Written answers to the six questions, and proposed changes to the PRD and the build plan | Draft: Q1 to Q5 answered ([findings](phase0/notes/findings.md)), Q6 waits for the seL4 taster | GitHub's automated checks, Claude's cloud machine |

**Early findings so far** (details in the notes):
- The puzzle program still controls *which* answers get out first when the budget is full. A fix is for the outside to fix the order.
- Logging rejected answers would itself leak information, so rejections leave no trace.
- "Destroy everything" needs a list and an outside check. gVisor left a host-side object behind until the kill switch was taught to remove it.
- Firecracker's lack of shared folders matches the PRD's "inputs fixed before sealing" rule closely.
- Stacking gVisor inside Firecracker cost about 0.1 s more start time and four times the VM memory. The airlock worked unchanged behind one wall, a different wall, and both.
- Debugging a sealed box needs a planned way to see in, and that way must not exist in the sealed run.
- If the outside fixes the order and timing in which answers leave (an "agenda"), the inside's choice shrinks from over 19 bits to at most one yes/no per task.
- The answer checker runs fine in a gVisor box of its own (about 0.1 ms per answer), but its real weight is the Python runtime under it.
- Measuring, not assuming, showed the jailed Firecracker process was still on the host's network. It now gets an empty network namespace.

Every Phase 0 sandbox still relies on the host's unverified Linux kernel. Phase 0 measures how far short that falls of the PRD's bar. It's not meant to meet it.

### Try it yourself

- **Tests and demo, no sandbox:** anywhere with Python 3.11 or newer (see [phase0/README.md](phase0/README.md)). Windows support for the outbox code was added in [#6](https://github.com/vickey-kapoor/ai-isolation-research/pull/6).
- **gVisor, Firecracker and stacked:** a Linux machine with KVM. Step-by-step instructions for one Google Cloud VM are in [phase0/GCP_SETUP.md](phase0/GCP_SETUP.md). Terraform that creates the same VM is in [phase0/infra/gcp/](phase0/infra/gcp/README.md). It has been applied to a real account once (2026-10-26), and Firecracker ran on the VM it created.
- **Automated checks:** [.github/workflows/phase0.yml](.github/workflows/phase0.yml) runs these on every change under `phase0/`:
  - the unit tests and the demo
  - the full gVisor run
  - the full Firecracker run
  - the full stacked run (gVisor inside Firecracker)
  - the answer checker in its own gVisor sandbox
  - a side-by-side comparison of all of them, with what each relies on
  - a Terraform check

---

## Words we use

These words have one meaning each here, to avoid misreading. The full table is in [phase0/README.md](phase0/README.md#words-we-use-and-what-they-mean-here).

| Word | Meaning | Not |
|---|---|---|
| **ASI**, **the resident** | The hypothetical superintelligence the PRD is about | Anything in this repository |
| **Puzzle program** | `phase0/puzzle_program/puzzle_program.py`: an ordinary Python program of about 125 lines that factors numbers and solves sudokus. It's the stand-in for the resident. [BUILD_PLAN.md](docs/BUILD_PLAN.md) calls its seL4 counterpart the "toy agent"; that's the same idea, and also not an AI | An AI, a model, or anything that learns or has goals |
| **Sandbox** | Software that confines a program: gVisor and Firecracker here | A proven boundary |
| **Habitat** | In the PRD, the full sealed environment. In Phase 0 code, one sandbox plus its outbox | The same thing in both places. The Phase 0 version is far weaker |
| **Airlock** | The outside code that reads the outbox, checks answers and holds them in quarantine | A two-way channel |
| **Tested** / **has run** | The code actually ran, in the place named, with a log | Proven secure |

---

## Layout

```
docs/
  PRD.md               requirements (v0.2)
  BUILD_PLAN.md        seL4 build plan (later phase)
  STUDY_PLAN.md        what to learn, in order
phase0/                learning baseline
  PLAN.md              plan, six questions, milestones
  README.md            how to run, full glossary
  GCP_SETUP.md         Google Cloud step by step
  airlock/             outside code: frames, checkers, gate, budget, ledger, governance
  puzzle_program/      the stand-in program that runs inside a sandbox
  sandboxes/           gVisor, Firecracker and stacked backends, probe, kill switch
  infra/gcp/           Terraform for the lab VM
  notes/               plain-language note per milestone
  tests/
```

Research notes behind the PRD are kept outside the repository, in the project's shared files under `asi-containment/research_notes/`.
