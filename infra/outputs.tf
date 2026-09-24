###############################################################################
# NetTwin 2.0 — Terraform Outputs
###############################################################################

output "nettwin_public_ip" {
  description = "Public IP of the NetTwin engine EC2 instance"
  value       = aws_instance.nettwin.public_ip
}

output "nettwin_ssh_command" {
  description = "SSH tunnel command to access the NetTwin dashboard"
  value       = "ssh -L 8000:localhost:8000 ec2-user@${aws_instance.nettwin.public_ip}"
}

output "attacker_public_ip" {
  description = "Public IP of the attacker EC2 instance"
  value       = aws_instance.attacker.public_ip
}

output "attacker_ssh_command" {
  description = "SSH command to the attacker instance for launching attacks"
  value       = "ssh ec2-user@${aws_instance.attacker.public_ip}"
}

output "web1_public_ip" {
  description = "Public IP of the web1 EC2 instance"
  value       = aws_instance.web1.public_ip
}

output "web1_private_ip" {
  description = "Private IP of web1 — DDoS target from attacker"
  value       = aws_instance.web1.private_ip
}

output "app1_private_ip" {
  description = "Private IP of app1"
  value       = aws_instance.app1.private_ip
}

output "db1_private_ip" {
  description = "Private IP of db1"
  value       = aws_instance.db1.private_ip
}

output "flow_log_group" {
  description = "CloudWatch Log Group for VPC Flow Logs"
  value       = aws_cloudwatch_log_group.flowlogs.name
}

output "s3_archive_bucket" {
  description = "S3 bucket for long-term flow log retention"
  value       = aws_s3_bucket.flowlogs.id
}

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}
