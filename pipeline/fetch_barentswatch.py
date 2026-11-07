"""BarentsWatch bulk fish-health export -> data/raw/barentswatch/<report>/

Pulls the lice, treatments and disease reports for every salmonid site, one ISO year per
request (the export allows at most one year and one week per call), single-threaded as
BarentsWatch asks. Finished years are saved as <report>_<year>.csv and skipped on rerun, so a
crash loses nothing. The current year is always downloaded again under a timestamped name, so
earlier snapshots stay on disk.

Order: 2026 back to 2017 first (the core window), then 2016 back to 2012.

Run: python -m pipeline.fetch_barentswatch [--years 2026-2017] [--reports lice,treatments]
"""

from __future__ import annotations

import sys
import time
from datetime import date

from pipeline.bw_client import BarentsWatch
from pipeline.common import RAW, ROOT, available_at_bw, iso_week_str
from pipeline.release_log import log_download, stamp

REPORTS = {"lice": "Lice", "treatments": "Treatments", "disease": "Disease"}
YEARS = list(range(2026, 2016, -1)) + list(range(2016, 2011, -1))
OUT = RAW / "barentswatch"


def last_week(year: int) -> int:
    """The last ISO week of a year, or the last week that has started if the year is current."""
    if year == date.today().isocalendar().year:
        return date.today().isocalendar().week
    return date(year, 12, 28).isocalendar().week


def raw_files(report: str, year: int) -> list:
    """All saved files for a report-year, oldest first (final file or timestamped snapshots)."""
    return sorted((OUT / report).glob(f"{report}_{year}*.csv"))


def pull(bw: BarentsWatch, report: str, year: int) -> None:
    current = year == date.today().isocalendar().year
    final = OUT / report / f"{report}_{year}.csv"
    if not current and final.exists():
        print(f"skip {report} {year} (on disk)")
        return
    to_week = last_week(year)
    t0 = time.time()
    resp = bw.get("/v1/geodata/download/fishhealth", params=dict(
        reporttype=REPORTS[report], filetype="Csv",
        fromyear=year, fromweek=1, toyear=year, toweek=to_week))
    out = OUT / report / (f"{report}_{year}_{stamp()}.csv" if current else f"{report}_{year}.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".part")
    tmp.write_bytes(resp.content)
    tmp.rename(out)  # only a complete download gets the real name
    rows = resp.content.count(b"\n") - 1
    print(f"{report} {year} W01-W{to_week:02d}: {rows:,} rows, {len(resp.content) / 1e6:.1f} MB, "
          f"{time.time() - t0:.0f}s -> {out.relative_to(ROOT)}", flush=True)
    last = iso_week_str(year, to_week)
    log_download(f"barentswatch_{report}", iso_week_str(year, 1), last, available_at_bw(last), out, rows)


def parse_args() -> tuple[list[int], list[str]]:
    years, reports = YEARS, list(REPORTS)
    args = sys.argv[1:]
    if "--years" in args:
        a, b = map(int, args[args.index("--years") + 1].split("-"))
        years = list(range(a, b - 1, -1)) if a >= b else list(range(a, b + 1))
    if "--reports" in args:
        reports = args[args.index("--reports") + 1].split(",")
    return years, reports


def main() -> None:
    years, reports = parse_args()
    bw = BarentsWatch()
    failed = []
    for year in years:
        for report in reports:
            for attempt in range(3):
                try:
                    pull(bw, report, year)
                    break
                except Exception as e:  # network hiccup: wait and retry, then move on
                    print(f"error {report} {year} (attempt {attempt + 1}): {e}", flush=True)
                    time.sleep(10 * (attempt + 1))
            else:
                failed.append(f"{report} {year}")
    if failed:
        # Finished years already on disk are skipped, so a rerun fetches only these.
        raise SystemExit(f"FAILED after 3 attempts: {', '.join(failed)}. Rerun to fetch just these.")
    print("done")


if __name__ == "__main__":
    main()
