import requests
import re
import warnings
from urllib3.exceptions import InsecureRequestWarning
warnings.simplefilter('ignore', InsecureRequestWarning)

endpoints = [
    ("23_cic_iot2022", "https://cicresearch.ca/IOTDataset/CIC_IOT_Dataset2022/"),
    ("28_cic_iot2024", "https://cicresearch.ca/IOTDataset/CIC-BCCC-NRC-TabularIoTAttacks-2024/"),
    ("29_cic_iiot2025", "https://cicresearch.ca/IOTDataset/Datasense/"),
    ("30_cic_darknet", "https://cicresearch.ca/CICDataset/CICDarknet2020/")
]

for name, base_url in endpoints:
    print(f"\n==================== {name} ====================")
    s = requests.Session()
    s.headers.update({'User-Agent': 'Mozilla/5.0'})
    insert_url = f"{base_url}insert.php"
    browse_url = f"{base_url}browse.php"
    try:
        r = s.post(insert_url, data={
            'first_name': 'Researcher',
            'last_name': 'Evaluation',
            'email': 'nettwin.evaluation@gmail.com',
            'institution': 'Academic Lab',
            'job_title': 'Researcher',
            'country': 'Canada'
        }, verify=False, timeout=10)
        print("Insert:", r.status_code)
        r2 = s.get(browse_url, verify=False, timeout=10)
        print("Browse:", r2.status_code)
        files = []
        for f in re.findall(r'href=["\'](.*?)["\']', r2.text):
            if 'download.php' in f or 'p=' in f:
                files.append(f)
        for f in files[:8]:
            print("  ->", f)
    except Exception as e:
        print("Error:", e)
