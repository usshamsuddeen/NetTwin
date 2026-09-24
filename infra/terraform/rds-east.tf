###############################################################################
# NetTwin 3.0 — RDS MySQL Database & S3 Telemetry Lake Prod East (us-east-1)
#
# Free-Tier db.t3.micro MySQL instance (20GB gp3 storage) in private data tier.
# Inbound 3306 restricted strictly to the Web/App security group.
# S3 Telemetry Lake bucket dynamically named with current account ID.
###############################################################################

resource "random_password" "db_password" {
  length  = 16
  special = false
}

# =============================================================================
# Security Group for Database Tier
# =============================================================================
resource "aws_security_group" "sg_db_east" {
  provider    = aws.east
  name        = "nettwin-db-prod-east"
  description = "Access to MySQL db1 strictly from web and app tier"
  vpc_id      = aws_vpc.prod_east.id

  ingress {
    description     = "MySQL port from Web instances"
    from_port       = 3306
    to_port         = 3306
    protocol        = "tcp"
    security_groups = [aws_security_group.sg_web_east.id]
  }

  egress {
    description = "Egress to local VPC only"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [aws_vpc.prod_east.cidr_block]
  }

  tags = {
    Name = "sg-db-prod-east"
  }
}

# =============================================================================
# DB Subnet Group (2 AZs required)
# =============================================================================
resource "aws_db_subnet_group" "db_subnets_east" {
  provider   = aws.east
  name       = "dbsg-prod-east"
  subnet_ids = [aws_subnet.private_data_1a.id, aws_subnet.private_data_1b.id]

  tags = {
    Name = "dbsg-prod-east"
  }
}

# =============================================================================
# RDS MySQL Instance (db1) - 100% Free Tier Eligible
# =============================================================================
resource "aws_db_instance" "db1" {
  provider               = aws.east
  identifier             = "db1-prod-east"
  engine                 = "mysql"
  engine_version         = "8.0"
  instance_class         = "db.t3.micro"
  allocated_storage      = 20
  max_allocated_storage  = 20
  storage_type           = "gp3"
  db_name                = "nettwin"
  username               = "nettwin_admin"
  password               = random_password.db_password.result
  db_subnet_group_name   = aws_db_subnet_group.db_subnets_east.name
  vpc_security_group_ids = [aws_security_group.sg_db_east.id]
  skip_final_snapshot    = true
  publicly_accessible    = false

  tags = {
    Name        = "db1"
    Role        = "database-primary"
    EntityId    = "db1"
    Project     = "nettwin"
    Environment = "prod-east"
  }
}

# =============================================================================
# S3 Telemetry Lake (Dynamic Account ID - Never Hardcoded)
# =============================================================================
resource "aws_s3_bucket" "telemetry_lake_east" {
  provider      = aws.east
  bucket        = "nettwin-telemetry-lake-east-${data.aws_caller_identity.current.account_id}"
  force_destroy = true

  tags = {
    Name        = "nettwin-telemetry-lake-east"
    Project     = "nettwin"
    Environment = "prod-east"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "telemetry_crypto" {
  provider = aws.east
  bucket   = aws_s3_bucket.telemetry_lake_east.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "telemetry_block_public" {
  provider                = aws.east
  bucket                  = aws_s3_bucket.telemetry_lake_east.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
