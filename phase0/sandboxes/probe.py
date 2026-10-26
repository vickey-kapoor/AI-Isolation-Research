"""Configuration check that runs inside a sandbox, with the same settings as the habitat.

It answers plain yes/no questions about how the sandbox is set up, so we
can confirm the configuration matches the plan:

  - Is there any network interface apart from loopback?
  - Can a network socket reach anything?
  - Is the root filesystem read-only?
  - Is the task list read-only?
  - Is the outbox the one writable path we gave it?

Usage: python3 probe.py [OUTBOX_PATH]

It prints one JSON line to stdout. That stdout is a test-only channel used
while setting up; the real habitat run has no stdout path to the outside.
Standard library only.
"""

import json
import os
import socket
import sys


def interfaces() -> list[str]:
    try:
        with open("/proc/net/dev") as f:
            lines = f.read().splitlines()[2:]
        return sorted(line.split(":")[0].strip() for line in lines)
    except OSError:
        return [name for _, name in socket.if_nameindex()]


def can_connect() -> bool:
    try:
        s = socket.create_connection(("1.1.1.1", 53), timeout=2)
        s.close()
        return True
    except OSError:
        return False


def can_write(path: str) -> bool:
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT, 0o600)
        os.close(fd)
        return True
    except OSError:
        return False


if __name__ == "__main__":
    print(json.dumps({
        "interfaces": interfaces(),
        "network_reachable": can_connect(),
        "root_writable": can_write("/probe-was-here"),
        "tasks_writable": can_write("/habitat/tasks.json"),
        "outbox_writable": can_write(sys.argv[1] if len(sys.argv) > 1 else "/habitat/outbox.bin"),
        "uid": os.getuid(),
    }))
