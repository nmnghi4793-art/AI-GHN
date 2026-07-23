import json

with open('scratch/dashboard_cache.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
khos = d.get('data', {}).get('khoGxtData', [])

master_map = {}
for k in khos:
    id_kho = str(k.get('idKho') or '').strip()
    ten_kho = str(k.get('tenKho') or '').strip()
    link = str(k.get('linkGGM') or k.get('googleMapsLink') or '').strip()
    coords = k.get('coords')
    
    info = {"linkGGM": link, "coords": coords}
    if id_kho:
        master_map[id_kho] = info
    if ten_kho:
        master_map[ten_kho] = info

print("Generated MASTER_KHO_MAP entries:", len(master_map))
print(json.dumps(master_map, ensure_ascii=False, indent=2))
