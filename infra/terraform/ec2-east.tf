###############################################################################
# NetTwin 3.0 — EC2 Web & App Instances Prod East (us-east-1)
#
# web1 and web2: t3.micro in private subnets behind ALB
# Hosts Nginx reverse proxy + containerized app1 (order-svc :8080) and
# app2 (auth-svc :8081), fulfilling the 12-node topology on 2 Free-Tier hosts.
###############################################################################

data "aws_ami" "al2023_east" {
  provider    = aws.east
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
# IAM Role for Web Instances (SSM + CloudWatch Metrics)
# =============================================================================
resource "aws_iam_role" "ec2_east_role" {
  provider = aws.east
  name     = "nettwin-ec2-east-role"

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

resource "aws_iam_role_policy_attachment" "ssm_east" {
  provider   = aws.east
  role       = aws_iam_role.ec2_east_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "cw_east" {
  provider   = aws.east
  role       = aws_iam_role.ec2_east_role.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_iam_instance_profile" "ec2_east_profile" {
  provider = aws.east
  name     = "nettwin-ec2-east-profile"
  role     = aws_iam_role.ec2_east_role.name
}

# =============================================================================
# User Data Script Template for Web & App Microservices
# =============================================================================
locals {
  user_data_web1 = <<-EOF
    #!/bin/bash
    dnf update -y
    dnf install -y nginx python3 python3-pip

    # Start Nginx serving Node Status and simulated app endpoints
    cat << 'HTML' > /usr/share/nginx/html/index.html
    <!DOCTYPE html>
    <html>
    <head><title>NetTwin Prod East - Web Server 1</title></head>
    <body style="font-family:sans-serif; background:#050a12; color:#60cdff; padding:40px;">
      <h1>NetTwin 3.0 Enterprise Cloud</h1>
      <p>Node: <b>web1</b> | Tier: <b>Web ASG (AZ-1a)</b> | Status: <b style="color:#10b981;">HEALTHY</b></p>
      <p>Subnet: 10.0.10.0/24 | Private IP: $(hostname -I)</p>
    </body>
    </html>
    HTML

    # Dedicated ALB health check file
    echo '{"status":"ok","node":"web1","tier":"web"}' > /usr/share/nginx/html/health

    # Microservice app1: Order Service on port 8080
    cat << 'PY' > /opt/app1_order.py
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import json
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"service":"app1-order","status":"ok","tier":"application"}\n')
    HTTPServer(('0.0.0.0', 8080), H).serve_forever()
    PY

    # Microservice app2: Auth Service on port 8081
    cat << 'PY' > /opt/app2_auth.py
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import json
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"service":"app2-auth","status":"ok","tier":"application"}\n')
    HTTPServer(('0.0.0.0', 8081), H).serve_forever()
    PY

    python3 /opt/app1_order.py &
    python3 /opt/app2_auth.py &

    systemctl enable nginx
    systemctl start nginx
  EOF

  user_data_web2 = <<-EOF
    #!/bin/bash
    dnf update -y
    dnf install -y nginx python3 python3-pip

    cat << 'HTML' > /usr/share/nginx/html/index.html
    <!DOCTYPE html>
    <html>
    <head><title>NetTwin Prod East - Web Server 2</title></head>
    <body style="font-family:sans-serif; background:#050a12; color:#60cdff; padding:40px;">
      <h1>NetTwin 3.0 Enterprise Cloud</h1>
      <p>Node: <b>web2</b> | Tier: <b>Web ASG (AZ-1b)</b> | Status: <b style="color:#10b981;">HEALTHY</b></p>
      <p>Subnet: 10.0.11.0/24 | Private IP: $(hostname -I)</p>
    </body>
    </html>
    HTML

    # Dedicated ALB health check file
    echo '{"status":"ok","node":"web2","tier":"web"}' > /usr/share/nginx/html/health

    systemctl enable nginx
    systemctl start nginx
  EOF
}

# =============================================================================
# EC2 Instances
# =============================================================================

resource "aws_instance" "web1" {
  provider               = aws.east
  ami                    = data.aws_ami.al2023_east.id
  instance_type          = "t3.micro"
  subnet_id              = aws_subnet.private_web_1a.id
  vpc_security_group_ids = [aws_security_group.sg_web_east.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_east_profile.name
  key_name               = var.key_name != "" ? var.key_name : null

  user_data = local.user_data_web1

  root_block_device {
    volume_size           = 20
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
  }

  tags = {
    Name        = "web1"
    Role        = "web-server-az1a"
    EntityId    = "web1"
    Project     = "nettwin"
    Environment = "prod-east"
  }
}

resource "aws_instance" "web2" {
  provider               = aws.east
  ami                    = data.aws_ami.al2023_east.id
  instance_type          = "t3.micro"
  subnet_id              = aws_subnet.private_web_1b.id
  vpc_security_group_ids = [aws_security_group.sg_web_east.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_east_profile.name
  key_name               = var.key_name != "" ? var.key_name : null

  user_data = local.user_data_web2

  root_block_device {
    volume_size           = 20
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
  }

  tags = {
    Name        = "web2"
    Role        = "web-server-az1b"
    EntityId    = "web2"
    Project     = "nettwin"
    Environment = "prod-east"
  }
}

# =============================================================================
# Attach web instances to ALB Target Group
# =============================================================================
resource "aws_lb_target_group_attachment" "web1_attach" {
  provider         = aws.east
  target_group_arn = aws_lb_target_group.tg_web_east.arn
  target_id        = aws_instance.web1.id
  port             = 80
}

resource "aws_lb_target_group_attachment" "web2_attach" {
  provider         = aws.east
  target_group_arn = aws_lb_target_group.tg_web_east.arn
  target_id        = aws_instance.web2.id
  port             = 80
}
