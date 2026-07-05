"""
download_hls.py — Download completed HLS tasks from AppEEARS
Downloads BOTH the raw bands CSV and VI CSV per task
Merges all into one training dataset
"""
import requests, os, json, csv
from pathlib import Path

APPEEARS   = "https://appeears.earthdatacloud.nasa.gov/api"
OUTPUT_DIR = Path('hls_data')
OUTPUT_DIR.mkdir(exist_ok=True)

def get_token():
    r = requests.post(f"{APPEEARS}/login",
                      auth=(os.environ['NASA_EARTHDATA_USER'],
                            os.environ['NASA_EARTHDATA_PASS']),
                      timeout=30)
    return r.json()['token']

def download_task(token, name, tid):
    headers = {"Authorization": f"Bearer {token}"}
    bundle  = requests.get(f"{APPEEARS}/bundle/{tid}",
                            headers=headers, timeout=60).json()
    files   = bundle.get('files', [])
    saved   = []

    for f in files:
        fname = f['file_name']
        if not fname.endswith('-results.csv'):
            continue

        # Save bands and VI files separately
        if 'VI' in fname:
            out_path = OUTPUT_DIR / f"{name}_vi.csv"
        else:
            out_path = OUTPUT_DIR / f"{name}.csv"

        if out_path.exists():
            print(f"  ✅ {out_path.name} already downloaded")
            saved.append(out_path)
            continue

        print(f"  Downloading {fname}...")
        r = requests.get(
            f"{APPEEARS}/bundle/{tid}/{f['file_id']}",
            headers=headers, timeout=300)
        with open(out_path, 'w') as fp:
            fp.write(r.text)
        print(f"  Saved: {out_path} ({len(r.text)/1e3:.1f} KB)")
        saved.append(out_path)

    return saved

def check_and_download():
    token   = get_token()
    headers = {"Authorization": f"Bearer {token}"}

    with open('hls_task_ids.json') as f:
        task_ids = json.load(f)

    done    = []
    pending = []
    for name, tid in task_ids.items():
        r      = requests.get(f"{APPEEARS}/task/{tid}",
                               headers=headers, timeout=15)
        status = r.json().get('status')
        if status == 'done':
            done.append((name, tid))
        else:
            pending.append((name, status))

    print(f"Done: {len(done)}/20")
    print(f"Pending: {len(pending)}/20")

    if pending:
        print("\nStill processing:")
        for name, status in pending:
            print(f"  ⏳ {name}: {status}")

    print("\nDownloading completed tasks...")
    for name, tid in done:
        download_task(token, name, tid)

    if len(pending) == 0:
        print("\nAll tasks complete — merging...")
        merge_all()

def merge_all():
    """Merge bands and VI files by Date+ID into one combined CSV."""
    print("Loading VI data (NDVI/EVI/NDWI)...")

    # Load VI data into lookup: (id, date) → {NDVI, EVI, NDWI}
    vi_data = {}
    vi_files = sorted(OUTPUT_DIR.glob("*_vi.csv"))
    print(f"VI files found: {len(vi_files)}")

    for vi_path in vi_files:
        with open(vi_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row['ID'], row['Date'])
                vi_data[key] = {
                    'NDVI': row.get('HLSS30_VI_020_NDVI', ''),
                    'EVI':  row.get('HLSS30_VI_020_EVI', ''),
                    'NDWI': row.get('HLSS30_VI_020_NDWI', ''),
                }

    print(f"VI observations loaded: {len(vi_data):,}")

    # Merge bands files with VI data
    print("Merging bands + VI...")
    band_files = sorted(OUTPUT_DIR.glob("*.csv"))
    band_files = [f for f in band_files if '_vi' not in f.name
                  and 'all_parcels' not in f.name]

    all_rows = []
    header   = None

    for band_path in band_files:
        with open(band_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row['ID'], row['Date'])
                vi  = vi_data.get(key, {})
                row['HLSS30_VI_NDVI'] = vi.get('NDVI', '')
                row['HLSS30_VI_EVI']  = vi.get('EVI', '')
                row['HLSS30_VI_NDWI'] = vi.get('NDWI', '')
                all_rows.append(row)
                if header is None:
                    header = list(row.keys())

    output = 'hls_all_parcels.csv'
    with open(output, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nMerged: {len(all_rows):,} total rows")
    print(f"Saved:  {output} ✅")

if __name__ == '__main__':
    check_and_download()
