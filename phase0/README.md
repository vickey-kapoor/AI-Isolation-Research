# Phase 0: learning baseline

A small working version of the habitat's shape, built on today's isolation
tech, to learn from before the seL4 build. See [PLAN.md](PLAN.md) for the why
and the milestones, and [notes/](notes/) for what each milestone taught us.

## Layout

| Path | What it is | Side |
|---|---|---|
| `agent/toy_agent.py` | The stand-in resident. Solves the frozen tasks and writes answers to its outbox. Standard library only, shares no code with `airlock/` | Inside |
| `tasks/tasks.json` | The frozen task list, fixed before sealing | Both (read-only) |
| `airlock/` | Frames, verifiers, outbox reader, gate, budget, quarantine, ledger, governance | Outside |
| `tests/` | Tests for everything in `airlock/` | Outside |

## Run it

Needs Python 3.11 or newer.

```sh
cd phase0
pip install -r requirements.txt
python3 -m unittest discover -s tests -t . -v   # 31 tests
python3 -m airlock.demo                          # the whole path, end to end
```

The demo has no sandbox yet: the agent runs as an ordinary process. P0.2
puts it inside gVisor, P0.3 inside Firecracker.
