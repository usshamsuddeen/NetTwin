"""Capture live AWS telemetry for NetTwin 2.0 Paper 5 figures.

This script uses the existing ``AWSAdapter`` (``nettwin/ingestion/adapters/aws_adapter.py``)
to record real VPC Flow Log volumes and CloudWatch EC2 metrics over a configurable
capture window.  Output is written to ``eval/results/aws_capture_<utc-timestamp>.json``
and is consumed by ``eval/p5_system.py`` when rendering fig0a/fig0b.

Run without arguments to capture for the default window (5 minutes) using the
settings in ``config.json``.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Ensure project root is importable when run as a standalone script.
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from nettwin.ingestion.adapters.aws_adapter import AWSAdapter  # noqa: E402

log = logging.getLogger("capture_aws_telemetry")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

CONFIG_PATH = PROJECT_ROOT / "config.json"
RESULTS_DIR = PROJECT_ROOT / "eval" / "results"
DEFAULT_WINDOW_MIN = 5
DEFAULT_POLL_INTERVAL_S = 10.0


@dataclass
class _CaptureState:
    """Mutable capture bookkeeping."""
    flow_counts: list[dict[str, Any]] = field(default_factory=list)
    metric_samples: list[dict[str, Any]] = field(default_factory=list)
    latency_samples: list[dict[str, Any]] = field(default_factory=list)
    last_batch: list[dict[str, Any]] | None = None
    prev_flow_records: int = 0
    prev_metric_records: int = 0


class _NoOpNormalizer:
    """Normalizer stub: AWSAdapter only needs a ``normalize`` method."""

    def normalize(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return records


class _CapturingSync:
    """SyncEngine stub that records the last ingested batch for metrics parsing."""

    def __init__(self, state: _CaptureState) -> None:
        self.state = state

    def ingest(self, batch: Any, tick_s: float) -> None:
        if isinstance(batch, list):
            self.state.last_batch = batch


def _load_config() -> dict[str, Any]:
    """Load ``config.json`` if present, otherwise return sensible defaults."""
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            log.warning("Could not parse %s: %s; using defaults", CONFIG_PATH, exc)
    return {}


def _build_settings(config: dict[str, Any], overrides: dict[str, Any] | None = None) -> Any:
    """Build a settings object compatible with ``AWSAdapter``."""
    aws_cfg = config.get("aws", {})
    if overrides:
        aws_cfg = {**aws_cfg, **overrides}

    aws = SimpleNamespace(
        region=aws_cfg.get("region", "us-east-1"),
        flow_log_group=aws_cfg.get("flow_log_group", "/vpc/nettwin-flowlogs"),
        poll_interval_s=float(aws_cfg.get("poll_interval_s", DEFAULT_POLL_INTERVAL_S)),
        cloudwatch_metrics=bool(aws_cfg.get("cloudwatch_metrics", True)),
        cloudtrail_enabled=bool(aws_cfg.get("cloudtrail_enabled", False)),
        instance_tags=dict(aws_cfg.get("instance_tags", {"Project": "nettwin"})),
    )
    return SimpleNamespace(aws=aws, tick_s=10.0)


def _check_aws_credentials(region: str) -> bool:
    """Verify that boto3 can obtain valid AWS credentials."""
    try:
        session = boto3.Session(region_name=region)
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        log.info("AWS identity: %s", identity.get("Arn", "unknown"))
        return True
    except NoCredentialsError:
        log.error(
            "AWS credentials not found. Configure credentials via one of:\n"
            "  - environment variables AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY\n"
            "  - ~/.aws/credentials (and optionally AWS_PROFILE)\n"
            "  - an attached IAM role/instance profile"
        )
        return False
    except ClientError as exc:
        log.error("AWS credential check failed: %s", exc)
        return False


def _extract_metric_samples(
    batch: list[dict[str, Any]] | None,
    ip_to_iid: dict[str, str],
    bucket_ts: str,
) -> list[dict[str, Any]]:
    """Parse a normalized CloudWatch metrics batch into per-instance samples."""
    samples: list[dict[str, Any]] = []
    if not batch:
        return samples
    for record in batch:
        host_ip = record.get("host")
        iid = ip_to_iid.get(host_ip or "")
        if not iid:
            continue
        sample: dict[str, Any] = {
            "timestamp": bucket_ts,
            "instance_id": iid,
            "host_ip": host_ip,
        }
        rtype = record.get("type")
        if rtype == "gauge":
            metrics = record.get("metrics", {})
            if "cpu_pct" in metrics:
                sample["CPUUtilization"] = round(float(metrics["cpu_pct"]), 4)
        elif rtype == "interface":
            for key, metric in [
                ("in_bps", "NetworkIn"),
                ("out_bps", "NetworkOut"),
                ("in_pps", "NetworkPacketsIn"),
                ("out_pps", "NetworkPacketsOut"),
            ]:
                val = record.get(key)
                if val is not None:
                    sample[metric] = round(float(val), 4)
        if len(sample) > 3:
            samples.append(sample)
    return samples


def _latest_metric_by_instance(
    samples: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Return the most recent sample per instance."""
    latest: dict[str, dict[str, Any]] = {}
    for sample in samples:
        iid = sample.get("instance_id")
        if not iid:
            continue
        prev = latest.get(iid)
        if prev is None or sample.get("timestamp", "") > prev.get("timestamp", ""):
            latest[iid] = sample
    return latest


