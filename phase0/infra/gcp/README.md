# Terraform for the Phase 0 lab VM on Google Cloud

This creates the same VM as steps 1 to 3 of [../../GCP_SETUP.md](../../GCP_SETUP.md), as code:

- one `n2-standard-4` VM (Intel, 4 vCPU, 16 GB), Spot by default
- **nested virtualization on**, so `/dev/kvm` exists and Firecracker works
- Ubuntu 24.04, 30 GB disk
- a startup script that installs `git`, `docker.io`, `python3-venv` and `e2fsprogs`
- a firewall rule that allows SSH only from Google's IAP range, so port 22 isn't open to the internet
- the Compute Engine and IAP APIs turned on

It creates nothing else. The VM's state (`terraform.tfstate`) stays on your machine or in Cloud Shell. Don't commit it.

## Use it

From [Cloud Shell](https://console.cloud.google.com), which already has Terraform and is logged in to your account:

```sh
git clone https://github.com/vickey-kapoor/ai-isolation-research.git
cd ai-isolation-research/phase0/infra/gcp
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars: set project_id (find it with: gcloud config get-value project)

terraform init
terraform plan      # shows what it will create; read it before applying
terraform apply     # type "yes" to create the VM
```

When it finishes, it prints the SSH command. Wait a minute or two for the startup script, then:

```sh
gcloud compute ssh habitat-lab --zone=us-central1-a --tunnel-through-iap
ls -l /dev/kvm                       # should start with "crw"
ls /var/lib/phase0-ready             # exists once the tools are installed
```

Then continue from step 4 of [../../GCP_SETUP.md](../../GCP_SETUP.md). You can skip its `apt-get install` line, because the startup script already did that.

## Stop or remove it

```sh
gcloud compute instances stop habitat-lab --zone=us-central1-a   # pause; you pay only for the disk
terraform destroy                                                # remove everything this created
```

`terraform destroy` removes the VM, its disk and the firewall rule. It leaves the two APIs turned on, which costs nothing.

## Cost

Roughly $0.05 to $0.10 an hour while running as Spot, plus a few cents a day for the disk. Prices change, so check the [pricing calculator](https://cloud.google.com/products/calculator).
