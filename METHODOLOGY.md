# Sentinel-1 SAR Integration: From Crop Classification to Structural Monitoring

## Summary

This document records an investigation into whether Sentinel-1 SAR data
improves parcel-level crop classification, and the pipeline redesign that
followed a clean negative result. It includes a worked case study —
independent corroboration of a detected structural anomaly cluster against
a documented storm event — as a demonstration of the resulting structural
monitoring framework.

---

## Phase 1 — Crop Classification

### Objective

Evaluate whether Sentinel-1 SAR improves parcel-level crop classification
beyond a Sentinel-2 HLS optical baseline.

### Optical Baseline

- **Data**: Sentinel-2 HLS (2022–2025), parcel-level spectral indices
  (NDVI, EVI, NDWI, NDRE, NDII), 32-dekad time series
- **Model**: CatBoost classifier
- **Result**: 86.43% accuracy on ~4,865 labeled parcels

### SAR Evaluation

SAR representations evaluated: VV, VH, VH/VV ratio, Radar Vegetation
Index (RVI), Dual-Polarisation RVI (DpRVIc), each as a 32-dekad time
series matching the HLS structure.

**Data quality issues found and resolved before results could be
trusted:**

1. The SAR feature file initially used for fusion (`sar_scene_features.csv`)
   contained only a single year (2025) of data — 164 columns instead of
   the expected 644 (4 years × 5 metrics × 32 dekads) — versus the HLS
   baseline's full 2022–2025 coverage. This was traced to the training
   script referencing a stale/incomplete extraction output rather than
   the complete dataset.

2. A second SAR extraction (`sar_e84_features.csv`, sourced via a STAC
   catalog / Element84) was found to pull ~131 scenes/year per parcel
   across multiple orbit tracks and acquisition times (both ascending
   and descending passes, mixed swaths), compared to a separate
   zonal-statistics extraction (`sar_zonal_features.csv`) with a clean,
   consistent ~28 scenes/year single-track series. Cross-checking the
   same parcel/dekad/year between the two sources showed matching
   summary statistics but a Pearson correlation of only **0.21** at
   the individual-observation level — indicating the two extraction
   methods frequently disagree on the same nominal measurement,
   consistent with incidence-angle and geometry differences between
   mixed orbit passes. `sar_zonal_features.csv` (single consistent
   orbit, full 4-year coverage) was adopted as the trustworthy SAR
   source for all subsequent testing.

**Corrected fusion result** (HLS + `sar_zonal_features.csv`, same
train/test split):

| Model | Accuracy |
|---|---|
| HLS only | 86.43% |
| HLS + clean multi-year SAR | 84.99% |

**Feature importance** (CatBoost, fused model):

| Source | Share of importance |
|---|---|
| HLS | 88.7% |
| SAR | 11.3% |

No SAR-derived variable appeared among the top 20 predictors by
importance. SAR features carried a lower median importance than HLS
features even after correcting the coverage and orbit-consistency
issues above.

### Conclusion

For the parcel-level feature representation and models evaluated here,
Sentinel-1 C-band SAR (VV, VH, VH/VV, RVI, DpRVIc) did not improve crop
classification beyond the multi-year Sentinel-2 HLS optical baseline.
This is a clean result — obtained only after correcting two independent
SAR data-quality problems — not an artifact of incomplete or noisy SAR
input.

**Interpretation**: crop-type classification depends on
species-discriminative spectral and phenological signal (chlorophyll
content, senescence timing, canopy color), which HLS optical bands
already capture directly. SAR backscatter responds primarily to canopy
structure and moisture — informative for structural parameters, but
largely redundant with, rather than additive to, what NDVI/EVI/NDRE
already encode for the classification task specifically.

---

## Phase 2 — Structural Monitoring

