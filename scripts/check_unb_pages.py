import urllib.request
import re
import ssl

ctx = ssl._create_unverified_context()
for page in ['ciciomt-2024.html', 'apt-iiot-2024.html', 'tabular-iot-attack-2024.html', 'cicevse-2024.html', 'iot-diad-2024.html']:

    url = f'https://www.unb.ca/cic/datasets/{page}'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            html = r.read().decode('utf-8', errors='ignore')
            links = set()
            for m in re.findall(r'href=["\'](.*?)["\']', html):
                if any(x in m for x in ['cicresearch', 'download', 'form', 'drive.google', 'mega.nz', 'kaggle']):
                    links.add(m)
            print(f"\n=== {page} ===")
            for l in sorted(links):
                print("  ->", l)
    except Exception as e:
        print(page, 'ERR:', e)
