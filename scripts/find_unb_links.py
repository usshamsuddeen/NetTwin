import urllib.request, re, ssl

ctx = ssl._create_unverified_context()
req = urllib.request.Request('https://www.unb.ca/cic/datasets/iotdataset-2023.html', headers={'User-Agent': 'Mozilla/5.0'})
url = 'http://cicresearch.ca/IOTDataset/CIC_IOT_Dataset2023/'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req, context=ctx, timeout=15) as r:
        html = r.read().decode('utf-8', errors='ignore')
        for m in re.findall(r'href=["\'](.*?)["\']', html):
            print("SERVER FILE:", m)
except Exception as e:
    print("Error:", e)

