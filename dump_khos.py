import json

with open('scratch/dashboard_cache.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
khos = d.get('data', {}).get('khoGxtData', [])
print(f"Total in cache: {len(khos)}")
for k in khos:
    print(f"{k.get('idKho')} | {k.get('tenKho')} | {k.get('linkGGM')} | {k.get('coords')}")
