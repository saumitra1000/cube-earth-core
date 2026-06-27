"""
sar.py — Sentinel-1 SAR statistics
Returns VV, VH in dB scale to match GEE training data
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

def get_s1_statistics(bbox: list, start: str, end: str, interval: str = "P10D") -> list:
    session = get_session()

    payload = {
        "input": {
            "bounds": {"bbox": bbox},
            "data": [{"type": "sentinel-1-grd",
                      "dataFilter": {
                          "timeRange": {"from": start, "to": end},
                          "acquisitionMode": "IW",
                          "polarization": "DV"
                      },
                      "processing": {
                          "orthorectify": True,
                          "backCoeff": "SIGMA0_ELLIPSOID"
                      }}]
        },
        "aggregation": {
            "timeRange": {"from": start, "to": end},
            "aggregationInterval": {"of": interval},
            "evalscript": """
//VERSION=3
function setup() {
  return {
    input: [{bands: ["VV","VH","dataMask"]}],
    output: [
      {id: "sar", bands: 4, sampleType: "FLOAT32"},
      {id: "dataMask", bands: 1, sampleType: "UINT8"}
    ]
  };
}
function evaluatePixel(s) {
  let eps = 1e-10;
  // Convert linear to dB to match GEE training data
  let vv_db   = 10 * Math.log10(s.VV + eps);
  let vh_db   = 10 * Math.log10(s.VH + eps);
  // RVI from linear
  let rvi     = (4 * s.VH) / (s.VV + s.VH + eps);
  // VHVV in dB
  let vhvv_db = vh_db - vv_db;
  return {
    sar: [vv_db, vh_db, rvi, vhvv_db],
    dataMask: [s.dataMask]
  };
}
"""
        },
        "calculations": {
            "sar": {
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
        bands = item['outputs']['sar']['bands']
        results.append({
            'date': date,
            'VV':   safe_float(bands['B0']['stats'].get('mean')),
            'VH':   safe_float(bands['B1']['stats'].get('mean')),
            'RVI':  safe_float(bands['B2']['stats'].get('mean')),
            'VHVV': safe_float(bands['B3']['stats'].get('mean')),
        })

    return results

if __name__ == '__main__':
    bbox = [-6.96, 52.82, -6.90, 52.86]
    results = get_s1_statistics(
        bbox,
        "2024-04-01T00:00:00Z",
        "2024-09-30T23:59:59Z"
    )
    print(f"\nS1 statistics: {len(results)} dekads")
    print(f"\n{'Date':<12} {'VV(dB)':>8} {'VH(dB)':>8} {'RVI':>7} {'VHVV':>7}")
    print("-" * 48)
    for r in results:
        def fmt(v): return f"{v:>8.3f}" if v is not None else "    None"
        print(f"{r['date']:<12}{fmt(r['VV'])}{fmt(r['VH'])}{fmt(r['RVI'])}{fmt(r['VHVV'])}")
