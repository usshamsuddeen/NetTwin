import requests
import re
import warnings
from urllib3.exceptions import InsecureRequestWarning
warnings.simplefilter('ignore', InsecureRequestWarning)

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0'})

# 2022 CSV
s.post('https://cicresearch.ca/IOTDataset/CIC_IOT_Dataset2022/insert.php', data={'first_name': 'Test', 'last_name': 'User', 'email': 'test@example.com', 'institution': 'Test', 'job_title': 'Test', 'country': 'Canada'}, verify=False)
r = s.get('https://cicresearch.ca/IOTDataset/CIC_IOT_Dataset2022/browse.php?p=CSV%2FCSV+files%2FCIC+Device+Type%2FCamera', verify=False)
print("=== 2022 Camera Files ===")
for f in re.findall(r'href=["\'](.*?)["\']', r.text):
    if 'download.php' in f or 'file=' in f:
        print("  2022 Camera ->", f)



# 2025 Processed
s.post('https://cicresearch.ca/IOTDataset/Datasense/insert.php', data={'first_name': 'Test', 'last_name': 'User', 'email': 'test@example.com', 'institution': 'Test', 'job_title': 'Test', 'country': 'Canada'}, verify=False)
r2 = s.get('https://cicresearch.ca/IOTDataset/Datasense/browse.php?p=dataset%2Fprocessed_files', verify=False)
print("\n=== 2025 Processed Files ===")
for f in re.findall(r'href=["\'](.*?)["\']', r2.text):
    if 'download.php' in f or 'file=' in f or 'p=' in f:
        print("  2025 ->", f)
