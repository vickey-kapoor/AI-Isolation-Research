# Phase 0 findings (draft)

**Date:** 2026-10-27
**Status:** draft. Q1 to Q5 have answers backed by code and runs. Q6 waits for the seL4 taster (P0.S). Nothing here changes PRD.md or BUILD_PLAN.md. The proposals at the end are for Vickey to accept or reject.

**What was run, and where.** Everything here comes from the puzzle program (an ordinary Python program that factors numbers and solves sudokus, not an AI) and the outside airlock code in `phase0/`. The runs happened in three places:
- GitHub's automated checks. Each job runs on a fresh Ubuntu VM that GitHub provides, with KVM.
- Claude's cloud machine, which has no KVM, so gVisor only.
- Once on Vickey's Google Cloud VM, Firecracker only (see the P0.3 note).

Each section links its run. Every number comes from one run and is rough.

---

## Q1. What freedom does the inside still have over what reaches the outside?

**Answer: with first come, first served, a lot more than it looks. With an outside-fixed agenda, at most one yes/no per task. If a missed task closes the airlock, only "when to stop".**

Unique answers and canonical encodings mean every passing frame for a task is byte-for-byte the same. So the content of an answer carries nothing extra. What the inside could still choose:

| Gate design | What the inside chooses | Upper bound, 7 tasks |
|---|---|---|
| First come, first served (P0.1) | which tasks, in what order, in which period | over 19 bits (order alone is log2(7!) ≈ 12.3) |
| Agenda, a missed task is skipped | which tasks are answered by their due time | 7 bits |
| Agenda, a missed task closes the airlock | when to stop | 3 bits (one of 8 outcomes) |

These are counts of distinguishable outcomes. They're upper bounds on what the inside can choose, not a measured leak.

**What we built and tested.** `airlock/agenda.py`, and tests in `tests/test_agenda.py`, which pass in GitHub's checks.
- With an agenda fixed at sealing, verified answers wait in a holding area the inside can't see.
- Each answer is admitted only at its task's due tick.
- Seven different write orders gave exactly the same quarantine contents at the same ticks.
- Without the agenda, they didn't.

**Something we didn't expect.** The first version set the first due time too early, and the inside's *slot placement* decided whether an answer was seen in time. That made placement a timing choice again. The first deadline must leave time for the gate to read every slot once. A test now pins that down.

**Also from P0.1:** anything the outside records about the inside is itself a channel, including logs, counters and error messages. The gate records only what entered quarantine. Rejections leave no trace.

## Q2. How small can a verifier be, and can it be isolated?

**Answer: our part is small (312 lines, comments included). The real weight is the language runtime under it. Isolating it is cheap. Isolation doesn't stop a wrong verdict, though, so it doesn't replace a second, independent verifier.**

**What we built.**
- `airlock/verifier.py` runs the checks as a separate program. It reads 256-byte frames on standard input and answers each with exactly 4 bytes. A failure carries no reason.
- `sandboxes/verifier_box.py` runs that program under gVisor:
  - no network
  - nothing writable at all, not even `/tmp`
  - only the four files it imports, plus the task list, read-only
  - user "nobody"

