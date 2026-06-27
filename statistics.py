"""
statistics.py — Sentinel Hub Statistics API
Uses ORBIT mosaicking with SCL pixel masking
Matches GEE training pipeline: best clear pixel per dekad
"""
from auth import get_session

SH_STATS_URL = "https://sh.dataspace.copernicus.eu/api/v1/statistics"

def safe_float(val, default=None):
    try:
        v = float(val)
        if v != v or abs(v) == float('inf') or abs(v) > 1e6:
            return default
        return round(v, 4)
    except (TypeError, ValueError):
        return default

def get_s2_statistics(bbox: list, start: str, end: str,
                      interval: str = "P10D") -> list:
    """
    Get S2 indices with ORBIT mosaicking and SCL cloud masking.
    Best clear pixel selected per dekad — matches GEE pipeline.
    """
    session = get_session()

    payload = {
        "input": {
            "bounds": {"bbox": bbox},
            "data": [{"type": "sentinel-2-l2a",
                      "dataFilter": {
                          "timeRange": {"from": start, "to": end},
                          "maxCloudCoverage": 90
                      },
                      "processing": {"harmonizeValues": True}}]
        },
        "aggregation": {
            "timeRange": {"from": start, "to": end},
            "aggregationInterval": {"of": interval},
            "resampling": "NEAREST",
            "evalscript": """
//VERSION=3
function setup() {
  return {
    input: [{bands:["B02","B03","B04","B05","B08","B8A","B11","SCL","dataMask"],
             units:["REFLECTANCE","REFLECTANCE","REFLECTANCE","REFLECTANCE",
                    "REFLECTANCE","REFLECTANCE","REFLECTANCE","DN","DN"]}],
    output: [
      {id:"indices",  bands:5, sampleType:"FLOAT32"},
      {id:"dataMask", bands:1, sampleType:"UINT8"}
    ],
    mosaicking: "ORBIT"
  };
}
function evaluatePixel(samples) {
  var best = null;
  var best_ndvi = -999;
  for (var i=0; i<samples.length; i++) {
    var s = samples[i];
    var scl = s.SCL;
    var clear = (scl!=0&&scl!=1&&scl!=2&&scl!=3&&
                 scl!=8&&scl!=9&&scl!=10);
    if (clear && s.dataMask==1 && s.B04<=1.0 && s.B08<=1.0) {
      var ndvi = (s.B08-s.B04)/(s.B08+s.B04+1e-8);
      if (ndvi > best_ndvi) {
        best_ndvi = ndvi;
        best = s;
      }
    }
  }
  if (!best) {
    return {indices:[NaN,NaN,NaN,NaN,NaN], dataMask:[0]};
  }
  var eps = 1e-8;
  var ndvi = (best.B08-best.B04)/(best.B08+best.B04+eps);
  var ndre = (best.B08-best.B05)/(best.B08+best.B05+eps);
  var d    = best.B08+6*best.B04-7.5*best.B02+1;
  var evi  = Math.abs(d)>eps ? 2.5*(best.B08-best.B04)/d : 0;
  evi = Math.max(-1, Math.min(1, evi));
  var ndwi = (best.B03-best.B08)/(best.B03+best.B08+eps);
  var ndii = (best.B8A-best.B11)/(best.B8A+best.B11+eps);
  return {
    indices:  [ndvi, ndre, evi, ndwi, ndii],
    dataMask: [1]
  };
}
"""
        },
        "calculations": {
            "indices": {
                "statistics": {
                    "default": {"percentiles": {"k": [50]}}
                }
            }
        }
    }

    r = session.post(SH_STATS_URL, json=payload, timeout=90)
    if r.status_code != 200:
        print(f"Error {r.status_code}: {r.text[:200]}")
        return []

    results = []
    for item in r.json().get('data', []):
        date = item['interval']['from'][:10]
        bands = item['outputs']['indices']['bands']
        ndvi = safe_float(bands['B0']['stats'].get('mean'))
        if ndvi is None:
            continue
        results.append({
            'date': date,
            'NDVI': ndvi,
            'NDRE': safe_float(bands['B1']['stats'].get('mean')),
            'EVI':  safe_float(bands['B2']['stats'].get('mean')),
            'NDWI': safe_float(bands['B3']['stats'].get('mean')),
            'NDII': safe_float(bands['B4']['stats'].get('mean')),
        })

    return results

if __name__ == '__main__':
    import json
    with open('lpis_2024_unique.json') as f:
        parcels = json.load(f)
    p = next(x for x in parcels if x['crop'] == 'Spring Barley')
    coords = p['geometry']['coordinates'][0]
    lngs = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    bbox = [min(lngs), min(lats), max(lngs), max(lats)]

    print("Testing ORBIT mosaicking with SCL masking...")
    results = get_s2_statistics(
        bbox,
        "2024-01-01T00:00:00Z",
        "2024-11-21T23:59:59Z"
    )
    print(f"\nValid dekads: {len(results)}")
    print(f"\n{'Date':<12} {'NDVI':>7} {'NDRE':>7} {'EVI':>7} {'NDWI':>7} {'NDII':>7}")
    print("-" * 55)
    for r in results:
        def fmt(v): return f"{v:>7.4f}" if v is not None else "   None"
        print(f"{r['date']:<12}{fmt(r['NDVI'])}{fmt(r['NDRE'])}{fmt(r['EVI'])}{fmt(r['NDWI'])}{fmt(r['NDII'])}")
