import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from real_data.loader import DatasetCatalog

for d_key in ['14_cidds001', '15_cidds002', '16_ctu13', '17_iot23']:
    gen = DatasetCatalog.stream_telemetry_batch(d_key, batch_size=5)
    batch = next(gen)
    p = batch[0]
    src = p.get("src_ip")
    dst = p.get("dst_ip")
    proto = p.get("protocol")
    anom = p.get("is_anomaly")
    print(f"[STREAM OK] {d_key}: {len(batch)} pkts | {src} -> {dst} ({proto}) anomaly={anom}")
