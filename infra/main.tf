###############################################################################
# NetTwin 2.0 — AWS Infrastructure (Terraform)
#
# Creates a complete mini-enterprise network for real-time digital twin
# ingestion: VPC, 5 EC2 instances, NAT Instance, VPC Flow Logs to
# CloudWatch Logs, optional Traffic Mirroring, and least-privilege IAM.
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

provider "aws" {
  region = var.region
}

# Random suffix for globally unique S3 bucket name
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

data "aws_caller_identity" "current" {}

# Amazon Linux 2023 AMI (latest, x86_64)
data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

###############################################################################
# VPC + Subnets + Gateways
###############################################################################

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "nettwin-vpc", Project = "nettwin" }
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "nettwin-igw", Project = "nettwin" }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  map_public_ip_on_launch = true
  availability_zone       = "${var.region}a"

  tags = { Name = "nettwin-public", Project = "nettwin" }
}

resource "aws_subnet" "private" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.2.0/24"
  availability_zone = "${var.region}a"

  tags = { Name = "nettwin-private", Project = "nettwin" }
}

# Public route table → internet via IGW
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "nettwin-public-rt", Project = "nettwin" }
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.igw.id
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# Private route table → internet via NAT Instance
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "nettwin-private-rt", Project = "nettwin" }
}

resource "aws_route" "private_nat" {
  route_table_id         = aws_route_table.private.id
  destination_cidr_block = "0.0.0.0/0"
  network_interface_id   = aws_instance.nat.primary_network_interface_id
}

resource "aws_route_table_association" "private" {
  subnet_id      = aws_subnet.private.id
  route_table_id = aws_route_table.private.id
}

###############################################################################
# Security Groups
###############################################################################

resource "aws_security_group" "web" {
  name        = "nettwin-web-sg"
  description = "HTTP/SSH from admin IP; all egress"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "SSH from admin"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.your_ip]
  }

  ingress {
    description = "HTTP from admin"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = [var.your_ip]
  }

  ingress {
    description = "NetTwin dashboard"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = [var.your_ip]
  }

  ingress {
    description = "All from VPC"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [aws_vpc.main.cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "nettwin-web-sg", Project = "nettwin" }
}

resource "aws_security_group" "private" {
  name        = "nettwin-private-sg"
  description = "Internal only - from public subnet SG, no direct internet"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "All from web SG"
    from_port       = 0
    to_port         = 0
    protocol        = "-1"
    security_groups = [aws_security_group.web.id]
  }

  ingress {
    description = "All from VPC"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [aws_vpc.main.cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "nettwin-private-sg", Project = "nettwin" }
}

resource "aws_security_group" "mirror" {
  name        = "nettwin-mirror-sg"
  description = "VXLAN port 4789 for Traffic Mirroring"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "VXLAN from VPC"
    from_port   = 4789
    to_port     = 4789
    protocol    = "udp"
    cidr_blocks = [aws_vpc.main.cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "nettwin-mirror-sg", Project = "nettwin" }
}

###############################################################################
# IAM Role — Least Privilege for nettwin EC2
###############################################################################

resource "aws_iam_role" "nettwin" {
  name = "nettwin-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = { Project = "nettwin" }
}

resource "aws_iam_role_policy" "nettwin" {
  name = "nettwin-ec2-policy"
  role = aws_iam_role.nettwin.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat([
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:FilterLogEvents",
          "logs:GetLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/vpc/nettwin-flowlogs:*"
      },
      {
        Sid    = "CloudWatchMetrics"
        Effect = "Allow"
        Action = [
          "cloudwatch:GetMetricData",
          "cloudwatch:ListMetrics"
        ]
        Resource = "*"
      },
      {
        Sid    = "EC2Describe"
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances",
          "ec2:DescribeSubnets",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeInternetGateways",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DescribeVpcs"
        ]
        Resource = "*"
      },
      {
        Sid    = "S3Archive"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:ListBucket"]
        Resource = [
          "arn:aws:s3:::nettwin-flowlogs-${random_id.bucket_suffix.hex}",
          "arn:aws:s3:::nettwin-flowlogs-${random_id.bucket_suffix.hex}/*"
        ]
      },
      {
        Sid      = "CostExplorer"
        Effect   = "Allow"
        Action   = ["ce:GetCostAndUsage"]
        Resource = "*"
      },
      {
        Sid    = "CloudWatchBilling"
        Effect = "Allow"
        Action = [
          "cloudwatch:GetMetricData"
        ]
        Resource = "*"
      }
    ], var.enable_actuation ? [{
      Sid    = "NetTwinActuation"
      Effect = "Allow"
      Action = [
        "ec2:CreateSecurityGroup",
        "ec2:ModifyInstanceAttribute",
        "ec2:CreateNetworkAclEntry",
        "ec2:DeleteNetworkAclEntry",
        "ec2:CreateTags",
        "ssm:SendCommand",
        "ssm:GetCommandInvocation"
      ]
      Resource = "*"
      Condition = {
        StringEquals = {
          "aws:RequestTag/ManagedBy" = "NetTwin"
        }
      }
    }] : [])
  })
}

