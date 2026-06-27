"""
features.py — Assemble S1+S2 features into model input vector
Matches exact column order from feature_columns_v2.json
"""
import json
import numpy as np
from statistics import get_s2_statistics
from sar import get_s1_statistics

S2_METRICS = ['NDVI', 'NDRE', 'EVI', 'NDWI', 'NDII']
S1_METRICS = ['VV', 'VH', 'RVI', 'VHVV']
YEARS = [2022, 2023, 2024, 2025]
DEKADS_PER_YEAR = 33

def get_year_bbox(lat: float, lng: float, buffer: float = 0.03) -> list:
    """Create bounding box around a point."""
    return [lng - buffer, lat - buffer, lng + buffer, lat + buffer]

def year_to_dates(year: int):
    """Get start and end dates for a growing year."""
    return f"{year}-01-01T00:00:00Z", f"{year}-12-31T23:59:59Z"

def interpolate(values: list, target_n: int = 33) -> list:
    """Interpolate/resample to exactly target_n dekads."""
    if not values:
        return [None] * target_n
    valid_idx = [i for i, v in enumerate(values) if v is not None]
    valid_val = [values[i] for i in valid_idx]
    if len(valid_idx) < 2:
        fill = valid_val[0] if valid_val else 0.4
        return [fill] * target_n
    x_old = np.linspace(0, 1, len(values))
    x_new = np.linspace(0, 1, target_n)
    interpolated = np.interp(x_new,
                             [x_old[i] for i in valid_idx],
                             valid_val)
    return [round(float(v), 4) for v in interpolated]

def extract_features(lat: float, lng: float,
                     years: list = None,
                     feat_cols: list = None) -> dict:
    """
    Extract full S1+S2 feature vector for a location.
    Returns dict of {col_name: value} matching feature_columns_v2.json
    """
    if years is None:
        years = YEARS

    bbox = get_year_bbox(lat, lng)
    features = {}

    for year in years:
        start, end = year_to_dates(year)
        print(f"  Extracting {year}...")

        # S2 extraction
        s2_data = get_s2_statistics(bbox, start, end)
        s2_by_metric = {m: [] for m in S2_METRICS}
        for obs in s2_data:
            for m in S2_METRICS:
                s2_by_metric[m].append(obs.get(m))

        for metric in S2_METRICS:
            vals = interpolate(s2_by_metric[metric], DEKADS_PER_YEAR)
            for i, v in enumerate(vals):
                col = f'y{year}_d{i:02d}_{metric}'
                features[col] = v if v is not None else 0.4

        # S1 extraction
        s1_data = get_s1_statistics(bbox, start, end)
        s1_by_metric = {m: [] for m in S1_METRICS}
        for obs in s1_data:
            for m in S1_METRICS:
                s1_by_metric[m].append(obs.get(m))

        for metric in S1_METRICS:
            vals = interpolate(s1_by_metric[metric], DEKADS_PER_YEAR)
            for i, v in enumerate(vals):
                col = f'y{year}_d{i:02d}_{metric}'
                features[col] = v if v is not None else 0.0

    # If feat_cols provided, align to exact order
    if feat_cols:
        aligned = {}
        for col in feat_cols:
            aligned[col] = features.get(col, 0.4)
        return aligned

    return features

if __name__ == '__main__':
    print("Extracting features for Carlow parcel (52.84, -6.93)...")
    print("Using 2024 only for quick test...\n")

    feats = extract_features(52.84, -6.93, years=[2024])

    s2_cols = [k for k in feats if k.endswith('NDVI')]
    s1_cols = [k for k in feats if k.endswith('VV')]

    print(f"\nTotal features: {len(feats)}")
    print(f"S2 NDVI cols:   {len(s2_cols)}")
    print(f"S1 VV cols:     {len(s1_cols)}")
    print(f"\nSample NDVI trajectory (2024):")
    for col in sorted(s2_cols)[:6]:
        print(f"  {col}: {feats[col]}")
    print(f"\nSample VV trajectory (2024):")
    for col in sorted(s1_cols)[:6]:
        print(f"  {col}: {feats[col]}")
