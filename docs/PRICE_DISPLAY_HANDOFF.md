# Pricing display handoff: use SISALMONI v2

**This is the pricing result to use in the presentation after merge.**

| Purpose | File |
| --- | --- |
| Frontend entry point | `web/public/data/price_display_manifest.json` |
| Canonical pricing-result payload | `web/public/data/price_sisalmoni_v2.json` |
| Actual versus predicted chart | `web/public/charts/price_sisalmoni_v2_actual_vs_predicted.vl.json` |
| Forecast-error chart | `web/public/charts/price_sisalmoni_v2_forecast_errors.vl.json` |
| Full evidence and limitations | `price/experiments/sisalmoni_v2/RESULTS.md` |
| Reproducible exporter | `python -m price.export_display` |

Browser paths omit `web/public/` and use the site's base path, for example
`data/price_sisalmoni_v2.json`. The manifest points to the payload and matching
charts so filenames do not need to be guessed. The exporter reads frozen v2
results and never retrains or reselects a model.

## Exact identity and labels

- Dataset ID: **`sisalmoni_v2`**.
- Target: **SISALMONI 3–6 kg index**.
- Currency/unit: **EUR/kg**.
- Display model: **Price-only Ridge v2**, ID **`ridge_level_a10`**, six price/calendar
  features, direct level target and alpha 10. It was selected in development.
- Status: **Experimental · retrospective evaluation**.
- Primary horizon: **four delivery-week shifts**. The target week starts 18 days
  after the normal Thursday issue; this is not four complete weeks after issue.
- Final target period: **2026-W21 to 2026-W44**, 18 May–26 October 2026,
  **24 matched forecasts** and **100% coverage**.

## Display fields and approved wording

Read the numbers from the JSON rather than hard-coding the rounded copy below.

| JSON field | Rounded display | Meaning |
| --- | --- | --- |
| `headline.mae_eur_per_kg` | **EUR 0.292/kg** | Average absolute price error |
| `headline.improvement_vs_no_change_pct` | **33.6% less error** | EUR/kg MAE reduction versus no change |
| `headline.improvement_vs_original_biology_pct` | **4.7% less error** | Reduction versus old c1 on the same 24 weeks |
| `headline.direction_accuracy_pct` | **79.2% correct direction** | 19 of 24 rise/fall calls |
| `evaluation.forecasts` | **24 forecasts** | The common final evaluation sample |

Place `uncertainty.must_display` beside the headline results. The 95% paired
block-bootstrap intervals include no benefit, and the declared 10% improvement
objective against the strongest baseline was not met. Use “promising retrospective
result”; do not describe it as independently validated or a guaranteed price edge.
The 79.2% figure measures direction, not overall price accuracy.

**Display selection and deployment recommendation are different fields.**
`display_model.id` is `ridge_level_a10`: this is the experiment being presented.
`recommendation.recommended_live_model_id` remains `rw`: no change is still the
conservative live default. Displaying Ridge does not change that recommendation.

`comparisons` contains the selected Ridge, no change and original biology model
on the same dates. `secondary_horizons` covers two through eight delivery weeks;
`backtest_h4` contains the 24 observed/forecast rows for a custom chart. The Vega
specs already contain the correct series and EUR axes.

## Other files have different purposes

| File | Identity | Use |
| --- | --- | --- |
| `web/public/data/price.json` | SSB export price, **NOK/kg** | Registered F2 archive, not the SISALMONI v2 headline |
| `web/public/data/outlook_price.json` | Earlier ML/SSB export-price outlook | Separate older target/model track |
| `price/RESULTS.md` | SSB/NOK evaluation | Historical registered price result |
| `price/experiments/sisalmoni/` | Original unstable SISALMONI OLS test | Different model and evaluation dates |
| `ridge_level_a100` in the v2 comparison table | Unselected secondary candidate | Not the frozen development-selected headline |
| `web/public/charts/price_backtest.vl.json` and the other unversioned price charts | SSB/NOK charts | Pair only with the SSB archive |

The old EUR 5.392/kg error uses 78 different target weeks and must not be compared
with v2's EUR 0.292/kg as if it were a matched improvement. The matched original
biology-model error in the v2 test is **EUR 0.306/kg**.

## Frontend wiring and merge handoff

The existing frontend's `web/src/data/files.ts` → `price` entry and `PriceSchema`
still load `price.json` as SSB/NOK. This change prepares an explicit integration
handoff; it does not silently change that schema or claim that the UI has already
been rewired. For the main pricing result, load the manifest's canonical payload
with its own type/schema, render the explicit EUR fields and use its two chart
paths. Keep the SSB F2 view separately labelled if it remains visible.

Include the exporter, this document, the manifest, the versioned payload/charts
and the v2 experiment/code/test files in the merge. No raw index download or
BarentsWatch credential is needed to display the committed package. The payload
records hashes of its frozen source artifacts; regenerating it is deterministic.
The root README, price README, shared contract and presentation notes all point
to this same package.
