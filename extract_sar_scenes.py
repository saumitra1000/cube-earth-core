
import json, csv, os, time
import numpy as np
import planetary_computer
import pystac_client
import rasterio
from rasterio.warp import transform as warp_transform
from shapely.geometry import shape, box as shapely_box
from collections import defaultdict
from datetime import datetime

OUTPUT_FILE   = 'sar_scene_features.csv'
PROGRESS_DIR  = 'sar_progress'
YEARS         = [2025]
DEKADS        = 32
SAR_METRICS   = ['VV', 'VH', 'RVI', 'VHVV', 'DpRVIc']
PARCEL_BBOX   = [-7.3, 52.2, -6.1, 53.1]
PARCEL_EXTENT = shapely_box(*PARCEL_BBOX)

MONTHS = [
    ('01-01','01-31'), ('02-01','02-28'), ('03-01','03-31'),
    ('04-01','04-30'), ('05-01','05-31'), ('06-01','06-30'),
    ('07-01','07-31'), ('08-01','08-31'), ('09-01','09-30'),
    ('10-01','10-31'), ('11-01','11-21'),
]

os.makedirs(PROGRESS_DIR, exist_ok=True)

def compute_metrics(vv_lin, vh_lin):
    eps    = 1e-10
    vv_db  = 10 * np.log10(vv_lin + eps)
    vh_db  = 10 * np.log10(vh_lin + eps)
    rvi    = (4 * vh_lin) / (vv_lin + vh_lin + eps)
    vhvv   = vh_db - vv_db
    q      = vh_lin / (vv_lin + eps)
    dprvic = 1 - ((1-q)/(1+q+eps)) * (1/(1+q+eps))
    return {'VV': round(float(vv_db),4), 'VH': round(float(vh_db),4),
            'RVI': round(float(rvi),4), 'VHVV': round(float(vhvv),4),
            'DpRVIc': round(float(dprvic),4)}

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
    if not valid_idx: return [0.0] * n
    if len(valid_idx) == 1: return [valid_val[0]] * n
    return [round(float(v), 4) for v in
            np.interp(np.arange(n, dtype=float),
                      np.array(valid_idx, dtype=float), valid_val)]

def get_catalog():
    return pystac_client.Client.open(
        'https://planetarycomputer.microsoft.com/api/stac/v1',
        modifier=planetary_computer.sign_inplace)

def month_done(year, month):
    return os.path.exists(
        os.path.join(PROGRESS_DIR, str(year) + '_' + month + '_done.txt'))

