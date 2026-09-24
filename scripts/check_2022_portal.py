import requests
import re
import warnings
from urllib3.exceptions import InsecureRequestWarning
warnings.simplefilter('ignore', InsecureRequestWarning)

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0'})
s.post('https://cicresearch.ca/IOTDataset/CIC-BCCC-NRC-TabularIoTAttacks-2024/insert.php', data={'first_name': 'Test', 'last_name': 'User', 'email': 'test@example.com', 'institution': 'Test', 'job_title': 'Test', 'country': 'Canada'}, verify=False)
r = s.get('https://cicresearch.ca/IOTDataset/CIC-BCCC-NRC-TabularIoTAttacks-2024/browse.php?p=CIC-BCCC-NRC-IoT-2022', verify=False)
for f in re.findall(r'href=["\'](.*?)["\']', r.text):
    if 'download.php' in f or 'p=' in f:
        print("2022:", f)
