###############################################################################
# NetTwin 3.0 — VPC Prod East (us-east-1)
#
# Complete multi-tier enterprise VPC following AWS Well-Architected design:
# - Dual public subnets for ALB and NAT Gateway
# - Isolated private subnets for Web, App, and Data tiers
# - S3 Gateway Endpoint to eliminate NAT data processing charges
# - VPC Flow Logs streaming to CloudWatch
###############################################################################

resource "aws_vpc" "prod_east" {
  provider             = aws.east
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name        = "vpc-prod-east"
    Environment = "prod-east"
    Role        = "organization-twin-prod"
  }
}

resource "aws_internet_gateway" "igw_east" {
  provider = aws.east
  vpc_id   = aws_vpc.prod_east.id

  tags = {
    Name = "igw-prod-east"
  }
}

# =============================================================================
# Public Subnets (ALB & NAT only)
# =============================================================================
resource "aws_subnet" "public_1a" {
  provider                = aws.east
  vpc_id                  = aws_vpc.prod_east.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.east_region}a"
  map_public_ip_on_launch = true

  tags = {
    Name = "subnet-public-1a"
    Tier = "public-ingress"
  }
}

resource "aws_subnet" "public_1b" {
  provider                = aws.east
  vpc_id                  = aws_vpc.prod_east.id
  cidr_block              = "10.0.2.0/24"
  availability_zone       = "${var.east_region}b"
  map_public_ip_on_launch = true

  tags = {
    Name = "subnet-public-1b"
    Tier = "public-ingress"
  }
}

# =============================================================================
# NAT Gateway (in Public 1a)
# =============================================================================
resource "aws_eip" "nat_east" {
  provider = aws.east
  domain   = "vpc"

  tags = {
    Name = "eip-nat-prod-east"
  }
}

resource "aws_nat_gateway" "nat_east" {
  provider      = aws.east
  allocation_id = aws_eip.nat_east.id
  subnet_id     = aws_subnet.public_1a.id

  tags = {
    Name = "nat-prod-east-1a"
  }

  depends_on = [aws_internet_gateway.igw_east]
}

# =============================================================================
# Private Subnets
# =============================================================================
# Web Tier (web1, web2)
resource "aws_subnet" "private_web_1a" {
  provider          = aws.east
  vpc_id            = aws_vpc.prod_east.id
  cidr_block        = "10.0.10.0/24"
  availability_zone = "${var.east_region}a"

  tags = {
    Name = "subnet-private-web-1a"
    Tier = "web-tier"
  }
}

resource "aws_subnet" "private_web_1b" {
  provider          = aws.east
  vpc_id            = aws_vpc.prod_east.id
  cidr_block        = "10.0.11.0/24"
  availability_zone = "${var.east_region}b"

  tags = {
    Name = "subnet-private-web-1b"
    Tier = "web-tier"
  }
}

# App Tier (app1, app2 microservices)
resource "aws_subnet" "private_app_1a" {
  provider          = aws.east
  vpc_id            = aws_vpc.prod_east.id
  cidr_block        = "10.0.20.0/24"
  availability_zone = "${var.east_region}a"

  tags = {
    Name = "subnet-private-app-1a"
    Tier = "app-tier"
  }
}

resource "aws_subnet" "private_app_1b" {
  provider          = aws.east
  vpc_id            = aws_vpc.prod_east.id
  cidr_block        = "10.0.21.0/24"
  availability_zone = "${var.east_region}b"

  tags = {
    Name = "subnet-private-app-1b"
    Tier = "app-tier"
  }
}

# Data Tier (db1 RDS MySQL - requires 2 AZs for DB subnet group)
resource "aws_subnet" "private_data_1a" {
  provider          = aws.east
  vpc_id            = aws_vpc.prod_east.id
  cidr_block        = "10.0.30.0/24"
  availability_zone = "${var.east_region}a"

  tags = {
    Name = "subnet-private-data-1a"
    Tier = "data-tier"
  }
}

