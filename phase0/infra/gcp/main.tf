# One VM for running Phase 0 by hand: gVisor and Firecracker.
# Firecracker needs /dev/kvm, which on Google Cloud means nested
# virtualization, which needs an Intel machine type such as N2.

resource "google_project_service" "compute" {
  service            = "compute.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "iap" {
  service            = "iap.googleapis.com"
  disable_on_destroy = false
}

resource "google_compute_firewall" "ssh_via_iap" {
  name          = "${var.name}-allow-ssh-iap"
  network       = "default"
  direction     = "INGRESS"
  source_ranges = var.ssh_source_ranges
  target_tags   = [var.name]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  depends_on = [google_project_service.compute]
}

resource "google_compute_instance" "lab" {
  name         = var.name
  machine_type = var.machine_type
  zone         = var.zone
  tags         = [var.name]
  labels       = { purpose = "phase0-learning" }

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2404-lts-amd64"
      size  = var.disk_gb
      type  = "pd-balanced"
    }
  }

  # The VM needs outbound internet to download gVisor, Firecracker and
  # the Python image. The external IP is for that; inbound is limited to
  # SSH from the IAP range by the firewall rule above.
  network_interface {
    network = "default"
    access_config {}
  }

  # The setting that makes /dev/kvm appear inside the VM.
  advanced_machine_features {
    enable_nested_virtualization = true
  }

  scheduling {
    provisioning_model          = var.spot ? "SPOT" : "STANDARD"
    preemptible                 = var.spot
    automatic_restart           = var.spot ? false : true
    on_host_maintenance         = var.spot ? "TERMINATE" : "MIGRATE"
    instance_termination_action = var.spot ? "STOP" : null
  }

  metadata = {
    enable-oslogin = "TRUE"
  }

  # Installs the tools on first boot. Takes a minute or two after the VM starts.
  metadata_startup_script = file("${path.module}/startup.sh")

  depends_on = [google_project_service.compute]
}