def process_month(year, m_start, m_end, ids, lats, lngs, out_csv):
    month_key = str(year) + '-' + m_start[:2]
    done_file = os.path.join(PROGRESS_DIR,
                             str(year) + '_' + m_start[:2] + '_done.txt')

    if os.path.exists(done_file):
        print('  Skipping ' + month_key + ' (done)', flush=True)
        return

    catalog  = get_catalog()
    start    = str(year) + '-' + m_start
    end      = str(year) + '-' + m_end
    search   = catalog.search(
        collections=['sentinel-1-rtc'],
        bbox=PARCEL_BBOX,
        datetime=start + '/' + end
    )
    items = [i for i in search.items()
             if shape(i.geometry).intersects(PARCEL_EXTENT)]
    print('  ' + month_key + ': ' + str(len(items)) + ' scenes', flush=True)

    if not items:
        open(done_file, 'w').close()
        return

    write_hdr  = not os.path.exists(out_csv)
    fieldnames = ['scene_id', 'date', 'dekad', 'pid'] + SAR_METRICS
    count      = 0

    for i, item in enumerate(items):
        if i > 0 and i % 20 == 0:
            catalog = get_catalog()

        try:
            signed = planetary_computer.sign(item)
            date_s = item.datetime.strftime('%Y-%m-%d')
            dekad  = get_dekad(date_s)
            scene_id = item.id

            with rasterio.open(signed.assets['vv'].href) as src:
                xs, ys = warp_transform('EPSG:4326', src.crs, lngs, lats)
                vv_vals = []
                for x, y in zip(xs, ys):
                    try:
                        r, c  = src.index(x, y)
                        win   = rasterio.windows.Window(c-1, r-1, 3, 3)
                        d2    = src.read(1, window=win).astype(float)
                        valid = d2[d2 > 0]
                        vv_vals.append(float(np.nanmean(valid)) if len(valid) > 0 else None)
                    except:
                        vv_vals.append(None)

            with rasterio.open(signed.assets['vh'].href) as src:
                vh_vals = []
                for x, y in zip(xs, ys):
                    try:
                        r, c  = src.index(x, y)
                        win   = rasterio.windows.Window(c-1, r-1, 3, 3)
                        d2    = src.read(1, window=win).astype(float)
                        valid = d2[d2 > 0]
                        vh_vals.append(float(np.nanmean(valid)) if len(valid) > 0 else None)
                    except:
                        vh_vals.append(None)

            rows_out = []
            for pid, vv, vh in zip(ids, vv_vals, vh_vals):
                if vv and vh and not np.isnan(vv) and not np.isnan(vh):
                    m = compute_metrics(vv, vh)
                    rows_out.append({'scene_id': scene_id, 'date': date_s,
                                     'dekad': dekad, 'pid': pid, **m})

            if rows_out:
                with open(out_csv, 'a', newline='') as f:
                    w = csv.DictWriter(f, fieldnames=fieldnames)
                    if write_hdr:
                        w.writeheader()
                        write_hdr = False
                    w.writerows(rows_out)
                count += 1

        except Exception as e:
            if '403' not in str(e):
                print('    Error: ' + str(e))
            continue

    open(done_file, 'w').close()
    print('  ' + month_key + ': ' + str(count) + ' scenes with valid data ✅', flush=True)

def build_features(ids, crops, lats, lngs):
    print('Building feature vectors...')
    data = {pid: {yr: {d: {m: [] for m in SAR_METRICS}
                        for d in range(DEKADS)}
                  for yr in YEARS}
            for pid in ids}

    for year in YEARS:
        csv_path = os.path.join(PROGRESS_DIR, str(year) + '_raw.csv')
        if not os.path.exists(csv_path):
            continue
        with open(csv_path) as f:
            for row in csv.DictReader(f):
                pid   = row['pid']
                dekad = int(row['dekad'])
                if pid in data:
                    for m in SAR_METRICS:
                        if row.get(m):
                            data[pid][year][dekad][m].append(float(row[m]))

    rows = []
    for i, pid in enumerate(ids):
        row = {'sp_id': pid, 'crop': crops[i], 'lat': lats[i], 'lng': lngs[i]}
        for year in YEARS:
            for metric in SAR_METRICS:
                vals = {d: data[pid][year][d][metric]
                        for d in range(DEKADS)
                        if data[pid][year][d][metric]}
                series = interpolate(vals, DEKADS)
                for d, v in enumerate(series):
                    row['y' + str(year) + '_d' + str(d).zfill(2) + '_' + metric] = v
        rows.append(row)

    header = list(rows[0].keys())
    with open(OUTPUT_FILE, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    print('Saved ' + str(len(rows)) + ' parcels to ' + OUTPUT_FILE + ' ✅')

if __name__ == '__main__':
    with open('lpis_2024_unique.json') as f:
        parcels = json.load(f)
    ids   = [str(p.get('sp_id', i)) for i, p in enumerate(parcels)]
    lats  = [p['lat'] for p in parcels]
    lngs  = [p['lng'] for p in parcels]
    crops = [p['crop'] for p in parcels]
    print('Parcels: ' + str(len(parcels)))

    for year in YEARS:
        out_csv = os.path.join(PROGRESS_DIR, str(year) + '_raw.csv')
        print('Processing ' + str(year) + '...')
        for m_start, m_end in MONTHS:
            process_month(year, m_start, m_end, ids, lats, lngs, out_csv)

    build_features(ids, crops, lats, lngs)
    print('Done ✅')
