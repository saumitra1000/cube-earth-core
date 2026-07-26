# National HLS Classifier v1 -- Results

## Headline
- Parcels used: 61,566 (target 61,866; see Known Issues below)
- Balanced accuracy (held-out test set): 77.05%
- Original national baseline: 71.70%
- Improvement: +5.35 points

## Per-class performance

| Crop | Support | Recall | F1 |
|---|---|---|---|
| Barley - Spring | 6638 | 75.2% | 83.9% |
| Barley - Winter | 1571 | 86.1% | 86.8% |
| Maize | 1126 | 94.6% | 87.0% |
| Oats - Spring | 1009 | 72.1% | 50.6% |
| Oats - Winter | 263 | 76.8% | 67.9% |
| Rye | 100 | 64.0% | 49.2% |
| Wheat - Spring | 291 | 61.2% | 45.4% |
| Wheat - Winter | 1316 | 86.6% | 85.4% |

## Known issues / open questions (unresolved as of this run)

1. **300 missing parcels (61,566 vs target 61,866).** Cause not confirmed. Likely
   explanation: parcels with zero valid (cloud-free) observations across all 4
   years, which the pipeline correctly excludes rather than fill with bad data --
   but this is NOT verified. The original 61,866-parcel raw file needed to diff
   exact parcel IDs was lost to an environment reset before this could be checked.
   If these 300 are disproportionately from small classes (Rye n=100, Wheat-Spring
   n=291 in this test set alone), real-world minority-class reliability could be
   worse than this report shows.

2. **Comparison to original 71.7% baseline's per-class breakdown: not available.**
   This report only has the original baseline's overall accuracy, not its
   per-crop numbers. Any claim about specific per-crop regression/improvement
   vs. the original model (e.g. for Wheat-Spring, Rye) is UNVERIFIED until that
   breakdown is located and compared directly.

3. **Original baseline's exact validation methodology not independently confirmed.**
   This run used: stratified 68/12/20 train/val/test split, balanced_accuracy_score,
   class_weights='balanced'. Assumed but not verified that the original 71.7%
   figure was computed the same way.

4. **Random Forest tested with identical methodology for comparison: 52.54%
   balanced accuracy** -- collapsed badly on minority classes (Wheat-Spring
   recall 7.6%, Rye 13.0%) despite class_weight='balanced' being set. CatBoost
   clearly the better choice for this dataset/imbalance.

## Methodology
- CatBoost, iterations=1500, lr=0.04, depth=6, class_weights='balanced', early
  stopping (80 rounds), best iteration 926/1500
- Train/val/test split: 68%/12%/20%, stratified
- Features: NDVI, EVI, NDWI, NDRE, NDII, all computed directly from raw HLS
  bands (B02-B11) -- NOT AppEEARS' precomputed VI product (unavailable for this
  national task submission) -- 32 dekads x 4 years = 640 features/parcel
- Fmask quality screen applied (cloud, shadow, water, snow, high aerosol)
- 21.1% of raw observations passed quality screen (consistent with regional set)

## NOT yet done
- Not deployed to live site (dashboard/Methodology page still show 71.7% S2-only model)
- Confidence calibration (isotonic) not yet applied to this model
