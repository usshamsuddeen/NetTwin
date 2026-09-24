#!/bin/bash
set -euo pipefail

###############################################################################
# NetTwin Engine EC2 Bootstrap — installs Python, NetTwin, and starts service
###############################################################################

# System packages
dnf install -y python3.12 python3.12-pip git

# Optional: Zeek for L7 Traffic Mirroring analysis
# dnf install -y zeek

# Application directory
APP_DIR="/opt/nettwin"
mkdir -p "$APP_DIR"
cd "$APP_DIR"

# Install Python dependencies
cat > requirements.txt << 'REQS'
fastapi>=0.115
uvicorn[standard]>=0.30
numpy>=2.0
pydantic>=2.7
boto3>=1.35
REQS
python3.12 -m pip install --no-cache-dir -r requirements.txt

# Note: In production, clone from your git repo:
# git clone https://github.com/YOUR_ORG/nettwin.git .
# For now, the code will be deployed via SCP or CodeDeploy.

# Create config with AWS enabled
cat > config.json << 'CONFIG'
{
  "host": "0.0.0.0",
  "port": 8000,
  "tick_ms": 1000,
  "db_path": "/opt/nettwin/nettwin.db",
  "history_len": 300,
  "seed": 42,
  "detector": {
    "warmup_ticks": 25,
    "ema_alpha": 0.06,
    "z_warn": 4.5,
    "z_alert": 7.0,
    "alert_threshold": 0.72,
    "warn_threshold": 0.5,
    "iforest_enabled": true,
    "iforest_trees": 40,
    "iforest_sample": 128,
    "iforest_retrain_ticks": 120,
    "iforest_threshold": 0.62,
    "iforest_window": 2000,
    "persistence_ticks": 5
  },
  "alerts": { "cooldown_ticks": 30, "resolve_after_ticks": 15 },
  "forecast": { "default_horizon": 15, "damping": 0.9 },
  "llm": { "ollama_url": "http://localhost:11434", "model": "llama3.2" },
  "auto_attacks": false,
  "snapshot_every_ticks": 10,
  "sync": {
    "enabled": true,
    "udp_port": 5514,
    "staleness_s": 8.0,
    "hybrid_after_ticks": 8,
    "fidelity_hybrid_min": 50.0,
    "sync_map": {}
  },
  "response": { "mode": "approval" },
  "aws": {
    "enabled": true,
    "region": "us-east-1",
    "flow_log_group": "/vpc/nettwin-flowlogs",
    "poll_interval_s": 10.0,
    "cloudwatch_metrics": true,
    "cloudtrail_enabled": false,
    "traffic_mirror_enabled": false,
    "instance_tags": { "Project": "nettwin" },
    "cost_limit_daily_usd": 5.0
  }
}
CONFIG

# Create systemd service for auto-restart
cat > /etc/systemd/system/nettwin.service << 'SVC'
[Unit]
Description=NetTwin Digital Twin Engine
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/nettwin
ExecStart=/usr/bin/python3.12 run.py
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SVC

systemctl daemon-reload
systemctl enable nettwin.service
# Service will start once code is deployed to /opt/nettwin

echo "NetTwin engine bootstrap complete"
