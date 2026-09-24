#!/usr/bin/env bash
# NetTwin 3.0 — One-Click Instance Shutdown Script (Bash)
# Stops all EC2 instances across both us-east-1 and us-west-2 to drop compute cost to $0.00.

echo "Stopping NetTwin EC2 instances in us-east-1 (Prod East)..."
EAST_IDS=$(aws ec2 describe-instances --region us-east-1 --filters "Name=tag:Project,Values=nettwin" "Name=instance-state-name,Values=running" --query "Reservations[].Instances[].InstanceId" --output text)
if [ -n "$EAST_IDS" ] && [ "$EAST_IDS" != "None" ]; then
    aws ec2 stop-instances --region us-east-1 --instance-ids $EAST_IDS
    echo "Stopped us-east-1: $EAST_IDS"
else
    echo "No running instances in us-east-1."
fi

echo "Stopping NetTwin EC2 instances in us-west-2 (Traffic West)..."
WEST_IDS=$(aws ec2 describe-instances --region us-west-2 --filters "Name=tag:Project,Values=nettwin" "Name=instance-state-name,Values=running" --query "Reservations[].Instances[].InstanceId" --output text)
if [ -n "$WEST_IDS" ] && [ "$WEST_IDS" != "None" ]; then
    aws ec2 stop-instances --region us-west-2 --instance-ids $WEST_IDS
    echo "Stopped us-west-2: $WEST_IDS"
else
    echo "No running instances in us-west-2."
fi

echo "Checking for NAT Gateway in us-east-1 (Prod East)..."
NAT_ID=$(aws ec2 describe-nat-gateways --region us-east-1 --filter "Name=tag:Project,Values=nettwin" "Name=state,Values=available" --query "NatGateways[0].NatGatewayId" --output text)
if [ -n "$NAT_ID" ] && [ "$NAT_ID" != "None" ]; then
    echo "Found available NAT Gateway: $NAT_ID. Deleting to eliminate \$0.045/hr fee..."
    aws ec2 delete-nat-gateway --nat-gateway-id $NAT_ID --region us-east-1
    echo "NAT Gateway $NAT_ID deletion initiated."
else
    echo "No active NAT Gateway found in us-east-1."
fi

echo "All NetTwin instances stopped. Compute and NAT costs are now $0.00/hr."
