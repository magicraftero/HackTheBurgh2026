"""Explicit, recorded timing exception for a user-requested early final run.

The registered model, saved development selection, package/input/code checks,
and once-only final guard are unchanged. Only the scheduled wall-clock gate
is overridden. Actual execution timestamps are never changed or simulated.
"""

import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from analysis import nowcast
from analysis.io import write_json_atomic


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=nowcast.PROCESSED_DATA_DIR)
    parser.add_argument("--output-root", type=Path, default=nowcast.REPO_ROOT)
    parser.add_argument("--authorize-early-final", action="store_true")
    args = parser.parse_args(argv)
    actual = datetime.now(ZoneInfo("Europe/London"))
    scheduled = nowcast.FREEZE
    command = ["--final", "--input-dir", str(args.input_dir), "--output-root", str(args.output_root)]
    if actual >= scheduled:
        nowcast.main(command, now=actual)
        return
    if not args.authorize_early_final:
        raise ValueError("Early final execution requires explicit authorization; the default freeze remains 04:00")
    final_record = args.output_root / "analysis/nowcast_final_run.json"
    if final_record.exists():
        raise ValueError("Final nowcast already recorded; preserve the frozen results")
    exception = {
        "actual_execution_started_at": actual.isoformat(),
        "original_scheduled_freeze": scheduled.isoformat(),
        "reason": "User requested final holdout evaluation immediately, before the scheduled freeze.",
        "user_request": "Test the final holdout and see how it performs",
        "changes": "Wall-clock timing only; no model, feature, tuning, selection, scoring, or data changes.",
        "entrypoint_sha256": nowcast.digest(Path(__file__)),
    }
    authorization = args.output_root / "analysis/nowcast_early_authorization.json"
    write_json_atomic(exception, authorization)
    # Scoped operational exception; now=actual is passed to retain the real
    # timestamp in all provenance. The original guard is restored afterwards.
    try:
        nowcast.FREEZE = actual
        nowcast.main(command, now=actual)
    finally:
        nowcast.FREEZE = scheduled
    import json
    for name in ("nowcast_provenance.json", "nowcast_final_run.json"):
        path = args.output_root / "analysis" / name
        record = json.loads(path.read_text())
        record["timing_exception"] = exception
        record["authorization_sha256"] = nowcast.digest(authorization)
        write_json_atomic(record, path)
    report = args.output_root / "analysis/RESULTS.md"
    with report.open("a", encoding="utf-8") as handle:
        handle.write(f"\n## Final execution timing\n\nRun started {actual.isoformat()}, before the originally scheduled {scheduled.isoformat()} freeze, at the user's explicit request. Development selection and all model configurations remained locked.\n")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, FileNotFoundError, FileExistsError) as error:
        raise SystemExit(f"Production final run: {error}")