async def _capture(
    window_minutes: int,
    settings: Any,
    state: _CaptureState,
) -> dict[str, Any]:
    """Run the capture loop and return the serialized capture dict."""
    sync_stub = _CapturingSync(state)
    adapter = AWSAdapter(settings, _NoOpNormalizer(), sync_stub)

    start_utc = datetime.now(timezone.utc)
    log.info("Starting AWS telemetry capture at %s (region=%s, window=%d min)",
             start_utc.isoformat(), settings.aws.region, window_minutes)

    await adapter._discover_instances()
    instance_ids = sorted(adapter._instance_ips.keys())
    log.info("Discovered %d EC2 instance(s): %s", len(instance_ids), instance_ids)

    if not instance_ids:
        log.error(
            "No NetTwin testbed instances found matching tags %s in region %s.\n"
            "Deploy the testbed (see infra/main.tf) before capturing telemetry.",
            settings.aws.instance_tags, settings.aws.region,
        )
        sys.exit(1)

    # Start the flow cursor at the capture start time so we record only data
    # that arrives during the window (plus any small lookback CloudWatch provides).
    adapter._flow_cursor_ms = int(start_utc.timestamp() * 1000)

    end_time = start_utc.timestamp() + window_minutes * 60
    poll_interval = settings.aws.poll_interval_s

    while time.time() < end_time:
        bucket_ts = datetime.now(timezone.utc).isoformat()

        # --- VPC Flow Logs poll ---
        t0 = time.perf_counter()
        try:
            await adapter._poll_flow_logs()
        except ClientError as exc:
            log.error("Flow-log poll failed: %s", exc)
        except Exception as exc:
            log.error("Unexpected flow-log poll error: %s", exc)
        flow_latency_ms = (time.perf_counter() - t0) * 1000.0
        flow_delta = max(0, adapter.stats.flow_records - state.prev_flow_records)
        state.prev_flow_records = adapter.stats.flow_records
        state.flow_counts.append({"window_start": bucket_ts, "count": flow_delta})
        state.latency_samples.append({
            "timestamp": bucket_ts,
            "kind": "flow_logs",
            "latency_ms": round(flow_latency_ms, 3),
        })

        # --- CloudWatch Metrics poll ---
        if settings.aws.cloudwatch_metrics and instance_ids:
            state.last_batch = None  # ensure we only see records from this poll
            t0 = time.perf_counter()
            try:
                await adapter._poll_metrics()
            except ClientError as exc:
                log.error("CloudWatch metrics poll failed: %s", exc)
            except Exception as exc:
                log.error("Unexpected metrics poll error: %s", exc)
            metrics_latency_ms = (time.perf_counter() - t0) * 1000.0
            state.latency_samples.append({
                "timestamp": bucket_ts,
                "kind": "cloudwatch_metrics",
                "latency_ms": round(metrics_latency_ms, 3),
            })

            # Record the latest per-instance metric values returned by this poll.
            ip_to_iid = {ip: iid for iid, ip in adapter._instance_ips.items()}
            metric_delta = _extract_metric_samples(
                state.last_batch, ip_to_iid, bucket_ts)
            state.metric_samples.extend(metric_delta)
            state.last_batch = None
            metric_delta_count = max(
                0, adapter.stats.metric_records - state.prev_metric_records)
            state.prev_metric_records = adapter.stats.metric_records
            log.debug("metrics poll: %d samples", metric_delta_count)

        await asyncio.sleep(poll_interval)

    end_utc = datetime.now(timezone.utc)
    total_flow_records = adapter.stats.flow_records

    # Compute a per-instance average CPU/network summary for the heatmap.
    latest = _latest_metric_by_instance(state.metric_samples)
    heatmap_rows = []
    for iid in instance_ids:
        s = latest.get(iid, {})
        heatmap_rows.append({
            "instance_id": iid,
            "CPUUtilization": s.get("CPUUtilization"),
            "NetworkIn": s.get("NetworkIn"),
            "NetworkOut": s.get("NetworkOut"),
            "NetworkPacketsIn": s.get("NetworkPacketsIn"),
            "NetworkPacketsOut": s.get("NetworkPacketsOut"),
        })

    capture = {
        "metadata": {
            "region": settings.aws.region,
            "instance_ids": instance_ids,
            "window_minutes": window_minutes,
            "poll_interval_s": poll_interval,
            "start_utc": start_utc.isoformat(),
            "end_utc": end_utc.isoformat(),
            "capture_duration_s": round(end_utc.timestamp() - start_utc.timestamp(), 1),
            "total_flow_records": total_flow_records,
            "total_metric_samples": len(state.metric_samples),
            "total_latency_samples": len(state.latency_samples),
            "flow_log_group": settings.aws.flow_log_group,
        },
        "flow_counts": state.flow_counts,
        "metric_samples": state.metric_samples,
        "heatmap_summary": heatmap_rows,
        "latency_samples": state.latency_samples,
    }
    return capture


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture live AWS telemetry for NetTwin 2.0 Paper 5 figures.",
    )
    parser.add_argument(
        "--window-minutes",
        type=int,
        default=DEFAULT_WINDOW_MIN,
        help=f"Capture window in minutes (default: {DEFAULT_WINDOW_MIN}).",
    )
    parser.add_argument(
        "--region",
        type=str,
        default=None,
        help="AWS region override.",
    )
    parser.add_argument(
        "--flow-log-group",
        type=str,
        default=None,
        help="CloudWatch Logs log group for VPC Flow Logs v2.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=RESULTS_DIR,
        help="Directory for the output JSON file.",
    )
    args = parser.parse_args()

    config = _load_config()
    overrides: dict[str, Any] = {}
    if args.region:
        overrides["region"] = args.region
    if args.flow_log_group:
        overrides["flow_log_group"] = args.flow_log_group

    settings = _build_settings(config, overrides=overrides)

    if not _check_aws_credentials(settings.aws.region):
        sys.exit(1)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    state = _CaptureState()

    try:
        capture = asyncio.run(_capture(args.window_minutes, settings, state))
    except KeyboardInterrupt:
        log.info("Capture interrupted by user.")
        sys.exit(130)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = args.output_dir / f"aws_capture_{timestamp}.json"
    out_path.write_text(json.dumps(capture, indent=2), encoding="utf-8")

    meta = capture["metadata"]
    log.info("Capture saved to %s", out_path)
    log.info(
        "Recorded %d flow records (%d windows) and %d metric samples from %s instances.",
        meta["total_flow_records"], len(capture["flow_counts"]),
        meta["total_metric_samples"], len(meta["instance_ids"]),
    )


if __name__ == "__main__":
    main()
