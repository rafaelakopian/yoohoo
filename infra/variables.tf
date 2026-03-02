# Yoohoo Terraform Variables

variable "hcloud_token" {
  description = "Hetzner Cloud API token"
  type        = string
  sensitive   = true
}

variable "ssh_public_key" {
  description = "SSH public key for the deploy user"
  type        = string
}

variable "server_name" {
  description = "Name of the VPS"
  type        = string
  default     = "yoohoo-prod"
}

variable "server_type" {
  description = "Hetzner server type (CCX13=2vCPU/8GB dedicated, CCX23=4vCPU/16GB dedicated)"
  type        = string
  default     = "ccx13"
}

variable "location" {
  description = "Hetzner datacenter location"
  type        = string
  default     = "nbg1" # Nuremberg, Germany
}
