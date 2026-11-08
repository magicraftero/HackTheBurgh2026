# ML challenger results

Exploratory; fixed in `prereg/ML_PLAN.md` before any ML run. F1 and F2 are unaffected.

Run: final (holdout scored).

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
| holdout | 0 | log_avg_kg | 0.08703 (0.4204 kg per fish) | 0.08708 (0.4209 kg per fish) | 0.08723 (0.4216 kg per fish) | 0.07577 (0.3671 kg per fish) | 0.06965 (0.3362 kg per fish) | 0.07043 (0.3408 kg per fish) | 231 |
| holdout | 0 | log_count | 0.2848 (620100.0 fish) | 0.2477 (571400.0 fish) | 0.249 (575100.0 fish) | 0.232 (536500.0 fish) | 0.2165 (497600.0 fish) | 0.2179 (499700.0 fish) | 231 |
| holdout | 0 | log_kg | 0.2979 (3175.0 tonnes) | 0.244 (2744.0 tonnes) | 0.2414 (2719.0 tonnes) | 0.2337 (2607.0 tonnes) | 0.2216 (2463.0 tonnes) | 0.222 (2468.0 tonnes) | 231 |
| holdout | 1 | log_avg_kg | 0.0939 (0.4534 kg per fish) | 0.09332 (0.451 kg per fish) | 0.09387 (0.4533 kg per fish) | 0.08263 (0.4005 kg per fish) | 0.08383 (0.4065 kg per fish) | 0.08133 (0.3947 kg per fish) | 231 |
| holdout | 1 | log_count | 0.3055 (658600.0 fish) | 0.2375 (540100.0 fish) | 0.2375 (539700.0 fish) | 0.2409 (542300.0 fish) | 0.2422 (540100.0 fish) | 0.2366 (528700.0 fish) | 231 |
| holdout | 1 | log_kg | 0.3188 (3386.0 tonnes) | 0.2362 (2622.0 tonnes) | 0.2363 (2613.0 tonnes) | 0.2384 (2623.0 tonnes) | 0.2373 (2602.0 tonnes) | 0.231 (2513.0 tonnes) | 231 |
| holdout | 2 | log_avg_kg | 0.09669 (0.4663 kg per fish) | 0.09412 (0.4552 kg per fish) | 0.09394 (0.4538 kg per fish) | 0.08616 (0.4172 kg per fish) | 0.08856 (0.4281 kg per fish) | 0.0854 (0.4137 kg per fish) | 232 |
| holdout | 2 | log_count | 0.3151 (669600.0 fish) | 0.2445 (549500.0 fish) | 0.2454 (558700.0 fish) | 0.2465 (551900.0 fish) | 0.2593 (562100.0 fish) | 0.2496 (549400.0 fish) | 232 |
| holdout | 2 | log_kg | 0.3298 (3459.0 tonnes) | 0.249 (2744.0 tonnes) | 0.2493 (2769.0 tonnes) | 0.2474 (2717.0 tonnes) | 0.2538 (2676.0 tonnes) | 0.2466 (2645.0 tonnes) | 232 |
| holdout | 3 | log_avg_kg | 0.09894 (0.4772 kg per fish) | 0.09463 (0.4578 kg per fish) | 0.09463 (0.4574 kg per fish) | 0.09415 (0.4552 kg per fish) | 0.09509 (0.4604 kg per fish) | 0.09338 (0.4529 kg per fish) | 232 |
| holdout | 3 | log_count | 0.3191 (674500.0 fish) | 0.2538 (580200.0 fish) | 0.2542 (582800.0 fish) | 0.2754 (648000.0 fish) | 0.2666 (591800.0 fish) | 0.2661 (605500.0 fish) | 232 |
| holdout | 3 | log_kg | 0.3325 (3480.0 tonnes) | 0.2567 (2892.0 tonnes) | 0.2566 (2889.0 tonnes) | 0.2701 (3119.0 tonnes) | 0.2692 (2957.0 tonnes) | 0.2655 (2984.0 tonnes) | 232 |

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
| holdout | 1 | 0.04576 (3.835 NOK) | 0.0437 (3.639 NOK) | 0.04191 (3.494 NOK) | 0.04108 (3.38 NOK) | 0.04222 (3.502 NOK) | 0.04142 (3.443 NOK) | 96 |
| holdout | 2 | 0.07184 (6.06 NOK) | 0.06877 (5.767 NOK) | 0.06494 (5.446 NOK) | 0.06488 (5.343 NOK) | 0.069 (5.737 NOK) | 0.0648 (5.42 NOK) | 96 |
| holdout | 3 | 0.08241 (6.979 NOK) | 0.07806 (6.601 NOK) | 0.07786 (6.61 NOK) | 0.07537 (6.233 NOK) | 0.07625 (6.39 NOK) | 0.07671 (6.47 NOK) | 96 |
| holdout | 4 | 0.08537 (7.229 NOK) | 0.08694 (7.314 NOK) | 0.08384 (7.121 NOK) | 0.08115 (6.698 NOK) | 0.08257 (6.954 NOK) | 0.08076 (6.826 NOK) | 96 |
| holdout | 5 | 0.09394 (7.896 NOK) | 0.09556 (7.965 NOK) | 0.0916 (7.744 NOK) | 0.08687 (7.105 NOK) | 0.08497 (7.087 NOK) | 0.08554 (7.181 NOK) | 96 |
| holdout | 6 | 0.1061 (8.869 NOK) | 0.1062 (8.815 NOK) | 0.1019 (8.651 NOK) | 0.09763 (8.103 NOK) | 0.0882 (7.279 NOK) | 0.09271 (7.759 NOK) | 96 |
| holdout | 7 | 0.1108 (9.264 NOK) | 0.1171 (9.682 NOK) | 0.1113 (9.475 NOK) | 0.1092 (9.205 NOK) | 0.09733 (8.212 NOK) | 0.1023 (8.652 NOK) | 96 |
| holdout | 8 | 0.1181 (9.858 NOK) | 0.126 (10.43 NOK) | 0.1196 (10.22 NOK) | 0.1205 (10.26 NOK) | 0.1117 (9.293 NOK) | 0.1134 (9.565 NOK) | 96 |

