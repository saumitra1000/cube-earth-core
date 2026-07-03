"""
download_hls.py — Download completed HLS tasks from AppEEARS
Run once all 20 tasks show 'done'
Merges all CSVs into one training dataset
"""
import requests, os, json, csv
from pathlib import Path

APPEEARS = "https://appeears.earthdatacloud.nasa.gov/api"
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
    bundle = requests.get(f"{APPEEARS}/bundle/{tid}",
                           headers=headers, timeout=60).json()
    files = bundle.get('files', [])

    for f in files:
        fname = f['file_name']
        if not fname.endswith('-results.csv'):
            continue
        print(f"  Downloading {fname}...")
        r = requests.get(
            f"{APPEEARS}/bundle/{tid}/{f['file_id']}",
            headers=headers, timeout=300)
        out_path = OUTPUT_DIR / f"{name}.csv"
        with open(out_path, 'w') as fp:
            fp.write(r.text)
        print(f"  Saved: {out_path} ({len(r.text)/1e3:.1f} KB)")
        return out_path
    return None

def check_and_download():
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}

    with open('hls_task_ids.json') as f:
        task_ids = json.load(f)

    done = []
    pending = []
    for name, tid in task_ids.items():
        r = requests.get(f"{APPEEARS}/task/{tid}",
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
        out = OUTPUT_DIR / f"{name}.csv"
        if out.exists():
            print(f"  ✅ {name} already downloaded")
            continue
        download_task(token, name, tid)

    # Check if all done — merge
    if len(pending) == 0:
        print("\nAll tasks complete — merging...")
        merge_all()

def merge_all():
    """Merge all 20 CSVs into one training file."""
    all_rows = []
    header = None

    for csv_path in sorted(OUTPUT_DIR.glob("*.csv")):
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if not header:
                header = reader.fieldnames
            # Filter out fill values (-19999 / -28672)
            for row in rows:
                all_rows.append(row)
        print(f"  {csv_path.name}: {len(rows)} rows")

    output = 'hls_all_parcels.csv'
    with open(output, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nMerged: {len(all_rows)} total rows")
    print(f"Saved:  {output} ✅")

if __name__ == '__main__':
    check_and_download()
