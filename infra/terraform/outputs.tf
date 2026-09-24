###############################################################################
# NetTwin 3.0 — Terraform Outputs for Multi-Region Architecture
###############################################################################

output "east_vpc_id" {
  description = "VPC ID of Org 1 Prod East (to input into NetTwin onboarding modal)"
  value       = aws_vpc.prod_east.id
}

output "alb_dns_name" {
  description = "Public DNS name of the Prod East Application Load Balancer"
  value       = aws_lb.alb_prod_east.dns_name
}

output "alb_arn" {
  description = "ARN of the Prod East Application Load Balancer"
  value       = aws_lb.alb_prod_east.arn
}

output "web1_private_ip" {
  description = "Private IP of Web Server 1 (AZ-1a)"
  value       = aws_instance.web1.private_ip
}

output "web2_private_ip" {
  description = "Private IP of Web Server 2 (AZ-1b)"
  value       = aws_instance.web2.private_ip
}

output "db1_endpoint" {
  description = "Endpoint of MySQL db1 instance"
  value       = aws_db_instance.db1.endpoint
}

output "s3_telemetry_lake_east" {
  description = "S3 bucket for Prod East telemetry lake"
  value       = aws_s3_bucket.telemetry_lake_east.bucket
}

output "west_vpc_id" {
  description = "VPC ID of Org 2 Traffic West"
  value       = aws_vpc.traffic_west.id
}

output "traffic_gen_public_ip" {
  description = "Public IP of Traffic Generator instance (us-west-2)"
  value       = aws_instance.traffic_gen.public_ip
}

output "traffic_gen_id" {
  description = "Instance ID of Traffic Generator (us-west-2)"
  value       = aws_instance.traffic_gen.id
}

output "traffic_test_command" {
  description = "Turnkey command to launch cross-region traffic test from West to East"
  value       = "python scripts/west_traffic_generator.py --target http://${aws_lb.alb_prod_east.dns_name}/ --phase benign"
}
