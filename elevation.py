"""
elevation.py — Copernicus DEM 30m elevation and slope
Free, no auth, AWS S3 public bucket
Adds: elevation_m, slope_deg, elevation_std
"""
import os
import numpy as np
import rasterio
from rasterio.windows import Window

os.environ['AWS_NO_SIGN_REQUEST'] = 'YES'
os.environ['GDAL_DISABLE_READDIR_ON_OPEN'] = 'EMPTY_DIR'

def get_tile_path(lat: float, lng: float) -> str:
    lat_int = int(abs(lat))
    lng_int = int(abs(lng)) + 1
    lat_hem = 'N' if lat >= 0 else 'S'
    lng_hem = 'W' if lng < 0 else 'E'
    tile = f"Copernicus_DSM_COG_10_{lat_hem}{lat_int:02d}_00_{lng_hem}{lng_int:03d}_00_DEM"
    return f"/vsis3/copernicus-dem-30m/{tile}/{tile}.tif"

def get_elevation_features(lat: float, lng: float,
                           polygon: list = None) -> dict:
    """
    Get elevation and slope for a location or polygon.
    Returns: elevation_m, slope_deg, elevation_std
    """
    path = get_tile_path(lat, lng)
    try:
        with rasterio.open(path) as src:
            if polygon:
                lngs = [c[0] for c in polygon]
                lats = [c[1] for c in polygon]
                row_min, col_min = src.index(min(lngs), max(lats))
                row_max, col_max = src.index(max(lngs), min(lats))
                row_min, row_max = min(row_min,row_max), max(row_min,row_max)+1
                col_min, col_max = min(col_min,col_max), max(col_min,col_max)+1
                win = Window(col_min, row_min,
                             col_max-col_min, row_max-row_min)
            else:
                row, col = src.index(lng, lat)
                win = Window(col-3, row-3, 7, 7)

            data = src.read(1, window=win).astype(float)
            data[data < -1000] = np.nan

            # Slope calculation
            res_m = 30.0
            dy, dx = np.gradient(data, res_m, res_m)
            slope = np.degrees(np.arctan(np.sqrt(dx**2 + dy**2)))

            return {
                'elevation_m':   round(float(np.nanmean(data)), 1),
                'slope_deg':     round(float(np.nanmean(slope)), 2),
                'elevation_std': round(float(np.nanstd(data)), 2),
            }
    except Exception as e:
        return {
            'elevation_m':   None,
            'slope_deg':     None,
            'elevation_std': None,
        }

if __name__ == '__main__':
    import json
    with open('lpis_2024_unique.json') as f:
        parcels = json.load(f)

    # Test across different crop types
    targets = {}
    for p in parcels:
        if p['crop'] not in targets:
            targets[p['crop']] = p
        if len(targets) == 10:
            break

    print(f"{'Crop':<20} {'Elevation':>10} {'Slope':>8} {'Std':>6}")
    print("-" * 48)
    for crop, p in sorted(targets.items()):
        polygon = p['geometry']['coordinates'][0]
        feats = get_elevation_features(p['lat'], p['lng'], polygon=polygon)
        elev = feats['elevation_m']
        slope = feats['slope_deg']
        std = feats['elevation_std']
        print(f"{crop:<20} {str(elev):>10} {str(slope):>8} {str(std):>6}")
