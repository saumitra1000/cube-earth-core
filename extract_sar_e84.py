import sys, json, csv, os, time
sys.path.insert(0, "/tmp/crop-trajectory")
import pystac_client, rasterio, numpy as np
from rasterio.transform import from_gcps, rowcol
from shapely.geometry import shape, box
from datetime import datetime

OUTPUT_DIR  = "sar_progress_e84"
OUTPUT_FILE = "sar_e84_features.csv"
YEARS       = [2022, 2023, 2024, 2025]
DEKADS      = 32
PARCEL_BOX  = box(-7.3, 52.2, -6.1, 53.1)

os.makedirs(OUTPUT_DIR, exist_ok=True)

def s3_to_https(url):
    if url.startswith("s3://"):
        parts = url[5:].split("/", 1)
        return f"https://{parts[0]}.s3.amazonaws.com/{parts[1]}"
    return url

def get_dekad(date_str):
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return min(int((d.timetuple().tm_yday - 1) / (365/32)), 31)

def compute_metrics(vv_lin, vh_lin):
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

def read_scene(url, lats, lngs):
    try:
        with rasterio.open(url) as src:
            gcps, _ = src.gcps
            if not gcps: return [None] * len(lats)
            transform = from_gcps(gcps)
            rows, cols = rowcol(transform, lngs, lats)
            data = src.read(1).astype(float)
            h, w = data.shape
            vals = []
            for r, c in zip(rows, cols):
                try:
                    r, c = int(r), int(c)
                    if 1 <= r < h-1 and 1 <= c < w-1:
                        window = data[r-1:r+2, c-1:c+2]
                        valid  = window[window > 0]
                        vals.append(float(np.mean(valid)) if len(valid) > 0 else None)
                    else:
                        vals.append(None)
                except Exception:
                    vals.append(None)
            return vals
    except Exception as e:
        print(f"    Scene error: {type(e).__name__}: {e}", flush=True)
        return [None] * len(lats)

def interpolate(vals_by_dekad, default=0.0, n=32):
    series = [None] * n
    for d, vals in vals_by_dekad.items():
        if vals: series[d] = float(np.mean(vals))
    valid_idx = [i for i, v in enumerate(series) if v is not None]
    valid_val = [series[i] for i in valid_idx]
    if not valid_idx: return [default] * n
    if len(valid_idx) == 1: return [valid_val[0]] * n
    return [round(float(v), 6) for v in
            np.interp(np.arange(n), valid_idx, valid_val)]

