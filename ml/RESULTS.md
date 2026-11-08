# Harvest model results

The model is the mean of the linear Drivers model and gradient-boosted trees, fixed in `prereg/ML_PLAN.md` before any ML run; `ml/README.md` says why this model. The seasonal normal is the reference line.

Run: final (holdout scored).

## Areas (matched rows)

| Window | h | Outcome | seasonal | blend | better than seasonal | 80% band hit | n |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dev | 0 | log_avg_kg | 0.07509 (0.3539 kg per fish) | 0.07028 (0.3318 kg per fish) | 6.407% | 0.7674 | 506 |
| dev | 0 | log_count | 0.3043 (582600.0 fish) | 0.2674 (513600.0 fish) | 12.13% | 0.8021 | 506 |
| dev | 0 | log_kg | 0.3117 (2815.0 tonnes) | 0.2672 (2419.0 tonnes) | 14.29% | 0.8155 | 506 |
| dev | 1 | log_avg_kg | 0.08096 (0.3812 kg per fish) | 0.07994 (0.3773 kg per fish) | 1.261% | 0.7443 | 495 |
| dev | 1 | log_count | 0.3179 (615700.0 fish) | 0.2764 (527400.0 fish) | 13.03% | 0.8182 | 495 |
| dev | 1 | log_kg | 0.3258 (2984.0 tonnes) | 0.2732 (2433.0 tonnes) | 16.14% | 0.8352 | 495 |
| dev | 2 | log_avg_kg | 0.0818 (0.3853 kg per fish) | 0.08197 (0.3888 kg per fish) | -0.1979% | 0.7182 | 484 |
| dev | 2 | log_count | 0.3146 (614500.0 fish) | 0.2755 (550900.0 fish) | 12.41% | 0.8394 | 484 |
| dev | 2 | log_kg | 0.3247 (3004.0 tonnes) | 0.272 (2537.0 tonnes) | 16.23% | 0.8212 | 484 |
| dev | 3 | log_avg_kg | 0.0818 (0.3863 kg per fish) | 0.08195 (0.3905 kg per fish) | -0.1938% | 0.7071 | 462 |
| dev | 3 | log_count | 0.3079 (613000.0 fish) | 0.2803 (575800.0 fish) | 8.97% | 0.8384 | 462 |
| dev | 3 | log_kg | 0.3187 (3012.0 tonnes) | 0.2807 (2691.0 tonnes) | 11.92% | 0.8384 | 462 |
| holdout | 0 | log_avg_kg | 0.08703 (0.4204 kg per fish) | 0.07043 (0.3408 kg per fish) | 19.08% | 0.8095 | 231 |
| holdout | 0 | log_count | 0.2848 (620100.0 fish) | 0.2179 (499700.0 fish) | 23.5% | 0.8355 | 231 |
| holdout | 0 | log_kg | 0.2979 (3175.0 tonnes) | 0.222 (2468.0 tonnes) | 25.49% | 0.8182 | 231 |
| holdout | 1 | log_avg_kg | 0.0939 (0.4534 kg per fish) | 0.08133 (0.3947 kg per fish) | 13.39% | 0.7792 | 231 |
| holdout | 1 | log_count | 0.3055 (658600.0 fish) | 0.2366 (528700.0 fish) | 22.57% | 0.7965 | 231 |
| holdout | 1 | log_kg | 0.3188 (3386.0 tonnes) | 0.231 (2513.0 tonnes) | 27.54% | 0.7922 | 231 |
| holdout | 2 | log_avg_kg | 0.09669 (0.4663 kg per fish) | 0.0854 (0.4137 kg per fish) | 11.68% | 0.7716 | 232 |
| holdout | 2 | log_count | 0.3151 (669600.0 fish) | 0.2496 (549400.0 fish) | 20.77% | 0.7759 | 232 |
| holdout | 2 | log_kg | 0.3298 (3459.0 tonnes) | 0.2466 (2645.0 tonnes) | 25.22% | 0.8103 | 232 |
| holdout | 3 | log_avg_kg | 0.09894 (0.4772 kg per fish) | 0.09338 (0.4529 kg per fish) | 5.617% | 0.7457 | 232 |
| holdout | 3 | log_count | 0.3191 (674500.0 fish) | 0.2661 (605500.0 fish) | 16.62% | 0.7845 | 232 |
| holdout | 3 | log_kg | 0.3325 (3480.0 tonnes) | 0.2655 (2984.0 tonnes) | 20.14% | 0.8017 | 232 |

