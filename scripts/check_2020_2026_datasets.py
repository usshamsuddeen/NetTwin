import urllib.request
import json
import ssl
import re

ctx = ssl._create_unverified_context()

def check_zenodo(rec_id):
    url = f"https://zenodo.org/api/records/{rec_id}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            title = data.get('metadata', {}).get('title')
            files = data.get('files', [])
            print(f"[ZENODO {rec_id}] {title}")
            for f in files[:5]:
                print(f"   -> {f.get('key')}: {f.get('size')/1024/1024:.2f} MB ({f.get('links', {}).get('self')})")
            return files
    except Exception as e:
        print(f"[ZENODO ERR {rec_id}]: {e}")
        return []

print("=== 1. Checking Zenodo Datasets ===")
# 21_mqtt_iot: record 3863211
check_zenodo("3863211")

# 26_hikari2021: record 6462975
check_zenodo("6462975")

# Check if Edge-IIoTset is on Zenodo (search api)
try:
    url = "https://zenodo.org/api/records?q=Edge-IIoTset"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        hits = data.get('hits', {}).get('hits', [])
        print(f"\n=== Zenodo Edge-IIoTset Search ({len(hits)} hits) ===")
        for h in hits[:3]:
            print(f"   ID: {h.get('id')} | Title: {h.get('metadata', {}).get('title')}")
            for f in h.get('files', [])[:3]:
                print(f"      File: {f.get('key')} ({f.get('size')/1024/1024:.2f} MB)")
except Exception as e:
    print("Zenodo search error:", e)

# Check if ToN_IoT is on Zenodo or GitHub
try:
    url = "https://zenodo.org/api/records?q=ToN_IoT"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        hits = data.get('hits', {}).get('hits', [])
        print(f"\n=== Zenodo ToN_IoT Search ({len(hits)} hits) ===")
        for h in hits[:3]:
            print(f"   ID: {h.get('id')} | Title: {h.get('metadata', {}).get('title')}")
            for f in h.get('files', [])[:3]:
                print(f"      File: {f.get('key')} ({f.get('size')/1024/1024:.2f} MB)")
except Exception as e:
    print("Zenodo ToN search error:", e)
