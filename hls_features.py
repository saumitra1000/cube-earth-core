"""
hls_features.py — Build training features from HLS data
Full Fmask quality screen: Cloud, Shadow, Water, Snow, High Aerosol
Computes: NDVI, EVI, NDWI, NDRE, NDII per parcel per dekad
Matches training pipeline format: 32 dekads × 4 years × 5 metrics
"""
import csv, json
import numpy as np
from pathlib import Path
from collections import defaultdict
from datetime import datetime

INPUT_FILE  = 'hls_all_parcels.csv'
OUTPUT_FILE = 'hls_features.csv'

YEARS          = [2022, 2023, 2024, 2025]
DEKADS_PER_YEAR = 32
METRICS        = ['NDVI', 'EVI', 'NDWI', 'NDRE', 'NDII']

def is_valid(row):
    """Full Fmask quality screen."""
    if row.get('HLSS30_020_Fmask_Cloud_Description') != 'No':
        return False
    if row.get('HLSS30_020_Fmask_Cloud_shadow_Description') != 'No':
        return False
    if row.get('HLSS30_020_Fmask_Water_Description') != 'No':
        return False
    if row.get('HLSS30_020_Fmask_Snow/ice_Description') != 'No':
        return False
    if row.get('HLSS30_020_Fmask_Aerosol_level_Description') == 'High aerosol':
        return False
    return True

def get_dekad(date_str):
    """Convert date to dekad index (0-31) within year."""
    d = datetime.strptime(date_str, '%Y-%m-%d')
    day_of_year = d.timetuple().tm_yday
    dekad = min(int((day_of_year - 1) / (365/32)), 31)
    return dekad

def compute_metrics(row):
    """Compute all 5 optical metrics from raw bands."""
    eps = 1e-8
    try:
        b05 = float(row['HLSS30_020_B05'])
        b08 = float(row['HLSS30_020_B08'])
        b11 = float(row['HLSS30_020_B11'])

        # Fill value check
        if b05 < 0 or b08 < 0 or b11 < 0:
            return None
        if b05 > 1 or b08 > 1 or b11 > 1:
            return None

        ndvi_raw = row.get('HLSS30_VI_NDVI', '')
        evi_raw  = row.get('HLSS30_VI_EVI', '')
        ndwi_raw = row.get('HLSS30_VI_NDWI', '')

        ndvi = float(ndvi_raw) if ndvi_raw and float(ndvi_raw) > -9000 else None
        evi  = float(evi_raw)  if evi_raw  and float(evi_raw)  > -9000 else None
        ndwi = float(ndwi_raw) if ndwi_raw and float(ndwi_raw) > -9000 else None

        ndre = (b08 - b05) / (b08 + b05 + eps)
        ndii = (b08 - b11) / (b08 + b11 + eps)

        return {
            'NDVI': round(ndvi, 4) if ndvi is not None else None,
            'EVI':  round(evi,  4) if evi  is not None else None,
            'NDWI': round(ndwi, 4) if ndwi is not None else None,
            'NDRE': round(ndre, 4),
            'NDII': round(ndii, 4),
        }
    except (ValueError, TypeError):
        return None

def interpolate(values_by_dekad, n=32):
    """Interpolate sparse dekad observations to full 32-dekad series."""
    series = [None] * n
    for dekad, vals in values_by_dekad.items():
        if vals:
            series[dekad] = round(np.nanmean(vals), 4)

    # Linear interpolation for gaps
    valid_idx = [i for i, v in enumerate(series) if v is not None]
    valid_val = [series[i] for i in valid_idx]

    if len(valid_idx) == 0:
        return [0.0] * n
    if len(valid_idx) == 1:
        return [valid_val[0]] * n

    x_old = np.array(valid_idx, dtype=float)
    x_new = np.arange(n, dtype=float)
    interp = np.interp(x_new, x_old, valid_val)
    return [round(float(v), 4) for v in interp]

def build_features():
    print("Reading HLS data and building features...")
    print("Applying full Fmask quality screen...")

    # Structure: parcel_id → year → dekad → metric → [values]
    data = defaultdict(lambda: defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    ))
    parcel_meta = {}

    total = 0
    valid = 0

    with open(INPUT_FILE) as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            if total % 200000 == 0:
                print(f"  Processed {total:,} rows, {valid:,} valid ({valid/total*100:.1f}%)")

            if not is_valid(row):
                continue

            metrics = compute_metrics(row)
            if metrics is None:
                continue

            valid += 1
            pid  = row['ID']
            year = int(row['Date'][:4])
            dekad = get_dekad(row['Date'])

            if pid not in parcel_meta:
                parcel_meta[pid] = {
                    'crop': row['Category'],
                    'lat':  row['Latitude'],
                    'lng':  row['Longitude']
                }

            for metric, value in metrics.items():
                if value is not None:
                    data[pid][year][dekad][metric].append(value)

    print(f"\nTotal rows:  {total:,}")
    print(f"Valid rows:  {valid:,} ({valid/total*100:.1f}%)")
    print(f"Parcels:     {len(data)}")

    # Build feature vectors
    print("\nBuilding feature vectors...")
    rows_out = []
    header = None

    for pid, year_data in data.items():
        meta = parcel_meta[pid]
        row_out = {
            'sp_id': pid,
            'crop':  meta['crop'],
            'lat':   meta['lat'],
            'lng':   meta['lng'],
        }

        for year in YEARS:
            for metric in METRICS:
                dekad_vals = {
                    d: year_data[year][d][metric]
                    for d in range(DEKADS_PER_YEAR)
                    if metric in year_data[year][d]
                }
                series = interpolate(dekad_vals, DEKADS_PER_YEAR)
                for d, val in enumerate(series):
                    row_out[f'y{year}_d{d:02d}_{metric}'] = val

        rows_out.append(row_out)
        if header is None:
            header = list(row_out.keys())

    print(f"Feature vectors built: {len(rows_out)}")
    print(f"Features per parcel:   {len(header) - 4}")

    with open(OUTPUT_FILE, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows_out)

    print(f"\nSaved: {OUTPUT_FILE} ✅")
    return rows_out

if __name__ == '__main__':
    build_features()
