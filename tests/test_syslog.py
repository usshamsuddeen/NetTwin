"""Syslog parsing / ingestion integration tests."""
from nettwin.ingestion.normalize import Normalizer, parse_payload
from nettwin.ingestion.syslog_parser import parse_syslog


def _resolve(host: str) -> str | None:
    return {"10.0.1.11": "web1", "web1": "web1"}.get(host)


def test_parse_rfc3164_gauge():
    line = '<14>Oct 11 22:14:15 web1 cpu=31.2 mem=44.0 latency=1.2 loss=0.01'
    rec = parse_syslog(line)
    assert rec == {
        "type": "gauge",
        "host": "web1",
        "metrics": {
            "cpu_pct": 31.2,
            "mem_pct": 44.0,
            "latency_ms": 1.2,
            "packet_loss_pct": 0.01,
        },
    }


def test_parse_rfc5424_interface():
    line = ('<165>1 2023-10-11T22:14:15.000Z web1 - - - - '
            'type=interface in_bps=12000000 out_bps=4000000 in_pps=1500 out_pps=500')
    rec = parse_syslog(line)
    assert rec["type"] == "interface"
    assert rec["host"] == "web1"
    assert rec["in_bps"] == 12000000
    assert rec["out_pps"] == 500


def test_parse_flow_from_plain_kv():
    line = 'host=fw1 type=flow src=10.0.1.5 dst=10.0.2.11 proto=TCP bytes=51200 packets=40'
    rec = parse_syslog(line)
    assert rec == {
        "type": "flow",
        "src": "10.0.1.5",
        "dst": "10.0.2.11",
        "proto": "TCP",
        "bytes": 51200,
        "packets": 40,
    }


def test_parse_payload_mixed_json_and_syslog():
    text = (
        '{"type": "gauge", "host": "web1", "metrics": {"cpu_pct": 5}}\n'
        '<14>Oct 11 22:14:15 web1 cpu=22.0 mem=33.0\n'
    )
    records = parse_payload(text)
    assert len(records) == 2
    assert records[0]["type"] == "gauge"
    assert records[1]["type"] == "gauge"
    assert records[1]["host"] == "web1"


def test_normalizer_accepts_syslog_records():
    norm = Normalizer(_resolve)
    batch = norm.normalize([parse_syslog(
        '<14>Oct 11 22:14:15 10.0.1.11 cpu=50.0 mem=60.0')])
    assert "web1" in batch.gauges
    assert batch.gauges["web1"]["cpu_pct"] == 50.0


def test_normalizer_accepts_syslog_interface():
    norm = Normalizer(_resolve)
    batch = norm.normalize([parse_syslog(
        '<14>Oct 11 22:14:15 10.0.1.11 type=interface in_bps=100 out_bps=200')])
    assert batch.rx_bytes["web1"] == 12
    assert batch.tx_bytes["web1"] == 25


def test_percent_values_are_coerced():
    rec = parse_syslog('<14>Oct 11 22:14:15 web1 cpu=31.2% mem=44%')
    assert rec["metrics"]["cpu_pct"] == 31.2
    assert rec["metrics"]["mem_pct"] == 44.0
