"""
Reads readme.md, cheatsheet.md and lists benchmarking_IDS_datasets from ctinnil/CY0P5_ML_Datasets.
"""
import urllib.request
import json
import re

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="replace")

# 1. Check readme.md
readme = fetch("https://raw.githubusercontent.com/ctinnil/CY0P5_ML_Datasets/main/readme.md")
print(f"=== readme.md ({len(readme)} chars) ===")
# Find dataset download links in readme
links = re.findall(r'\[([^\]]+)\]\((http[^\)]+)\)', readme)
for text, link in links:
    if any(k in link.lower() for k in ["dataset", "download", "drive", "kaggle", "zip", "tar", "csv", "data", "box.com", "dropbox", "s3"]):
        print(f"  Link: [{text}] -> {link}")

# 2. Check cheatsheet.md
cheatsheet = fetch("https://raw.githubusercontent.com/ctinnil/CY0P5_ML_Datasets/main/cheatsheet.md")
print(f"\n=== cheatsheet.md ({len(cheatsheet)} chars) ===")
links_cs = re.findall(r'\[([^\]]+)\]\((http[^\)]+)\)', cheatsheet)
for text, link in links_cs[:25]:
    print(f"  Link: [{text}] -> {link}")

# 3. Check benchmarking_IDS_datasets contents
url_dir = "https://api.github.com/repos/ctinnil/CY0P5_ML_Datasets/contents/benchmarking_IDS_datasets"
req = urllib.request.Request(url_dir, headers={"User-Agent": "Mozilla/5.0"})
try:
    items = json.loads(urllib.request.urlopen(req, timeout=10).read().decode("utf-8"))
    print(f"\n=== benchmarking_IDS_datasets ({len(items)} items) ===")
    for it in items:
        print(f"  {it.get('name')} ({it.get('type')}) -> {it.get('download_url')}")
except Exception as e:
    print("benchmarking_IDS_datasets error:", e)
