"""AWS Adapter — polls CloudWatch Logs (VPC Flow Logs), CloudWatch Metrics,
and optionally CloudTrail events, converting them to the same record format
that ``simulate_real_feed.py`` produces.

All records feed through the existing ``Normalizer`` → ``SyncEngine.ingest()``
pipeline.  Zero changes to the twin engine, detector, or any downstream
component.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import boto3
from botocore.exceptions import ClientError

from nettwin.ingestion.normalize import Normalizer

log = logging.getLogger("nettwin.aws")

# VPC Flow Log v2 protocol number → human-readable name
PROTO_MAP: dict[int, str] = {6: "TCP", 17: "UDP", 1: "ICMP"}


@dataclass
class AWSAdapterStats:
    """Observable counters exposed by ``GET /api/aws/status``."""
    flow_polls: int = 0
    flow_records: int = 0
    metric_polls: int = 0
    metric_records: int = 0
    cloudtrail_polls: int = 0
    cloudtrail_events: int = 0
    errors: int = 0
    last_poll_ts: float = 0.0
    instances_discovered: int = 0
    started_at: float = field(default_factory=time.time)
    # Flow Log delivery delay instrumentation (end-to-end: flow end time → CW Logs receive)
    flow_delay_samples: int = 0
    flow_delay_min_s: float = 0.0
    flow_delay_max_s: float = 0.0
    flow_delay_sum_s: float = 0.0
    flow_delay_recent_s: list[float] = field(default_factory=list)


class AWSAdapter:
    """Async adapter that polls live AWS data and feeds the NetTwin pipeline.

    Parameters
    ----------
    settings : Settings
        Full application settings (reads ``settings.aws.*``).
    normalizer : Normalizer
        The shared normalizer wired to ``SyncEngine.resolve``.
    sync : SyncEngine
        The sync engine whose ``.ingest()`` method receives batches.
    """

    def __init__(self, settings, normalizer: Normalizer, sync) -> None:
        self.aws = settings.aws
        self.normalizer = normalizer
        self.sync = sync
        self.tick_s: float = settings.tick_s

        self.stats = AWSAdapterStats()

        # boto3 clients — created once, reused across polls
        session = boto3.Session(region_name=self.aws.region)
        self._logs = session.client("logs")
        self._cw = session.client("cloudwatch")
        self._ec2 = session.client("ec2")
        if self.aws.cloudtrail_enabled:
            self._ct = session.client("cloudtrail")
        else:
            self._ct = None

        # Cursor tracking: millisecond timestamp of last processed event
        self._flow_cursor_ms: int = int(time.time() * 1000) - 60_000
        self._ct_cursor: float = time.time() - 300  # 5-min lookback on start

        # Discovered EC2 instance private IPs keyed by instance ID
        self._instance_ips: dict[str, str] = {}

        # Background task handles
        self._tasks: list[asyncio.Task] = []
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def start(self) -> None:
        """Launch polling loops as background asyncio tasks."""
        if self._running:
            return
        self._running = True
        log.info("AWS adapter starting (region=%s, poll=%ss)",
                 self.aws.region, self.aws.poll_interval_s)

        # Discover instances before starting pollers
        await self._discover_instances()

        self._tasks.append(asyncio.create_task(self._flow_loop()))
        self._tasks.append(asyncio.create_task(self._metrics_loop()))
        if self.aws.cloudtrail_enabled and self._ct:
            self._tasks.append(asyncio.create_task(self._cloudtrail_loop()))
        log.info("AWS adapter started: %d instance(s), %d poller(s)",
                 len(self._instance_ips), len(self._tasks))

    async def stop(self) -> None:
        """Cancel all background polling tasks."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()
        log.info("AWS adapter stopped")

    # ------------------------------------------------------------------
    # Instance discovery
    # ------------------------------------------------------------------
    async def _discover_instances(self) -> None:
        """Discover running EC2 instances tagged with ``Project=nettwin``."""
        try:
            loop = asyncio.get_running_loop()
            resp = await loop.run_in_executor(None, lambda: self._ec2.describe_instances(
                Filters=[{
                    "Name": f"tag:{k}",
                    "Values": [v],
                } for k, v in self.aws.instance_tags.items()] + [{
                    "Name": "instance-state-name",
                    "Values": ["running"],
                }],
            ))
            self._instance_ips.clear()
            for res in resp.get("Reservations", []):
                for inst in res.get("Instances", []):
                    iid = inst["InstanceId"]
                    ip = inst.get("PrivateIpAddress")
                    if ip:
                        self._instance_ips[iid] = ip
            self.stats.instances_discovered = len(self._instance_ips)
            log.info("discovered %d EC2 instances: %s",
                     len(self._instance_ips), list(self._instance_ips.values()))
        except ClientError as exc:
            self.stats.errors += 1
            log.warning("EC2 discovery failed: %s", exc)

    # ------------------------------------------------------------------
    # 1. VPC Flow Log Poller (CloudWatch Logs)
    # ------------------------------------------------------------------
    async def _flow_loop(self) -> None:
        """Poll ``logs:FilterLogEvents`` on the CloudWatch Log Group."""
        while self._running:
            try:
                await self._poll_flow_logs()
            except asyncio.CancelledError:
                return
            except Exception as exc:
                self.stats.errors += 1
                log.warning("flow poll error: %s", exc)
            await asyncio.sleep(self.aws.poll_interval_s)

    async def _poll_flow_logs(self) -> None:
        loop = asyncio.get_running_loop()
        kwargs: dict[str, Any] = {
            "logGroupName": self.aws.flow_log_group,
            "startTime": self._flow_cursor_ms,
            "interleaved": True,
        }
        records: list[dict[str, Any]] = []
        max_ts = self._flow_cursor_ms

        while True:
            resp = await loop.run_in_executor(
                None, lambda kw=dict(kwargs): self._logs.filter_log_events(**kw))
            for event in resp.get("events", []):
                parsed = self._parse_flow_line(event.get("message", ""))
                if parsed:
                    records.append(parsed)
                ts = event.get("timestamp", self._flow_cursor_ms)
                if ts > max_ts:
                    max_ts = ts
            next_token = resp.get("nextToken")
            if next_token:
                kwargs["nextToken"] = next_token
            else:
                break

        now = time.time()
        for rec in records:
            delay = rec.pop("_delay_s", None)
            if delay is not None:
                self._record_delay(delay)

        if records:
            batch = self.normalizer.normalize(records)
            self.sync.ingest(batch, self.tick_s)
            self.stats.flow_records += len(records)
            log.debug("flow poll: %d records ingested", len(records))

        # Advance cursor past the last processed event (+1ms to avoid re-read)
        self._flow_cursor_ms = max_ts + 1
        self.stats.flow_polls += 1
        self.stats.last_poll_ts = now
        if self.stats.flow_delay_samples and self.stats.flow_polls % 10 == 0:
            log.info("flow log delivery delay (last=%.1fs, min=%.1fs, max=%.1fs, mean=%.1fs, n=%d)",
                     self.stats.flow_delay_recent_s[-1] if self.stats.flow_delay_recent_s else 0,
                     self.stats.flow_delay_min_s,
                     self.stats.flow_delay_max_s,
                     self.stats.flow_delay_sum_s / self.stats.flow_delay_samples,
                     self.stats.flow_delay_samples)

    def _record_delay(self, delay_s: float) -> None:
        s = self.stats
        if s.flow_delay_samples == 0:
            s.flow_delay_min_s = s.flow_delay_max_s = delay_s
        else:
            s.flow_delay_min_s = min(s.flow_delay_min_s, delay_s)
            s.flow_delay_max_s = max(s.flow_delay_max_s, delay_s)
        s.flow_delay_sum_s += delay_s
        s.flow_delay_samples += 1
        s.flow_delay_recent_s.append(delay_s)
        if len(s.flow_delay_recent_s) > 30:
            s.flow_delay_recent_s.pop(0)

    def _parse_flow_line(self, line: str) -> dict[str, Any] | None:
        """Parse a VPC Flow Log v2 line into a normalizer-compatible record.

        Format (space-delimited, 14 fields):
            version account-id interface-id srcaddr dstaddr srcport dstport
            protocol packets bytes start end action log-status

        Also computes end-to-end delivery delay (flow end time → now) when the
        flow log ``end`` field is present.
        """
        parts = line.strip().split()
        if len(parts) < 14:
            return None
        try:
            srcaddr = parts[3]
            dstaddr = parts[4]
            protocol = int(parts[7])
            packets = int(parts[8])
            nbytes = int(parts[9])
            start_s = int(parts[10])
            end_s = int(parts[11])
            action = parts[12]  # ACCEPT or REJECT
        except (ValueError, IndexError):
            return None
        # Skip header rows or malformed lines
        if srcaddr == "srcaddr" or srcaddr == "-":
            return None
        proto_name = PROTO_MAP.get(protocol, f"PROTO-{protocol}")
        rec: dict[str, Any] = {
            "type": "flow",
            "src": srcaddr,
            "dst": dstaddr,
            "proto": proto_name,
            "bytes": nbytes,
            "packets": packets,
            "action": action,
            "start": start_s,
            "end": end_s,
        }
        # Delivery delay = time between when the flow ended and when we received it.
        delay_s = time.time() - end_s
        if delay_s >= 0:
            rec["_delay_s"] = delay_s
        return rec

    # ------------------------------------------------------------------
    # 2. CloudWatch Metrics Poller
    # ------------------------------------------------------------------
    async def _metrics_loop(self) -> None:
        """Poll ``cloudwatch:GetMetricData`` for EC2 instance metrics."""
        while self._running:
            try:
                if self._instance_ips and self.aws.cloudwatch_metrics:
                    await self._poll_metrics()
            except asyncio.CancelledError:
                return
            except Exception as exc:
                self.stats.errors += 1
                log.warning("metrics poll error: %s", exc)
            await asyncio.sleep(self.aws.poll_interval_s)

    async def _poll_metrics(self) -> None:
        import datetime as dt

        loop = asyncio.get_running_loop()
        now = dt.datetime.now(dt.timezone.utc)
        start = now - dt.timedelta(minutes=5)
        records: list[dict[str, Any]] = []

        instance_list = list(self._instance_ips.items())
        metric_names = [
            "CPUUtilization", "NetworkIn", "NetworkOut",
            "NetworkPacketsIn", "NetworkPacketsOut",
        ]

        # Build MetricDataQueries for each instance
        queries: list[dict[str, Any]] = []
        for idx, (iid, _ip) in enumerate(instance_list):
            for midx, mname in enumerate(metric_names):
                queries.append({
                    "Id": f"m{idx}_{midx}",
                    "MetricStat": {
                        "Metric": {
                            "Namespace": "AWS/EC2",
                            "MetricName": mname,
                            "Dimensions": [
                                {"Name": "InstanceId", "Value": iid},
                            ],
                        },
                        "Period": 60,
                        "Stat": "Average",
                    },
                })

        if not queries:
            return

        resp = await loop.run_in_executor(None, lambda: self._cw.get_metric_data(
            MetricDataQueries=queries,
            StartTime=start,
            EndTime=now,
        ))

        # Group results by instance index
        per_instance: dict[int, dict[str, float]] = {}
        for result in resp.get("MetricDataResults", []):
            qid = result.get("Id", "")
            values = result.get("Values", [])
            if not values:
                continue
            try:
                parts_id = qid.lstrip("m").split("_")
                inst_idx = int(parts_id[0])
                met_idx = int(parts_id[1])
            except (ValueError, IndexError):
                continue
            latest = values[0]  # most recent datapoint
            per_instance.setdefault(inst_idx, {})[metric_names[met_idx]] = latest

        # Build normalizer records using private IPs as host keys
        for inst_idx, metrics in per_instance.items():
            if inst_idx >= len(instance_list):
                continue
            _iid, host_ip = instance_list[inst_idx]

            cpu = metrics.get("CPUUtilization")
            if cpu is not None:
                records.append({
                    "type": "gauge",
                    "host": host_ip,
                    "ts": time.time(),
                    "metrics": {"cpu_pct": round(cpu, 2)},
                })

            net_in = metrics.get("NetworkIn", 0)
            net_out = metrics.get("NetworkOut", 0)
            pps_in = metrics.get("NetworkPacketsIn", 0)
            pps_out = metrics.get("NetworkPacketsOut", 0)
            if net_in or net_out:
                records.append({
                    "type": "interface",
                    "host": host_ip,
                    "in_bps": net_in * 8,       # bytes/s → bits/s
                    "out_bps": net_out * 8,
                    "in_pps": pps_in,
                    "out_pps": pps_out,
                })

        if records:
            batch = self.normalizer.normalize(records)
            self.sync.ingest(batch, self.tick_s)
            self.stats.metric_records += len(records)
            log.debug("metrics poll: %d records ingested", len(records))

        self.stats.metric_polls += 1
        self.stats.last_poll_ts = time.time()

    # ------------------------------------------------------------------
    # 3. CloudTrail Event Watcher (optional)
    # ------------------------------------------------------------------
    async def _cloudtrail_loop(self) -> None:
        """Poll ``cloudtrail:LookupEvents`` for topology-change events."""
        while self._running:
            try:
                await self._poll_cloudtrail()
            except asyncio.CancelledError:
                return
            except Exception as exc:
                self.stats.errors += 1
                log.warning("cloudtrail poll error: %s", exc)
            await asyncio.sleep(30.0)  # CloudTrail delivers slowly

    async def _poll_cloudtrail(self) -> None:
        import datetime as dt

        loop = asyncio.get_running_loop()
        start_time = dt.datetime.fromtimestamp(
            self._ct_cursor, tz=dt.timezone.utc)
        events_of_interest = [
            "RunInstances", "TerminateInstances",
            "CreateSecurityGroupRule", "RevokeSecurityGroupIngress",
        ]
        resp = await loop.run_in_executor(None, lambda: self._ct.lookup_events(
            LookupAttributes=[{
                "AttributeKey": "ReadOnly",
                "AttributeValue": "false",
            }],
            StartTime=start_time,
            MaxResults=50,
        ))
        count = 0
        for event in resp.get("Events", []):
            event_name = event.get("EventName", "")
            if event_name in events_of_interest:
                log.info("CloudTrail topology event: %s at %s",
                         event_name, event.get("EventTime"))
                count += 1
                if event_name in ("RunInstances", "TerminateInstances"):
                    await self._discover_instances()

        self._ct_cursor = time.time()
        self.stats.cloudtrail_polls += 1
        self.stats.cloudtrail_events += count

    # ------------------------------------------------------------------
    # Status snapshot for API
    # ------------------------------------------------------------------
    def status(self) -> dict[str, Any]:
        """Return adapter status for ``GET /api/aws/status``."""
        delay_mean = 0.0
        if self.stats.flow_delay_samples:
            delay_mean = self.stats.flow_delay_sum_s / self.stats.flow_delay_samples
        return {
            "connected": self._running,
            "region": self.aws.region,
            "instances_discovered": self.stats.instances_discovered,
            "instance_ips": list(self._instance_ips.values()),
            "flow_log_group": self.aws.flow_log_group,
            "flow_polls": self.stats.flow_polls,
            "flow_records": self.stats.flow_records,
            "flow_delay_s": {
                "samples": self.stats.flow_delay_samples,
                "min": round(self.stats.flow_delay_min_s, 2),
                "max": round(self.stats.flow_delay_max_s, 2),
                "mean": round(delay_mean, 2),
                "recent": [round(x, 2) for x in self.stats.flow_delay_recent_s[-10:]],
            },
            "metric_polls": self.stats.metric_polls,
            "metric_records": self.stats.metric_records,
            "cloudtrail_polls": self.stats.cloudtrail_polls,
            "cloudtrail_events": self.stats.cloudtrail_events,
            "errors": self.stats.errors,
            "last_poll_ts": self.stats.last_poll_ts,
            "uptime_s": round(time.time() - self.stats.started_at, 1),
        }
