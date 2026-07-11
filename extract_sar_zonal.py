
import sys, json, csv, os, time
import numpy as np
import pystac_client, rasterio
from numpy.linalg import lstsq
from rasterio.windows import Window
from shapely.geometry import shape, box
from datetime import datetime

OUTPUT_DIR   = "sar_zonal_progress"
OUTPUT_FILE  = "sar_zonal_features.csv"
YEARS        = [2022, 2023, 2024, 2025]
DEKADS       = 32
SAR_METRICS  = ["VV", "VH", "RVI", "VHVV", "DpRVIc"]
PARCEL_BOX   = box(-7.3, 52.2, -6.1, 53.1)
TARGET_ORBIT = 125
SCENES_PER_MONTH = 5

os.makedirs(OUTPUT_DIR, exist_ok=True)

def s3_to_https(url):
    if url.startswith("s3://"):
        parts = url[5:].split("/", 1)
        return f"https://{parts[0]}.s3.amazonaws.com/{parts[1]}"
    return url

def get_dekad(date_str):
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return min(int((d.timetuple().tm_yday-1)/(365/32)), 31)

def compute_metrics(vv_dn, vh_dn):
    eps    = 1e-10
    vv_lin = (vv_dn*vv_dn)/(600*600)
    vh_lin = (vh_dn*vh_dn)/(600*600)
    vv_db  = 10*np.log10(vv_lin+eps)
    vh_db  = 10*np.log10(vh_lin+eps)
    rvi    = min((4*vh_lin)/(vv_lin+vh_lin+eps), 1.0)
    vhvv   = vh_db - vv_db
    q      = vh_lin/(vv_lin+eps)
    dprvic = min(1-((1-q)/(1+q+eps))*(1/(1+q+eps)), 1.0)
    return {"VV":round(float(vv_db),4), "VH":round(float(vh_db),4),
            "RVI":round(float(max(rvi,0)),4), "VHVV":round(float(vhvv),4),
            "DpRVIc":round(float(max(dprvic,0)),4)}

def interpolate(vals_by_dekad, default=0.0, n=32):
    series = [None]*n
    for d, vals in vals_by_dekad.items():
        if vals: series[d] = float(np.median(vals))
    valid_idx = [i for i,v in enumerate(series) if v is not None]
    valid_val = [series[i] for i in valid_idx]
    if not valid_idx: return [default]*n
    if len(valid_idx)==1: return [valid_val[0]]*n
    return [round(float(v),4) for v in np.interp(np.arange(n), valid_idx, valid_val)]

def extract_chip(url, polygons, parcel_box):
    with rasterio.open(url) as src:
        gcps, _ = src.gcps
        if not gcps: return None, None, None, None
        cols_g = np.array([g.col for g in gcps])
        rows_g = np.array([g.row for g in gcps])
        lngs_g = np.array([g.x   for g in gcps])
        lats_g = np.array([g.y   for g in gcps])
        A = np.column_stack([lngs_g, lats_g, np.ones(len(gcps))])
        col_c, _, _, _ = lstsq(A, cols_g, rcond=None)
        row_c, _, _, _ = lstsq(A, rows_g, rcond=None)
        def ll2px(lat, lng):
            return (int(row_c[0]*lng+row_c[1]*lat+row_c[2]),
                    int(col_c[0]*lng+col_c[1]*lat+col_c[2]))
        H, W = src.height, src.width
        all_r = [ll2px(p.centroid.y, p.centroid.x)[0] for p in polygons]
        all_c = [ll2px(p.centroid.y, p.centroid.x)[1] for p in polygons]
        r0=max(0,min(all_r)-50); r1=min(H,max(all_r)+50)
        c0=max(0,min(all_c)-50); c1=min(W,max(all_c)+50)
        if r1<=r0 or c1<=c0: return None,None,None,None
        chip = src.read(1, window=Window(c0,r0,c1-c0,r1-r0)).astype(float)
        chip[chip<=0] = np.nan
        return chip, r0, c0, ll2px

