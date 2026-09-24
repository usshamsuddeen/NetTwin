import requests
import re
import warnings
from urllib3.exceptions import InsecureRequestWarning
warnings.simplefilter('ignore', InsecureRequestWarning)

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0'})

for ds in ['CIC_IOT_Dataset2022', 'CIC_IOT_Dataset2024', 'CIC_E_IoT2025']:
    url = f'https://cicresearch.ca/IOTDataset/{ds}/insert.php'
    try:
        r = s.post(url, data={
            'first_name': 'Researcher',
            'last_name': 'Evaluation',
            'email': 'nettwin.evaluation@gmail.com',
            'institution': 'Academic Lab',
            'job_title': 'Researcher',
            'country': 'Canada'
        }, verify=False, timeout=10)
        print(f"\n=== {ds} ===")
        print("POST:", r.status_code, r.text)
        r2 = s.get(f'https://cicresearch.ca/IOTDataset/{ds}/browse.php', verify=False, timeout=10)
        print("Browse status:", r2.status_code)
        for f in re.findall(r'href=["\'](.*?)["\']', r2.text):
            if 'download.php' in f or 'p=' in f:
                print("   ->", f)
    except Exception as e:
        print(f"Error {ds}:", e)