The negative classification result reframed the question: rather than
"does SAR help identify crop type," the literature (Fieuzal et al. 2013;
Veloso et al., MCM'10 campaign) suggests SAR is well suited to *canopy
structure retrieval* (LAI, crop height) — a different task, better
matched to what the sensor physically measures.

### Constraint: No Ground Truth

No field-measured canopy height or LAI observations exist in this
dataset. Directly reproducing published regression coefficients (e.g.
Fieuzal's French wheat/rapeseed calibrations) onto Irish parcels would
not be defensible — different soils, row spacings, cultivars, and
maritime climate invalidate a direct transfer. The framework therefore
adopts **relative structural monitoring** rather than absolute
biophysical retrieval.

### Pipeline

Sentinel-2 HLS
│
▼
Crop Classification (86.4%)
│
▼
Known Crop Type
│
▼
Sentinel-1 VH/VV (clean, single-orbit)
│
▼
Historical Crop Baseline (per crop, per dekad)
│
▼
Structural Divergence Score
│
▼
Weather Corroboration
│
▼
Confidence Tier

### Structural Divergence Scoring

For each crop type, a historical reference trajectory is built per
dekad by pooling VH/VV across all four years:

- Median, 25th/75th percentile, and Median Absolute Deviation (MAD)

Two scoring methods were implemented and compared:

1. **Robust z-score**: `0.6745 × (x − median) / MAD`
2. **Percentile rank** within the crop/dekad cohort

**Skew check**: VH/VV distributions were found to be consistently
left-skewed across all crops and dekads tested (Spring Barley: −0.38 to
−0.79 depending on dekad; Winter Wheat: −0.23 to −0.45; OSR: −0.34 to
−0.90), most pronounced early in the season (low-canopy conditions,
consistent with the angular/soil-moisture sensitivity reported by
Fieuzal et al. at low NDVI). This skew caused the z-score method to
flag structural declines at roughly 1.7× the rate of structural surges
— a statistical artifact of applying a symmetric measure to an
asymmetric distribution, not a real agronomic asymmetry. **Percentile
rank was adopted as the production scoring method**, producing a
near-symmetric flag distribution (28,073 declines vs 28,365 surges
across ~623K parcel-dekad observations).

Cohort-size gating: local cohorts below a minimum size (default: 15
parcels) fall back to a broader crop-level national baseline to avoid
unstable percentile/MAD estimates from thin samples.

Flags produced: `structural_decline`, `below_trajectory`,
`normal_development`, `above_trajectory`, `structural_surge`; a
separate trend flag (`sudden_negative_shift` / `sudden_positive_shift`)
captures abrupt dekad-to-dekad changes.

**Important**: these outputs describe departures from the crop's own
historical behavior — not estimates of LAI, canopy height, or any
absolute biophysical quantity.

### Weather Corroboration

Weather does not create or define an anomaly; it provides supporting
context for interpreting one already detected from SAR. Open-Meteo
historical daily rainfall (`precipitation_sum`) and wind
(`windspeed_10m_max`) are checked in a 4-day window preceding each
flagged parcel/dekad observation.

Confidence tiers:

| Condition | Confidence |
|---|---|
| Abrupt decline + storm-tier rain/wind (≥20mm or ≥60km/h) | High |
| Abrupt decline, no storm event found | Medium |
| Gradual/sustained deviation, no abrupt shift | Low |
| Structural surge (any) | Low |

Language is deliberately hedged: a high-confidence flag states the
anomaly is *consistent with* possible lodging or storm damage, not that
lodging is confirmed. Harvest timing, management operations, and
extraction artifacts remain plausible alternative explanations that
SAR and weather data alone cannot rule out.

**Implementation note**: weather lookups were batched by shared date
(Open-Meteo supports up to 1,000 locations per call for a given date
range) rather than queried per-row, reducing a ~56,000-row enrichment
task from an estimated ~3 hours of sequential calls to 109 total API
calls.

---

## Case Study: Late October 2022

The detector flagged **38 high-confidence structural anomalies**,
characterized by:

- Concentrated in a single year (2022)
- Clustered in a single dekad (dekad 26, approx. late October)
- Spanning multiple crop types (Spring Barley, Winter Wheat, Spring
  Wheat, Maize) and multiple, unrelated parcels
- Concurrent rainfall of approximately 20.2–42.8 mm and wind speeds of
  approximately 25.3–44.9 km/h in the preceding days at each flagged
  parcel's location. Note the lower end of the wind range (25.3 km/h)
  is well below the storm-tier threshold (60 km/h) used in confidence
  classification — a meaningful share of these 38 rows were flagged
  high-confidence on elevated rainfall alone, not combined wind+rain,
  so "storm" should be read loosely here rather than implying
  uniformly severe gusts across every flagged parcel.

Rather than appearing randomly across the four-year dataset, these
anomalies formed a coherent temporal and geographic cluster.

**Independent corroboration**: publicly documented European windstorm
records show a storm system (named Armand by Portugal's IPMA; Georgina
in Germany) affecting Ireland around 21–23 October 2022, with strong
gales and heavy rain, consistent with the flagged dekad window. Note
this system does not appear on Met Éireann's official storm-naming list
for the 2022/23 season, which may reflect a naming/threshold
difference rather than the absence of a real weather event; an
Ireland-specific primary source (Met Éireann historical bulletin) would
strengthen this corroboration further.

This does not prove that the flagged parcels experienced lodging
specifically — no field observations exist to confirm cause — but it
demonstrates that the structural divergence detector is sensitive to a
real, independently documented disturbance event, using zero
calibration data.

---

## Current System Architecture

Layer 1: Sentinel-2 HLS → Crop Classification
Layer 2: Sentinel-1 → Relative Structural Divergence
Layer 3: Weather Context → Confidence Assessment
Output: Crop identity + structural status + supporting environmental context

---

## Limitations

- No field-measured canopy height, LAI, or biomass data exists for
  calibration or validation of absolute structural estimates.
- Structural anomalies cannot be conclusively attributed to a specific
  cause (lodging vs. harvest vs. management vs. artifact) without
  independent field or imagery validation.
- The framework currently produces relative structural assessments only,
  not absolute biophysical quantities.
- Regional/local cohorting is not yet implemented — reference
  trajectories are currently pooled at the national crop level; true
  local (e.g. county-level) cohorts may reduce geographic variability
  but require sufficient per-cohort sample sizes to remain statistically
  stable.
- The October 2022 case study is a single worked example; broader
  validation against additional documented weather events across more
  years would strengthen confidence in the detector generally.

## Future Work

- Build region-specific crop cohorts (subject to minimum sample size)
  to reduce geographic variability in reference trajectories.
- Validate anomaly detection against additional independently
  documented weather events across multiple years.
- Incorporate persistence across consecutive dekads into the confidence
  score (a single-dekad anomaly vs. a multi-dekad sustained deviation
  likely warrant different confidence weighting).
- If field measurements become available, develop crop-specific
  regression models for canopy height or LAI using local calibration
  data, rather than relative divergence scoring alone.
- Obtain an Ireland-specific primary source (Met Éireann bulletin) for
  the October 2022 case study to strengthen the corroboration beyond
  general European windstorm records.

---

*Compiled from an internal investigation into SAR/optical fusion for
Cube Earth's Irish tillage crop classification and monitoring pipeline.*
