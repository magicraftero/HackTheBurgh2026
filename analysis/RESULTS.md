# Production nowcast results

Real observations; expanding monthly windows; no random row split.
Development: 2021-01–2024-12, with eligible pre-2021 training. Holdout: 2025-01–2026-09.
Training/development covers 87 calendar months (2017-10–2024-12); the 21-month test remains separate.

## Available-row performance

MAE is in log units. Coverage counts scored area-months, out of 624 per development model/outcome.

| Training sample | Window | Family | Predictors | Outcome | MAE | Scored / total |
| --- | --- | --- | --- | --- | ---: | ---: |
| common_training | dev | catboost | b1 | log_avg_kg | 0.090976 | 493 / 624 |
| common_training | dev | catboost | b1 | log_count | 0.36288 | 493 / 624 |
| common_training | dev | catboost | b1 | log_kg | 0.37306 | 493 / 624 |
| common_training | dev | catboost | drivers | log_avg_kg | 0.090168 | 493 / 624 |
| common_training | dev | catboost | drivers | log_count | 0.36167 | 493 / 624 |
| common_training | dev | catboost | drivers | log_kg | 0.3819 | 493 / 624 |
| common_training | dev | ols | b0 | log_avg_kg | 0.0906 | 493 / 624 |
| common_training | dev | ols | b0 | log_count | 0.35573 | 493 / 624 |
| common_training | dev | ols | b0 | log_kg | 0.37043 | 493 / 624 |
| common_training | dev | ols | b1 | log_avg_kg | 0.090567 | 493 / 624 |
| common_training | dev | ols | b1 | log_count | 0.35465 | 493 / 624 |
| common_training | dev | ols | b1 | log_kg | 0.36868 | 493 / 624 |
| common_training | dev | ols | drivers | log_avg_kg | 0.091402 | 493 / 624 |
| common_training | dev | ols | drivers | log_count | 0.36173 | 493 / 624 |
| common_training | dev | ols | drivers | log_kg | 0.38033 | 493 / 624 |
| common_training | dev | ridge | b1 | log_avg_kg | 0.090595 | 493 / 624 |
| common_training | dev | ridge | b1 | log_count | 0.35569 | 493 / 624 |
| common_training | dev | ridge | b1 | log_kg | 0.36912 | 493 / 624 |
| common_training | dev | ridge | drivers | log_avg_kg | 0.090135 | 493 / 624 |
| common_training | dev | ridge | drivers | log_count | 0.36114 | 493 / 624 |
| common_training | dev | ridge | drivers | log_kg | 0.37949 | 493 / 624 |
| common_training | holdout | catboost | b1 | log_avg_kg | 0.092287 | 235 / 273 |
| common_training | holdout | catboost | b1 | log_count | 0.2881 | 235 / 273 |
| common_training | holdout | catboost | b1 | log_kg | 0.27519 | 235 / 273 |
| common_training | holdout | catboost | drivers | log_avg_kg | 0.08465 | 235 / 273 |
| common_training | holdout | catboost | drivers | log_count | 0.26919 | 235 / 273 |
| common_training | holdout | catboost | drivers | log_kg | 0.28608 | 235 / 273 |
| common_training | holdout | ols | b0 | log_avg_kg | 0.09246 | 235 / 273 |
| common_training | holdout | ols | b0 | log_count | 0.25854 | 235 / 273 |
| common_training | holdout | ols | b0 | log_kg | 0.25586 | 235 / 273 |
| common_training | holdout | ols | b1 | log_avg_kg | 0.092644 | 235 / 273 |
| common_training | holdout | ols | b1 | log_count | 0.26058 | 235 / 273 |
| common_training | holdout | ols | b1 | log_kg | 0.25318 | 235 / 273 |
| common_training | holdout | ols | drivers | log_avg_kg | 0.078105 | 233 / 273 |
| common_training | holdout | ols | drivers | log_count | 0.23587 | 233 / 273 |
| common_training | holdout | ols | drivers | log_kg | 0.24024 | 233 / 273 |
| common_training | holdout | ridge | b1 | log_avg_kg | 0.092644 | 235 / 273 |
| common_training | holdout | ridge | b1 | log_count | 0.26059 | 235 / 273 |
| common_training | holdout | ridge | b1 | log_kg | 0.25318 | 235 / 273 |
| common_training | holdout | ridge | drivers | log_avg_kg | 0.078105 | 233 / 273 |
| common_training | holdout | ridge | drivers | log_count | 0.23523 | 233 / 273 |
| common_training | holdout | ridge | drivers | log_kg | 0.24011 | 233 / 273 |
| available | dev | catboost | b1 | log_avg_kg | 0.088999 | 537 / 624 |
| available | dev | catboost | b1 | log_count | 0.35732 | 537 / 624 |
| available | dev | catboost | b1 | log_kg | 0.36828 | 537 / 624 |
| available | dev | catboost | drivers | log_avg_kg | 0.088628 | 537 / 624 |
| available | dev | catboost | drivers | log_count | 0.3574 | 537 / 624 |
| available | dev | catboost | drivers | log_kg | 0.3756 | 537 / 624 |
| available | dev | ols | b0 | log_avg_kg | 0.089018 | 537 / 624 |
| available | dev | ols | b0 | log_count | 0.35003 | 537 / 624 |
| available | dev | ols | b0 | log_kg | 0.36299 | 537 / 624 |
| available | dev | ols | b1 | log_avg_kg | 0.08917 | 537 / 624 |
| available | dev | ols | b1 | log_count | 0.3491 | 537 / 624 |
| available | dev | ols | b1 | log_kg | 0.36131 | 537 / 624 |
| available | dev | ols | drivers | log_avg_kg | 0.091402 | 493 / 624 |
| available | dev | ols | drivers | log_count | 0.36173 | 493 / 624 |
| available | dev | ols | drivers | log_kg | 0.38033 | 493 / 624 |
| available | dev | ridge | b1 | log_avg_kg | 0.089112 | 537 / 624 |
| available | dev | ridge | b1 | log_count | 0.35017 | 537 / 624 |
| available | dev | ridge | b1 | log_kg | 0.36288 | 537 / 624 |
| available | dev | ridge | drivers | log_avg_kg | 0.090135 | 493 / 624 |
| available | dev | ridge | drivers | log_count | 0.36114 | 493 / 624 |
| available | dev | ridge | drivers | log_kg | 0.37949 | 493 / 624 |
| available | holdout | catboost | b1 | log_avg_kg | 0.092175 | 235 / 273 |
| available | holdout | catboost | b1 | log_count | 0.2894 | 235 / 273 |
| available | holdout | catboost | b1 | log_kg | 0.30254 | 235 / 273 |
| available | holdout | catboost | drivers | log_avg_kg | 0.086373 | 235 / 273 |
| available | holdout | catboost | drivers | log_count | 0.26239 | 235 / 273 |
| available | holdout | catboost | drivers | log_kg | 0.29503 | 235 / 273 |
| available | holdout | ols | b0 | log_avg_kg | 0.092621 | 235 / 273 |
| available | holdout | ols | b0 | log_count | 0.25196 | 235 / 273 |
| available | holdout | ols | b0 | log_kg | 0.25238 | 235 / 273 |
| available | holdout | ols | b1 | log_avg_kg | 0.092207 | 235 / 273 |
| available | holdout | ols | b1 | log_count | 0.25302 | 235 / 273 |
| available | holdout | ols | b1 | log_kg | 0.24962 | 235 / 273 |
| available | holdout | ols | drivers | log_avg_kg | 0.078105 | 233 / 273 |
| available | holdout | ols | drivers | log_count | 0.23587 | 233 / 273 |
| available | holdout | ols | drivers | log_kg | 0.24024 | 233 / 273 |
| available | holdout | ridge | b1 | log_avg_kg | 0.092196 | 235 / 273 |
| available | holdout | ridge | b1 | log_count | 0.25303 | 235 / 273 |
| available | holdout | ridge | b1 | log_kg | 0.24962 | 235 / 273 |
| available | holdout | ridge | drivers | log_avg_kg | 0.078105 | 233 / 273 |
| available | holdout | ridge | drivers | log_count | 0.23523 | 233 / 273 |
| available | holdout | ridge | drivers | log_kg | 0.24011 | 233 / 273 |

