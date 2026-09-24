###############################################################################
# NetTwin 3.0 — ALB & WAF v2 Prod East (us-east-1)
#
# Internet-facing Application Load Balancer in public subnets, routing to
# private web instances with AWS WAF v2 Layer 7 protection.
###############################################################################

# =============================================================================
# Security Groups
# =============================================================================

# ALB Security Group: Inbound 80 from Internet
resource "aws_security_group" "sg_alb_east" {
  provider    = aws.east
  name        = "nettwin-alb-prod-east"
  description = "Public HTTP ingress for Prod East ALB"
  vpc_id      = aws_vpc.prod_east.id

  ingress {
    description = "Public HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Egress to all"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "nettwin-alb-prod-east"
  }
}

# Web Tier Security Group: Inbound ONLY from ALB
resource "aws_security_group" "sg_web_east" {
  provider    = aws.east
  name        = "nettwin-web-prod-east"
  description = "Private web tier ingress allowed only from ALB"
  vpc_id      = aws_vpc.prod_east.id

  ingress {
    description     = "HTTP from ALB"
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [aws_security_group.sg_alb_east.id]
  }

  ingress {
    description     = "App1 Order service from ALB or local"
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.sg_alb_east.id]
  }

  ingress {
    description     = "App2 Auth service from ALB or local"
    from_port       = 8081
    to_port         = 8081
    protocol        = "tcp"
    security_groups = [aws_security_group.sg_alb_east.id]
  }

  egress {
    description = "Outbound via NAT"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "sg-web-prod-east"
  }
}

# =============================================================================
# Application Load Balancer
# =============================================================================
resource "aws_lb" "alb_prod_east" {
  provider           = aws.east
  name               = "alb-prod-east"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.sg_alb_east.id]
  subnets            = [aws_subnet.public_1a.id, aws_subnet.public_1b.id]

  enable_deletion_protection = false

  tags = {
    Name = "alb-prod-east"
    Role = "ingress-lb"
  }
}

resource "aws_lb_target_group" "tg_web_east" {
  provider    = aws.east
  name        = "tg-web-prod-east"
  port        = 80
  protocol    = "HTTP"
  vpc_id      = aws_vpc.prod_east.id
  target_type = "instance"

  health_check {
    enabled             = true
    path                = "/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 3
    interval            = 5
    matcher             = "200-399"
  }

  tags = {
    Name = "tg-web-prod-east"
  }
}

resource "aws_lb_listener" "http_east" {
  provider          = aws.east
  load_balancer_arn = aws_lb.alb_prod_east.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.tg_web_east.arn
  }
}

# =============================================================================
# AWS WAF v2 Web ACL
# =============================================================================
resource "aws_wafv2_web_acl" "waf_east" {
  provider    = aws.east
  name        = "waf-prod-east"
  description = "AWS Managed Rule Set for NetTwin Prod East Ingress"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 1

    # In COUNT mode for testing: counts and monitors attack traffic in CloudWatch
    # without blocking it at edge, allowing ALB saturation and twin health degradation drills
    override_action {
      count {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "waf-common-rules-east"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "waf-prod-east"
    sampled_requests_enabled   = true
  }

  tags = {
    Name = "waf-prod-east"
  }
}

resource "aws_wafv2_web_acl_association" "alb_waf_assoc" {
  provider     = aws.east
  resource_arn = aws_lb.alb_prod_east.arn
  web_acl_arn  = aws_wafv2_web_acl.waf_east.arn
}
