# Yoohoo Infrastructure — Hetzner Cloud VPS
#
# Usage:
#   terraform init
#   terraform plan
#   terraform apply

terraform {
  required_version = ">= 1.5"

  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.45"
    }
  }
}

provider "hcloud" {
  token = var.hcloud_token
}

# --- SSH Key ---

resource "hcloud_ssh_key" "deploy" {
  name       = "yoohoo-deploy"
  public_key = var.ssh_public_key
}

# --- Firewall ---

resource "hcloud_firewall" "web" {
  name = "yoohoo-web"

  # SSH
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  # HTTP
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "80"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  # HTTPS
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "443"
    source_ips = ["0.0.0.0/0", "::/0"]
  }
}

# --- Server ---

resource "hcloud_server" "app" {
  name        = var.server_name
  server_type = var.server_type
  location    = var.location
  image       = "ubuntu-24.04"

  ssh_keys = [hcloud_ssh_key.deploy.id]

  firewall_ids = [hcloud_firewall.web.id]

  user_data = templatefile("${path.module}/cloud-init.yml", {
    ssh_public_key = var.ssh_public_key
  })

  labels = {
    project     = "yoohoo"
    environment = "production"
    managed_by  = "terraform"
  }

  lifecycle {
    ignore_changes = [user_data]
  }
}
