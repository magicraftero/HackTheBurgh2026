# SISALMONI source verification

Checked on 8 November 2026 before scoring the target experiment.

## Target and coverage

The official public [price-history page](https://salmonprice.com/fishpool/public/priceHistory)
labels observations from 2024 week 32 as SISALMONI. Its public data endpoint is
`https://salmonprice.com/fishpool/servlets/newt/public/json/fpiAverages?year=YEAR`.
The endpoint and JSON field names retain the older FPI naming.

The downloaded 2024, 2025 and 2026 responses contain 117 consecutive unique weeks,
2024-W32 through 2026-W44. December 2025 includes week 1 of ISO year 2026;
settlement years must not be treated as ISO years without that correction.
Original responses are cached locally in `data/raw/sisalmoni/` and hashed in the
experiment provenance. No index history predating the SISALMONI launch is used.

## Currency and benchmark checks

The target is the **3–6 kg SISALMONI EUR/kg benchmark**, not the all-size average.
[Sitagri's definition](https://www.sitagri.com/sitagri-salmon-index/) distinguishes
these benchmarks and identifies the EUR 3–6 kg series as the Euronext settlement
reference.

Two exact observations were checked against original published reports:

| Delivery week | Public JSON fpiEUR | Original report SISALMONI 3–6 kg EUR/kg |
| --- | --- | --- |
| 2024-W33 | 6.20 | 6.20 |
| 2025-W26 | 5.56 | 5.56 |

Sources: [2024-W33 EUR report](https://salmonprice.com/fishpool/servlets/newt/public/json/files?action=download&category=eur&month=8&type=nasdaq&week=33&year=2024),
[2025-W26 EUR report](https://salmonprice.com/fishpool/servlets/newt/public/json/files?action=download&category=eur&month=6&type=nasdaq&week=26&year=2025).
The PDF download URL also retains a legacy `type=nasdaq` parameter; the actual
report title and benchmark are SISALMONI. No Nasdaq observations are used.

The 2024 NOK field is unsuitable for this target: in week 33 the JSON gives 73.04,
whereas the [original pure SISALMONI NOK report](https://salmonprice.com/fishpool/servlets/newt/public/json/files?action=download&category=nok&month=8&type=nasdaq&week=33&year=2024)
gives 73.19. [Fish Pool's transition explanation](https://fishpool.eu/wp-content/uploads/2024/08/ABC-Fish-Pool-contracts-at-Euronext.pdf)
explains that the 2024 NOK settlement remained a 95% SISALMONI / 5% SSB blend,
while the EUR settlement used pure SISALMONI. This is why the model is evaluated
in EUR/kg rather than silently testing the composite NOK column.

## Publication timing

The 2024-W33 report states that subscribers receive the report on Tuesday and
it is made public on Wednesday around 15:00. The experiment therefore uses
Thursday midnight of the following week (delivery-week Monday plus 10 days),
or the SSB export-volume release if later, as the combined issue date. This
avoids assuming the public index was known at Wednesday midnight. Exact holiday
and exceptional-release timings are not available in the yearly history, so
these dates remain a conservative normal-week reconstruction, not verified
historical release timestamps for every observation.
