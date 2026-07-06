
import json, csv, os, time
import numpy as np
import planetary_computer
import pystac_client
import rasterio
from rasterio.warp import transform as warp_transform
from collections import defaultdict
from datetime import datetime, date
import pickle

OUTPUT_FILE  = 'sar_scene_features.csv'
PROGRESS_FILE = 'sar_progress.pkl'
YEARS        = [2022, 2023, 2024, 2025]
DEKADS       = 32
SAR_METRICS  = ['VV', 'VH', 'RVI', 'VHVV', 'DpRVIc']
IRELAND_BBOX = [-10.5, 51.0, -5.0, 55.5]

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

def get_fresh_catalog():
    return pystac_client.Client.open(
        'https://planetarycomputer.microsoft.com/api/stac/v1',
        modifier=planetary_computer.sign_inplace)

def extract_all(parcels):
    ids   = [str(p.get('sp_id', i)) for i, p in enumerate(parcels)]
    lats  = [p['lat'] for p in parcels]
    lngs  = [p['lng'] for p in parcels]
    crops = [p['crop'] for p in parcels]

    # Load existing progress
    if os.path.exists(PROGRESS_FILE):
        print('Resuming from saved progress...')
        with open(PROGRESS_FILE, 'rb') as f:
            data = pickle.load(f)
        completed_years = data.get('completed_years', [])
        scene_data = data.get('scene_data', {})
    else:
        completed_years = []
        scene_data = {pid: {yr: {d: {m: [] for m in SAR_METRICS}
                            for d in range(DEKADS)}
                          for yr in YEARS}
                    for pid in ids}

    print('Already completed years: ' + str(completed_years))

    for year in YEARS:
        if year in completed_years:
            print('Skipping ' + str(year) + ' (already done)')
            continue

        print('Processing ' + str(year) + '...')
        catalog = get_fresh_catalog()
        search  = catalog.search(
            collections=['sentinel-1-rtc'],
            bbox=IRELAND_BBOX,
            datetime=str(year) + '-01-01/' + str(year) + '-11-21',
            max_items=500
        )
        items = list(search.items())
        print('  Found ' + str(len(items)) + ' scenes')

        for i, item in enumerate(items):
            # Refresh catalog every 50 scenes to avoid token expiry
            if i > 0 and i % 50 == 0:
                print('  Refreshing token at scene ' + str(i) + '...')
                catalog = get_fresh_catalog()

            try:
                signed = planetary_computer.sign(item)
                date_s = item.datetime.strftime('%Y-%m-%d')
                dekad  = get_dekad(date_s)

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

                for pid, vv, vh in zip(ids, vv_vals, vh_vals):
                    if vv and vh and not np.isnan(vv) and not np.isnan(vh):
                        metrics = compute_metrics(vv, vh)
                        for m, v in metrics.items():
                            scene_data[pid][year][dekad][m].append(v)

                if (i+1) % 50 == 0:
                    with open(PROGRESS_FILE, 'wb') as pf:
                        import pickle
                        pickle.dump({'completed_years': completed_years,
                                    'scene_data': scene_data}, pf)
                    print('  Progress saved at scene ' + str(i+1), flush=True)
                if (i+1) % 20 == 0:
                    print('  Scene ' + str(i+1) + '/' + str(len(items)) + ': ' + date_s, flush=True)

            except Exception as e:
                print('  Scene error: ' + str(e))
                continue

        # Save progress after each year
        completed_years.append(year)
        with open(PROGRESS_FILE, 'wb') as f:
            pickle.dump({'completed_years': completed_years,
                        'scene_data': scene_data}, f)
        print('  Year ' + str(year) + ' complete and saved ✅')

    print('Building feature vectors...')
    rows = []
    for i, pid in enumerate(ids):
        row = {'sp_id': pid, 'crop': crops[i],
               'lat': lats[i], 'lng': lngs[i]}
        for year in YEARS:
            for metric in SAR_METRICS:
                vals = {d: scene_data[pid][year][d][metric]
                        for d in range(DEKADS)
                        if scene_data[pid][year][d][metric]}
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
    return rows

if __name__ == '__main__':
    with open('lpis_2024_unique.json') as f:
        parcels = json.load(f)
    print('Parcels: ' + str(len(parcels)))
    start = time.time()
    extract_all(parcels)
    print('Total time: ' + str(round((time.time()-start)/60, 1)) + ' minutes')
