import requests
import re
import sys
import warnings
from urllib3.exceptions import InsecureRequestWarning
warnings.simplefilter('ignore', InsecureRequestWarning)

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0'})
r = s.post('https://cicresearch.ca/IOTDataset/CIC_IOT_Dataset2023/insert.php', data={
    'first_name': 'Researcher',
    'last_name': 'Evaluation',
    'email': 'nettwin.evaluation@gmail.com',
    'institution': 'Academic Lab',
    'job_title': 'Researcher',
    'country': 'Canada'
}, verify=False)

r_sub = s.get('https://cicresearch.ca/IOTDataset/CIC_IOT_Dataset2023/browse.php?p=CSV%2FMERGED_CSV', verify=False)
for href in re.findall(r'href=["\'](.*?)["\']', r_sub.text):
    if 'download.php' in href or 'file=' in href:
        print("MERGED FILE:", href)



