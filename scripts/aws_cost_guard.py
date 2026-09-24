"""AWS Cost Guard — three-tier cost monitoring safety net.

Tier 1 (primary, ~6h delay):  CloudWatch EstimatedCharges metric
Tier 2 (instant backup):      Local estimate from running EC2 count × hourly rate
Tier 3 (daily reconciliation): Cost Explorer GetCostAndUsage (24h delayed)

Usage:
    python scripts/aws_cost_guard.py --limit 5 --region us-east-1
    python scripts/aws_cost_guard.py --limit 5 --destroy   # auto-destroy on breach

Cron:
    */30 * * * * python /app/scripts/aws_cost_guard.py --limit 5 --destroy
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys

import boto3
from botocore.exceptions import ClientError


# Approximate hourly rates for common instance types (us-east-1, on-demand)
HOURLY_RATES: dict[str, float] = {
    "t3.nano": 0.0052,
    "t3.micro": 0.0104,
    "t3.small": 0.0208,
    "t3.medium": 0.0416,
    "t3.large": 0.0832,
}


def tier1_cloudwatch(region: str) -> float | None:
    """Tier 1: CloudWatch EstimatedCharges metric (~6h delay)."""
    cw = boto3.client("cloudwatch", region_name="us-east-1")  # billing is always us-east-1
    now = dt.datetime.now(dt.timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        resp = cw.get_metric_data(
            MetricDataQueries=[{
                "Id": "cost",
                "MetricStat": {
                    "Metric": {
                        "Namespace": "AWS/Billing",
                        "MetricName": "EstimatedCharges",
                        "Dimensions": [
                            {"Name": "Currency", "Value": "USD"},
                        ],
                    },
                    "Period": 21600,  # 6 hours
                    "Stat": "Maximum",
                },
            }],
            StartTime=today_start,
            EndTime=now,
        )
        values = resp.get("MetricDataResults", [{}])[0].get("Values", [])
        if values:
            return float(max(values))
    except ClientError as exc:
        print(f"  [tier1] CloudWatch billing error: {exc}", file=sys.stderr)
    return None


def tier2_local_estimate(region: str) -> float:
    """Tier 2: Count running nettwin EC2 instances × hourly rate × hours today."""
    ec2 = boto3.client("ec2", region_name=region)
    try:
        resp = ec2.describe_instances(Filters=[
            {"Name": "tag:Project", "Values": ["nettwin"]},
            {"Name": "instance-state-name", "Values": ["running"]},
        ])
    except ClientError as exc:
        print(f"  [tier2] EC2 describe error: {exc}", file=sys.stderr)
        return 0.0

    total_hourly = 0.0
    count = 0
    for res in resp.get("Reservations", []):
        for inst in res.get("Instances", []):
            itype = inst.get("InstanceType", "t3.micro")
            rate = HOURLY_RATES.get(itype, 0.0104)
            total_hourly += rate
            count += 1

    now = dt.datetime.now(dt.timezone.utc)
    hours_today = now.hour + now.minute / 60.0
    estimate = total_hourly * max(hours_today, 1.0)

    print(f"  [tier2] {count} instances, ${total_hourly:.4f}/hr, "
          f"{hours_today:.1f}h today → ${estimate:.2f} estimated")
    return estimate


def tier3_cost_explorer(region: str) -> float | None:
    """Tier 3: Cost Explorer GetCostAndUsage (accurate but 24h delayed)."""
    ce = boto3.client("ce", region_name="us-east-1")
    now = dt.datetime.now(dt.timezone.utc)
    start = (now - dt.timedelta(days=1)).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")
    try:
        resp = ce.get_cost_and_usage(
            TimePeriod={"Start": start, "End": end},
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
            Filter={
                "Tags": {
                    "Key": "Project",
                    "Values": ["nettwin"],
                },
            },
        )
        for result in resp.get("ResultsByTime", []):
            amount = float(result["Total"]["UnblendedCost"]["Amount"])
            if amount > 0:
                return amount
    except ClientError as exc:
        print(f"  [tier3] Cost Explorer error: {exc}", file=sys.stderr)
    return None


def check_cost(limit: float, region: str, destroy: bool = False) -> int:
    """Run all three tiers and alert if any exceeds the daily limit."""
    print(f"NetTwin Cost Guard — daily limit: ${limit:.2f}")
    print(f"Region: {region}")
    print()

    breached = False
    results: dict[str, float | None] = {}

    # Tier 1
    t1 = tier1_cloudwatch(region)
    results["tier1_cloudwatch"] = t1
    if t1 is not None:
        status = "⚠️  OVER LIMIT" if t1 > limit else "✅ OK"
        print(f"  [tier1] CloudWatch EstimatedCharges: ${t1:.2f} {status}")
        if t1 > limit:
            breached = True
    else:
        print("  [tier1] CloudWatch billing data unavailable")

    # Tier 2
    t2 = tier2_local_estimate(region)
    results["tier2_local"] = t2
    if t2 > limit:
        print(f"  [tier2] ⚠️  OVER LIMIT (${t2:.2f} > ${limit:.2f})")
        breached = True
    else:
        print(f"  [tier2] ✅ OK (${t2:.2f})")

    # Tier 3
    t3 = tier3_cost_explorer(region)
    results["tier3_ce"] = t3
    if t3 is not None:
        status = "⚠️  OVER LIMIT" if t3 > limit else "✅ OK"
        print(f"  [tier3] Cost Explorer (yesterday): ${t3:.2f} {status}")
        if t3 > limit:
            breached = True
    else:
        print("  [tier3] Cost Explorer data unavailable (24h delay)")

    print()
    print(json.dumps(results, indent=2))

    if breached:
        print()
        print("=" * 60)
        print("⚠️  DAILY COST LIMIT EXCEEDED!")
        print("=" * 60)
        if destroy:
            print("Running terraform destroy -auto-approve ...")
            try:
                subprocess.run(
                    ["terraform", "destroy", "-auto-approve"],
                    cwd="infra",
                    check=True,
                )
                print("Infrastructure destroyed.")
            except (subprocess.CalledProcessError, FileNotFoundError) as exc:
                print(f"terraform destroy failed: {exc}", file=sys.stderr)
        return 1

    print("✅ All tiers within budget.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="NetTwin AWS Cost Guard")
    ap.add_argument("--limit", type=float, default=5.0,
                    help="daily cost limit in USD (default: 5.0)")
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--destroy", action="store_true",
                    help="auto-run terraform destroy if over limit")
    args = ap.parse_args()
    return check_cost(args.limit, args.region, args.destroy)


if __name__ == "__main__":
    sys.exit(main())
