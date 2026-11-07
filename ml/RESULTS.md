# ML challenger results

Exploratory; fixed in `prereg/ML_PLAN.md` before any ML run. F1 and F2 are unaffected.

Run: development window only; holdout locked.

## Production (areas, matched rows)

| Window | h | Outcome | seasonal | b0 | b1 | drivers | ml | blend | n |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dev | 0 | log_avg_kg | 0.07509 (0.3539 kg per fish) | 0.07408 (0.3499 kg per fish) | 0.07408 (0.3498 kg per fish) | 0.07494 (0.3544 kg per fish) | 0.06957 (0.3281 kg per fish) | 0.07028 (0.3318 kg per fish) | 506 |
| dev | 0 | log_count | 0.3043 (582600.0 fish) | 0.2721 (517300.0 fish) | 0.2719 (514900.0 fish) | 0.2694 (527700.0 fish) | 0.2805 (535000.0 fish) | 0.2674 (513600.0 fish) | 506 |
| dev | 0 | log_kg | 0.3117 (2815.0 tonnes) | 0.2698 (2412.0 tonnes) | 0.2688 (2400.0 tonnes) | 0.2727 (2537.0 tonnes) | 0.2789 (2510.0 tonnes) | 0.2672 (2419.0 tonnes) | 506 |
| dev | 1 | log_avg_kg | 0.08096 (0.3812 kg per fish) | 0.08006 (0.3779 kg per fish) | 0.07981 (0.3767 kg per fish) | 0.08222 (0.3874 kg per fish) | 0.0812 (0.3844 kg per fish) | 0.07994 (0.3773 kg per fish) | 495 |
| dev | 1 | log_count | 0.3179 (615700.0 fish) | 0.2695 (514200.0 fish) | 0.2723 (520800.0 fish) | 0.2765 (531200.0 fish) | 0.2879 (552600.0 fish) | 0.2764 (527400.0 fish) | 495 |
| dev | 1 | log_kg | 0.3258 (2984.0 tonnes) | 0.2655 (2375.0 tonnes) | 0.2676 (2402.0 tonnes) | 0.274 (2459.0 tonnes) | 0.2848 (2560.0 tonnes) | 0.2732 (2433.0 tonnes) | 495 |
| dev | 2 | log_avg_kg | 0.0818 (0.3853 kg per fish) | 0.08161 (0.386 kg per fish) | 0.08136 (0.3847 kg per fish) | 0.0857 (0.4052 kg per fish) | 0.08262 (0.3929 kg per fish) | 0.08197 (0.3888 kg per fish) | 484 |
| dev | 2 | log_count | 0.3146 (614500.0 fish) | 0.2727 (531900.0 fish) | 0.2719 (530200.0 fish) | 0.283 (578200.0 fish) | 0.2864 (568700.0 fish) | 0.2755 (550900.0 fish) | 484 |
| dev | 2 | log_kg | 0.3247 (3004.0 tonnes) | 0.2713 (2472.0 tonnes) | 0.271 (2471.0 tonnes) | 0.2787 (2666.0 tonnes) | 0.2832 (2625.0 tonnes) | 0.272 (2537.0 tonnes) | 484 |
| dev | 3 | log_avg_kg | 0.0818 (0.3863 kg per fish) | 0.08193 (0.3892 kg per fish) | 0.08198 (0.3895 kg per fish) | 0.08688 (0.4124 kg per fish) | 0.0831 (0.3966 kg per fish) | 0.08195 (0.3905 kg per fish) | 462 |
| dev | 3 | log_count | 0.3079 (613000.0 fish) | 0.2735 (547600.0 fish) | 0.2739 (548400.0 fish) | 0.286 (603300.0 fish) | 0.2865 (583900.0 fish) | 0.2803 (575800.0 fish) | 462 |
| dev | 3 | log_kg | 0.3187 (3012.0 tonnes) | 0.273 (2558.0 tonnes) | 0.273 (2557.0 tonnes) | 0.285 (2776.0 tonnes) | 0.2876 (2771.0 tonnes) | 0.2807 (2691.0 tonnes) | 462 |

MAE in log points (and natural units per area-month).

