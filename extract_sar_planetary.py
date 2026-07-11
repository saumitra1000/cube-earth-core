"""
extract_sar_planetary.py — Bulk SAR extraction for all 4865 parcels
Uses Microsoft Planetary Computer — free, no auth required
Extracts VV, VH, RVI, VHVV, DpRVIc for 2022-2025
Saves progress after each parcel — fully resumable
"""
import json, csv, os, time
import numpy as np
import planetary_computer
import pystac_client
import rasterio
from rasterio.warp import transform as warp_transform
from collections import defaultdict
from datetime import datetime

CATALOG = pystac_client.Client.open(
    "https://planetarycomputer.microsoft.com/api/stac/v1",
    modifier=planetary_computer.sign_inplace
)

OUTPUT_FILE  = 'sar_features.csv'
YEARS        = [2022, 2023, 2024, 2025]
DEKADS       = 32
SAR_METRICS  = ['VV', 'VH', 'RVI', 'VHVV', 'DpRVIc']

def compute_sar_metrics(vv_lin, vh_lin):
    eps    = 1e-10
    vv_db  = 10 * np.log10(vv_lin + eps)
    vh_db  = 10 * np.log10(vh_lin + eps)
    rvi    = (4 * vh_lin) / (vv_lin + vh_lin + eps)
    vhvv   = vh_db - vv_db
    q      = vh_lin / (vv_lin + eps)
    dprvic = 1 - ((1-q)/(1+q+eps)) * (1/(1+q+eps))
    return {
        'VV': round(float(vv_db), 4),
        'VH': round(float(vh_db), 4),
        'RVI': round(float(rvi), 4),
        'VHVV': round(float(vhvv), 4),
        'DpRVIc': round(float(dprvic), 4),
    }

def get_dekad(date_str):
    d = datetime.strptime(date_str, '%Y-%m-%d')
    return min(int((d.timetuple().tm_yday - 1) / (365/32)), 31)

def interpolate(vals_by_dekad, n=32):
    series = [None] * n
    for d, vals in vals_by_dekad.items():
        if vals:
            series[d] = round(float(np.mean(vals)), 4)
    valid_idx = [i for i, v in enumerate(series) if v is not None]
    valid_val = [series[i] for i in valid_idx]
    if not valid_idx:
        return [0.0] * n
    if len(valid_idx) == 1:
        return [valid_val[0]] * n
    interp = np.interp(np.arange(n, dtype=float),
                       np.array(valid_idx, dtype=float), valid_val)
    return [round(float(v), 4) for v in interp]

def extract_parcel_sar(lat, lng, year):
    """Extract SAR observations for one parcel one year."""
    bbox = [lng-0.005, lat-0.005, lng+0.005, lat+0.005]
    try:
        search = CATALOG.search(
            collections=["sentinel-1-rtc"],
            bbox=bbox,
            datetime=f"{year}-01-01/{year}-11-21",
            max_items=100
        )
        items = list(search.items())
    except Exception:
        return {}

    by_dekad = defaultdict(lambda: defaultdict(list))

    for item in items:
        try:
            signed = planetary_computer.sign(item)
            date   = item.datetime.strftime('%Y-%m-%d')
            dekad  = get_dekad(date)
            vv_url = signed.assets['vv'].href
            vh_url = signed.assets['vh'].href

            with rasterio.open(vv_url) as src:
                xs, ys = warp_transform('EPSG:4326', src.crs, [lng], [lat])
                row, col = src.index(xs[0], ys[0])
                win  = rasterio.windows.Window(col-1, row-1, 3, 3)
                data = src.read(1, window=win).astype(float)
                vv_lin = float(np.nanmean(data[data > 0]))

            with rasterio.open(vh_url) as src:
                row, col = src.index(xs[0], ys[0])
                win  = rasterio.windows.Window(col-1, row-1, 3, 3)
                data = src.read(1, window=win).astype(float)
                vh_lin = float(np.nanmean(data[data > 0]))

            metrics = compute_sar_metrics(vv_lin, vh_lin)
            for m, v in metrics.items():
                by_dekad[dekad][m].append(v)

        except Exception:
            continue

    return by_dekad

def build_feature_row(sp_id, crop, lat, lng):
    """Build full SAR feature vector for one parcel."""
    row = {'sp_id': sp_id, 'crop': crop, 'lat': lat, 'lng': lng}
    for year in YEARS:
        by_dekad = extract_parcel_sar(lat, lng, year)
        for metric in SAR_METRICS:
            vals = {d: by_dekad[d][metric]
                    for d in range(DEKADS)
                    if metric in by_dekad[d]}
            series = interpolate(vals, DEKADS)
            for d, v in enumerate(series):
                row[f'y{year}_d{d:02d}_{metric}'] = v
    return row

def get_done_ids():
    done = set()
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE) as f:
            for r in csv.DictReader(f):
                done.add(r.get('sp_id', ''))
    return done

if __name__ == '__main__':
    with open('lpis_2024_unique.json') as f:
        parcels = json.load(f)

    done_ids   = get_done_ids()
    remaining  = [p for p in parcels
                  if str(p.get('sp_id', '')) not in done_ids]

    print(f"Total parcels:    {len(parcels)}")
    print(f"Already done:     {len(done_ids)}")
    print(f"Remaining:        {len(remaining)}")
    print(f"Est time:         {len(remaining)*4/60:.1f} hours")

    write_hdr = not os.path.exists(OUTPUT_FILE)
    header    = None
    start     = time.time()

    for i, p in enumerate(remaining):
        sp_id = str(p.get('sp_id', i))
        lat   = p['lat']
        lng   = p['lng']
        crop  = p['crop']

        try:
            row = build_feature_row(sp_id, crop, lat, lng)
            if header is None:
                header = list(row.keys())

            with open(OUTPUT_FILE, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=header)
                if write_hdr:
                    writer.writeheader()
                    write_hdr = False
                writer.writerow(row)

            elapsed = time.time() - start
            eta_h   = (len(remaining)-i-1) * (elapsed/(i+1)) / 3600
            print(f"[{i+1}/{len(remaining)}] ✅ {crop:<20} | ETA {eta_h:.1f}h")

        except Exception as e:
            print(f"[{i+1}/{len(remaining)}] ❌ {sp_id}: {e}")

    print(f"\nDone ✅ Saved to {OUTPUT_FILE}")
