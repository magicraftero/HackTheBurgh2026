# Reproducing the SISALMONI v2 experiment

Run from the repository root. The verified interpreter for this checkout is
`/private/tmp/htb-price-venv/bin/python` (CPython 3.13). The exact direct dependency
versions used are in `requirements.txt`; runtime metadata is in `provenance.json`.
This experiment uses NumPy Ridge rather than adding a scikit-learn dependency.
Its pandas 2.3.3 environment differs from the main repository's pandas 3.1.1 pin;
the recorded tests were run in the experiment environment.

The source inputs already exist in this checkout:

- `data/raw/sisalmoni/{2024,2025,2026}.json`: original public EUR index responses.
- `data/processed/`: the existing publication-stamped exogenous tables.
- `price/experiments/sisalmoni/predictions.parquet`: original-model predictions
  used only as matched reference forecasts, with source hashes verified.

Retain these cached snapshots to reproduce the exact historical experiment.
Fetching a later public response can add weeks or revise observations; it is not
the same frozen input. The original source URLs and content hashes are recorded
in the v1 source notes and v2 selection manifest. The raw directory is ignored
by Git, and its cached files have not been republished to the website.

The initial execution command was:

```sh
/private/tmp/htb-price-venv/bin/python -m price.sisalmoni_v2 develop --raw-dir data/raw/sisalmoni
/private/tmp/htb-price-venv/bin/python -m price.sisalmoni_v2 final --raw-dir data/raw/sisalmoni
/private/tmp/htb-price-venv/bin/python -m price.sisalmoni_v2_report --raw-dir data/raw/sisalmoni
```

The completed final evaluation is intentionally protected against overwrite.
To reproduce the unchanged protocol in a fresh output directory:

```sh
mkdir -p /tmp/sisalmoni-v2-replay
cp price/experiments/sisalmoni_v2/PLAN.md /tmp/sisalmoni-v2-replay/PLAN.md
/private/tmp/htb-price-venv/bin/python -m price.sisalmoni_v2 run --raw-dir data/raw/sisalmoni --output-dir /tmp/sisalmoni-v2-replay
/private/tmp/htb-price-venv/bin/python -m price.sisalmoni_v2_report --raw-dir data/raw/sisalmoni --output-dir /tmp/sisalmoni-v2-replay
```

For another machine, create a Python 3.13 environment and install this folder's
`requirements.txt`; this exact run did not test a fresh dependency installation.
The final command's input-path guard binds data to the paths and hashes chosen
during that replay's development phase.

Tests:

```sh
/private/tmp/htb-price-venv/bin/python -m unittest discover -s price/tests
```

`PLAN.md` defines the protocol; `DIAGNOSIS.md` records confirmed defects and
hypotheses; `RESULTS.md` explains the outcome. `comparison.csv` and
`development_comparison.csv` contain all candidate/horizon metrics. The selected
challenger and deployment recommendation are distinct fields in `decision.json`:
the conservative fallback is the strongest development baseline if the declared
improvement and uncertainty criteria are not met.
