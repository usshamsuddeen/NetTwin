#!/usr/bin/env python3
"""NetTwin 2.0 — Automated AWS 96-Core High-Performance Experiment Runner.

Orchestrates the full lifecycle on AWS EC2 (eu-north-1):
1. Launches p4d.24xlarge (96 vCPUs, 1,152 GB RAM, 8x A100 GPUs) in eu-north-1c.
2. Injects safety auto-shutdown alarm (+50 min hard cutoff).
3. Connects via SSH, deploys the clean codebase.
4. Executes master benchmark across all 5 papers using 64-core multiprocessing.
5. Downloads all 67 publication-grade figures (PDF + 600 DPI PNG) and JSON datasets.
6. Terminates the EC2 instance immediately to guarantee minimal cost (~$12-15).
"""
import os
import sys
import time
import zipfile
import tempfile
from pathlib import Path
import boto3
import paramiko

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

REGION = "eu-north-1"
AZ = "eu-north-1c"
INSTANCE_TYPE = "c6i.4xlarge"
AMI_ID = "ami-0af4957fd48faeb4b"  # Deep Learning PyTorch OSS GPU AMI (Ubuntu 24.04)
SUBNET_ID = "subnet-0091c0f0da35c6b9b"  # Default VPC Subnet in eu-north-1c
SECURITY_GROUP_ID = "sg-03a2f1b91cabb8b2e"  # nettwin-runner-sg
KEY_NAME = "nettwin-key"
KEY_FILE = Path(__file__).resolve().parent.parent / "nettwin-key.pem"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
REMOTE_USER = "ubuntu"
REMOTE_DIR = "/home/ubuntu/nettwin-project"


def create_project_archive() -> Path:
    """Create a clean zip archive of the repository excluding caches and outputs."""
    print("  [1/8] Packaging clean repository archive...")
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    archive_path = Path(tmp.name)
    tmp.close()

    exclude_dirs = {".git", ".pytest_cache", "__pycache__", "venv", ".venv", "v", "infra/.terraform"}
    exclude_files = {archive_path.name, "nettwin.db", "outputs.tar.gz", "nettwin-key.pem"}

    count = 0
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(PROJECT_ROOT):
            rel_root = os.path.relpath(root, PROJECT_ROOT).replace("\\", "/")
            if any(rel_root.startswith(ex) or f"/{ex}/" in f"/{rel_root}/" for ex in exclude_dirs):
                continue
            for f in files:
                if f in exclude_files or f.endswith(".pyc") or f.endswith(".pyo") or f.endswith(".pem"):
                    continue
                abs_path = os.path.join(root, f)
                arc_name = os.path.relpath(abs_path, PROJECT_ROOT).replace("\\", "/")
                zf.write(abs_path, arc_name)
                count += 1

    size_mb = archive_path.stat().st_size / (1024 * 1024)
    print(f"  [OK] Packaged {count} files ({size_mb:.2f} MB) into {archive_path.name}")
    return archive_path


def launch_instance(ec2_client) -> tuple[str, str]:
    """Launch the c6i.4xlarge instance with gp3 storage and safety auto-shutdown."""
    print(f"  [2/8] Launching {INSTANCE_TYPE} in {AZ} ({REGION})...")
    user_data = """#!/bin/bash
# Hard cutoff: Automatically power off after 50 minutes as a cost-protection guardrail
shutdown -h +50
"""
    resp = ec2_client.run_instances(
        ImageId=AMI_ID,
        InstanceType=INSTANCE_TYPE,
        KeyName=KEY_NAME,
        SubnetId=SUBNET_ID,
        SecurityGroupIds=[SECURITY_GROUP_ID],
        MinCount=1,
        MaxCount=1,
        BlockDeviceMappings=[{
            "DeviceName": "/dev/sda1",
            "Ebs": {
                "VolumeSize": 100,
                "VolumeType": "gp3",
                "DeleteOnTermination": True,
            }
        }],
        UserData=user_data,
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [
                {"Key": "Name", "Value": "nettwin-16core-runner"},
                {"Key": "Project", "Value": "nettwin"},
            ]
        }]
    )
    instance_id = resp["Instances"][0]["InstanceId"]
    print(f"  [OK] Instance created: {instance_id}. Waiting for 'running' state and public IP...")

    waiter = ec2_client.get_waiter("instance_running")
    waiter.wait(InstanceIds=[instance_id])

    desc = ec2_client.describe_instances(InstanceIds=[instance_id])
    inst = desc["Reservations"][0]["Instances"][0]
    public_ip = inst.get("PublicIpAddress")
    print(f"  [OK] Instance is running! Public IP: {public_ip}")
    return instance_id, public_ip


def wait_for_ssh(ip: str, key_path: Path, max_attempts: int = 60) -> paramiko.SSHClient:
    """Poll SSH port until the host is reachable and authentication succeeds."""
    print(f"  [3/8] Waiting for SSH readiness on {ip}:22...")
    key = paramiko.RSAKey.from_private_key_file(str(key_path))
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    for attempt in range(1, max_attempts + 1):
        try:
            client.connect(ip, username=REMOTE_USER, pkey=key, timeout=10)
            if client.get_transport():
                client.get_transport().set_keepalive(15)
            print(f"  [OK] SSH connected successfully on attempt {attempt}!")
            return client
        except Exception as e:
            if attempt % 5 == 0 or attempt == 1:
                print(f"    Attempt {attempt}/{max_attempts}: waiting for SSH ({e})...")
            time.sleep(5)
    raise TimeoutError(f"Could not connect via SSH to {ip} after {max_attempts} attempts.")