## Matched-row comparisons

Positive improvement means the right-hand model has lower MAE.

| Training sample | Window | Outcome | Left | Right | Rows | MAE left | MAE right | Improvement % |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| common_training | dev | log_avg_kg | catboost_b1 | catboost_drivers | 493 | 0.090976 | 0.090168 | 0.88878 |
| common_training | dev | log_count | catboost_b1 | catboost_drivers | 493 | 0.36288 | 0.36167 | 0.33485 |
| common_training | dev | log_kg | catboost_b1 | catboost_drivers | 493 | 0.37306 | 0.3819 | -2.3701 |
| common_training | holdout | log_avg_kg | catboost_b1 | catboost_drivers | 235 | 0.092287 | 0.08465 | 8.276 |
| common_training | holdout | log_count | catboost_b1 | catboost_drivers | 235 | 0.2881 | 0.26919 | 6.5614 |
| common_training | holdout | log_kg | catboost_b1 | catboost_drivers | 235 | 0.27519 | 0.28608 | -3.9566 |
| common_training | dev | log_avg_kg | ols_b1 | ols_drivers | 493 | 0.090567 | 0.091402 | -0.92101 |
| common_training | dev | log_count | ols_b1 | ols_drivers | 493 | 0.35465 | 0.36173 | -1.9971 |
| common_training | dev | log_kg | ols_b1 | ols_drivers | 493 | 0.36868 | 0.38033 | -3.1605 |
| common_training | holdout | log_avg_kg | ols_b1 | ols_drivers | 233 | 0.089348 | 0.078105 | 12.583 |
| common_training | holdout | log_count | ols_b1 | ols_drivers | 233 | 0.2513 | 0.23587 | 6.1408 |
| common_training | holdout | log_kg | ols_b1 | ols_drivers | 233 | 0.24672 | 0.24024 | 2.6283 |
| common_training | dev | log_avg_kg | ridge_b1 | ridge_drivers | 493 | 0.090595 | 0.090135 | 0.50816 |
| common_training | dev | log_count | ridge_b1 | ridge_drivers | 493 | 0.35569 | 0.36114 | -1.5315 |
| common_training | dev | log_kg | ridge_b1 | ridge_drivers | 493 | 0.36912 | 0.37949 | -2.8088 |
| common_training | holdout | log_avg_kg | ridge_b1 | ridge_drivers | 233 | 0.089348 | 0.078105 | 12.583 |
| common_training | holdout | log_count | ridge_b1 | ridge_drivers | 233 | 0.25131 | 0.23523 | 6.3989 |
| common_training | holdout | log_kg | ridge_b1 | ridge_drivers | 233 | 0.24673 | 0.24011 | 2.6842 |
| common_training | dev | log_avg_kg | catboost_b1 | ols_b1 | 493 | 0.090976 | 0.090567 | 0.44937 |
| common_training | dev | log_count | catboost_b1 | ols_b1 | 493 | 0.36288 | 0.35465 | 2.2698 |
| common_training | dev | log_kg | catboost_b1 | ols_b1 | 493 | 0.37306 | 0.36868 | 1.1751 |
| common_training | holdout | log_avg_kg | catboost_b1 | ols_b1 | 235 | 0.092287 | 0.092644 | -0.38642 |
| common_training | holdout | log_count | catboost_b1 | ols_b1 | 235 | 0.2881 | 0.26058 | 9.5509 |
| common_training | holdout | log_kg | catboost_b1 | ols_b1 | 235 | 0.27519 | 0.25318 | 8.0007 |
| common_training | dev | log_avg_kg | catboost_drivers | ols_drivers | 493 | 0.090168 | 0.091402 | -1.3684 |
| common_training | dev | log_count | catboost_drivers | ols_drivers | 493 | 0.36167 | 0.36173 | -0.016926 |
| common_training | dev | log_kg | catboost_drivers | ols_drivers | 493 | 0.3819 | 0.38033 | 0.4122 |
| common_training | holdout | log_avg_kg | catboost_drivers | ols_drivers | 233 | 0.081749 | 0.078105 | 4.4571 |
| common_training | holdout | log_count | catboost_drivers | ols_drivers | 233 | 0.25061 | 0.23587 | 5.8787 |
| common_training | holdout | log_kg | catboost_drivers | ols_drivers | 233 | 0.27095 | 0.24024 | 11.335 |
| common_training | dev | log_avg_kg | catboost_b1 | ridge_b1 | 493 | 0.090976 | 0.090595 | 0.41867 |
| common_training | dev | log_count | catboost_b1 | ridge_b1 | 493 | 0.36288 | 0.35569 | 1.9823 |
| common_training | dev | log_kg | catboost_b1 | ridge_b1 | 493 | 0.37306 | 0.36912 | 1.0548 |
| common_training | holdout | log_avg_kg | catboost_b1 | ridge_b1 | 235 | 0.092287 | 0.092644 | -0.38628 |
| common_training | holdout | log_count | catboost_b1 | ridge_b1 | 235 | 0.2881 | 0.26059 | 9.5484 |
| common_training | holdout | log_kg | catboost_b1 | ridge_b1 | 235 | 0.27519 | 0.25318 | 7.9989 |
| common_training | dev | log_avg_kg | catboost_drivers | ridge_drivers | 493 | 0.090168 | 0.090135 | 0.036239 |
| common_training | dev | log_count | catboost_drivers | ridge_drivers | 493 | 0.36167 | 0.36114 | 0.14682 |
| common_training | dev | log_kg | catboost_drivers | ridge_drivers | 493 | 0.3819 | 0.37949 | 0.63082 |
| common_training | holdout | log_avg_kg | catboost_drivers | ridge_drivers | 233 | 0.081749 | 0.078105 | 4.4567 |
| common_training | holdout | log_count | catboost_drivers | ridge_drivers | 233 | 0.25061 | 0.23523 | 6.1363 |
| common_training | holdout | log_kg | catboost_drivers | ridge_drivers | 233 | 0.27095 | 0.24011 | 11.383 |
| common_training | dev | log_avg_kg | ols_b1 | ridge_b1 | 493 | 0.090567 | 0.090595 | -0.030846 |
| common_training | dev | log_count | ols_b1 | ridge_b1 | 493 | 0.35465 | 0.35569 | -0.29418 |
| common_training | dev | log_kg | ols_b1 | ridge_b1 | 493 | 0.36868 | 0.36912 | -0.12175 |
| common_training | holdout | log_avg_kg | ols_b1 | ridge_b1 | 235 | 0.092644 | 0.092644 | 0.00012993 |
| common_training | holdout | log_count | ols_b1 | ridge_b1 | 235 | 0.26058 | 0.26059 | -0.00281 |
| common_training | holdout | log_kg | ols_b1 | ridge_b1 | 235 | 0.25318 | 0.25318 | -0.001963 |
| common_training | dev | log_avg_kg | ols_drivers | ridge_drivers | 493 | 0.091402 | 0.090135 | 1.3857 |
| common_training | dev | log_count | ols_drivers | ridge_drivers | 493 | 0.36173 | 0.36114 | 0.16371 |
| common_training | dev | log_kg | ols_drivers | ridge_drivers | 493 | 0.38033 | 0.37949 | 0.21952 |
| common_training | holdout | log_avg_kg | ols_drivers | ridge_drivers | 233 | 0.078105 | 0.078105 | -0.00040246 |
| common_training | holdout | log_count | ols_drivers | ridge_drivers | 233 | 0.23587 | 0.23523 | 0.27365 |
| common_training | holdout | log_kg | ols_drivers | ridge_drivers | 233 | 0.24024 | 0.24011 | 0.054481 |
| available | dev | log_avg_kg | catboost_b1 | catboost_drivers | 537 | 0.088999 | 0.088628 | 0.4168 |
| available | dev | log_count | catboost_b1 | catboost_drivers | 537 | 0.35732 | 0.3574 | -0.020975 |
| available | dev | log_kg | catboost_b1 | catboost_drivers | 537 | 0.36828 | 0.3756 | -1.9869 |
| available | holdout | log_avg_kg | catboost_b1 | catboost_drivers | 235 | 0.092175 | 0.086373 | 6.2945 |
| available | holdout | log_count | catboost_b1 | catboost_drivers | 235 | 0.2894 | 0.26239 | 9.3337 |
| available | holdout | log_kg | catboost_b1 | catboost_drivers | 235 | 0.30254 | 0.29503 | 2.4838 |
| available | dev | log_avg_kg | ols_b1 | ols_drivers | 493 | 0.090682 | 0.091402 | -0.79361 |
| available | dev | log_count | ols_b1 | ols_drivers | 493 | 0.35163 | 0.36173 | -2.8714 |
| available | dev | log_kg | ols_b1 | ols_drivers | 493 | 0.36431 | 0.38033 | -4.3977 |
| available | holdout | log_avg_kg | ols_b1 | ols_drivers | 233 | 0.088926 | 0.078105 | 12.169 |
| available | holdout | log_count | ols_b1 | ols_drivers | 233 | 0.24602 | 0.23587 | 4.1249 |
| available | holdout | log_kg | ols_b1 | ols_drivers | 233 | 0.24271 | 0.24024 | 1.0184 |
| available | dev | log_avg_kg | ridge_b1 | ridge_drivers | 493 | 0.090683 | 0.090135 | 0.60405 |
| available | dev | log_count | ridge_b1 | ridge_drivers | 493 | 0.35274 | 0.36114 | -2.3791 |
| available | dev | log_kg | ridge_b1 | ridge_drivers | 493 | 0.36591 | 0.37949 | -3.7125 |
| available | holdout | log_avg_kg | ridge_b1 | ridge_drivers | 233 | 0.088965 | 0.078105 | 12.207 |
| available | holdout | log_count | ridge_b1 | ridge_drivers | 233 | 0.24602 | 0.23523 | 4.3883 |
| available | holdout | log_kg | ridge_b1 | ridge_drivers | 233 | 0.24271 | 0.24011 | 1.074 |
| available | dev | log_avg_kg | catboost_b1 | ols_b1 | 537 | 0.088999 | 0.08917 | -0.19198 |
| available | dev | log_count | catboost_b1 | ols_b1 | 537 | 0.35732 | 0.3491 | 2.2998 |
| available | dev | log_kg | catboost_b1 | ols_b1 | 537 | 0.36828 | 0.36131 | 1.8939 |
| available | holdout | log_avg_kg | catboost_b1 | ols_b1 | 235 | 0.092175 | 0.092207 | -0.034777 |
| available | holdout | log_count | catboost_b1 | ols_b1 | 235 | 0.2894 | 0.25302 | 12.569 |
| available | holdout | log_kg | catboost_b1 | ols_b1 | 235 | 0.30254 | 0.24962 | 17.493 |
| available | dev | log_avg_kg | catboost_drivers | ols_drivers | 493 | 0.090285 | 0.091402 | -1.237 |
| available | dev | log_count | catboost_drivers | ols_drivers | 493 | 0.35968 | 0.36173 | -0.5685 |
| available | dev | log_kg | catboost_drivers | ols_drivers | 493 | 0.37809 | 0.38033 | -0.5931 |
| available | holdout | log_avg_kg | catboost_drivers | ols_drivers | 233 | 0.083617 | 0.078105 | 6.5921 |
| available | holdout | log_count | catboost_drivers | ols_drivers | 233 | 0.24438 | 0.23587 | 3.4829 |
| available | holdout | log_kg | catboost_drivers | ols_drivers | 233 | 0.28011 | 0.24024 | 14.234 |
| available | dev | log_avg_kg | catboost_b1 | ridge_b1 | 537 | 0.088999 | 0.089112 | -0.12706 |
| available | dev | log_count | catboost_b1 | ridge_b1 | 537 | 0.35732 | 0.35017 | 2.0021 |
| available | dev | log_kg | catboost_b1 | ridge_b1 | 537 | 0.36828 | 0.36288 | 1.468 |
| available | holdout | log_avg_kg | catboost_b1 | ridge_b1 | 235 | 0.092175 | 0.092196 | -0.02343 |
| available | holdout | log_count | catboost_b1 | ridge_b1 | 235 | 0.2894 | 0.25303 | 12.567 |
| available | holdout | log_kg | catboost_b1 | ridge_b1 | 235 | 0.30254 | 0.24962 | 17.492 |
| available | dev | log_avg_kg | catboost_drivers | ridge_drivers | 493 | 0.090285 | 0.090135 | 0.1659 |
| available | dev | log_count | catboost_drivers | ridge_drivers | 493 | 0.35968 | 0.36114 | -0.40386 |
| available | dev | log_kg | catboost_drivers | ridge_drivers | 493 | 0.37809 | 0.37949 | -0.37228 |
| available | holdout | log_avg_kg | catboost_drivers | ridge_drivers | 233 | 0.083617 | 0.078105 | 6.5917 |
| available | holdout | log_count | catboost_drivers | ridge_drivers | 233 | 0.24438 | 0.23523 | 3.747 |
| available | holdout | log_kg | catboost_drivers | ridge_drivers | 233 | 0.28011 | 0.24011 | 14.28 |
| available | dev | log_avg_kg | ols_b1 | ridge_b1 | 537 | 0.08917 | 0.089112 | 0.064795 |
| available | dev | log_count | ols_b1 | ridge_b1 | 537 | 0.3491 | 0.35017 | -0.3047 |
| available | dev | log_kg | ols_b1 | ridge_b1 | 537 | 0.36131 | 0.36288 | -0.43408 |
| available | holdout | log_avg_kg | ols_b1 | ridge_b1 | 235 | 0.092207 | 0.092196 | 0.011343 |
| available | holdout | log_count | ols_b1 | ridge_b1 | 235 | 0.25302 | 0.25303 | -0.0021747 |
| available | holdout | log_kg | ols_b1 | ridge_b1 | 235 | 0.24962 | 0.24962 | -0.00080031 |
| available | dev | log_avg_kg | ols_drivers | ridge_drivers | 493 | 0.091402 | 0.090135 | 1.3857 |
| available | dev | log_count | ols_drivers | ridge_drivers | 493 | 0.36173 | 0.36114 | 0.16371 |
| available | dev | log_kg | ols_drivers | ridge_drivers | 493 | 0.38033 | 0.37949 | 0.21952 |
| available | holdout | log_avg_kg | ols_drivers | ridge_drivers | 233 | 0.078105 | 0.078105 | -0.00040246 |
| available | holdout | log_count | ols_drivers | ridge_drivers | 233 | 0.23587 | 0.23523 | 0.27365 |
| available | holdout | log_kg | ols_drivers | ridge_drivers | 233 | 0.24024 | 0.24011 | 0.054481 |

