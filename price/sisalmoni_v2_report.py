"""Report and plot a completed, frozen SISALMONI v2 experiment."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from price.calendar import week_start
from price.sisalmoni import _write_json, parse_public_years

BASELINES = ("rw", "ar1", "old_ar", "old_c0", "old_c1")
LABELS = {
    "rw": "No change", "ar1": "Simple AR(1)",
    "old_ar": "Original price model", "old_c0": "Original market model",
    "old_c1": "Original biology model", "ridge_log_a10": "Ridge log change, alpha 10",
    "ridge_log_a100": "Ridge log change, alpha 100",
    "ridge_level_a10": "Ridge price level, alpha 10",
    "ridge_level_a100": "Ridge price level, alpha 100",
    "ridge_fx": "Ridge + FX", "ridge_exports": "Ridge + exports",
    "ridge_biology": "Ridge + biology", "blend": "50/50 Ridge + no change",
    "adaptive_policy": "Chronological selection policy", "frozen_policy": "Frozen forecast policy",
}


def paired_blocks(actual, candidate, baseline, *, block_length, repetitions=10000, seed=20261108):
    """Circular paired blocks preserve consecutive overlapping forecast errors."""
    actual, candidate, baseline = (np.asarray(v, dtype=float) for v in (actual, candidate, baseline))
    if not (actual.shape == candidate.shape == baseline.shape) or actual.ndim != 1:
        raise ValueError("Paired, one-dimensional forecast vectors are required")
    if len(actual) < block_length or block_length < 1 or not np.isfinite([actual, candidate, baseline]).all():
        raise ValueError("Finite paired data and a valid block length are required")
    n = len(actual)
    ce, be = np.abs(candidate - actual), np.abs(baseline - actual)
    starts = np.random.default_rng(seed).integers(0, n, size=(repetitions, int(np.ceil(n / block_length))))
    indices = ((starts[..., None] + np.arange(block_length)) % n).reshape(repetitions, -1)[:, :n]
    cm, bm = ce[indices].mean(axis=1), be[indices].mean(axis=1)
    differences = cm - bm
    percentages = 100 * (1 - cm / bm)
    return {
        "n": n, "block_length": block_length, "repetitions": repetitions, "seed": seed,
        "candidate_mae": float(ce.mean()), "baseline_mae": float(be.mean()),
        "mean_error_difference_eur_kg": float((ce - be).mean()),
        "difference_ci95": np.quantile(differences, [.025, .975]).tolist(),
        "improvement_pct": float(100 * (1 - ce.mean() / be.mean())),
        "improvement_ci95": np.quantile(percentages, [.025, .975]).tolist(),
    }


def independent_scores(rows, index, expected):
    """Recompute every score from all planned prediction records, never a successful subset."""
    scores = []
    for (h, model), g in rows.groupby(["h", "model"], sort=True):
        pred = g.pred_eur_kg.to_numpy(float)
        actual = g.actual_eur_kg.to_numpy(float)
        failed = g.failed.astype(bool).to_numpy() | ~np.isfinite(pred) | (pred <= 0)
        total = int(expected[h])
        n_failed = int(failed.sum()) + max(0, total - len(g))
        success = len(g) - int(failed.sum())
        all_finite = np.isfinite(pred).all() and np.isfinite(actual).all()
        raw_mae = float(np.mean(np.abs(pred - actual))) if all_finite else None
        valid = n_failed == 0 and len(g) == total
        origin_prices = g.origin_week.map(lambda w: index.loc[week_start(w)]).to_numpy()
        calls = np.sign(pred - origin_prices)
        actual_signs = np.sign(actual - origin_prices)
        nonzero = calls != 0
        scores.append({
            "h": int(h), "model": model, "expected": total, "n": len(g),
            "successful": success, "failures": n_failed, "coverage": success / total,
            "mae_eur_kg": raw_mae if valid else None, "raw_finite_mae_eur_kg": raw_mae,
            "rmse_eur_kg": float(np.sqrt(np.mean((pred - actual) ** 2))) if valid else None,
            "mae_log": float(np.mean(np.abs(np.log(pred / actual)))) if valid else None,
            "direction_accuracy": float((calls[nonzero] == actual_signs[nonzero]).mean())
                if valid and nonzero.any() and model != "rw" else None,
            "first_target": g.target_week.min(), "last_target": g.target_week.max(),
        })
    return pd.DataFrame(scores)


def make_plots(rows, selected, baseline, out):
    import altair as alt
    import vl_convert as vlc

    h4 = rows.loc[rows.h == 4]
    names = list(dict.fromkeys(["rw", baseline, selected, "old_c1"]))
    colors = ["#62717a", "#24895d", "#236bb4", "#db652f", "#75459c"]
    labels = [LABELS.get(m, m) for m in names]
    color = alt.Color("model:N", scale=alt.Scale(domain=["Actual"] + labels, range=["#17232b"] + colors[:len(names)]), title=None)
    error_color = alt.Color("model:N", scale=alt.Scale(domain=labels, range=colors[:len(names)]), title=None)
    points = []
    actual_rows = h4.loc[h4.model == "rw"].sort_values("target_week")
    for r in actual_rows.itertuples():
        points.append({"date": week_start(r.target_week).date().isoformat(), "week": r.target_week,
                       "model": "Actual", "price": r.actual_eur_kg})
    for r in h4.loc[h4.model.isin(names)].itertuples():
        value = float(r.pred_eur_kg) if np.isfinite(r.pred_eur_kg) else None
        points.append({"date": week_start(r.target_week).date().isoformat(), "week": r.target_week,
                       "model": LABELS.get(r.model, r.model), "price": value,
                       "error": value - r.actual_eur_kg if value is not None else None})
    data = alt.Data(values=points)
    actual_chart = alt.Chart(data).mark_line(point=True).encode(
        x=alt.X("date:T", title="Target delivery week"),
        y=alt.Y("price:Q", title="EUR/kg", scale=alt.Scale(zero=False)), color=color,
        tooltip=["week:N", "model:N", alt.Tooltip("price:Q", format=".3f")],
    ).properties(width=760, height=340, title="SISALMONI: actual and four-week forecasts")
    errors = alt.Chart(data).transform_filter(alt.datum.model != "Actual").mark_line(point=True).encode(
        x=alt.X("date:T", title="Target delivery week"),
        y=alt.Y("error:Q", title="Forecast minus actual, EUR/kg", scale=alt.Scale(zero=True)), color=error_color,
        tooltip=["week:N", "model:N", alt.Tooltip("error:Q", format="+.3f")],
    )
    zero = alt.Chart(alt.Data(values=[{"zero": 0}])).mark_rule(strokeDash=[4, 4], color="#777").encode(y="zero:Q")
    errors_chart = (errors + zero).properties(width=760, height=320, title="Four-week forecast errors: all test weeks retained")
    for name, chart in [("actual_vs_predicted", actual_chart), ("forecast_errors", errors_chart)]:
        chart = chart.configure(font="Arial").configure_axis(labelFontSize=12, titleFontSize=13).configure_legend(labelFontSize=11, orient="bottom")
        spec = chart.to_dict()
        _write_json(out / f"{name}.vl.json", spec)
        (out / f"{name}.svg").write_text(vlc.vegalite_to_svg(spec), encoding="utf-8")
        (out / f"{name}.png").write_bytes(vlc.vegalite_to_png(spec, scale=1.5))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("price/experiments/sisalmoni_v2"))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/sisalmoni"))
    args = parser.parse_args(argv)
    out = args.output_dir
    selection = json.loads((out / "selection.json").read_text())
    rows = pd.read_parquet(out / "final_predictions.parquet")
    development = pd.read_parquet(out / "development_predictions.parquet")
    index = parse_public_years(json.loads(p.read_text()) for p in sorted(args.raw_dir.glob("*.json")))
    scores = independent_scores(rows, index, {h: 24 for h in range(2, 9)})
    dev_expected = development.loc[development.model == "rw"].groupby("h").size().to_dict()
    dev_scores = independent_scores(development, index, dev_expected)
    for h in range(2, 9):
        rw = float(scores.loc[(scores.h == h) & (scores.model == "rw"), "mae_eur_kg"].iloc[0])
        old = float(scores.loc[(scores.h == h) & (scores.model == "old_c1"), "mae_eur_kg"].iloc[0])
        scores.loc[scores.h == h, "improvement_vs_rw_pct"] = 100 * (1 - scores.loc[scores.h == h, "mae_eur_kg"] / rw)
        scores.loc[scores.h == h, "improvement_vs_old_c1_pct"] = 100 * (1 - scores.loc[scores.h == h, "mae_eur_kg"] / old)
    scores.to_csv(out / "comparison.csv", index=False)
    dev_scores.to_csv(out / "development_comparison.csv", index=False)
    challenger, baseline = selection["selected_challenger"], selection["strongest_baseline"]
    primary = scores.loc[scores.h == 4].set_index("model")
    eligible_baselines = primary.loc[primary.index.isin(BASELINES) & primary.mae_eur_kg.notna()]
    best_final = eligible_baselines.mae_eur_kg.idxmin()
    intervals = []
    pair_records = []
    for h in range(2, 9):
        base_rows = rows.loc[(rows.h == h) & (rows.model == "rw")].set_index("origin_week").sort_index()
        cand_rows = rows.loc[(rows.h == h) & (rows.model == challenger)].set_index("origin_week").reindex(base_rows.index)
        refs = list(dict.fromkeys(["rw", baseline, best_final])) if h == 4 else ["rw"]
        for ref in refs:
            reference = rows.loc[(rows.h == h) & (rows.model == ref)].set_index("origin_week").reindex(base_rows.index)
            valid_pair = all(len(g) == 24 and not g.failed.fillna(True).any()
                             and np.isfinite(g.pred_eur_kg).all() and (g.pred_eur_kg > 0).all()
                             for g in [cand_rows, reference])
            if not valid_pair:
                intervals.append({"h": h, "candidate": challenger, "baseline": ref,
                                  "status": "not_estimable",
                                  "reason": "Incomplete, failed or invalid final forecasts; no subset inference."})
                continue
            for block in sorted(set([max(h, 4), max(h, 8)])):
                interval = paired_blocks(base_rows.actual_eur_kg, cand_rows.pred_eur_kg, reference.pred_eur_kg,
                                         block_length=block, seed=20261108 + h * 100 + block)
                intervals.append({"h": h, "candidate": challenger, "baseline": ref, "status": "estimated", **interval})
            if h == 4:
                for origin in base_rows.index:
                    a, c, b = base_rows.loc[origin, "actual_eur_kg"], cand_rows.loc[origin, "pred_eur_kg"], reference.loc[origin, "pred_eur_kg"]
                    pair_records.append({"origin_week": origin, "target_week": base_rows.loc[origin, "target_week"],
                                         "candidate": challenger, "baseline": ref, "candidate_abs_error": abs(c - a),
                                         "baseline_abs_error": abs(b - a), "difference_eur_kg": abs(c - a) - abs(b - a)})
    _write_json(out / "paired_uncertainty.json", intervals)
    pd.DataFrame(pair_records).to_csv(out / "paired_errors.csv", index=False)
    cm = float(primary.loc[challenger, "mae_eur_kg"])
    strongest_mae = float(primary.loc[best_final, "mae_eur_kg"])
    improvement = 100 * (1 - cm / strongest_mae) if np.isfinite(cm) else None
    relevant = [r for r in intervals if r["h"] == 4 and r["baseline"] in {"rw", baseline}]
    required_pairs = len({"rw", baseline}) * 2
    reliable = len(relevant) == required_pairs and all(r.get("status") == "estimated"
                                                      and r["difference_ci95"][1] < 0 for r in relevant)
    practical = improvement is not None and improvement >= 10
    achieved = practical and reliable and primary.loc[challenger, "failures"] == 0
    recommended = challenger if achieved else baseline
    decision = {"selected_challenger": challenger, "strongest_development_baseline": baseline,
                "frozen_policy": selection["selected_policy"], "strongest_observed_final_baseline": best_final,
                "improvement_vs_strongest_final_baseline_pct": improvement,
                "practical_ten_percent_objective": practical,
                "paired_intervals_exclude_no_benefit_at_both_block_lengths": reliable,
                "objective_supported": bool(achieved), "recommended_model": recommended,
                "evaluation": "retrospective; 24 primary target weeks; not independent confirmation"}
    _write_json(out / "decision.json", decision)
    make_plots(rows, challenger, baseline, out)
    change_text = f"{improvement:+.2f}%" if improvement is not None else "not estimable because of failed forecasts"
    specification = next(s for s in selection["candidate_specs"] if s["id"] == challenger)
    if specification["kind"] == "ridge":
        target_text = "the EUR price level directly" if specification["representation"] == "level" else "the log price change"
        design_text = (f"The selected candidate predicts {target_text}, using the six compact price/calendar inputs"
                       f" and feature groups {specification.get('groups', [])}. Its alpha-{specification['alpha']} Ridge penalty"
                       " and training-only scaling constrain coefficient instability. Direct level forecasts also avoid"
                       " exponential amplification of a fitted log return. This explains its design benefit, not a claim"
                       " of reliable future outperformance.")
    else:
        design_text = "The selected challenger is the fixed 50/50 blend of no change and alpha-100 price-only log-change Ridge. It adds no fitted ensemble weights."
    lines = ["# SISALMONI v2: retrospective results", "",
             "A separate short-history experiment using genuine SISALMONI 3–6 kg EUR/kg observations only.", "",
             f"**Recommended model: {LABELS.get(recommended, recommended)} (`{recommended}`).**",
             f"The frozen development-selected challenger is `{challenger}`; the frozen strongest development baseline is `{baseline}`.",
             f"The challenger changes final four-week MAE by {change_text} relative to the strongest eligible baseline on these same test dates (positive means improvement).",
             f"The 10% objective with supporting paired uncertainty evidence is {'met on this retrospective segment' if achieved else 'not met'}. No final result was used to retune models.", "",
             design_text,
             f"The no-change improvement on this segment is {float(primary.loc[challenger,'improvement_vs_rw_pct']):+.2f}%. The recommended baseline is the one selected in development, not a baseline re-picked using final outcomes. The strongest observed final baseline (`{best_final}`) is reported separately and descriptively.", "",
             "## Primary comparison: four weeks", "",
             "All models below use the same 24 target weeks, 2026-W21–2026-W44. Earlier full-history scores are not comparison baselines.", "",
             "| Model | MAE EUR/kg | RMSE EUR/kg | Log MAE | Direction accuracy | Coverage | vs no change |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for model, r in primary.iterrows():
        fmt = lambda x: "unavailable" if pd.isna(x) else f"{x:.3f}"
        direction = "no call" if pd.isna(r.direction_accuracy) else f"{100*r.direction_accuracy:.1f}%"
        lines.append(f"| {LABELS.get(model, model)} | {fmt(r.mae_eur_kg)} | {fmt(r.rmse_eur_kg)} | {fmt(r.mae_log)} | {direction} | {int(r.successful)}/24 | {r.improvement_vs_rw_pct:+.1f}% |")
    fixed_ids = [s["id"] for s in selection["candidate_specs"] if s["id"] not in BASELINES]
    best_fixed = primary.loc[primary.index.isin(fixed_ids) & primary.mae_eur_kg.notna()].mae_eur_kg.idxmin()
    if best_fixed != challenger:
        lines += ["", f"The unselected `{best_fixed}` configuration scored {primary.loc[best_fixed,'mae_eur_kg']:.3f} EUR/kg on this segment. It was not the development-selected challenger. This is a secondary observation for future research; it is not used to change the frozen model or claim a validated winner."]
    lines += ["", "## Paired uncertainty", "",
              "Negative EUR/kg differences favor the selected challenger. Blocks resample the same consecutive weeks for both models, preserving pairing and short-range dependence. The 24-week segment supplies only six four-week or three eight-week blocks; these intervals are approximate, not strong independent confirmation. They condition on the frozen selection and do not remove the effects of earlier historical-data inspection or establish robustness to new regimes.", "",
              "| Baseline | Block weeks | Mean MAE difference EUR/kg | 95% interval | Improvement | 95% improvement interval |",
              "| --- | --- | --- | --- | --- | --- |"]
    for r in [r for r in intervals if r["h"] == 4]:
        if r["status"] != "estimated":
            lines.append(f"| {LABELS.get(r['baseline'],r['baseline'])} | unavailable | unavailable | {r['reason']} | unavailable | unavailable |")
            continue
        lo, hi = r["difference_ci95"]; pl, ph = r["improvement_ci95"]
        lines.append(f"| {LABELS.get(r['baseline'],r['baseline'])} | {r['block_length']} | {r['mean_error_difference_eur_kg']:+.3f} | [{lo:+.3f}, {hi:+.3f}] | {r['improvement_pct']:+.1f}% | [{pl:+.1f}%, {ph:+.1f}%] |")
    lines += ["", "## Development and selection", "",
              "The earliest 93 target weeks are development; the latest 24 are reserved for the final retrospective segment. Selection uses only development labels public by 2 April 2026 (through 2026-W13), before the first h=8 final forecast. W14–W20 are an explicit selection gap. Training can subsequently expand as observations become public, with frozen configurations.",
              "Each fixed candidate is validated using expanding training windows and train-only scaling. The additional chronological development policy chooses from earlier validation errors only after those labels were published; it starts with no change until eight released observations exist. `selection.json` records the final pre-test choice and input/code hashes.", "",
              "| Development candidate | MAE EUR/kg | n |", "| --- | --- | --- |"]
    for r in dev_scores.loc[dev_scores.h == 4].itertuples():
        value = "unavailable" if pd.isna(r.mae_eur_kg) else f"{r.mae_eur_kg:.3f}"
        lines.append(f"| {LABELS.get(r.model,r.model)} | {value} | {r.n} |")
    lines += ["", "FX, export and biology comparisons all use the same alpha-100 log-change Ridge price core. A group is eligible only if its development MAE improves that core by at least 2%. Decisions and eligibility are recorded in `selection.json`; no unsupported group is added to the selected model.", "",
              "## Secondary horizons", "", "These were predefined secondary analyses, not a new model-selection step.", "",
              "| h | Selected challenger MAE | No-change MAE | Old c1 MAE | Challenger vs no change |",
              "| --- | --- | --- | --- | --- |"]
    for h in range(2, 9):
        table = scores.loc[scores.h == h].set_index("model")
        lines.append(f"| {h} | {table.loc[challenger,'mae_eur_kg']:.3f} | {table.loc['rw','mae_eur_kg']:.3f} | {table.loc['old_c1','mae_eur_kg']:.3f} | {table.loc[challenger,'improvement_vs_rw_pct']:+.1f}% |")
    lines += ["", "## Diagnosis and limits", "",
              "The original OLS model had 29 columns and as few as 30 training observations, with rank deficiency, severe collinearity and exponential amplification of large log predictions. The compact Ridge models use six price/calendar inputs and positive regularization, with means and scales fitted within each training window. The simple ensemble adds no fitted parameters. Direct level and log-change targets are tested explicitly. See `DIAGNOSIS.md` for measured evidence and hypotheses.",
              "This experiment reduces model instability; that does not guarantee an advantage over no change. Only 117 index prices and 24 final target weeks are available, with revised exogenous inputs and approximate public-release dates. The history and prior SISALMONI scores had already been examined, so this is retrospective. A future genuinely unseen evaluation is needed before claiming reliability.",
              "The target is the pure EUR benchmark, not the blended 2024 NOK field. Forecast issue dates are normally Thursday of the following week; h counts delivery-week shifts, not h complete weeks after that issue date. Features at every historical origin use their own publication-filtered snapshot. No Nasdaq or SSB prices fill target history, and no arbitrary forecast clipping or difficult-week deletion is used.", "",
              "## Reproduce and inspect", "",
              "```sh", "python -m price.sisalmoni_v2 run --raw-dir data/raw/sisalmoni",
              "python -m price.sisalmoni_v2_report --raw-dir data/raw/sisalmoni", "```", "",
              "The runner refuses to overwrite a completed final evaluation. Prediction Parquets, `comparison.csv`, `development_comparison.csv`, `paired_errors.csv`, `paired_uncertainty.json`, `selection.json`, `decision.json` and provenance retain the evidence. Original SSB and v1 outputs are preserved.", "",
              "See `README.md` for the verified interpreter, dependency snapshot and a fresh-output replay command. `selection.initial.json` preserves the first freeze; a documented pre-test amendment tightened the CLI input-path guard without changing configurations, selections, inputs, dates or development predictions.", "",
              "![Actual and predicted](actual_vs_predicted.png)", "", "![Forecast errors](forecast_errors.png)", "",
              "Sources: [SISALMONI definition](https://www.sitagri.com/sitagri-salmon-index/), [verified price source](../sisalmoni/SOURCES.md), [Ridge objective](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html), [circular block resampling](https://bashtage.github.io/arch/bootstrap/generated/arch.bootstrap.CircularBlockBootstrap.html).", ""]
    (out / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
