#!/bin/bash
set -euo pipefail

###############################################################################
# Attacker EC2 Bootstrap — installs attack tools with rate-limited helpers
###############################################################################

# Install attack tools
dnf install -y hping3 nmap ncat

# Helper scripts in /home/ec2-user/

# DDoS simulation — rate-limited SYN flood
cat > /home/ec2-user/ddos.sh << 'DDOS'
#!/bin/bash
# Usage: ~/ddos.sh <target_private_ip>
# Rate-limited to ~100 packets/sec (u10000 = 10ms between packets)
# Press Ctrl+C to stop
if [ -z "${1:-}" ]; then
    echo "Usage: ~/ddos.sh <target_ip>"
    exit 1
fi
echo "Starting rate-limited SYN flood to $1:80 (Ctrl+C to stop)"
echo "WARNING: Only attack instances with tag Project=nettwin"
hping3 -S -p 80 -i u10000 "$1"
DDOS

# Port scan simulation
cat > /home/ec2-user/portscan.sh << 'SCAN'
#!/bin/bash
# Usage: ~/portscan.sh <target_private_ip>
if [ -z "${1:-}" ]; then
    echo "Usage: ~/portscan.sh <target_ip>"
    exit 1
fi
echo "Starting TCP SYN scan of $1 (timing T3 = normal)"
nmap -sS -T3 "$1"
SCAN

# Data exfiltration simulation
cat > /home/ec2-user/exfil.sh << 'EXFIL'
#!/bin/bash
# Usage: ~/exfil.sh <target_private_ip>
# Sends 50MB of random data to port 9999 (simulates data exfiltration)
if [ -z "${1:-}" ]; then
    echo "Usage: ~/exfil.sh <target_ip>"
    exit 1
fi
echo "Simulating 50MB exfiltration to $1:9999"
dd if=/dev/urandom bs=1M count=50 2>/dev/null | ncat "$1" 9999
EXFIL

chmod +x /home/ec2-user/ddos.sh /home/ec2-user/portscan.sh /home/ec2-user/exfil.sh
chown ec2-user:ec2-user /home/ec2-user/ddos.sh /home/ec2-user/portscan.sh /home/ec2-user/exfil.sh

echo "Attacker bootstrap complete — scripts: ~/ddos.sh ~/portscan.sh ~/exfil.sh"
