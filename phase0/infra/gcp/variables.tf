variable "project_id" {
  description = "Your Google Cloud project ID (not its name). Find it with: gcloud config get-value project"
  type        = string
}

variable "region" {
  description = "Region for the VM."
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "Zone for the VM. Change it if Google says there's no capacity."
  type        = string
  default     = "us-central1-a"
}

variable "name" {
  description = "Name of the VM."
  type        = string
  default     = "habitat-lab"
}

variable "machine_type" {
  description = "N2 is Intel, which supports nested virtualization. 4 vCPU and 16 GB is plenty for Phase 0."
  type        = string
  default     = "n2-standard-4"
}

variable "spot" {
  description = "Spot VMs are much cheaper, but Google may stop them at any time. Set false for a normal VM."
  type        = bool
  default     = true
}

variable "disk_gb" {
  description = "Boot disk size in GB."
  type        = number
  default     = 30
}

variable "ssh_source_ranges" {
  description = "Who may reach port 22. The default is Google's IAP range only, so SSH works through 'gcloud compute ssh --tunnel-through-iap' and the VM's SSH port isn't open to the internet."
  type        = list(string)
  default     = ["35.235.240.0/20"]
}
