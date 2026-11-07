"""Render the three Price Vega-Lite v5 specs from price.json alone."""

import argparse
import json
from pathlib import Path
import sys

import altair as alt
from charts.theme import PANEL_WIDTH, model_scale, register
from price.calendar import week_start
from price.io import atomic_write

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "Source: Statistics Norway 03024; latest revised data."
DRIVERS_SOURCE = "Drivers: Directorate of Fisheries, Norges Bank, BarentsWatch."


def waiting(title, reason):
    return alt.Chart(alt.Data(values=[{"message": reason}])).mark_text(align="center").encode(
        text="message:N").properties(title=alt.TitleParams(title, subtitle=[SOURCE]), width=PANEL_WIDTH)


def scorecard(payload):
    panels = []
    for window in ["dev", "holdout"]:
        rows = [r for r in payload["scorecard"] if r["window"] == window and r["model"] != "rw"]
        if not rows:
            continue
        dates = " to ".join(payload["windows"][window])
        line = alt.Chart(alt.Data(values=rows)).mark_line(point=True).encode(
            x=alt.X("h:Q", title="Forecast horizon (ISO weeks)", axis=alt.Axis(values=list(range(2, 9)), format="d")),
            y=alt.Y("mae_ratio:Q", title="MAE / random-walk MAE (lower is better)", scale=alt.Scale(zero=False)),
            color=alt.Color("model:N", scale=model_scale(["ar", "c0", "c1"]), title="Model"),
            tooltip=["model:N", "h:Q", alt.Tooltip("mae:Q", title="MAE (log points)", format=".4f"),
                     alt.Tooltip("mae_ratio:Q", format=".3f"), alt.Tooltip("hit_rate:Q", format=".1%")])
        rule = alt.Chart(alt.Data(values=[{"baseline": 1}])).mark_rule(strokeDash=[5, 4]).encode(y="baseline:Q")
        panels.append((line + rule).properties(width=PANEL_WIDTH, title=alt.TitleParams(
            f"Price forecast errors — {window}: {dates}", subtitle=[SOURCE, DRIVERS_SOURCE, "MAE measured on log price changes; matched origins."])))
    if not panels:
        return waiting("Price forecast errors", "No scored price forecasts available yet")
    return panels[0] if len(panels) == 1 else alt.vconcat(*panels)


def by_year(payload):
    rows = [{"year": r["year"], "model": model, "mae": r["mae_" + model]}
            for r in payload["by_year"] for model in ["c0", "c1"] if r["mae_" + model] is not None]
    if not rows:
        return waiting("Four-week price errors by year", "Yearly scores are not available yet")
    return alt.Chart(alt.Data(values=rows)).mark_bar().encode(
        x=alt.X("year:O", title="Target ISO year", axis=alt.Axis(labelAngle=0)), xOffset="model:N",
        y=alt.Y("mae:Q", title="MAE (log price-change points)"),
        color=alt.Color("model:N", scale=model_scale(["c0", "c1"]), title="Model"),
        tooltip=["year:O", "model:N", alt.Tooltip("mae:Q", format=".4f")]
    ).properties(width=PANEL_WIDTH, title=alt.TitleParams("Four-week price errors by year",
        subtitle=[SOURCE, DRIVERS_SOURCE, "2021–2024 development; 2025–2026 holdout appears only after the final run."]))


def backtest(payload):
    rows = payload["backtest_h4"]
    if not rows:
        return waiting("Historical prices and four-week forecasts",
                       "Holdout replay unavailable — results remain unscored until the final run")
    data = [{**r, "date": week_start(r["week"]).date().isoformat()} for r in rows]
    lines = [{"date": r["date"], "week": r["week"], "model": name, "price": r[key]}
             for r in data for name, key in [("actual", "actual"), ("c0", "pred_c0"), ("c1", "pred_c1")]]
    band = alt.Chart(alt.Data(values=data)).mark_area().encode(
        x="date:T", y="p10:Q", y2="p90:Q",
        tooltip=["week:N", "band_model:N", alt.Tooltip("p10:Q", format=".2f"), alt.Tooltip("p90:Q", format=".2f")])
    line = alt.Chart(alt.Data(values=lines)).mark_line().encode(
        x=alt.X("date:T", title="Target ISO week (Monday)"),
        y=alt.Y("price:Q", title="Fresh salmon export price (NOK/kg)", scale=alt.Scale(zero=False)),
        color=alt.Color("model:N", scale=model_scale(["actual", "c0", "c1"]), title="Observed / predicted"),
        tooltip=["week:N", "model:N", alt.Tooltip("price:Q", format=".2f")])
    f2 = payload["f2"]
    verdict = "passed" if f2 and f2["pass"] else "did not pass"
    return (band + line).properties(width=PANEL_WIDTH, title=alt.TitleParams(
        f"Four-week forecasts against historical prices — F2 {verdict}", subtitle=[SOURCE,
        f"Holdout {' to '.join(payload['windows']['holdout'])}; forecasts made four ISO weeks earlier.",
        f"80% empirical interval: {rows[0]['band_model']}, using development errors; model selected by F2 after evaluation."]))


def build_charts(payload):
    if alt.__version__.split(".")[0] != "5":
        raise ValueError("Price charts require Altair 5 for the shared Vega-Lite v5 contract; install requirements.txt")
    register()
    alt.data_transformers.disable_max_rows()
    return {"price_scorecard": scorecard(payload), "price_by_year": by_year(payload),
            "price_backtest": backtest(payload)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "web/public/data/price.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "web/public/charts")
    args = parser.parse_args(argv)
    if not args.input.exists():
        print(f"Price charts waiting for {args.input}; run python -m price.backtest first.", file=sys.stderr)
        return 1
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    for name, chart in build_charts(payload).items():
        with alt.data_transformers.enable("default", consolidate_datasets=False):
            spec = chart.to_json()
        atomic_write(args.output_dir / f"{name}.vl.json", lambda p: p.write_text(spec + "\n", encoding="utf-8"))
        print(f"Wrote {name}.vl.json")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, KeyError) as exc:
        print(f"Price charts: invalid input or environment: {exc}", file=sys.stderr)
        sys.exit(1)