## Selection and numerical limitations

Challenger selection: {"family": "ridge", "mae": {"catboost_b1": 0.3730598534311496, "catboost_drivers": 0.38190192900618447, "ridge_b1": 0.3691247434206026, "ridge_drivers": 0.379492832851833}, "model": "b1", "n_matched": 493, "reason": "matched_development_log_kg_mae"}.
Official OLS uses identical complete-Drivers training rows across B0/B1/Drivers. The common_training challenger track uses those same training rows; available allows each model its own eligible rows, including CatBoost's native missing predictors.
All families receive identical numerical feature lists. No area identifiers were added.
Ridge scales predictors inside each training fold. CatBoost early stopping uses an earlier month's own vintage and already-published labels.
Candidate selection uses at most 12 earlier development validation months and at least 3 usable validation months; initial choices are fixed defaults.
A seasonal preparation bug was corrected by rejecting unidentified or catastrophically ill-conditioned seasonal designs; registered terms and transformations were preserved. See PREPARATION_FIX.md.
Sparse area 1 can still have extreme finite seasonal reconstructions even after that correction; no prediction or reconstruction was clipped. Area 13 often has no reconstruction base.

Area 1: {"actual_area_months": 108, "target_base_missing": {"log_avg_kg": 44, "log_count": 44, "log_kg": 44}, "target_base_range": {"log_avg_kg": {"max": 9.141032044484511, "min": 1.2078197708348162}, "log_count": {"max": 39.32719608445965, "min": 2.0420651749478225}, "log_kg": {"max": 48.46822812894423, "min": 3.5855043183147206}}, "undefined_log_targets": 36, "zero_harvest_months": 36}.
Area 13: {"actual_area_months": 108, "target_base_missing": {"log_avg_kg": 69, "log_count": 69, "log_kg": 69}, "target_base_range": {"log_avg_kg": {"max": null, "min": null}, "log_count": {"max": null, "min": null}, "log_kg": {"max": null, "min": null}}, "undefined_log_targets": 47, "zero_harvest_months": 47}.

Finite log-prediction range across exported forecasts: 0.622034 to 48.4294.

Failures, training sizes, year/area errors and pairwise matched coverage are in nowcast_challengers.json; prediction-level flags are in the Parquet files.
Ordinary logs remain undefined for zero harvests. Missing outcome bases cannot be repaired by Ridge or CatBoost.
Actuals are revised observations, not archived first releases. Capacity weights use today's register and publication dates approximate historical schedules.
Available-row differences can reflect coverage; interpret estimator comparisons using the common_training track and matched rows.

## Registered F1

{"cw_p": 0.010672025884969844, "cw_stat": 2.301842572058835, "improvement_pct": 2.6282513412514197, "mae_b1": 0.2467234236476493, "mae_drivers": 0.24023891195644853, "n_matched": 233, "n_months": 21, "pass": false, "reason": "ok", "window": "holdout"}

## Final execution timing

Run started 2026-11-08T01:41:47.113879+00:00, before the originally scheduled 2026-11-08T04:00:00+00:00 freeze, at the user's explicit request. Development selection and all model configurations remained locked.
