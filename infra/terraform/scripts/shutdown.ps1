# NetTwin 3.0 — One-Click Instance Shutdown Script (PowerShell)
# Stops all EC2 instances across both us-east-1 and us-west-2 to drop compute cost to $0.00.

Write-Host "Stopping NetTwin EC2 instances in us-east-1 (Prod East)..." -ForegroundColor Cyan
$eastInstances = aws ec2 describe-instances --region us-east-1 --filters "Name=tag:Project,Values=nettwin" "Name=instance-state-name,Values=running" --query "Reservations[].Instances[].InstanceId" --output text
if ($eastInstances -and $eastInstances.Trim() -ne "") {
    aws ec2 stop-instances --region us-east-1 --instance-ids ($eastInstances -split "`t| ")
    Write-Host "Stopped instances in us-east-1: $eastInstances" -ForegroundColor Green
} else {
    Write-Host "No running instances found in us-east-1." -ForegroundColor Yellow
}

Write-Host "`nStopping NetTwin EC2 instances in us-west-2 (Traffic West)..." -ForegroundColor Cyan
$westInstances = aws ec2 describe-instances --region us-west-2 --filters "Name=tag:Project,Values=nettwin" "Name=instance-state-name,Values=running" --query "Reservations[].Instances[].InstanceId" --output text
if ($westInstances -and $westInstances.Trim() -ne "") {
    aws ec2 stop-instances --region us-west-2 --instance-ids ($westInstances -split "`t| ")
    Write-Host "Stopped instances in us-west-2: $westInstances" -ForegroundColor Green
} else {
    Write-Host "No running instances found in us-west-2." -ForegroundColor Yellow
}

# Optional: Delete NAT Gateway to eliminate the $0.045/hr NAT charge when testing is paused
Write-Host "`nChecking for NAT Gateway in us-east-1 (Prod East)..." -ForegroundColor Cyan
$natId = aws ec2 describe-nat-gateways --region us-east-1 --filter "Name=tag:Project,Values=nettwin" "Name=state,Values=available" --query "NatGateways[0].NatGatewayId" --output text
if ($natId -and $natId -ne "None" -and $natId.Trim() -ne "") {
    Write-Host "Found available NAT Gateway: $natId. Deleting to eliminate $0.045/hr fee..." -ForegroundColor Yellow
    aws ec2 delete-nat-gateway --nat-gateway-id $natId --region us-east-1
    Write-Host "NAT Gateway $natId deletion initiated." -ForegroundColor Green
} else {
    Write-Host "No active NAT Gateway found in us-east-1." -ForegroundColor Gray
}

Write-Host "`nShutdown complete. Compute and NAT costs are now $0.00." -ForegroundColor Green
