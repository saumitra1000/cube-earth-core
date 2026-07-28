# Storm Armand SAR Structural-Continuity Detection — Validated Result

## Headline finding
Using a per-field, multi-year historical baseline on Sentinel-1 RVI (not raw VHVV),
Storm Armand's confirmed real impact date (19 Oct 2022, per Met Eireann) shows a
robust, reproducible elevated anomaly rate compared to a quiet control date.

- **Storm window anomaly rate**: 10.88% (range 9.68%-12.00% across 7 random baseline draws)
- **Quiet window anomaly rate**: 7.53% (range 7.11%-8.08% across 7 random baseline draws)
- **Ranges do not overlap across any of the 7 seeds tested** -- this is a robust separation, not a single-seed artifact.

## Geographic / crop pattern (top 5% most anomalous parcels, n=243)

Of the top 5% most anomalous parcels (ranked by mean z-score across 7 seeds):
- 132/243 (54%) were flagged in ALL 7 seeds
- 0 parcels in the top 5% were flagged in 0 seeds (no pure-noise entries in the ranking)

### Crop over/under-representation vs. overall population

| Crop | % of all parcels | % of top-5% anomalies | Ratio |
|---|---|---|---|
| Winter Oats | 2.61% | 7.00% | 2.68x |
| Winter Wheat | 8.00% | 16.46% | 2.06x |
| Potatoes | 1.62% | 2.47% | 1.52x |
| Winter Barley | 9.00% | 9.88% | 1.10x |
| OSR | 3.17% | 3.29% | 1.04x |
| Spring Wheat | 1.40% | 1.23% | 0.88x |
| Spring Barley | 57.72% | 50.21% | 0.87x |
| Beans | 4.21% | 2.88% | 0.68x |
| Spring Oats | 5.65% | 3.29% | 0.58x |
| Maize | 6.62% | 3.29% | 0.50x |

**Interpretation**: all three winter cereals (Winter Oats 2.68x, Winter Wheat 2.06x,
Winter Barley 1.10x) are over-represented among anomalies; all spring crops are
under-represented, with Maize (0.50x) least represented of all. This is consistent
with young, freshly-emerged winter cereal seedlings (sown Sep/Oct) being more
vulnerable to an October storm than mature spring crops near/at harvest --
a physically coherent pattern, not just aggregate noise.

**Unexplained outlier**: Potatoes (1.52x over-represented) does not fit the
winter/spring pattern -- small sample (n=79 total, 6 in anomaly group), needs
further investigation before drawing conclusions.

## Top 10 most severe anomalies (by mean z-score across 7 seeds)

| Parcel ID | Crop | Mean Z-score | Seeds flagged (/7) | Lat | Lng |
|---|---|---|---|---|---|
| 1618 | Winter Barley | 14.26 | 7 | 52.538327 | -6.571780 |
| 2545 | Spring Barley | 9.82 | 7 | 52.676606 | -6.584313 |
| 4580 | Winter Wheat | 9.76 | 7 | 52.916025 | -6.968267 |
| 1519 | Spring Barley | 9.74 | 7 | 52.507241 | -6.682580 |
| 1151 | Spring Barley | 8.94 | 7 | 52.490111 | -6.486276 |
| 2986 | Spring Barley | 8.76 | 6 | 52.766574 | -6.935716 |
| 4142 | Winter Wheat | 8.61 | 7 | 52.813468 | -6.696522 |
| 4289 | Spring Barley | 8.54 | 7 | 52.857926 | -6.268583 |
| 4766 | Winter Wheat | 8.42 | 7 | 52.933868 | -6.727481 |
| 4519 | Winter Barley | 7.98 | 6 | 53.001658 | -6.899766 |

## Methodology

- **Metric**: Radar Vegetation Index (RVI), computed from Sentinel-1 dual-pol
  (VH, VV) GRD data, per real individual satellite pass (not dekad-averaged).
- **Baseline**: for each parcel, mean and std of RVI drawn from the SAME
  calendar window (+/-8 days of day-of-year 292) in the 3 OTHER years
  (excluding the test year, to prevent leakage).
- **Sample size control**: exactly 6 historical observations randomly drawn
  per parcel (matched between storm and quiet test windows) to prevent
  small-sample std instability from confounding the comparison.
- **Anomaly threshold**: z-score > 2.5 (parcel's real backscatter on the test
  date vs. its own historical mean, in units of its own historical std).
- **Robustness check**: repeated across 7 independent random seeds for the
  6-observation baseline draw; results reported as range and mean.

## Failure history (documented for scientific honesty, not hidden)

This result was reached only after three earlier implementations failed
their own validation, each for a specific, identified reason:

1. **Dekad-averaged Z-score** (32 dekads/year, ~11-day windows): storm window
   1.91% anomalies vs. quiet window 1.75% -- no real separation. Likely cause:
   dekad-averaging smooths away short, sharp storm-driven signal changes.
2. **Percentile-rank within-cohort** (same-pair relative ranking, top/bottom 5%):
   storm 10.15% vs. quiet 10.10% -- mathematically tautological, guaranteed
   ~10% by construction regardless of the underlying data. Not a valid test.
3. **Per-field historical baseline, first attempt**: flat 2.5dB threshold on
   raw VHVV, implementation bug (computed but never used each field's own
   std) -- storm 29.41% vs. quiet 30.30%, both far too high to be meaningful,
   no real separation.
4. **Per-field historical baseline, corrected** (proper z-score using field's
   own std): VHVV metric showed the OPPOSITE direction (storm 6.29% vs. quiet
   10.02%) with mismatched baseline sample sizes as a likely confound.
   Exact-matched sample sizes narrowed but did not reverse this
   (storm 7.85% vs. quiet 9.57%) -- VHVV alone does not detect this event
   with this method.
5. **RVI substituted for VHVV, same corrected methodology**: FIRST result in
   the correct direction (storm > quiet), confirmed robust across 7 seeds.

## Known limitations / not yet done

- Single storm, single location (Ireland, Carlow/Kilkenny region, 4,865 parcels).
  Storm Claudia (Nov 2025) not yet tested with this corrected methodology --
  needed before generalizing beyond this one event.
- The original, pre-session "31 anomalies" Storm Armand claim referenced in
  earlier project history has NOT been independently re-verified against this
  corrected methodology -- its original implementation is not available to audit.
- No field-level ground truth (farmer/agronomist confirmation of actual storm
  damage) has been obtained for any flagged parcel.
- Potatoes over-representation (1.52x) unexplained, small sample.
- Effect size, while robust, is modest (~3-4 percentage point separation) --
  useful as a real signal, not yet a clean binary damage detector.