resource "aws_iam_instance_profile" "nettwin" {
  name = "nettwin-ec2-profile"
  role = aws_iam_role.nettwin.name
}

###############################################################################
# VPC Flow Logs → CloudWatch Log Group (primary, 30-60s delivery)
###############################################################################

resource "aws_cloudwatch_log_group" "flowlogs" {
  name              = "/vpc/nettwin-flowlogs"
  retention_in_days = 7

  tags = { Project = "nettwin" }
}

resource "aws_iam_role" "flowlog" {
  name = "nettwin-flowlog-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "vpc-flow-logs.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "flowlog" {
  name = "nettwin-flowlog-policy"
  role = aws_iam_role.flowlog.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams"
      ]
      Resource = "*"
    }]
  })
}

resource "aws_flow_log" "vpc" {
  vpc_id               = aws_vpc.main.id
  traffic_type         = "ALL"
  log_destination_type = "cloud-watch-logs"
  log_destination      = aws_cloudwatch_log_group.flowlogs.arn
  iam_role_arn         = aws_iam_role.flowlog.arn

  tags = { Name = "nettwin-vpc-flowlog", Project = "nettwin" }
}

###############################################################################
# S3 Bucket — Flow Log archive (long-term retention)
###############################################################################

resource "aws_s3_bucket" "flowlogs" {
  bucket        = "nettwin-flowlogs-${random_id.bucket_suffix.hex}"
  force_destroy = true

  tags = { Project = "nettwin" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "flowlogs" {
  bucket = aws_s3_bucket.flowlogs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "flowlogs" {
  bucket = aws_s3_bucket.flowlogs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

###############################################################################
# EC2 Instances
###############################################################################

# --- NAT Instance (t3.nano) — routes private subnet to internet -------------
resource "aws_instance" "nat" {
  ami                         = data.aws_ami.al2023.id
  instance_type               = "t3.nano"
  subnet_id                   = aws_subnet.public.id
  vpc_security_group_ids      = [aws_security_group.web.id]
  key_name                    = var.key_pair_name
  source_dest_check           = false  # CRITICAL for NAT forwarding
  associate_public_ip_address = true

  user_data = file("${path.module}/user_data/nat.sh")

  tags = { Name = "nettwin-nat", Project = "nettwin", Role = "nat" }
}

# --- web1 (public subnet) ---------------------------------------------------
resource "aws_instance" "web1" {
  ami                         = data.aws_ami.al2023.id
  instance_type               = var.node_instance_type
  subnet_id                   = aws_subnet.public.id
  vpc_security_group_ids      = [aws_security_group.web.id]
  key_name                    = var.key_pair_name
  iam_instance_profile        = aws_iam_instance_profile.nettwin.name
  associate_public_ip_address = true

  user_data = <<-EOF
    #!/bin/bash
    dnf install -y nginx
    systemctl enable --now nginx
  EOF

  tags = { Name = "nettwin-web1", Project = "nettwin", Role = "web" }
}

# --- app1 (private subnet) --------------------------------------------------
resource "aws_instance" "app1" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.node_instance_type
  subnet_id              = aws_subnet.private.id
  vpc_security_group_ids = [aws_security_group.private.id]
  key_name               = var.key_pair_name
  iam_instance_profile   = aws_iam_instance_profile.nettwin.name

  user_data = <<-EOF
    #!/bin/bash
    dnf install -y python3.12 python3.12-pip
  EOF

  tags = { Name = "nettwin-app1", Project = "nettwin", Role = "app" }
}

# --- db1 (private subnet) ---------------------------------------------------
resource "aws_instance" "db1" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.node_instance_type
  subnet_id              = aws_subnet.private.id
  vpc_security_group_ids = [aws_security_group.private.id]
  key_name               = var.key_pair_name
  iam_instance_profile   = aws_iam_instance_profile.nettwin.name

  user_data = <<-EOF
    #!/bin/bash
    dnf install -y postgresql16-server
    postgresql-setup --initdb
    systemctl enable --now postgresql
  EOF

  tags = { Name = "nettwin-db1", Project = "nettwin", Role = "db" }
}

# --- attacker (public subnet) -----------------------------------------------
resource "aws_instance" "attacker" {
  ami                         = data.aws_ami.al2023.id
  instance_type               = var.node_instance_type
  subnet_id                   = aws_subnet.public.id
  vpc_security_group_ids      = [aws_security_group.web.id]
  key_name                    = var.key_pair_name
  associate_public_ip_address = true

  user_data = file("${path.module}/user_data/attacker.sh")

  tags = { Name = "nettwin-attacker", Project = "nettwin", Role = "attacker" }
}

# --- nettwin engine (public subnet, t3.medium) ------------------------------
resource "aws_instance" "nettwin" {
  ami                         = data.aws_ami.al2023.id
  instance_type               = var.nettwin_instance_type
  subnet_id                   = aws_subnet.public.id
  vpc_security_group_ids      = [aws_security_group.web.id, aws_security_group.mirror.id]
  key_name                    = var.key_pair_name
  iam_instance_profile        = aws_iam_instance_profile.nettwin.name
  associate_public_ip_address = true

  user_data = file("${path.module}/user_data/nettwin.sh")

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
    encrypted   = true
  }

  tags = { Name = "nettwin-engine", Project = "nettwin", Role = "engine" }
}

###############################################################################
# Traffic Mirroring (optional — controlled by variable)
###############################################################################

resource "aws_ec2_traffic_mirror_filter" "main" {
  count       = var.enable_traffic_mirror ? 1 : 0
  description = "Accept all TCP traffic for L7 inspection"
  tags        = { Name = "nettwin-mirror-filter", Project = "nettwin" }
}

resource "aws_ec2_traffic_mirror_filter_rule" "tcp_in" {
  count                    = var.enable_traffic_mirror ? 1 : 0
  traffic_mirror_filter_id = aws_ec2_traffic_mirror_filter.main[0].id
  rule_number              = 100
  rule_action              = "accept"
  traffic_direction        = "ingress"
  protocol                 = 6  # TCP
  destination_cidr_block   = "0.0.0.0/0"
  source_cidr_block        = "0.0.0.0/0"
}

resource "aws_ec2_traffic_mirror_filter_rule" "tcp_out" {
  count                    = var.enable_traffic_mirror ? 1 : 0
  traffic_mirror_filter_id = aws_ec2_traffic_mirror_filter.main[0].id
  rule_number              = 200
  rule_action              = "accept"
  traffic_direction        = "egress"
  protocol                 = 6  # TCP
  destination_cidr_block   = "0.0.0.0/0"
  source_cidr_block        = "0.0.0.0/0"
}

resource "aws_ec2_traffic_mirror_target" "nettwin" {
  count                = var.enable_traffic_mirror ? 1 : 0
  network_interface_id = aws_instance.nettwin.primary_network_interface_id
  description          = "Mirror target: nettwin engine ENI"
  tags                 = { Name = "nettwin-mirror-target", Project = "nettwin" }
}

resource "aws_ec2_traffic_mirror_session" "web1" {
  count                    = var.enable_traffic_mirror ? 1 : 0
  network_interface_id     = aws_instance.web1.primary_network_interface_id
  traffic_mirror_filter_id = aws_ec2_traffic_mirror_filter.main[0].id
  traffic_mirror_target_id = aws_ec2_traffic_mirror_target.nettwin[0].id
  session_number           = 1
  description              = "Mirror web1 traffic to nettwin engine"
  tags                     = { Name = "nettwin-mirror-session-web1", Project = "nettwin" }
}

###############################################################################
# Billing Alert — CloudWatch EstimatedCharges alarm via SNS
###############################################################################

resource "aws_sns_topic" "billing_alerts" {
  count = var.billing_alert_email != "" ? 1 : 0
  name  = "nettwin-billing-alerts"

  tags = { Project = "nettwin" }
}

resource "aws_sns_topic_subscription" "billing_email" {
  count     = var.billing_alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.billing_alerts[0].arn
  protocol  = "email"
  endpoint  = var.billing_alert_email
}

resource "aws_cloudwatch_metric_alarm" "estimated_charges" {
  count               = var.billing_alert_email != "" ? 1 : 0
  alarm_name          = "nettwin-estimated-charges"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  period              = 86400
  statistic           = "Maximum"
  threshold           = var.billing_alert_threshold_usd
  alarm_description   = "Alert when estimated monthly AWS charges exceed $${var.billing_alert_threshold_usd}"
  alarm_actions       = [aws_sns_topic.billing_alerts[0].arn]
  ok_actions          = [aws_sns_topic.billing_alerts[0].arn]

  dimensions = {
    Currency = "USD"
  }

  tags = { Project = "nettwin" }
}