## Norway total (the areas forecast every month)

| Window | h | Outcome | seasonal | blend | better than seasonal | 80% band hit | n |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dev | 0 | log_count | 0.0775 (2024000 fish) | 0.06162 (1600000 fish) | 20.5% | 0.8529 | 46 |
| dev | 0 | log_kg | 0.07477 (9124 tonnes) | 0.05754 (6992 tonnes) | 23.04% | 0.7941 | 46 |
| dev | 1 | log_count | 0.07855 (2075000 fish) | 0.07649 (2021000 fish) | 2.633% | 0.7188 | 45 |
| dev | 1 | log_kg | 0.07569 (9322 tonnes) | 0.06591 (8127 tonnes) | 12.92% | 0.9375 | 45 |
| dev | 2 | log_count | 0.07745 (2069000 fish) | 0.06425 (1681000 fish) | 17.04% | 0.8 | 44 |
| dev | 2 | log_kg | 0.0741 (9230 tonnes) | 0.05852 (7218 tonnes) | 21.02% | 0.9333 | 44 |
| dev | 3 | log_count | 0.07822 (2109000 fish) | 0.06215 (1663000 fish) | 20.55% | 0.7037 | 42 |
| dev | 3 | log_kg | 0.07622 (9553 tonnes) | 0.06507 (7997 tonnes) | 14.64% | 0.7037 | 42 |
| holdout | 0 | log_count | 0.09197 (2603000 fish) | 0.05431 (1614000 fish) | 40.96% | 0.8571 | 21 |
| holdout | 0 | log_kg | 0.09988 (13460 tonnes) | 0.06041 (8298 tonnes) | 39.51% | 0.7143 | 21 |
| holdout | 1 | log_count | 0.1008 (2848000 fish) | 0.07455 (2179000 fish) | 26.06% | 0.8095 | 21 |
| holdout | 1 | log_kg | 0.1077 (14460 tonnes) | 0.08254 (11550 tonnes) | 23.39% | 0.4762 | 21 |
| holdout | 2 | log_count | 0.1033 (2907000 fish) | 0.06625 (1908000 fish) | 35.9% | 0.7143 | 21 |
| holdout | 2 | log_kg | 0.1091 (14590 tonnes) | 0.08145 (11250 tonnes) | 25.36% | 0.5714 | 21 |
| holdout | 3 | log_count | 0.1052 (2950000 fish) | 0.08778 (2589000 fish) | 16.55% | 0.619 | 21 |
| holdout | 3 | log_kg | 0.1114 (14900 tonnes) | 0.09484 (13500 tonnes) | 14.88% | 0.5238 | 21 |

MAE in log points (and natural units per area-month or per national month). h = 0 is last month (not yet published), 1 this month, 2 next month, 3 in two months.

## Final run

- Holdout scored at 2026-11-08T01:25.

## Caveats

- **Season guard (added after the first dev run, before any holdout run).** Area 1's season was fitted on 11-20 usable months, because its zero-harvest months drop out, and exploded (season terms of -1884 log points in early 2021). No forecast is made for an area-outcome until its season has 24 usable months. This leaves out area 13 and all but a few months of area 1.
- At h=0 the model's linear half reproduces the Drivers model in `analysis.nowcast` exactly (tested).
- Bands use only errors public by each issue date; the warm-up (from 2019) is never scored.
- Actuals are latest revised data, not first releases.
