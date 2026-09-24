#!/bin/bash
set -euo pipefail

###############################################################################
# NAT Instance Bootstrap — enables IP forwarding + iptables MASQUERADE
#
# CRITICAL: The EC2 instance MUST have source_dest_check = false
# (set in Terraform) or AWS will silently drop all forwarded packets.
###############################################################################

# Enable IP forwarding (immediately + persist across reboots)
echo 1 > /proc/sys/net/ipv4/ip_forward
sed -i '/^net.ipv4.ip_forward/d' /etc/sysctl.conf
echo "net.ipv4.ip_forward = 1" >> /etc/sysctl.conf

# iptables masquerade: private subnet → internet via this instance's eth0
iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE

# Persist iptables rules across reboots
dnf install -y iptables-services
service iptables save
systemctl enable iptables

echo "NAT instance bootstrap complete — ip_forward=1, MASQUERADE active"