**Results** ([run](https://github.com/vickey-kapoor/ai-isolation-research/actions/runs/40448664815/job/122005928224), GitHub's checks):

| | In-process | In its own gVisor box |
|---|---|---|
| Verdicts on 220 frames (7 good and 4 bad, repeated) | reference | identical |
| Time per frame | 44 µs | 119 µs |
| Start-up | none | 0.27 s, once |
| Network, writable paths | everything the gate has | loopback only, none |
| Leftovers after stop | | none |

**What it means.**
- At one frame per gate tick, 0.1 ms is nothing. Isolation is affordable.
- Our 312 lines run on a Python interpreter and its standard library, which are millions of lines we didn't write. For the seL4 plan this argues for a verifier with no runtime under it. The plan's Rust choice already points that way.
- A broken verifier inside a box still answers "pass" or "fail". The box limits what a broken verifier can *reach*. It doesn't make its *verdict* right. The PRD's second, independent verifier (R-L3) is what covers that, so it shouldn't stay a stretch goal.

## Q3. What does governance actually need to do?

**Answer: four operations were enough to run every Phase 0 scenario: release, lower the budget, close, and terminate. The open questions are policy, not code.**

The code has 2-of-3 Ed25519 signatures, one-time nonces whose replay protection survives a restart, and a hash-chained ledger. It has no "widen" operation at all.

Gaps the PRD doesn't specify yet (unchanged since P0.1):
- **Should narrowing be easier than releasing?** Today close and terminate need two signatures, like a release. "Fail closed" suggests one signature should be enough to *narrow*. This is the same question as BUILD_PLAN's open "single-steward emergency stop" decision.
- **Key custody and loss.** How stewards hold keys, and what happens when one is lost.
- **Who remembers the ledger head.** A hash chain only catches edits if someone kept an earlier fingerprint. For example, each steward could keep the latest head hash.
- **The agenda is a governance object too.** Its order and due times are fixed at sealing (Q1). Changing them later should be at least as hard as a release, or it reopens the order channel.

## Q4. What does each sandbox still trust, measured rather than assumed?

**Answer: every one still relies on the unverified host kernel. Beyond that, they differ in ways we could only see by measuring.**

The run scripts now record:
- the files each wall is built from, with size and fingerprint;
- every host process the habitat shows while it runs, with that process's host user, system call filter, privilege and namespace status.

`sandboxes/compare.py` puts them side by side. These results come from GitHub's checks on host kernel 6.17.0-1022-azure ([comparison job](https://github.com/vickey-kapoor/ai-isolation-research/actions/runs/40448664815/job/122006119224)):

| | No sandbox | gVisor | Firecracker | Stacked |
|---|---|---|---|---|
| Code the walls are built from | none | 164.9 MB | 49.9 MB (VMM 3.4, jailer 2.2, guest kernel 44.3) | 214.8 MB |
| Host processes while running | 1 | 2 | 1 | 1 |
| ... with a system call filter | 0 | 2 | 1 | 1 |
| ... running as host user 0 | 0 | 2 | 0 | 0 |
| ... with their own network namespace | 0 | 2 | 0, then 1 after the fix below | 0, then 1 after the fix below |

What measuring showed that assuming wouldn't have:
1. **The jailed Firecracker process was still in the host's network namespace.** The VM has no network device, but the VMM process itself could still see the host network. It was confined only by its system call filter. The jailer now gets an empty network namespace, made at sealing and removed by the kill switch. The next run confirmed the VMM in a network namespace of its own, with no leftovers ([comparison job](https://github.com/vickey-kapoor/ai-isolation-research/actions/runs/40448854493/job/122006690343)). This finding came straight out of the first measured run.
2. **gVisor's two host processes run as host user 0.** They have a reduced set of capabilities, a system call filter, and their own namespaces, but the user namespace maps root to root. gVisor's rootless and user-mapping options are worth trying next.
3. **Stacking shows the host only one process: the VMM.** gVisor is entirely inside the VM. From the host, stacked looks like plain Firecracker with four times the memory.
4. **Bytes on disk aren't trust.** gVisor's folder is large because it ships several helper binaries. The guest kernel is a download we fingerprint but didn't build. Size is a rough proxy, nothing more.

## Q5. Can the kill switch destroy all state with nothing from inside, and can we confirm it from outside?

**Answer: yes for every backend, in every run so far. The work was in defining "all state", not in stopping things.**

- Each kill switch acts only from outside and asks the inside nothing. Times were 0.01 to 0.07 s in GitHub's checks.
- Each backend keeps a list of what counts as its state, and a leftover check looks for each item afterwards:
  - processes, folders and disk images
  - cgroups and mounts
  - and now the VMM's network namespace
- The list grew twice from real runs. gVisor left a pinned network namespace behind, and the new Firecracker namespace had to be added. Both times the leftover check is what caught it.
- The finding for the PRD: "destroy all state" needs an explicit list per backend and an outside check against that list (R-O4, R-O6). A delete command on its own isn't enough.

## Q6. What does seL4 change?

**Not answered yet.** It waits for the seL4 taster (P0.S, on QEMU). What to look for there:
- the outbox as a shared memory region the gate can only read;
- the gate's fixed schedule as a timer-driven protection domain;
- the verifier as its own protection domain with one channel in and one out;
- the agenda as data fixed at build time.

---

## Proposed changes (for Vickey to decide; not applied)

**PRD**
1. Add an outside-fixed agenda to the airlock. Answers leave only in an order and at times fixed at sealing. The first deadline comes after one full read of the outbox. Choose a miss policy: skip, or close.
2. Make the second, independent verifier required, not optional (Q2).
3. Extend R-B2 ("outside measurements reveal nothing") to the airlock's own logs, counters and error messages.
4. Define "destroy all state" as a per-backend list plus an outside check.
5. Name the governance policy gaps from Q3 as open decisions.

**BUILD_PLAN (seL4)**
1. Give the gate an agenda. The order and due times are build-time data.
2. Run the verifier as its own protection domain, with no language runtime under it.
3. Add a leftover check to the kill-switch milestone.
