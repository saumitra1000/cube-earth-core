"""
soil.py — SoilGrids v2 soil properties
Free, no auth, WCS endpoint
Provides: clay, sand, soc, phh2o, nitrogen at 0-30cm
"""
import requests
import numpy as np
import rasterio
import io

SOILGRIDS_URL = "https://maps.isric.org/mapserv"

SOIL_PROPERTIES = {
    'clay':     {'map': '/map/clay.map',     'factor': 10, 'unit': '%'},
    'sand':     {'map': '/map/sand.map',     'factor': 10, 'unit': '%'},
    'soc':      {'map': '/map/soc.map',      'factor': 10, 'unit': 'g/kg'},
    'phh2o':    {'map': '/map/phh2o.map',    'factor': 10, 'unit': 'pH'},
    'nitrogen': {'map': '/map/nitrogen.map', 'factor': 100,'unit': 'cg/kg'},
}

DEPTHS = ['0-5cm', '5-15cm', '15-30cm']

def get_soil_features(lat: float, lng: float,
                      buffer: float = 0.05) -> dict:
    """
    Get soil properties for a location.
    Returns mean values across 0-30cm depth.
    """
    features = {}

    for prop, cfg in SOIL_PROPERTIES.items():
        values_by_depth = []

        for depth in DEPTHS:
            coverage_id = f"{prop}_{depth}_mean"
            params = {
                "map": cfg['map'],
                "SERVICE": "WCS",
                "VERSION": "2.0.1",
                "REQUEST": "GetCoverage",
                "COVERAGEID": coverage_id,
                "FORMAT": "image/tiff",
                "SUBSET": [
                    f"long({lng-buffer},{lng+buffer})",
                    f"lat({lat-buffer},{lat+buffer})"
                ],
                "SUBSETTINGCRS": "http://www.opengis.net/def/crs/EPSG/0/4326",
                "OUTPUTCRS": "http://www.opengis.net/def/crs/EPSG/0/4326"
            }

            try:
                r = requests.get(SOILGRIDS_URL, params=params, timeout=30)
                if r.status_code == 200 and 'tiff' in r.headers.get('Content-Type',''):
                    with rasterio.open(io.BytesIO(r.content)) as src:
                        data = src.read(1).astype(float)
                        data[data < 0] = np.nan
                        val = np.nanmean(data) / cfg['factor']
                        values_by_depth.append(round(val, 2))
            except Exception:
                values_by_depth.append(None)

        # Mean across depths 0-30cm
        valid = [v for v in values_by_depth if v is not None]
        features[f'soil_{prop}'] = round(sum(valid)/len(valid), 2) if valid else None

    return features

if __name__ == '__main__':
    import json
    with open('lpis_2024_unique.json') as f:
        parcels = json.load(f)

    targets = {}
    for p in parcels:
        if p['crop'] not in targets:
            targets[p['crop']] = p
        if len(targets) == 5:
            break

    print(f"{'Crop':<20} {'Clay%':>6} {'Sand%':>6} {'SOC':>6} {'pH':>6} {'N':>6}")
    print("-" * 52)

    for crop, p in sorted(targets.items()):
        feats = get_soil_features(p['lat'], p['lng'])
        print(f"{crop:<20} "
              f"{str(feats.get('soil_clay','?')):>6} "
              f"{str(feats.get('soil_sand','?')):>6} "
              f"{str(feats.get('soil_soc','?')):>6} "
              f"{str(feats.get('soil_phh2o','?')):>6} "
              f"{str(feats.get('soil_nitrogen','?')):>6}")