resource "aws_subnet" "private_data_1b" {
  provider          = aws.east
  vpc_id            = aws_vpc.prod_east.id
  cidr_block        = "10.0.31.0/24"
  availability_zone = "${var.east_region}b"

  tags = {
    Name = "subnet-private-data-1b"
    Tier = "data-tier"
  }
}

# =============================================================================
# Routing
# =============================================================================
# Public Route Table -> IGW
resource "aws_route_table" "public_east" {
  provider = aws.east
  vpc_id   = aws_vpc.prod_east.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw_east.id
  }

  tags = {
    Name = "rt-public-prod-east"
  }
}

resource "aws_route_table_association" "pub_1a" {
  provider       = aws.east
  subnet_id      = aws_subnet.public_1a.id
  route_table_id = aws_route_table.public_east.id
}

resource "aws_route_table_association" "pub_1b" {
  provider       = aws.east
  subnet_id      = aws_subnet.public_1b.id
  route_table_id = aws_route_table.public_east.id
}

# Private Route Table -> NAT Gateway
resource "aws_route_table" "private_east" {
  provider = aws.east
  vpc_id   = aws_vpc.prod_east.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.nat_east.id
  }

  tags = {
    Name = "rt-private-prod-east"
  }
}

resource "aws_route_table_association" "web_1a" {
  provider       = aws.east
  subnet_id      = aws_subnet.private_web_1a.id
  route_table_id = aws_route_table.private_east.id
}

resource "aws_route_table_association" "web_1b" {
  provider       = aws.east
  subnet_id      = aws_subnet.private_web_1b.id
  route_table_id = aws_route_table.private_east.id
}

resource "aws_route_table_association" "app_1a" {
  provider       = aws.east
  subnet_id      = aws_subnet.private_app_1a.id
  route_table_id = aws_route_table.private_east.id
}

resource "aws_route_table_association" "app_1b" {
  provider       = aws.east
  subnet_id      = aws_subnet.private_app_1b.id
  route_table_id = aws_route_table.private_east.id
}

resource "aws_route_table_association" "data_1a" {
  provider       = aws.east
  subnet_id      = aws_subnet.private_data_1a.id
  route_table_id = aws_route_table.private_east.id
}

resource "aws_route_table_association" "data_1b" {
  provider       = aws.east
  subnet_id      = aws_subnet.private_data_1b.id
  route_table_id = aws_route_table.private_east.id
}

# =============================================================================
# S3 Gateway Endpoint (Zero Cost, No NAT Data Processing for S3)
# =============================================================================
resource "aws_vpc_endpoint" "s3_east" {
  provider          = aws.east
  vpc_id            = aws_vpc.prod_east.id
  service_name      = "com.amazonaws.${var.east_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private_east.id, aws_route_table.public_east.id]

  tags = {
    Name = "vpce-s3-prod-east"
  }
}

# =============================================================================
# VPC Flow Logs to CloudWatch
# =============================================================================
resource "aws_cloudwatch_log_group" "flow_logs_east" {
  provider          = aws.east
  name              = "/vpc/prod-east"
  retention_in_days = 7

  tags = {
    Name = "cw-vpc-flow-logs-prod-east"
  }
}

resource "aws_iam_role" "flow_logs_role_east" {
  provider = aws.east
  name     = "nettwin-flow-logs-role-east"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "vpc-flow-logs.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "flow_logs_policy_east" {
  provider = aws.east
  name     = "nettwin-flow-logs-policy-east"
  role     = aws_iam_role.flow_logs_role_east.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams"
        ]
        Effect   = "Allow"
        Resource = "*"
      }
    ]
  })
}

resource "aws_flow_log" "prod_east" {
  provider        = aws.east
  iam_role_arn    = aws_iam_role.flow_logs_role_east.arn
  log_destination = aws_cloudwatch_log_group.flow_logs_east.arn
  traffic_type    = "ALL"
  vpc_id          = aws_vpc.prod_east.id
}
