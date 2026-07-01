"""
features.py — Parallel S1+S2 feature extraction
4 years extracted simultaneously → ~11s per parcel vs 36s sequential
"""
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from statistics import get_s2_statistics
from sar import get_s1_statistics

S2_METRICS     = ['NDVI', 'NDRE', 'EVI', 'NDWI', 'NDII']
S1_METRICS     = ['VV', 'VH', 'RVI', 'VHVV']
YEARS          = [2022, 2023, 2024, 2025]
DEKADS_PER_YEAR = 32

def get_bbox(lat, lng, buffer=0.003):
    return [lng-buffer, lat-buffer, lng+buffer, lat+buffer]

def get_polygon_bbox(coords):
    lngs = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return [min(lngs), min(lats), max(lngs), max(lats)]

def year_dates(year):
    return f"{year}-01-01T00:00:00Z", f"{year}-11-21T23:59:59Z"

def interpolate(values, target_n=32):
    if not values:
        return [0.0] * target_n
    valid_idx = [i for i,v in enumerate(values) if v is not None]
    valid_val = [values[i] for i in valid_idx]
    if len(valid_idx) < 2:
        fill = valid_val[0] if valid_val else 0.0
        return [fill] * target_n
    x_old = np.linspace(0, 1, len(values))
    x_new = np.linspace(0, 1, target_n)
    interp = np.interp(x_new,
                       [x_old[i] for i in valid_idx],
                       valid_val)
    return [round(float(v), 4) for v in interp]

def _extract_year(args):
    bbox, year = args
    start, end = year_dates(year)
    s2 = get_s2_statistics(bbox, start, end)
    s1 = get_s1_statistics(bbox, start, end)
    return year, s2, s1

def extract_features(lat=None, lng=None, polygon=None,
                     years=None, feat_cols=None):
    if years is None:
        years = YEARS

    bbox = get_polygon_bbox(polygon) if polygon else get_bbox(lat, lng)
    features = {}

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(_extract_year, [(bbox, y) for y in years]))

    for year, s2_data, s1_data in results:
        s2_by_metric = {m: [obs.get(m) for obs in s2_data] for m in S2_METRICS}
        s1_by_metric = {m: [obs.get(m) for obs in s1_data] for m in S1_METRICS}

        s2_interp = {m: interpolate(s2_by_metric[m], DEKADS_PER_YEAR) for m in S2_METRICS}
        s1_interp = {m: interpolate(s1_by_metric[m], DEKADS_PER_YEAR) for m in S1_METRICS}

        for d in range(DEKADS_PER_YEAR):
            for m in S1_METRICS:
                features[f'y{year}_d{d:02d}_{m}'] = s1_interp[m][d]
            for m in S2_METRICS:
                features[f'y{year}_d{d:02d}_{m}'] = s2_interp[m][d]

    if feat_cols:
        return {col: features.get(col, 0.0) for col in feat_cols}
    return features

if __name__ == '__main__':
    import json, time
    with open('lpis_2024_unique.json') as f:
        parcels = json.load(f)
    p = parcels[0]
    print(f"Testing: {p['crop']}")
    start = time.time()
    feats = extract_features(polygon=p['geometry']['coordinates'][0])
    elapsed = time.time() - start
    print(f"Features: {len(feats)} in {elapsed:.1f}s")
