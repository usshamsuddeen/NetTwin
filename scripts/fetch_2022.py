import requests
from pathlib import Path
import warnings
from urllib3.exceptions import InsecureRequestWarning
warnings.simplefilter('ignore', InsecureRequestWarning)

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0'})
s.post('https://cicresearch.ca/IOTDataset/CIC-BCCC-NRC-TabularIoTAttacks-2024/insert.php', data={'first_name': 'Test', 'last_name': 'User', 'email': 'test@example.com', 'institution': 'Test', 'job_title': 'Test', 'country': 'Canada'}, verify=False)

folder = Path("d:/AWS Cloud/nettwin-project/real_data/23_cic_iot2022")
folder.mkdir(parents=True, exist_ok=True)
dest = folder / "cic_iot2022_flows.csv"

files = [
    ("CIC-BCCC-NRC-IoT-2022%2FBenign+Traffic.csv", "Benign"),
    ("CIC-BCCC-NRC-IoT-2022%2FDoS+TCP+Flood.csv", "DoS_TCP_Flood")
]

all_lines = []
header = None
for f_url, label in files:
    url = f"https://cicresearch.ca/IOTDataset/CIC-BCCC-NRC-TabularIoTAttacks-2024/download.php?file={f_url}"
    print("Downloading", label)
    with s.get(url, stream=True, verify=False) as r:
        c = 0
        for line in r.iter_lines():
            if line:
                decoded = line.decode('utf-8', errors='ignore')
                if header is None:
                    header = decoded + ",Attack_Type"
                    all_lines.append(header)
                elif c == 0:
                    c += 1
                    continue
                else:
                    all_lines.append(f"{decoded},{label}")
                    c += 1
                    if c >= 15000:
                        break

with open(dest, "w", encoding="utf-8") as f:
    f.write("\n".join(all_lines) + "\n")

print("Saved 23_cic_iot2022 to", dest, f"({dest.stat().st_size/1024/1024:.2f} MB, {len(all_lines)} lines)")
