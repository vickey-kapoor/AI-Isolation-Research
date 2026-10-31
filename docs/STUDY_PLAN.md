# Study plan: the tech behind the habitat build

As of 2026-10-28. Written for Vickey, who is learning enough of each area to guide the build. The live version is a [Claude Doc](https://claude.ai/artifact/V5JT1jCMcLGc2MMx3ZMYXu); this copy is for reference from the repo.

Start with virtualization, then fill in Linux, Python, Git, cloud and security as Phase 0 needs them; that core takes about 12 weeks at 6 hours a week. The seL4 path comes last and is a 6 to 12 month effort on its own.

The goal is to be able to guide the build: read a design note, ask the right question, and spot when something is wrong. You don't need to write all of it yourself, so each section says what "fluent enough" means for this project.

- **Order.** Sections follow the order you'll use them. Virtualization is first because it explains why each wall in Phase 0 exists. Linux basics sit under everything, so dip into that section whenever virtualization material assumes it.
- **Time.** Estimates assume about 6 hours a week and are rough. Halve them if you skim, double them if you do every exercise.
- **In this repo.** Each section points to the files where the topic shows up, so you can check your understanding against real work.
- **Sources.** All links are free. They were written from memory and not opened when this plan was written, so report a dead one and it will be replaced.

## 1. Virtualization (start here, about 3 weeks)

This is the one topic that explains every Phase 0 result. A container shares the host's kernel, so a kernel bug is a way out. A VM gets its own kernel, and the CPU itself keeps it apart. gVisor sits in between: a kernel rewritten in software that catches the program's requests before they reach the real one.

**Fluent enough means** you can explain, in your own words, what wall each of these draws and what a hole in it would look like: a plain process, a container, gVisor, a Firecracker VM, a Kata container.

**Where it shows up here**

- [`phase0/notes/P0.2-gvisor.md`](../phase0/notes/P0.2-gvisor.md): the puzzle program inside gVisor.
- [`phase0/notes/P0.3-firecracker.md`](../phase0/notes/P0.3-firecracker.md): the puzzle program inside its own small VM, with the jailer around Firecracker.
- [`phase0/notes/P0.4-stacked.md`](../phase0/notes/P0.4-stacked.md): gVisor inside a Firecracker VM, two walls in a row.
- [`phase0/infra/gcp/`](../phase0/infra/gcp/): why the cloud VM needs nested virtualization (Firecracker needs `/dev/kvm`).
- [`BUILD_PLAN.md`](BUILD_PLAN.md) section 3.2: why the final habitat drops all three in favour of seL4.

**Study path**

1. **What a kernel is and what "virtualizing the CPU" means.** [Operating Systems: Three Easy Pieces](https://pages.cs.wisc.edu/~remzi/OSTEP/), the free textbook. Read the intro, the process chapters and the appendix on virtual machine monitors. About 6 hours.
2. **Containers from the ground up.** Julia Evans, [What even is a container](https://jvns.ca/blog/2016/10/10/what-even-is-a-container/), then the man pages for [namespaces](https://man7.org/linux/man-pages/man7/namespaces.7.html) and [capabilities](https://man7.org/linux/man-pages/man7/capabilities.7.html). About 3 hours.
3. **KVM, the piece Firecracker stands on.** LWN, [Using the KVM API](https://lwn.net/Articles/658511/). Read for the idea, not the code: a normal program asks the kernel to run a guest on the CPU. About 2 hours.
4. **gVisor.** The [gVisor docs](https://gvisor.dev/docs/), especially the [security model](https://gvisor.dev/docs/architecture_guide/security/) page. About 3 hours.
5. **Firecracker.** The 2020 paper [Firecracker: Lightweight Virtualization for Serverless Applications](https://www.usenix.org/conference/nsdi20/presentation/agache) (there's also a talk video on that page), then the [getting started guide](https://github.com/firecracker-microvm/firecracker/blob/main/docs/getting-started.md). About 4 hours.
6. **Kata Containers.** [Kata's learn page](https://katacontainers.io/learn/). Kata wraps each container in a small VM, often using Firecracker or QEMU underneath. About 1 hour.

**Check yourself:** reread P0.4 and explain to someone why wall 2 (gVisor) still matters when wall 1 (the VM) is already there.

## 2. Linux basics (about 2 weeks, alongside virtualization)

Every wall in Phase 0 is built out of ordinary Linux features: users, permissions, mounts and system calls. If you can read a setup script and say what each line changes, you can follow the build.

**Fluent enough means** you're comfortable in a terminal, can read a short shell script, and know what root, a mount, a process and a system call are.

**Where it shows up here**

- [`phase0/sandboxes/setup_gvisor.sh`](../phase0/sandboxes/setup_gvisor.sh) and [`setup_firecracker.sh`](../phase0/sandboxes/setup_firecracker.sh): shell scripts that build the habitat's filesystem.
- The P0.2 note's configuration check: user "nobody", no capabilities, read-only root, only loopback networking. Each of those is a Linux concept.
- The jailer in P0.3, which uses a seccomp filter to limit which system calls Firecracker may make.

**Study path**

1. **The shell.** [The Linux Command Line](https://linuxcommand.org/tlcl.php), a free book. Parts 1 and 2 are enough. About 6 hours.
2. **Practice.** [OverTheWire Bandit](https://overthewire.org/wargames/bandit/), a game you play over SSH. Levels 0 to 15 teach files, permissions and processes. About 4 hours.
3. **The tools around the shell.** MIT's [Missing Semester](https://missing.csail.mit.edu/): the shell, scripting and data-wrangling lectures. About 3 hours.
4. **System calls and seccomp.** The [seccomp man page](https://man7.org/linux/man-pages/man2/seccomp.2.html), read for the idea. About 1 hour.

**Check yourself:** read `setup_gvisor.sh` top to bottom and write one line on what each command does.

## 3. Python (about 2 weeks)

The whole Phase 0 airlock, the sandbox runners and the puzzle program are Python. You need to read it well, not write it fast.

**Fluent enough means** you can open any file in `phase0/airlock/` and follow what it does: functions, classes, dataclasses, reading and writing files, and running another program.

**Where it shows up here**

- [`phase0/airlock/`](../phase0/airlock/): the gate (`gate.py`), fixed-size frames (`frames.py`), the outbox, the shrinking budget, the tamper-evident log (`ledger.py`) and steward signatures (`governance.py`).
- [`phase0/puzzle_program/puzzle_program.py`](../phase0/puzzle_program/puzzle_program.py): the stand-in workload. It's an ordinary Python program that solves puzzles, not an AI.
- [`phase0/sandboxes/`](../phase0/sandboxes/): the scripts that start the puzzle program inside gVisor or Firecracker.
- [`phase0/tests/`](../phase0/tests/): tests written with Python's built-in `unittest`.

**Study path**

1. **The language.** The official [Python tutorial](https://docs.python.org/3/tutorial/), sections 1 to 9. About 8 hours.
2. **The parts this repo leans on.** [hashlib](https://docs.python.org/3/library/hashlib.html) (hashing for the log), [struct](https://docs.python.org/3/library/struct.html) (fixed binary layouts, the same idea the frames use), [subprocess](https://docs.python.org/3/library/subprocess.html) (how the runners start sandboxes) and [unittest](https://docs.python.org/3/library/unittest.html). About 3 hours.
3. **Signatures.** The [Ed25519 page of the cryptography library](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/), which `governance.py` uses for steward keys. About 1 hour.

**Check yourself:** run the airlock demo (`python -m airlock.demo` from `phase0/`) and match each line it prints to the code that printed it.

## 4. Git and GitHub Actions (about 1 week)

Every Phase 0 run that counts so far happened in GitHub Actions, GitHub's automated checks. Git is how you review what changed and approve it.

**Fluent enough means** you can read a pull request diff, understand branches and merges, and open a failed check to see which step broke and why.

**Where it shows up here**

- [`.github/workflows/phase0.yml`](../.github/workflows/phase0.yml): one job per stage (airlock tests, gVisor, Firecracker, stacked, plus a Terraform check). Each job installs what it needs and runs the habitat.
- The "run" links at the top of the P0.3 and P0.4 notes go straight to those check results.
- The pull requests that brought in the PRD and the build plan.

**Study path**

1. **Git's model.** [Learn Git Branching](https://learngitbranching.js.org/), an interactive visual game. About 2 hours.
2. **Reference.** [Pro Git](https://git-scm.com/book/en/v2), chapters 1 to 3 (basics and branching). About 3 hours.
3. **Actions.** The [GitHub Actions docs](https://docs.github.com/en/actions): the quickstart and the page on workflow syntax. About 2 hours.

**Check yourself:** open `phase0.yml` and explain why the Firecracker job can run on GitHub's machines but not on Claude's cloud machine (hint: KVM).

## 5. Cloud and Terraform (about 1 week)

Your laptop can't run Firecracker, so the lab machine lives on Google Cloud. Terraform describes that machine as code, so you can create it, check it and delete it the same way every time.

**Fluent enough means** you can read `terraform plan` output before typing "yes", know what each resource costs roughly, and always remember to run `terraform destroy` when you're done.

**Where it shows up here**

- [`phase0/infra/gcp/main.tf`](../phase0/infra/gcp/main.tf): one Spot VM with nested virtualization on (so `/dev/kvm` exists), and a firewall rule that only allows SSH through Google's IAP, so port 22 isn't open to the internet.
- [`phase0/GCP_SETUP.md`](../phase0/GCP_SETUP.md): the same steps done by hand in the console.
- The `terraform` job in `phase0.yml`, which checks the Terraform files on every push.

**Study path**

1. **Terraform on Google Cloud.** HashiCorp's [Get Started on Google Cloud](https://developer.hashicorp.com/terraform/tutorials/gcp-get-started) tutorial. It walks through init, plan, apply and destroy. About 3 hours.
2. **The two Google features this repo needs.** [Nested virtualization](https://cloud.google.com/compute/docs/instances/nested-virtualization/overview) and [IAP TCP forwarding](https://cloud.google.com/iap/docs/using-tcp-forwarding) for SSH without a public port. About 2 hours.
3. **Do it once for real.** Follow [`phase0/infra/gcp/README.md`](../phase0/infra/gcp/README.md) from Cloud Shell, run the gVisor stage on the VM, then destroy it. A Spot n2-standard-4 runs to cents per hour, but set a billing budget alert first. About 2 hours.

**Check yourself:** read `main.tf` and point to the line that turns on nested virtualization and the one that limits who can reach SSH.

## 6. Security ideas (about 2 weeks, ongoing)

These ideas outlast any one tool, and they're how you'll judge every design choice. The habitat is built on a few of them: give each part only what it needs, make every way in or out explicit, and assume any single wall can fail.

**Fluent enough means** you can name the principle behind a design choice ("the gate only accepts fixed-size frames because...") and ask what happens if a given wall breaks.

**Where it shows up here**

- [`PRD.md`](PRD.md): the five layers and the guarded, verify-only airlock.
- [`phase0/airlock/`](../phase0/airlock/): least privilege and fail-closed in practice (fixed frames, a budget that only shrinks, a log you can't quietly edit, approvals that need several stewards).
- `phase0/notes/findings.md` in the project's shared files (not in this repo): what Phase 0 has learned so far about each wall.
- `research_notes/` in the project's shared files: the literature on boxing and on hidden (covert) channels.

**Study path**

1. **The classic principles.** Saltzer and Schroeder, [The Protection of Information in Computer Systems](https://web.mit.edu/Saltzer/www/publications/protection/) (1975). Read section I.A.3, the eight design principles. It's short and still the best list. About 2 hours.
2. **Thinking like the other side.** Ross Anderson, [Security Engineering](https://www.cl.cam.ac.uk/~rja14/book.html), free chapters. Start with the chapters on access control and on multilevel security. About 6 hours.
3. **A full course, if you want depth.** MIT [6.858 Computer Systems Security](https://ocw.mit.edu/courses/6-858-computer-systems-security-fall-2014/) lecture videos: privilege separation, capabilities, sandboxing. Pick 4 to 6 lectures. About 6 hours.

**Check yourself:** for each of the eight Saltzer and Schroeder principles, find one place in the PRD or the airlock that follows it.

## 7. Later: the seL4 path (6 to 12 months, after Phase 0)

This is the hard part, which is why it comes last. The final habitat has no Linux kernel at all. It runs on seL4, a small kernel whose correctness has been mathematically proven, with the inside written in Rust and run on an emulated ARM board in QEMU.

**Fluent enough means** you can read the Microkit system description (the one XML file listing every compartment and channel), explain what seL4's proofs do and don't promise, and follow a Rust code review at a high level.

**Where it shows up here**

- [`BUILD_PLAN.md`](BUILD_PLAN.md) section 3: seL4 with MCS, the Microkit framework, AArch64 on QEMU `virt`, Rust via the `rust-sel4` crates.
- `BUILD_PLAN.md` section 5: the protection domains (compartments) and the system description sketch.
- `BUILD_PLAN.md` section 8.3: what the proofs cover here and what they don't.

**Study path, in order**

1. **Operating-system concepts** (about 4 weeks). Finish [Three Easy Pieces](https://pages.cs.wisc.edu/~remzi/OSTEP/): memory, scheduling, concurrency, devices. Optionally browse MIT's teaching kernel [xv6](https://pdos.csail.mit.edu/6.828/2023/xv6.html) to see a whole small kernel.
2. **Rust** (about 6 weeks). [The Rust Book](https://doc.rust-lang.org/book/), then [The Embedded Rust Book](https://docs.rust-embedded.org/book/) for `no_std`, which means Rust with no operating system underneath. If you'd rather start with C, [Modern C](https://gustedt.gitlabpages.inria.fr/modern-c/) is free.
3. **seL4 itself** (about 4 weeks). The [seL4 whitepaper](https://sel4.systems/About/seL4-whitepaper.pdf) first, since it's written for non-specialists. Then the [Microkit tutorial](https://trustworthy.systems/projects/microkit/tutorial/) and the [rust-sel4 repo](https://github.com/seL4/rust-sel4). The [seL4 tutorials](https://docs.sel4.systems/Tutorials/) go deeper into capabilities.
4. **ARM** (about 2 weeks). Arm's [Learn the architecture: exception model](https://developer.arm.com/documentation/102412/latest/) and the [QEMU Arm docs](https://www.qemu.org/docs/master/system/target-arm.html). Aim for exception levels and memory mapping, not assembly.
5. **A taste of formal verification** (about 4 weeks, optional). [Software Foundations](https://softwarefoundations.cis.upenn.edu/) volume 1 teaches what a machine-checked proof is. Then read the original [seL4 verification paper](https://www.sigops.org/s/conferences/sosp/2009/papers/klein-sosp09.pdf) (2009). seL4's proofs use Isabelle; [Concrete Semantics](http://concrete-semantics.org/) is the free introduction if you want it.

**Check yourself:** explain why `BUILD_PLAN.md` section 3.2 rules out gVisor, Kata and Firecracker for the final habitat, even though Phase 0 uses all of them.

## At a glance and a suggested schedule

| Topic | Rough time | Where it shows up first |
| --- | --- | --- |
| 1. Virtualization | 19 hours | `phase0/notes/P0.2` to `P0.4` |
| 2. Linux basics | 14 hours | `phase0/sandboxes/setup_*.sh` |
| 3. Python | 12 hours | `phase0/airlock/` |
| 4. Git and GitHub Actions | 7 hours | `.github/workflows/phase0.yml` |
| 5. Cloud and Terraform | 7 hours | `phase0/infra/gcp/` |
| 6. Security ideas | 14 hours | `PRD.md`, `phase0/airlock/` |
| 7. seL4 path | 6 to 12 months | `BUILD_PLAN.md` |

At about 6 hours a week:

1. **Weeks 1 to 4:** virtualization, with Linux basics alongside whenever a reading assumes them.
2. **Weeks 5 and 6:** Python, ending with the airlock demo.
3. **Week 7:** Git and GitHub Actions, ending with a read-through of a real check run.
4. **Week 8:** Cloud and Terraform, ending with one real create, run and destroy on Google Cloud.
5. **Weeks 9 and 10:** security ideas, ending with the Saltzer and Schroeder exercise.
6. **Weeks 11 and 12:** buffer. Reread the four Phase 0 notes; they should now read easily.
7. **Month 4 onward:** the seL4 path, in the order given in section 7.
