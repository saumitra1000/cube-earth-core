# National HLS Classifier v1 -- Results

- Parcels: 61566 (61,866 target; 300 excluded, no valid observations in any of 4 years)
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

## Methodology

- CatBoost, iterations=1500, lr=0.04, depth=6, class_weights='balanced', early stopping (80 rounds)
- Train/val/test split: 68%/12%/20%, stratified
- Features: NDVI, EVI, NDWI, NDRE, NDII, all computed directly from raw HLS bands (B02-B11), 32 dekads x 4 years
- Random Forest tested with identical methodology for comparison: 52.54% balanced accuracy (collapsed on minority classes)
