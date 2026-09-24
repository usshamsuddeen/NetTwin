"""
NetTwin 3.0 — Multi-Region Infrastructure Test Suite
===================================================
Validates the 1-Account, 2-Region Terraform modular architecture:
- Verification of dynamic caller identity (no hardcoded account IDs)
- Well-Architected multi-tier VPC subnetting (public ALB, private Web/App/Data)
- NAT Gateway + S3 Gateway Endpoint to eliminate data fees
- Web security group isolation (inbound strictly from ALB)
- RDS MySQL Free Tier sizing and dynamic S3 naming
- West traffic generator configuration with cross-region ELB discovery
"""

import os
import sys
from pathlib import Path
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_REPO_ROOT_PATH = Path(_REPO_ROOT)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import re
from pathlib import Path
import pytest

TF_DIR = _REPO_ROOT_PATH / "infra" / "terraform"


def test_required_terraform_modules_exist():
    required_files = [
        "providers.tf",
        "vpc-east.tf",
        "alb-waf-east.tf",
        "ec2-east.tf",
        "rds-east.tf",
        "vpc-west.tf",
        "ec2-west.tf",
        "outputs.tf",
        "scripts/shutdown.ps1",
        "scripts/shutdown.sh",
    ]
    for rel_path in required_files:
        full_path = TF_DIR / rel_path
        assert full_path.exists(), f"Missing required file: {rel_path}"


def test_providers_dynamic_caller_identity_and_no_hardcoded_accounts():
    providers_file = TF_DIR / "providers.tf"
    content = providers_file.read_text(encoding="utf-8")

    assert 'alias  = "east"' in content
    assert 'alias  = "west"' in content
    assert 'data "aws_caller_identity" "current"' in content

    # Ensure no hardcoded 12-digit AWS account IDs exist in any .tf file
    for tf_file in TF_DIR.glob("*.tf"):
        tf_content = tf_file.read_text(encoding="utf-8")
        # Match 12 digit AWS account numbers not in comments
        matches = re.findall(r'(?<!\d)\d{12}(?!\d)', tf_content)
        assert not matches, f"Hardcoded 12-digit account ID found in {tf_file.name}: {matches}"


def test_vpc_east_private_subnetting_and_endpoints():
    vpc_east = (TF_DIR / "vpc-east.tf").read_text(encoding="utf-8")

    # VPC CIDR
    assert '10.0.0.0/16' in vpc_east

    # Public subnets (ALB/NAT only)
    assert '10.0.1.0/24' in vpc_east  # Public 1a
    assert '10.0.2.0/24' in vpc_east  # Public 1b

    # Private web subnets
    assert '10.0.10.0/24' in vpc_east
    assert '10.0.11.0/24' in vpc_east

    # Private app subnets
    assert '10.0.20.0/24' in vpc_east
    assert '10.0.21.0/24' in vpc_east

    # Private data subnets
    assert '10.0.30.0/24' in vpc_east
    assert '10.0.31.0/24' in vpc_east

    # NAT Gateway and S3 Gateway Endpoint
    assert "aws_nat_gateway" in vpc_east
    assert "com.amazonaws.${var.east_region}.s3" in vpc_east
    assert "aws_flow_log" in vpc_east
    assert "/vpc/prod-east" in vpc_east


def test_alb_and_waf_security_isolation():
    alb_waf = (TF_DIR / "alb-waf-east.tf").read_text(encoding="utf-8")

    # ALB Security Group
    assert "nettwin-alb-prod-east" in alb_waf
    assert "0.0.0.0/0" in alb_waf

    # Web Security Group allows HTTP ONLY from ALB security group
    assert "nettwin-web-prod-east" in alb_waf
    assert "security_groups = [aws_security_group.sg_alb_east.id]" in alb_waf

    # Target group and WAF v2 association
    assert "aws_lb_target_group" in alb_waf
    assert "aws_wafv2_web_acl" in alb_waf
    assert "AWSManagedRulesCommonRuleSet" in alb_waf
    assert "aws_wafv2_web_acl_association" in alb_waf


def test_ec2_east_instances_and_containers():
    ec2_east = (TF_DIR / "ec2-east.tf").read_text(encoding="utf-8")

    assert '"web1"' in ec2_east
    assert '"web2"' in ec2_east
    assert 'instance_type          = "t3.micro"' in ec2_east

    # Microservice containers mapped on web instances
    assert "app1_order.py" in ec2_east
    assert "app2_auth.py" in ec2_east
    assert "8080" in ec2_east
    assert "8081" in ec2_east

    # Attached to private subnets
    assert "aws_subnet.private_web_1a.id" in ec2_east
    assert "aws_subnet.private_web_1b.id" in ec2_east


def test_rds_mysql_free_tier_and_dynamic_s3():
    rds_east = (TF_DIR / "rds-east.tf").read_text(encoding="utf-8")

    # MySQL engine and free tier sizing
    assert 'engine                 = "mysql"' in rds_east
    assert 'instance_class         = "db.t3.micro"' in rds_east
    assert 'allocated_storage      = 20' in rds_east
    assert "publicly_accessible    = false" in rds_east

    # S3 telemetry bucket with dynamic account id
    assert 'nettwin-telemetry-lake-east-${data.aws_caller_identity.current.account_id}' in rds_east
    assert "aws_s3_bucket_server_side_encryption_configuration" in rds_east
    assert "aws_s3_bucket_public_access_block" in rds_east


def test_vpc_west_and_traffic_gen():
    vpc_west = (TF_DIR / "vpc-west.tf").read_text(encoding="utf-8")
    ec2_west = (TF_DIR / "ec2-west.tf").read_text(encoding="utf-8")

    assert "10.1.0.0/16" in vpc_west
    assert "10.1.1.0/24" in vpc_west

    assert 'instance_type          = "t3.small"' in ec2_west
    assert "AmazonS3ReadOnlyAccess" in ec2_west
    assert "elasticloadbalancing:DescribeLoadBalancers" in ec2_west
