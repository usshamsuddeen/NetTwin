###############################################################################
# NetTwin 3.0 — Multi-Region Providers & Dynamic Caller Identity
#
# Region us-east-1: Org 1 PROD (The Enterprise Network Being Twinned)
# Region us-west-2: Org 2 TRAFFIC (Adversarial Fleet & Traffic Generator)
###############################################################################

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

# Primary Provider: us-east-1 (Prod East Twin)
provider "aws" {
  alias  = "east"
  region = var.east_region

  default_tags {
    tags = {
      Project     = "nettwin"
      Environment = "prod-east"
      ManagedBy   = "terraform"
    }
  }
}

# Secondary Provider: us-west-2 (Traffic Lab)
provider "aws" {
  alias  = "west"
  region = var.west_region

  default_tags {
    tags = {
      Project     = "nettwin"
      Environment = "traffic-west"
      ManagedBy   = "terraform"
    }
  }
}

# Dynamic caller identity — never hardcode account IDs
data "aws_caller_identity" "current" {
  provider = aws.east
}

variable "east_region" {
  description = "AWS region for Org 1 Prod (Digital Twin)"
  type        = string
  default     = "us-east-1"
}

variable "west_region" {
  description = "AWS region for Org 2 Traffic Generator"
  type        = string
  default     = "us-west-2"
}

variable "key_name" {
  description = "Optional existing EC2 key pair for SSH access"
  type        = string
  default     = ""
}
