"""
enrich_features.py — Add elevation + soil to HLS features
Saves progress every row — fully resumable if interrupted
"""
import csv, json, os
from elevation import get_elevation_features
from soil import get_soil_features

INPUT  = 'hls_features.csv'
OUTPUT = 'hls_features_enriched.csv'

print("Loading HLS features...")
with open(INPUT) as f:
    reader = csv.DictReader(f)
    rows   = list(reader)
    header = list(rows[0].keys())

done_ids = set()
if os.path.exists(OUTPUT):
    with open(OUTPUT) as f:
        for row in csv.DictReader(f):
            done_ids.add(row.get('sp_id',''))
    print(f"Already done: {len(done_ids)} — resuming...")

elev_cols = ['elevation_m', 'slope_deg', 'elevation_std']
soil_cols = ['soil_clay', 'soil_sand', 'soil_soc', 'soil_phh2o', 'soil_nitrogen']
new_cols  = elev_cols + soil_cols
full_hdr  = header + new_cols
write_hdr = not os.path.exists(OUTPUT)

with open(OUTPUT, 'a', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=full_hdr)
    if write_hdr:
        writer.writeheader()

    for i, row in enumerate(rows):
        sp_id = row.get('sp_id', str(i))
        if sp_id in done_ids:
            continue
        try:
            lat = float(row['lat'])
            lng = float(row['lng'])
            row.update(get_elevation_features(lat, lng))
            row.update(get_soil_features(lat, lng))
        except:
            for c in new_cols:
                row[c] = 0
        writer.writerow(row)
        f.flush()
        if i % 100 == 0:
            print(f"  {i+1}/{len(rows)} ({(i+1)/len(rows)*100:.0f}%)")

print("Done ✅")