def sample_polygon(geom, chip, r0, c0, ll2px):
    centroid = geom.centroid
    coords   = list(geom.exterior.coords)
    step     = max(1, len(coords)//4)
    pts = [(centroid.y, centroid.x)]
    for j in range(0, len(coords)-1, step):
        lo, la = coords[j]
        pts.append(((la+centroid.y)/2, (lo+centroid.x)/2))
    vals = []
    for la, lo in pts:
        r, c = ll2px(la, lo)
        r -= r0; c -= c0
        if 1<=r<chip.shape[0]-1 and 1<=c<chip.shape[1]-1:
            w = chip[r-1:r+2, c-1:c+2]
            v = w[~np.isnan(w)]
            if len(v): vals.append(float(np.nanmean(v)))
    return float(np.median(vals)) if vals else None

def month_done(year, month):
    return os.path.exists(os.path.join(OUTPUT_DIR, f"{year}_{month:02d}_done.txt"))

def process_month(catalog, year, month, ids, polygons, raw_csv):
    done_file = os.path.join(OUTPUT_DIR, f"{year}_{month:02d}_done.txt")
    if os.path.exists(done_file):
        print(f"  {year}-{month:02d}: skip", flush=True)
        return
    m_end = month+1 if month < 11 else 12
    if month == 11: end_str = f"{year}-11-21"
    else: end_str = f"{year}-{m_end:02d}-01"
    start_str = f"{year}-{month:02d}-01"

    items = [i for i in catalog.search(
        collections=["sentinel-1-grd"],
        bbox=[-7.3, 52.2, -6.1, 53.1],
        datetime=f"{start_str}/{end_str}"
    ).items()
    if shape(i.geometry).intersects(PARCEL_BOX)
    and i.properties.get("sat:relative_orbit") == TARGET_ORBIT]

    # Use up to SCENES_PER_MONTH evenly spaced
    if len(items) > SCENES_PER_MONTH:
        step = len(items) // SCENES_PER_MONTH
        items = items[::step][:SCENES_PER_MONTH]

    print(f"  {year}-{month:02d}: {len(items)} scenes (orbit {TARGET_ORBIT})", flush=True)
    if not items:
        open(done_file,"w").close()
        return

    write_hdr  = not os.path.exists(raw_csv)
    fieldnames = ["scene_id","date","dekad","pid","VV_dn","VH_dn"]
    count = 0

    for item in items:
        vv_url = s3_to_https(item.assets["vv"].href)
        vh_url = s3_to_https(item.assets["vh"].href)
        date_s = item.datetime.strftime("%Y-%m-%d")
        dekad  = get_dekad(date_s)

        vv_chip, r0, c0, ll2px = extract_chip(vv_url, polygons, PARCEL_BOX)
        if vv_chip is None: continue
        vh_chip, _, _, _ = extract_chip(vh_url, polygons, PARCEL_BOX)
        if vh_chip is None: continue

        rows_out = []
        for pid, geom in zip(ids, polygons):
            vv_dn = sample_polygon(geom, vv_chip, r0, c0, ll2px)
            vh_dn = sample_polygon(geom, vh_chip, r0, c0, ll2px)
            if vv_dn and vh_dn:
                rows_out.append({"scene_id":item.id,"date":date_s,
                                 "dekad":dekad,"pid":pid,
                                 "VV_dn":round(vv_dn,2),"VH_dn":round(vh_dn,2)})

        if rows_out:
            with open(raw_csv,"a",newline="") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                if write_hdr: w.writeheader(); write_hdr=False
                w.writerows(rows_out)
            count += 1

    open(done_file,"w").close()
    # Commit after each month
    import subprocess
    subprocess.run(["git","add","-f",done_file], capture_output=True)
    subprocess.run(["git","commit","-m",f"Zonal SAR {year}-{month:02d}"], capture_output=True)
    subprocess.run(["git","push"], capture_output=True)
    print(f"  {year}-{month:02d}: {count} scenes ✅ committed", flush=True)

def build_features(ids, crops, lats, lngs):
    print("Building zonal features...")
    data = {pid: {yr: {d: {"VV":[],"VH":[]} for d in range(DEKADS)} for yr in YEARS} for pid in ids}
    for year in YEARS:
        raw_csv = os.path.join(OUTPUT_DIR, f"{year}_raw.csv")
        if not os.path.exists(raw_csv): continue
        with open(raw_csv) as f:
            for row in csv.DictReader(f):
                pid=row["pid"]; d=int(row["dekad"])
                if pid in data and row.get("VV_dn") and row.get("VH_dn"):
                    data[pid][year][d]["VV"].append(float(row["VV_dn"]))
                    data[pid][year][d]["VH"].append(float(row["VH_dn"]))
    rows = []
    for i, pid in enumerate(ids):
        row = {"sp_id":pid,"crop":crops[i],"lat":lats[i],"lng":lngs[i]}
        for year in YEARS:
            for metric in ["VV","VH"]:
                lin_by_d = {}
                for d in range(DEKADS):
                    dns = data[pid][year][d][metric]
                    if dns: lin_by_d[d] = [np.mean([(dn*dn)/(600*600) for dn in dns])]
                lin_s = interpolate(lin_by_d, default=0.0)
                for d, lin in enumerate(lin_s):
                    row[f"y{year}_d{d:02d}_{metric}"] = round(10*np.log10(max(lin,1e-10)),4)
            for d in range(DEKADS):
                vv_dns = data[pid][year][d]["VV"]
                vh_dns = data[pid][year][d]["VH"]
                if vv_dns and vh_dns:
                    # convert DN to linear power before computing metrics
                    vv_dn_med = np.median(vv_dns)
                    vh_dn_med = np.median(vh_dns)
                    m = compute_metrics(vv_dn_med, vh_dn_med)
                    row[f"y{year}_d{d:02d}_RVI"]    = m["RVI"]
                    row[f"y{year}_d{d:02d}_DpRVIc"] = m["DpRVIc"]
                    row[f"y{year}_d{d:02d}_VHVV"]   = m["VHVV"]
                else:
                    row[f"y{year}_d{d:02d}_RVI"]    = 0.3
                    row[f"y{year}_d{d:02d}_DpRVIc"] = 0.5
                    row[f"y{year}_d{d:02d}_VHVV"]   = -6.0
        rows.append(row)
    header = list(rows[0].keys())
    with open(OUTPUT_FILE,"w",newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} parcels to {OUTPUT_FILE} ✅")

if __name__ == "__main__":
    with open("lpis_2024_unique.json") as f:
        parcels = json.load(f)
    ids      = [str(p.get("sp_id",i)) for i,p in enumerate(parcels)]
    lats     = [p["lat"] for p in parcels]
    lngs     = [p["lng"] for p in parcels]
    crops    = [p["crop"] for p in parcels]
    polygons = [shape(p["geometry"]) for p in parcels]

    catalog = pystac_client.Client.open("https://earth-search.aws.element84.com/v1")
    print(f"Parcels: {len(parcels)} | Orbit: {TARGET_ORBIT} | Scenes/month: {SCENES_PER_MONTH}")

    start = time.time()
    for year in YEARS:
        raw_csv = os.path.join(OUTPUT_DIR, f"{year}_raw.csv")
        print(f"Year {year}...")
        for month in range(1, 13):
            process_month(catalog, year, month, ids, polygons, raw_csv)

    build_features(ids, crops, lats, lngs)
    print(f"Total: {(time.time()-start)/3600:.1f}h")