MAE in log price-change points (and NOK/kg).

Winner rule: ml or blend replaces the best of ar, c0 and c1 only if its dev MAE at h=4 is at least 2% lower (prereg/ML_PLAN.md).
Result: `{'rule': 'ml or blend replaces the best of ar, c0 and c1 only if its dev MAE at h=4 is at least 2% lower (prereg/ML_PLAN.md)', 'model': 'ar', 'incumbent': 'ar', 'challenger': 'blend', 'challenger_wins': False, 'margin_pct': 2.0, 'dev_mae': {'ar': 0.07555, 'c0': 0.07701, 'c1': 0.09763, 'ml': 0.08389, 'blend': 0.07597}, 'improvement_pct': -0.5559, 'leakage_check': False}`.

## When the holdout was opened

- supply: final run at 2026-11-07T23:47, before the 04:00 freeze, on the team's say-so.
- price: final run at 2026-11-07T23:51, before the 04:00 freeze, on the team's say-so.

## Deviations and caveats

- **Season guard (added after the first dev run, before any holdout run).** Area 1's season was fitted on 11-20 usable months, because its zero-harvest months drop out, and exploded (season terms of -1884 log points in early 2021). Every model inherited it, including Production's B1 and Drivers. No forecast is made for an area-outcome until its season has 24 usable months. This applies to every model identically, and it excludes areas 1 and 13.
- At h=0 the b0/b1/drivers fits reproduce `analysis.nowcast` exactly (tested). At h=2-8, price ar and c0 reproduce `price_backtest.parquet` exactly. c1 differs by about 2e-4, because the authoritative national index replaces Price's temporary one.
- Bands use only errors public by each issue date; the warm-up (from 2019) is never scored.
- Actuals are latest revised data, not first releases.