def process_month(catalog, year, month, ids, lats, lngs, raw_csv):
    done_file = os.path.join(OUTPUT_DIR, f"{year}_{month:02d}_done.txt")
    if os.path.exists(done_file):
        print(f"  {year}-{month:02d}: skip", flush=True)
        return
    if month == 12: end_d = f"{year}-12-31"
    elif month == 11: end_d = f"{year}-11-21"
    else: end_d = f"{year}-{month+1:02d}-01"
    start_d = f"{year}-{month:02d}-01"
    items = list(catalog.search(
        collections=["sentinel-1-grd"],
        bbox=[-7.3, 52.2, -6.1, 53.1],
        datetime=f"{start_d}/{end_d}"
    ).items())
    items = [i for i in items if shape(i.geometry).intersects(PARCEL_BOX)]
    print(f"  {year}-{month:02d}: {len(items)} scenes", flush=True)
    write_hdr = not os.path.exists(raw_csv)
    fieldnames = ["scene_id","date","dekad","pid","VV_dn","VH_dn"]
    count = 0
    for item in items:
        vv_url = s3_to_https(item.assets["vv"].href)
        vh_url = s3_to_https(item.assets["vh"].href)
        date_s = item.datetime.strftime("%Y-%m-%d")
        dekad  = get_dekad(date_s)
        vv_vals = read_scene(vv_url, lats, lngs)
        vh_vals = read_scene(vh_url, lats, lngs)
        rows_out = []
        for pid, vv, vh in zip(ids, vv_vals, vh_vals):
            if vv and vh and vv > 0 and vh > 0:
                rows_out.append({"scene_id": item.id, "date": date_s,
                                 "dekad": dekad, "pid": pid,
                                 "VV_dn": round(vv,2), "VH_dn": round(vh,2)})
        if rows_out:
            with open(raw_csv, "a", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                if write_hdr: w.writeheader(); write_hdr = False
                w.writerows(rows_out)
            count += 1
    open(done_file, "w").close()
    print(f"  {year}-{month:02d}: {count} scenes with data ✅", flush=True)
    # Commit both done file AND raw CSV after each month
    import subprocess
    subprocess.run(["git", "add", "-f", "sar_progress_e84/"], capture_output=True)
    subprocess.run(["git", "add", "-f", raw_csv], capture_output=True)
    r = subprocess.run(["git", "commit", "-m", f"SAR {year}-{month:02d} complete"],
                       capture_output=True, text=True)
    if r.returncode == 0:
        subprocess.run(["git", "push"], capture_output=True)
        print(f"  {year}-{month:02d}: committed to GitHub ✅", flush=True)
    else:
        print(f"  {year}-{month:02d}: commit failed: {r.stderr.strip()}", flush=True)

def build_features(ids, crops, lats, lngs):
    print("Building features...")
    data = {pid: {yr: {d: {"VV":[],"VH":[]} for d in range(DEKADS)} for yr in YEARS} for pid in ids}
    for year in YEARS:
        raw_csv = os.path.join(OUTPUT_DIR, f"{year}_raw.csv")
        if not os.path.exists(raw_csv): continue
        with open(raw_csv) as f:
            for row in csv.DictReader(f):
                pid = row["pid"]; dekad = int(row["dekad"])
                if pid in data and row.get("VV_dn") and row.get("VH_dn"):
                    data[pid][year][dekad]["VV"].append(float(row["VV_dn"]))
                    data[pid][year][dekad]["VH"].append(float(row["VH_dn"]))
    rows = []
    for i, pid in enumerate(ids):
        row = {"sp_id":pid, "crop":crops[i], "lat":lats[i], "lng":lngs[i]}
        for year in YEARS:
            # Convert DN to linear power BEFORE interpolating
            for metric in ["VV","VH"]:
                lin_by_dekad = {}
                for d in range(DEKADS):
                    dns = data[pid][year][d][metric]
                    if dns:
                        lin_by_dekad[d] = [np.mean([(dn*dn)/(600*600) for dn in dns])]
                lin_series = interpolate(lin_by_dekad, default=0.0)
                for d, lin in enumerate(lin_series):
                    row[f"y{year}_d{d:02d}_{metric}"] = round(10*np.log10(max(lin,1e-10)),4)
            # RVI and DpRVIc
            for d in range(DEKADS):
                vv_dns = data[pid][year][d]["VV"]
                vh_dns = data[pid][year][d]["VH"]
                if vv_dns and vh_dns:
                    vv_lin = np.mean([(dn*dn)/(600*600) for dn in vv_dns])
                    vh_lin = np.mean([(dn*dn)/(600*600) for dn in vh_dns])
                    m = compute_metrics(vv_lin, vh_lin)
                    row[f"y{year}_d{d:02d}_RVI"] = m["RVI"]
                    row[f"y{year}_d{d:02d}_DpRVIc"] = m["DpRVIc"]
                    row[f"y{year}_d{d:02d}_VHVV"] = m["VHVV"]
                else:
                    row[f"y{year}_d{d:02d}_RVI"] = 0.5
                    row[f"y{year}_d{d:02d}_DpRVIc"] = 0.5
                    row[f"y{year}_d{d:02d}_VHVV"] = -6.0
        rows.append(row)
    header = list(rows[0].keys())
    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} parcels to {OUTPUT_FILE} ✅")

if __name__ == "__main__":
    with open("lpis_2024_unique.json") as f:
        parcels = json.load(f)
    ids   = [str(p.get("sp_id",i)) for i,p in enumerate(parcels)]
    lats  = [p["lat"] for p in parcels]
    lngs  = [p["lng"] for p in parcels]
    crops = [p["crop"] for p in parcels]
    catalog = pystac_client.Client.open("https://earth-search.aws.element84.com/v1")
    print(f"Parcels: {len(parcels)}")
    start = time.time()
    for year in YEARS:
        raw_csv = os.path.join(OUTPUT_DIR, f"{year}_raw.csv")
        print(f"Year {year}...")
        for month in range(1, 13):
            process_month(catalog, year, month, ids, lats, lngs, raw_csv)
    build_features(ids, crops, lats, lngs)
    print(f"Total: {(time.time()-start)/3600:.1f}h")
