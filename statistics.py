"""
statistics.py — Sentinel Hub Statistics API
Extracts temporal S2 band statistics for a bounding box
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

def get_s2_statistics(bbox: list, start: str, end: str, interval: str = "P10D") -> list:
    session = get_session()

    payload = {
        "input": {
            "bounds": {"bbox": bbox},
            "data": [{"type": "sentinel-2-l2a",
                      "dataFilter": {
                          "timeRange": {"from": start, "to": end},
                          "maxCloudCoverage": 90
                      }}]
        },
        "aggregation": {
            "timeRange": {"from": start, "to": end},
            "aggregationInterval": {"of": interval},
            "evalscript": """
//VERSION=3
function setup() {
  return {
    input: [{bands: ["B02","B03","B04","B05","B08","B8A","B11","dataMask"]}],
    output: [
      {id: "indices", bands: 5, sampleType: "FLOAT32"},
      {id: "dataMask", bands: 1, sampleType: "UINT8"}
    ]
  };
}
function evaluatePixel(s) {
  let eps = 1e-8;
  let ndvi = (s.B08 - s.B04) / (s.B08 + s.B04 + eps);
  let ndre = (s.B08 - s.B05) / (s.B08 + s.B05 + eps);
  let denom = s.B08 + 6*s.B04 - 7.5*s.B02 + 1;
  let evi  = Math.abs(denom) > eps ? 2.5*(s.B08-s.B04)/denom : 0;
  evi = Math.max(-1, Math.min(1, evi));
  let ndwi = (s.B03 - s.B08) / (s.B03 + s.B08 + eps);
  let ndii = (s.B8A - s.B11) / (s.B8A + s.B11 + eps);
  return {
    indices: [ndvi, ndre, evi, ndwi, ndii],
    dataMask: [s.dataMask]
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

    r = session.post(SH_STATS_URL, json=payload, timeout=60)
    if r.status_code != 200:
        print(f"Error {r.status_code}: {r.text[:200]}")
        return []

    results = []
    for item in r.json().get('data', []):
        date = item['interval']['from'][:10]
        bands = item['outputs']['indices']['bands']
        results.append({
            'date': date,
            'NDVI': safe_float(bands['B0']['stats'].get('mean')),
            'NDRE': safe_float(bands['B1']['stats'].get('mean')),
            'EVI':  safe_float(bands['B2']['stats'].get('mean')),
            'NDWI': safe_float(bands['B3']['stats'].get('mean')),
            'NDII': safe_float(bands['B4']['stats'].get('mean')),
        })

    return results

if __name__ == '__main__':
    bbox = [-6.96, 52.82, -6.90, 52.86]
    results = get_s2_statistics(
        bbox,
        "2024-04-01T00:00:00Z",
        "2024-09-30T23:59:59Z"
    )
    print(f"\nS2 statistics: {len(results)} dekads")
    print(f"\n{'Date':<12} {'NDVI':>7} {'NDRE':>7} {'EVI':>7} {'NDWI':>7} {'NDII':>7}")
    print("-" * 55)
    for r in results:
        def fmt(v): return f"{v:>7.4f}" if v is not None else "   None"
        print(f"{r['date']:<12}{fmt(r['NDVI'])}{fmt(r['NDRE'])}{fmt(r['EVI'])}{fmt(r['NDWI'])}{fmt(r['NDII'])}")
