"""
sar_planetary.py — Extract Sentinel-1 VV/VH from Microsoft Planetary Computer
Free, no account needed, anonymous access
Returns VV_db, VH_db, RVI, VHVV, DpRVIc per parcel per date
"""
import planetary_computer
import pystac_client
import rasterio
import numpy as np
from rasterio.warp import transform as warp_transform
from datetime import datetime, timedelta

CATALOG = pystac_client.Client.open(
    "https://planetarycomputer.microsoft.com/api/stac/v1",
    modifier=planetary_computer.sign_inplace
)

def compute_sar_metrics(vv_lin: float, vh_lin: float) -> dict:
    """Compute SAR metrics from linear backscatter values."""
    eps = 1e-10
    vv_db   = 10 * np.log10(vv_lin + eps)
    vh_db   = 10 * np.log10(vh_lin + eps)
    rvi     = (4 * vh_lin) / (vv_lin + vh_lin + eps)
    vhvv    = vh_db - vv_db
    q       = vh_lin / (vv_lin + eps)
    dprvic  = 1 - ((1-q)/(1+q+eps)) * (1/(1+q+eps))
    return {
        'VV':     round(float(vv_db),  4),
        'VH':     round(float(vh_db),  4),
        'RVI':    round(float(rvi),    4),
        'VHVV':   round(float(vhvv),   4),
        'DpRVIc': round(float(dprvic), 4),
    }

def get_sar_for_parcel(lat: float, lng: float,
                        year: int) -> list:
    """
    Get Sentinel-1 SAR observations for a parcel in a given year.
    Returns list of {date, VV, VH, RVI, VHVV, DpRVIc}
    """
    bbox = [lng-0.005, lat-0.005, lng+0.005, lat+0.005]

    search = CATALOG.search(
        collections=["sentinel-1-rtc"],
        bbox=bbox,
        datetime=f"{year}-01-01/{year}-11-21",
        max_items=100
    )
    items = list(search.items())
    results = []

    for item in items:
        try:
            signed = planetary_computer.sign(item)
            vv_url = signed.assets['vv'].href
            vh_url = signed.assets['vh'].href
            date   = item.datetime.strftime('%Y-%m-%d')

            with rasterio.open(vv_url) as src:
                xs, ys = warp_transform(
                    'EPSG:4326', src.crs, [lng], [lat])
                row, col = src.index(xs[0], ys[0])
                win  = rasterio.windows.Window(col-1, row-1, 3, 3)
                data = src.read(1, window=win).astype(float)
                vv_lin = float(np.nanmean(data[data > 0]))

            with rasterio.open(vh_url) as src:
                row, col = src.index(xs[0], ys[0])
                win  = rasterio.windows.Window(col-1, row-1, 3, 3)
                data = src.read(1, window=win).astype(float)
                vh_lin = float(np.nanmean(data[data > 0]))

            metrics = compute_sar_metrics(vv_lin, vh_lin)
            metrics['date'] = date
            results.append(metrics)

        except Exception as e:
            continue

    return sorted(results, key=lambda x: x['date'])

if __name__ == '__main__':
    # Test on one Spring Barley parcel in Carlow
    import json
    with open('lpis_2024_unique.json') as f:
        parcels = json.load(f)

    p = next(x for x in parcels if x['crop'] == 'Spring Barley')
    lat, lng = p['lat'], p['lng']
    print(f"Testing SAR extraction: {p['crop']} at {lat:.4f}, {lng:.4f}")

    results = get_sar_for_parcel(lat, lng, 2024)
    print(f"\n{len(results)} SAR observations found for 2024")
    print(f"\n{'Date':<12} {'VV':>8} {'VH':>8} {'RVI':>7} {'DpRVIc':>8}")
    print("-" * 48)
    for r in results[:10]:
        print(f"{r['date']:<12} {r['VV']:>8.2f} {r['VH']:>8.2f} "
              f"{r['RVI']:>7.4f} {r['DpRVIc']:>8.4f}")
