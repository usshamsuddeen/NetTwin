###############################################################################
# NetTwin 3.0 — EC2 Traffic Generator Instance (us-west-2)
#
# traffic-gen: t3.small in public subnet with S3 ReadOnly and ELB discovery
# Streams benchmark datasets directly into memory from s3://cse-cic-ids2018/
# and drives traffic across the public internet to the East ALB.
###############################################################################

data "aws_ami" "al2023_west" {
  provider    = aws.west
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

# =============================================================================
# Security Group for Traffic Generator
# =============================================================================
resource "aws_security_group" "sg_traffic_west" {
  provider    = aws.west
  name        = "nettwin-traffic-west"
  description = "Egress traffic to public internet and optional SSH"
  vpc_id      = aws_vpc.traffic_west.id

  ingress {
    description = "SSH from anywhere (or restricted IP)"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Full outbound to internet for WAN traffic generation"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "sg-traffic-west"
  }
}

# =============================================================================
# IAM Role for Traffic Generator (SSM + S3 Read + ELB Discovery in East)
# =============================================================================
resource "aws_iam_role" "traffic_gen_role" {
  provider = aws.west
  name     = "nettwin-traffic-gen-role-west"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ssm_west" {
  provider   = aws.west
  role       = aws_iam_role.traffic_gen_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "s3_read_west" {
  provider   = aws.west
  role       = aws_iam_role.traffic_gen_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
}

# Cross-region read policy allowing traffic-gen to auto-discover East ALB
resource "aws_iam_role_policy" "elb_describe_policy" {
  provider = aws.west
  name     = "nettwin-elb-discovery-policy"
  role     = aws_iam_role.traffic_gen_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "elasticloadbalancing:DescribeLoadBalancers",
          "elasticloadbalancing:DescribeTargetGroups",
          "ec2:DescribeSubnets",
          "ec2:DescribeInstances"
        ]
        Effect   = "Allow"
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_instance_profile" "traffic_gen_profile" {
  provider = aws.west
  name     = "nettwin-traffic-gen-profile-west"
  role     = aws_iam_role.traffic_gen_role.name
}

# =============================================================================
# EC2 Instance: traffic-gen (t3.small)
# =============================================================================
resource "aws_instance" "traffic_gen" {
  provider               = aws.west
  ami                    = data.aws_ami.al2023_west.id
  instance_type          = "t3.small"
  subnet_id              = aws_subnet.public_west.id
  vpc_security_group_ids = [aws_security_group.sg_traffic_west.id]
  iam_instance_profile   = aws_iam_instance_profile.traffic_gen_profile.name
  key_name               = var.key_name != "" ? var.key_name : null

  user_data = <<-EOF
    #!/bin/bash
    dnf update -y
    dnf install -y python3 python3-pip git htop

    pip3 install boto3 botocore httpx requests

    mkdir -p /opt/nettwin
    cat << 'README' > /opt/nettwin/README.txt
    NetTwin 3.0 Traffic Generator Instance (us-west-2)
    Execute tests using: python3 west_traffic_generator.py --phase benign
    README
  EOF

  root_block_device {
    volume_size           = 20
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
  }

  tags = {
    Name        = "traffic-gen"
    Role        = "adversarial-traffic-generator"
    Project     = "nettwin"
    Environment = "traffic-west"
  }
}
