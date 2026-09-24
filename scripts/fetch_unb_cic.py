import requests

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Referer': 'http://cicresearch.ca/IOTDataset/CIC_IOT_Dataset2023/'
})

form_data = {
    'first_name': 'Researcher',
    'last_name': 'Evaluation',
    'email': 'nettwin.benchmark@gmail.com',
    'institution': 'Academic Research Lab',
    'job_title': 'Researcher',
    'country': 'Canada'
}

resp = session.post('http://cicresearch.ca/IOTDataset/CIC_IOT_Dataset2023/insert.php', data=form_data)
print("Status:", resp.status_code)
print("Text:", resp.text)

if resp.status_code == 200:
    browse_resp = session.get('http://cicresearch.ca/IOTDataset/CIC_IOT_Dataset2023/browse.php')
    print("Browse Status:", browse_resp.status_code)
    print("Browse HTML:\n", browse_resp.text[:3000])


try:
    with opener.open(req) as resp:
        content = resp.read().decode('utf-8')
        print("Insert Response:", content)
        
        # Now visit browse.php
        browse_url = 'http://cicresearch.ca/IOTDataset/CIC_IOT_Dataset2023/browse.php'
        req2 = urllib.request.Request(
            browse_url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'Referer': 'http://cicresearch.ca/IOTDataset/CIC_IOT_Dataset2023/'
            }
        )
        with opener.open(req2) as resp2:
            html = resp2.read().decode('utf-8')
            print("Browse HTML (first 2000 chars):")
            print(html[:2000])
except Exception as e:
    print("Error:", e)