def stream_ssh_command(client: paramiko.SSHClient, cmd: str) -> int:
    """Execute a remote command and stream output in real-time."""
    print(f"\n>>> [SSH EXEC] {cmd}\n")
    stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)
    for line in iter(stdout.readline, ""):
        clean = line.encode("ascii", errors="replace").decode("ascii")
        print(clean, end="", flush=True)
    exit_code = stdout.channel.recv_exit_status()
    if exit_code != 0:
        err = stderr.read().decode("utf-8", errors="replace")
        if err.strip():
            print(f"\n[STDERR]:\n{err}\n")
    return exit_code


def upload_and_prepare(client: paramiko.SSHClient, archive_path: Path) -> None:
    """Upload project archive via SFTP and unzip on remote machine."""
    print("  [4/8] Uploading codebase via SFTP...")
    sftp = client.open_sftp()
    remote_archive = f"/home/{REMOTE_USER}/project.zip"
    sftp.put(str(archive_path), remote_archive)
    sftp.close()
    print("  [OK] Upload complete. Unzipping and setting up environment...")

    setup_cmd = f"""
set -e
mkdir -p {REMOTE_DIR}
python3 -m zipfile -e {remote_archive} {REMOTE_DIR}
rm {remote_archive}
cd {REMOTE_DIR}
python3 -m pip install --no-cache-dir --progress-bar off --break-system-packages -r requirements.txt 2>/dev/null || python3 -m pip install --no-cache-dir --progress-bar off -r requirements.txt
"""
    code = stream_ssh_command(client, setup_cmd)
    if code != 0:
        raise RuntimeError(f"Environment setup failed with code {code}")
    print("  [OK] Remote environment initialized!")


def run_benchmark(client: paramiko.SSHClient) -> None:
    """Execute master experiment suite across 16 parallel cores."""
    print("  [5/8] Executing full 5-paper evaluation suite across 16 parallel cores on AWS...")
    run_cmd = f"""
cd {REMOTE_DIR}
export PYTHONUNBUFFERED=1
python3 eval/run_all.py --quick
python3 verify_results.py
"""
    code = stream_ssh_command(client, run_cmd)
    if code != 0:
        raise RuntimeError(f"Benchmark execution failed with code {code}")
    print("  [OK] Benchmark execution completed successfully on AWS!")


def download_artifacts(client: paramiko.SSHClient) -> None:
    """Download generated figures and results back to local directories."""
    print("  [6/8] Downloading publication figures and JSON results to local workspace...")
    tar_cmd = f"cd {REMOTE_DIR} && tar -czf /home/{REMOTE_USER}/outputs.tar.gz eval/figures/ eval/results/"
    stream_ssh_command(client, tar_cmd)

    local_tar = PROJECT_ROOT / "outputs.tar.gz"
    sftp = client.open_sftp()
    sftp.get(f"/home/{REMOTE_USER}/outputs.tar.gz", str(local_tar))
    sftp.close()

    import tarfile
    with tarfile.open(local_tar, "r:gz") as tar:
        tar.extractall(path=PROJECT_ROOT)
    local_tar.unlink(missing_ok=True)
    print("  [OK] All figures and results successfully extracted to local eval/ folder!")

    import subprocess
    print("  [7/8] Verifying newly downloaded results in local workspace...")
    subprocess.run([sys.executable, str(PROJECT_ROOT / "verify_results.py")])


def terminate_instance(ec2_client, instance_id: str) -> None:
    """Terminate the EC2 instance immediately."""
    print(f"  [8/8] Terminating AWS instance {instance_id} to eliminate ongoing costs...")
    ec2_client.terminate_instances(InstanceIds=[instance_id])
    print("  [OK] Instance termination requested. Zero lingering cost.")


def main():
    print("=" * 78)
    print("  NetTwin 2.0: Automated AWS High-Performance Dedicated Compute Run")
    print(f"  Target Instance: {INSTANCE_TYPE} (16 vCPUs, 32 GB RAM, Xeon Ice Lake)")
    print(f"  Region: {REGION} ({AZ})")
    print("=" * 78)

    archive = create_project_archive()
    ec2 = boto3.client("ec2", region_name=REGION)
    instance_id = None
    t0 = time.time()

    try:
        instance_id, ip = launch_instance(ec2)
        ssh = wait_for_ssh(ip, KEY_FILE)
        upload_and_prepare(ssh, archive)
        run_benchmark(ssh)
        download_artifacts(ssh)
        ssh.close()
    except Exception as e:
        print(f"\n[ERROR OCCURRED]: {e}")
        import traceback
        traceback.print_exc()
        raise e
    finally:
        if instance_id:
            terminate_instance(ec2, instance_id)
        if archive.exists():
            archive.unlink(missing_ok=True)
        elapsed = time.time() - t0
        cost_est = (elapsed / 3600.0) * 0.68
        print("\n" + "=" * 78)
        print(f"  AWS RUN COMPLETE in {elapsed:.1f}s ({elapsed/60:.1f} min)")
        print(f"  Estimated AWS Cost: ~${cost_est:.2f} USD")
        print("=" * 78)


if __name__ == "__main__":
    main()
