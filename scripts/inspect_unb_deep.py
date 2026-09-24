import requests
import re
import warnings
from urllib3.exceptions import InsecureRequestWarning
warnings.simplefilter('ignore', InsecureRequestWarning)

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0'})

# 1. 23_cic_iot2022 CSV folder
print("=== 23_cic_iot2022 CSV ===")
s.post("https://cicresearch.ca/IOTDataset/CIC_IOT_Dataset2022/insert.php", data={'first_name': 'Test', 'last_name': 'User', 'email': 'test@example.com', 'institution': 'Test', 'job_title': 'Test', 'country': 'Canada'}, verify=False)
r = s.get("https://cicresearch.ca/IOTDataset/CIC_IOT_Dataset2022/browse.php?p=CSV", verify=False)
for f in re.findall(r'href=["\'](.*?)["\']', r.text):
    if 'download.php' in f or 'p=' in f:
        print("  ->", f)

# 2. 28_cic_iot2024 subfolders
print("\n=== 28_cic_iot2024 Tabular ===")
s.post("https://cicresearch.ca/IOTDataset/CIC-BCCC-NRC-TabularIoTAttacks-2024/insert.php", data={'first_name': 'Test', 'last_name': 'User', 'email': 'test@example.com', 'institution': 'Test', 'job_title': 'Test', 'country': 'Canada'}, verify=False)
r = s.get("https://cicresearch.ca/IOTDataset/CIC-BCCC-NRC-TabularIoTAttacks-2024/browse.php?p=CIC-BCCC-NRC-IoMT-2024", verify=False)
for f in re.findall(r'href=["\'](.*?)["\']', r.text):
    if 'download.php' in f or 'file=' in f or 'p=' in f:
        print("  IoMT ->", f)

# 3. 29_cic_iiot2025 dataset folder
print("\n=== 29_cic_iiot2025 dataset ===")
s.post("https://cicresearch.ca/IOTDataset/Datasense/insert.php", data={'first_name': 'Test', 'last_name': 'User', 'email': 'test@example.com', 'institution': 'Test', 'job_title': 'Test', 'country': 'Canada'}, verify=False)
r = s.get("https://cicresearch.ca/IOTDataset/Datasense/browse.php?p=dataset", verify=False)
for f in re.findall(r'href=["\'](.*?)["\']', r.text):
    if 'download.php' in f or 'file=' in f or 'p=' in f:
        print("  Datasense ->", f)

# 4. 30_cic_darknet Darknet.CSV
print("\n=== 30_cic_darknet ===")
s.post("https://cicresearch.ca/CICDataset/CICDarknet2020/insert.php", data={'first_name': 'Test', 'last_name': 'User', 'email': 'test@example.com', 'institution': 'Test', 'job_title': 'Test', 'country': 'Canada'}, verify=False)
r = s.head("https://cicresearch.ca/CICDataset/CICDarknet2020/download.php?file=Darknet.CSV", verify=False)
print("  Darknet.CSV Head:", r.headers.get('Content-Disposition'), r.headers.get('Content-Length'))
