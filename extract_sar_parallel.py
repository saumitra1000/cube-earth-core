
import json, csv, os, time, threading
import numpy as np
import planetary_computer
import pystac_client
import rasterio
from rasterio.warp import transform as warp_transform
from collections import defaultdict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

OUTPUT_FILE = "sar_features.csv"
YEARS       = [2022, 2023, 2024, 2025]
DEKADS      = 32
SAR_METRICS = ["VV", "VH", "RVI", "VHVV", "DpRVIc"]
N_WORKERS   = 8
write_lock  = threading.Lock()

def compute_sar_metrics(vv_lin, vh_lin):
    eps = 1e-10
    vv_db  = 10 * np.log10(vv_lin + eps)
    vh_db  = 10 * np.log10(vh_lin + eps)
    rvi    = (4 * vh_lin) / (vv_lin + vh_lin + eps)
    vhvv   = vh_db - vv_db
    q      = vh_lin / (vv_lin + eps)
    dprvic = 1 - ((1-q)/(1+q+eps)) * (1/(1+q+eps))
    return {"VV": round(float(vv_db),4), "VH": round(float(vh_db),4),
            "RVI": round(float(rvi),4), "VHVV": round(float(vhvv),4),
            "DpRVIc": round(float(dprvic),4)}

def get_dekad(date_str):
    d = datetime.strptime(date_str, "%Y-%m-%d")
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

def extract_year(lat, lng, year):
    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace)
    bbox = [lng-0.005, lat-0.005, lng+0.005, lat+0.005]
    try:
        items = list(catalog.search(
            collections=["sentinel-1-rtc"], bbox=bbox,
            datetime=f"{year}-01-01/{year}-11-21",
            max_items=100).items())
    except:
        return defaultdict(lambda: defaultdict(list))
    by_dekad = defaultdict(lambda: defaultdict(list))
    for item in items:
        try:
            signed = planetary_computer.sign(item)
            dekad  = get_dekad(item.datetime.strftime("%Y-%m-%d"))
            with rasterio.open(signed.assets["vv"].href) as src:
                xs, ys = warp_transform("EPSG:4326", src.crs, [lng], [lat])
                r, c   = src.index(xs[0], ys[0])
                win    = rasterio.windows.Window(c-1, r-1, 3, 3)
                data   = src.read(1, window=win).astype(float)
                vv_lin = float(np.nanmean(data[data > 0]))
            with rasterio.open(signed.assets["vh"].href) as src:
                r, c   = src.index(xs[0], ys[0])
                win    = rasterio.windows.Window(c-1, r-1, 3, 3)
                data   = src.read(1, window=win).astype(float)
                vh_lin = float(np.nanmean(data[data > 0]))
            for m, v in compute_sar_metrics(vv_lin, vh_lin).items():
                by_dekad[dekad][m].append(v)
        except:
            continue
    return by_dekad

def process_parcel(args):
    idx, total, p, header = args
    sp_id = str(p.get("sp_id", idx))
    lat, lng, crop = p["lat"], p["lng"], p["crop"]
    try:
        row = {"sp_id": sp_id, "crop": crop, "lat": lat, "lng": lng}
        for year in YEARS:
            by_dekad = extract_year(lat, lng, year)
            for metric in SAR_METRICS:
                vals = {d: by_dekad[d][metric] for d in range(DEKADS)
                        if metric in by_dekad[d]}
                for d, v in enumerate(interpolate(vals, DEKADS)):
                    row[f"y{year}_d{d:02d}_{metric}"] = v
        with write_lock:
            write_hdr = not os.path.exists(OUTPUT_FILE)
            with open(OUTPUT_FILE, "a", newline="") as f:
                w = csv.DictWriter(f, fieldnames=header)
                if write_hdr: w.writeheader()
                w.writerow(row)
            print(f"[{idx+1}/{total}] ✅ {crop}", flush=True)
        return True
    except Exception as e:
        print(f"[{idx+1}/{total}] ❌ {sp_id}: {e}", flush=True)
        return False

if __name__ == "__main__":
    with open("lpis_2024_unique.json") as f:
        parcels = json.load(f)
    done_ids = set()
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE) as f:
            for r in csv.DictReader(f):
                done_ids.add(r.get("sp_id",""))
    remaining = [p for p in parcels
                 if str(p.get("sp_id","")) not in done_ids]
    print(f"Total: {len(parcels)} | Done: {len(done_ids)} | Remaining: {len(remaining)}")
    sample = {"sp_id":"","crop":"","lat":"","lng":""}
    for year in YEARS:
        for d in range(DEKADS):
            for m in SAR_METRICS:
                sample[f"y{year}_d{d:02d}_{m}"] = 0
    header = list(sample.keys())
    args = [(i, len(remaining), p, header) for i, p in enumerate(remaining)]
    start = time.time()
    done_count = 0
    with ThreadPoolExecutor(max_workers=N_WORKERS) as executor:
        for future in as_completed(
                {executor.submit(process_parcel, a): a for a in args}):
            if future.result():
                done_count += 1
                elapsed = time.time() - start
                rate    = done_count / elapsed * 60
                eta_h   = (len(remaining)-done_count) / (rate+0.001) / 60
                print(f"  {done_count}/{len(remaining)} | {rate:.1f}/min | ETA {eta_h:.1f}h",
                      flush=True)
    print("Done ✅")