Winner rule: ml or blend replaces drivers only if its dev MAE on log kg at h=0 is at least 2% lower (prereg/ML_PLAN.md).
Result: `{'rule': 'ml or blend replaces drivers only if its dev MAE on log kg at h=0 is at least 2% lower (prereg/ML_PLAN.md)', 'model': 'blend', 'incumbent': 'drivers', 'challenger': 'blend', 'challenger_wins': True, 'margin_pct': 2.0, 'dev_mae': {'drivers': 0.2727, 'ml': 0.2789, 'blend': 0.2672}, 'improvement_pct': 2.017, 'leakage_check': False}`.

## Price (matched origins)

| Window | h | rw | ar | c0 | c1 | ml | blend | n |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dev | 1 | 0.03979 (3.359 NOK) | 0.03698 (3.107 NOK) | 0.03672 (3.114 NOK) | 0.03913 (3.305 NOK) | 0.03965 (3.351 NOK) | 0.03757 (3.176 NOK) | 202 |
| dev | 2 | 0.06335 (5.315 NOK) | 0.05834 (4.878 NOK) | 0.05977 (5.007 NOK) | 0.06752 (5.62 NOK) | 0.06235 (5.234 NOK) | 0.05852 (4.901 NOK) | 202 |
| dev | 3 | 0.07793 (6.553 NOK) | 0.06911 (5.771 NOK) | 0.0706 (5.926 NOK) | 0.08322 (6.974 NOK) | 0.07769 (6.564 NOK) | 0.07087 (5.966 NOK) | 202 |
| dev | 4 | 0.08891 (7.482 NOK) | 0.07555 (6.321 NOK) | 0.07701 (6.453 NOK) | 0.09763 (8.324 NOK) | 0.08389 (7.113 NOK) | 0.07597 (6.392 NOK) | 202 |
| dev | 5 | 0.1007 (8.444 NOK) | 0.08094 (6.749 NOK) | 0.0816 (6.824 NOK) | 0.1075 (9.25 NOK) | 0.0917 (7.624 NOK) | 0.08258 (6.897 NOK) | 202 |
| dev | 6 | 0.1136 (9.55 NOK) | 0.08668 (7.261 NOK) | 0.08904 (7.454 NOK) | 0.1166 (9.983 NOK) | 0.09729 (8.167 NOK) | 0.08829 (7.411 NOK) | 202 |
| dev | 7 | 0.1246 (10.52 NOK) | 0.09291 (7.803 NOK) | 0.09492 (7.975 NOK) | 0.1325 (11.25 NOK) | 0.1078 (9.073 NOK) | 0.09499 (7.977 NOK) | 202 |
| dev | 8 | 0.1376 (11.7 NOK) | 0.1016 (8.51 NOK) | 0.09932 (8.343 NOK) | 0.1482 (12.43 NOK) | 0.1178 (10.0 NOK) | 0.1023 (8.591 NOK) | 202 |

MAE in log price-change points (and NOK/kg).

Winner rule: ml or blend replaces the best of ar, c0 and c1 only if its dev MAE at h=4 is at least 2% lower (prereg/ML_PLAN.md).
Result: `{'rule': 'ml or blend replaces the best of ar, c0 and c1 only if its dev MAE at h=4 is at least 2% lower (prereg/ML_PLAN.md)', 'model': 'ar', 'incumbent': 'ar', 'challenger': 'blend', 'challenger_wins': False, 'margin_pct': 2.0, 'dev_mae': {'ar': 0.07555, 'c0': 0.07701, 'c1': 0.09763, 'ml': 0.08389, 'blend': 0.07597}, 'improvement_pct': -0.5559, 'leakage_check': False}`.

## Deviations and caveats

- **Season guard (added after the first dev run, before any holdout run).** Area 1's season was fitted on 11-20 usable months, because its zero-harvest months drop out, and exploded (season terms of -1884 log points in early 2021). Every model inherited it, including Production's B1 and Drivers. No forecast is made for an area-outcome until its season has 24 usable months. This applies to every model identically, and it excludes areas 1 and 13.
- At h=0 the b0/b1/drivers fits reproduce `analysis.nowcast` exactly (tested). At h=2-8, price ar and c0 reproduce `price_backtest.parquet` exactly. c1 differs by about 2e-4, because the authoritative national index replaces Price's temporary one.
- Bands use only errors public by each issue date; the warm-up (from 2019) is never scored.
- Actuals are latest revised data, not first releases.
