# Running Phase 0 on your Google Cloud account

This guide takes you from nothing to running everything in `phase0/` yourself on one Google Cloud virtual machine. It takes about 20 minutes. All commands are copy and paste.

**What you'll run.** Only the code in this folder: the puzzle program (an ordinary Python program, not an AI), the airlock, and the two sandboxes (gVisor and Firecracker). Nothing here connects to anything outside the machine.

**Cost.** One `n2-standard-4` Spot VM. That's roughly $0.05 to $0.10 an hour while it's running, plus a few cents a day for its disk while it's stopped. Prices change, so check the [pricing calculator](https://cloud.google.com/products/calculator). Step 7 shows how to stop or delete it.

**Status of each part:**

| Part | Status |
|---|---|
| Tests, demo, gVisor | Have run on Claude's machine and in GitHub's checks |
| Firecracker | Has run in GitHub's checks (PR #5, Firecracker v1.15.0). Not yet run on Google Cloud, so your run will be the first there |
| Stacked (gVisor inside Firecracker) | Has run in GitHub's checks (PR #8). Not yet run on Google Cloud |

---

**Prefer Terraform?** [infra/gcp/](infra/gcp/README.md) creates the same VM as steps 1 to 3 as code. Then continue from step 4 here.

## 1. Open Cloud Shell

Go to [console.cloud.google.com](https://console.cloud.google.com), pick (or create) a project with billing turned on, and click the **Activate Cloud Shell** button (the `>_` icon, top right). A terminal opens in your browser. You don't need anything installed on your laptop.

Turn on the Compute Engine API once:

```sh
gcloud services enable compute.googleapis.com
```

## 2. Create the VM

```sh
gcloud compute instances create habitat-lab \
  --zone=us-central1-a \
  --machine-type=n2-standard-4 \
  --enable-nested-virtualization \
  --provisioning-model=SPOT \
  --instance-termination-action=STOP \
  --image-family=ubuntu-2404-lts-amd64 \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=30GB
```

What the flags mean:
- `n2-standard-4`: 4 CPUs and 16 GB of memory, on Intel CPUs, which support nested virtualization.
- `--enable-nested-virtualization`: lets this VM run VMs of its own. Firecracker needs this. Without it there's no `/dev/kvm`.
- `--provisioning-model=SPOT`: much cheaper, but Google can stop it at any time if it needs the capacity. If that happens, just start it again (step 7). Nothing is lost, because the disk stays.

If `us-central1-a` has no capacity, try another zone, such as `us-central1-b` or `europe-west4-a`.

## 3. Log in to the VM

```sh
gcloud compute ssh habitat-lab --zone=us-central1-a
```

You're now inside the VM. Check that KVM is there:

```sh
ls -l /dev/kvm
```

You should see a line starting with `crw`. If it says "No such file", nested virtualization isn't on. gVisor will still work, but Firecracker won't.

## 4. Install the tools and get the code

```sh
sudo apt-get update
sudo apt-get install -y git docker.io python3-venv e2fsprogs

git clone https://github.com/vickey-kapoor/ai-isolation-research.git
cd ai-isolation-research/phase0

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

If the repository is private, `git clone` asks for a login. The easiest fix is to run `sudo apt-get install -y gh && gh auth login` first and follow its prompts.

## 5. Run the tests and the demo (no sandbox)

```sh
.venv/bin/python -m unittest discover -s tests -t . -v
.venv/bin/python -m airlock.demo
```

The tests should end with `OK`. The demo prints each step: sealing, the puzzle program writing answers, the gate reading them, a release that fails with one signature and works with two, a budget cut, termination, and the log catching an edit.

## 6. Run the sandboxes

**gVisor:**

```sh
./sandboxes/setup_gvisor.sh ~/habitat-rootfs
sudo .venv/bin/python -m sandboxes.run_gvisor --rootfs ~/habitat-rootfs
```

**Firecracker:**

```sh
./sandboxes/setup_firecracker.sh ~/habitat-fc
sudo .venv/bin/python -m sandboxes.run_firecracker --kernel ~/habitat-fc/vmlinux --rootfs ~/habitat-fc/rootfs
```

**Stacked (gVisor inside Firecracker):** needs both setups above, then:

```sh
sudo .venv/bin/python -m sandboxes.run_stacked --kernel ~/habitat-fc/vmlinux --rootfs ~/habitat-fc/rootfs
```

Each run prints:
- **configuration check:** what the probe saw from inside the sandbox. You want `"interfaces": ["lo"]`, `"network_reachable": false`, `"root_writable": false` and `"outbox_writable": true`.
- **the report:** start time, what the gate did, how many answers reached quarantine, kill time, and `"leftovers": []`.
- **`PROBLEM:` lines**, only if something didn't match the plan. The command then exits with an error.

Each run leaves its results in a folder under `/tmp/habitat-…`, printed as `results folder:` at the end. `report.json` is the summary and `ledger.jsonl` is the log.

## 7. Stop or delete the VM when you're done

From Cloud Shell, not from inside the VM:

```sh
gcloud compute instances stop habitat-lab --zone=us-central1-a     # pause, keeps the disk
gcloud compute instances start habitat-lab --zone=us-central1-a    # resume later
gcloud compute instances delete habitat-lab --zone=us-central1-a   # remove it completely
```

A stopped VM costs only its disk. A deleted one costs nothing.

## If something goes wrong

Copy the full output of the command that failed and paste it into the project thread. Also include the line from `ls -l /dev/kvm`.
