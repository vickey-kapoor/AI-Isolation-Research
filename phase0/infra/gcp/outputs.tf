output "ssh" {
  description = "Run this to log in."
  value       = "gcloud compute ssh ${google_compute_instance.lab.name} --zone=${var.zone} --tunnel-through-iap"
}

output "stop" {
  description = "Run this to pause the VM (keeps the disk, stops most of the cost)."
  value       = "gcloud compute instances stop ${google_compute_instance.lab.name} --zone=${var.zone}"
}
