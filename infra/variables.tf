###############################################################################
# NetTwin 2.0 — Terraform Variables
###############################################################################

variable "region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "key_pair_name" {
  description = "Name of an existing EC2 key pair for SSH access"
  type        = string
}

variable "your_ip" {
  description = "Your public IP in CIDR notation (e.g. 203.0.113.5/32) — SSH and dashboard access restricted to this IP"
  type        = string
}

variable "enable_traffic_mirror" {
  description = "Enable Traffic Mirroring from web1 ENI to nettwin engine"
  type        = bool
  default     = true
}

variable "nettwin_instance_type" {
  description = "EC2 instance type for the NetTwin engine"
  type        = string
  default     = "t3.medium"
}

variable "node_instance_type" {
  description = "EC2 instance type for web1, app1, db1, attacker nodes"
  type        = string
  default     = "t3.micro"
}

variable "enable_actuation" {
  description = "Grant NetTwin EC2 instance IAM permissions to mutate SGs/NACLs/SSM for closed-loop response (use with care; defaults to dry_run=true in app)"
  type        = bool
  default     = false
}

variable "billing_alert_email" {
  description = "Email address for billing alerts (required for EstimatedCharges alarm)"
  type        = string
  default     = ""
}

variable "billing_alert_threshold_usd" {
  description = "Estimated monthly charges threshold that triggers the billing alarm"
  type        = number
  default     = 10.0
}
