import requests
import warnings
from urllib3.exceptions import InsecureRequestWarning
warnings.simplefilter('ignore', InsecureRequestWarning)

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0'})

# Test Darknet
s.post("https://cicresearch.ca/CICDataset/CICDarknet2020/insert.php", data={'first_name': 'Test', 'last_name': 'User', 'email': 'test@example.com', 'institution': 'Test', 'job_title': 'Test', 'country': 'Canada'}, verify=False)
with s.get("https://cicresearch.ca/CICDataset/CICDarknet2020/download.php?file=Darknet.CSV", stream=True, verify=False) as r:
    chunk = next(r.iter_content(chunk_size=1024*64))
    print("Darknet header:\n", chunk.decode('utf-8', errors='ignore')[:300])

# Test 2024 IoMT
s.post("https://cicresearch.ca/IOTDataset/CIC-BCCC-NRC-TabularIoTAttacks-2024/insert.php", data={'first_name': 'Test', 'last_name': 'User', 'email': 'test@example.com', 'institution': 'Test', 'job_title': 'Test', 'country': 'Canada'}, verify=False)
with s.get("https://cicresearch.ca/IOTDataset/CIC-BCCC-NRC-TabularIoTAttacks-2024/download.php?file=CIC-BCCC-NRC-IoMT-2024%2FMQTT+DDoS+Publish+Flood.csv", stream=True, verify=False) as r:
    chunk2 = next(r.iter_content(chunk_size=1024*64))
    print("\n2024 IoMT header:\n", chunk2.decode('utf-8', errors='ignore')[:300])
