"""
extract_all_parcels.py
Bulk extraction of S1+S2 features for all 4865 LPIS parcels
Saves to features_cdse.csv — run once, retrain from CSV

Strategy:
  - Process in batches of 50 to avoid timeouts
  - Skip already-extracted parcels (resume on failure)
  - Save progress after each batch
  - Estimate PU consumption before running
"""
import json, csv, os, time
from datetime import datetime
from pipeline import extract_features
from elevation import get_elevation_features
from soil import get_soil_features

INPUT_FILE  = 'lpis_2024_unique.json'
OUTPUT_FILE = 'features_cdse.csv'
BATCH_SIZE  = 50

def estimate_pu(n_parcels):
    """
    Each parcel needs:
      S2 statistics: ~4 years × 32 dekads × ~0.5 PU = ~64 PU
      S1 statistics: ~4 years × 32 dekads × ~0.3 PU = ~38 PU
    Total per parcel: ~100 PU (conservative estimate)
    """
    return n_parcels * 100

def get_already_extracted():
    """Return set of SP_IDs already in output CSV."""
    done = set()
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE) as f:
            reader = csv.DictReader(f)
            for row in reader:
                done.add(row.get('sp_id', ''))
    return done

def run_extraction(max_parcels=None, dry_run=False):
    with open(INPUT_FILE) as f:
        parcels = json.load(f)

    if max_parcels:
        parcels = parcels[:max_parcels]

    already_done = get_already_extracted()
    remaining = [p for p in parcels if str(p.get('sp_id','')) not in already_done]

    print(f"Total parcels:     {len(parcels)}")
    print(f"Already extracted: {len(already_done)}")
    print(f"Remaining:         {len(remaining)}")
    print(f"Estimated PU:      {estimate_pu(len(remaining))}")

    if dry_run:
        print("\nDry run — no API calls made.")
        return

    if len(remaining) == 0:
        print("All parcels already extracted ✅")
        return

    # Confirm before running
    confirm = input(f"\nProceed with {len(remaining)} parcels (~{estimate_pu(len(remaining))} PU)? [y/N]: ")
    if confirm.lower() != 'y':
        print("Aborted.")
        return

    # Write header if new file
    write_header = not os.path.exists(OUTPUT_FILE)
    errors = []

    for batch_start in range(0, len(remaining), BATCH_SIZE):
        batch = remaining[batch_start:batch_start + BATCH_SIZE]
        print(f"\nBatch {batch_start//BATCH_SIZE + 1}: parcels {batch_start+1}-{batch_start+len(batch)}")

        for p in batch:
            sp_id = p.get('sp_id', '')
            lat   = p.get('lat')
            lng   = p.get('lng')
            crop  = p.get('crop', 'Unknown')

            try:
                # S1+S2 features
                features = extract_features(p)

                # Static features (free, no PU cost)
                elev = get_elevation_features(lat, lng, polygon=p['geometry']['coordinates'][0])
                soil = get_soil_features(lat, lng)

                row = {
                    'sp_id':  sp_id,
                    'lat':    lat,
                    'lng':    lng,
                    'crop':   crop,
                    'extracted_at': datetime.now().isoformat(),
                    **features,
                    **elev,
                    **soil
                }

                with open(OUTPUT_FILE, 'a', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=row.keys())
                    if write_header:
                        writer.writeheader()
                        write_header = False
                    writer.writerow(row)

                print(f"  ✅ {sp_id} ({crop})")

            except Exception as e:
                print(f"  ❌ {sp_id}: {e}")
                errors.append({'sp_id': sp_id, 'error': str(e)})

        print(f"  Batch complete. Sleeping 2s...")
        time.sleep(2)

    print(f"\n{'='*50}")
    print(f"Extraction complete: {len(remaining)-len(errors)} success, {len(errors)} errors")
    if errors:
        with open('extraction_errors.json', 'w') as f:
            json.dump(errors, f, indent=2)
        print(f"Errors saved to extraction_errors.json")

if __name__ == '__main__':
    import sys
    dry_run = '--dry-run' in sys.argv
    max_p   = int(sys.argv[2]) if len(sys.argv) > 2 else None
    run_extraction(max_parcels=max_p, dry_run=dry_run)
