# Production model v2: design options

A working document to decide, together, how to build a better production model. Nothing here has
been fitted yet. Once we pick, the chosen design is copied into `prereg/PRODUCTION_V2.md` and
committed **before** any fit, the same way Nikita did for the ML challenger.

---

## 1. Where we are and what we are allowed to do

**The current model (Drivers)** splits each area's monthly harvest into "normal" (trailing 12-month
level plus the usual seasonal pattern) and a "surprise", then predicts the surprise with a linear
regression on 19 driver anomalies. On 2021-2024:

| Outcome | B1 baseline error | Drivers error | |
|---|---|---|---|
| Kilograms | 0.2505 | 0.2530 | 1% worse |
| Fish count | 0.2544 | 0.2485 | 2% better |
| Average weight | 0.0782 | 0.0757 | 3% better |

Errors are mean absolute error in log points (0.25 ≈ typically 25% off).

**What it gets wrong, in plain terms:** it never looks at how many fish are actually in the water,
it ignores the fact that harvesting runs in campaigns, and it cannot handle areas that go silent
for months (areas 1 and 13 are never forecast).

**The rules:**

- F1 stays judged on the Drivers model exactly as pre-registered. We cannot "patch" it for F1:
  changing a model after seeing it lose makes any win meaningless.
- A new model is allowed if we fix its design in writing before fitting it. It competes in
  Nikita's contest and can drive the cockpit and the headline numbers.
- Honesty note: we have already seen 2021-2024 scores for the old model, and a few simple
  full-sample statistics (section 3). The 2025-2026 holdout has never been scored by anyone, so
  **the holdout is the real judge** of the new model. From now on, any exploration uses data up to
  2024 only.

---

## 2. The core idea: stocks and flows

Salmon farming is bookkeeping. Every month, for each area:

```
fish in the water at the end of the month
   = fish at the start  + growth  - deaths  - harvest
```

The Directorate publishes all of these, but about **50 days** after the month starts. When we
forecast month `t` (on the 10th of month `t+1`), we know the stock at the end of month `t-1`.

So instead of predicting kilograms from scratch, predict **what share of the stock comes out**:

```
harvest_kg(t)    = biomass(t-1)     x  kg_share(t)
harvest_count(t) = fish_stock(t-1)  x  count_share(t)
avg_kg(t)        = harvest_kg(t) / harvest_count(t)
```

Why this is better:

| Problem with the current model | How the share model fixes it |
|---|---|
| Doesn't know how much fish exists | The stock is built in: no fish in the water, no harvest |
| Kilograms swing 10x between areas | The share is about 15% everywhere, so areas can learn from each other |
| Zero-harvest months break the log | A zero month is just a 0% share |
| Needs 12+ months of history per area | Needs only last month's stock, so it starts sooner |
| Kilograms, count and weight can disagree | Weight is kg ÷ count by construction |

---

## 3. What the data already shows (simple full-sample statistics)

| Fact | Number | What it means |
|---|---|---|
| Typical monthly harvest share | 15% (half of area-months between 11% and 19%) | A stable, learnable target |
| This month's share vs last month's | correlation 0.55 | Harvesting runs in campaigns |
| This month's share vs 12 months ago | correlation 0.15 | The calendar matters much less than momentum |
| Share vs average weight of fish in the water | correlation 0.34 | Heavy fish are ready to come out |
| Export figures published | ~9 days after the week starts | Near real time |
| Official harvest published | ~50 days after the month starts | Slow |

---

## 4. The inputs, explained

For each input: what it is, why it should matter, when it's known, and the catch.

### 4.1 Stock inputs (from the Directorate, known up to month t-1)

- **Average weight of fish in the water** = `biomass / fish_stock` at t-1.
  Salmon are harvested at roughly 4-6 kg. If the average fish in an area is already heavy, a
  harvest wave is coming. *Catch:* it's an average, so a mix of small and big fish looks "medium".
- **Last month's harvest share (momentum).** Farms empty a site over several weeks, so a campaign
  that started last month usually continues. *Catch:* campaigns also end, and momentum can't see
  the end coming. That's what average weight and the fallow share are for.
- **Same month last year's share.** A weak seasonal echo (0.15). Cheap to include.
- **Feed per kg of biomass** (t-1). High feeding means fast growth, so fish reach harvest size
  sooner.
- **Deaths per 1,000 fish** (t-1). Disease outbreaks trigger emergency harvests.
- **Smolt released 14-20 months earlier.** Each year's young fish become a harvest about 1.5 years
  later: a cohort pipeline you can see coming a year ahead.

### 4.2 Farm-health inputs (from BarentsWatch, weekly, known to the forecast date)

- **Mobile lice per fish.** Above the legal limit (0.5 adult females), farms must treat or harvest.
  The current data shows the "more but smaller fish" signature in the bins.
- **Delousing treatments.** Treatments stress fish; farms often harvest right after, or delay.
- **Sea temperature bands.** Warm water means faster growth, so the harvest comes earlier.
  Above 14 °C, growth slows and fish get stressed.
- **Disease (ISA or PD sites).** ISA forces culling, which shows up as a sudden harvest.
- **Share of sites lying fallow** (new). Norway's areas rest sites in coordinated cycles. If most
  of an area's sites are empty, it can't harvest. This is exactly why areas 1 and 13 go silent,
  and it's known in advance.

### 4.3 Market inputs (from Statistics Norway, weekly, about 9 days after the week starts)

- **Export volume this month** (national). Almost all salmon is exported fresh within days of
  harvest, so exports are a near-direct reading of the harvest. This is the strongest single input
  and the reason B1 is hard to beat. It's national only, so each area gets its share via the
  model.
- **Salmon price** (new). When prices are high, farmers pull harvests forward.
  *Catch, and a good teaching point:* this month's price is also *caused* by this month's
  harvest (more salmon means a lower price). For prediction that's fine; for a story about
  farmer behaviour, use **last month's price**, which the current harvest can't have caused.

### 4.4 Shape inputs

- **Area** (13 separate baselines) and **calendar month** (seasonal shape). Let each area keep its
  own typical share and season.
- **Interactions:** for example, *lice × average weight*. Lice should force a harvest only when the
  fish are big enough to sell. A linear model can include this as one extra column.

---

## 5. Learner options

| Option | How it works | Strengths | Weaknesses | Cockpit sliders? |
|---|---|---|---|---|
| **A. Ridge regression** | Linear, with coefficients shrunk towards zero to avoid overfitting | Stable with ~1,000 rows; every input has a readable effect; cheap | Can't find curves unless we add them by hand | Yes, instantly in the browser |
| **B. Lasso** | Like ridge, but pushes useless inputs to exactly zero | Tells you which inputs matter | Unstable when inputs are correlated (stock inputs are) | Yes |
| **C. Gradient-boosted trees** | Many small decision trees, each fixing the last one's mistakes | Finds curves and interactions on its own | Needs more data; harder to explain; Nikita is already doing this | No; needs precomputed scenarios |
| **D. Hierarchical / mixed model** | Each area gets its own effects, pulled towards the national average | Small areas borrow strength from big ones | Slower to fit, more to explain | Yes |
| **E. Beta regression** | Built for shares between 0 and 1 | Statistically "correct" for a share | Can't take exact zeros without a fix | Partly |
| **F. Ridge + a few hand-built curves** | Option A plus, for example, "share rises steeply once average weight passes 4 kg" | Captures the main non-linearity and stays explainable | We choose the curves before fitting, so we must pick well | Yes |

**Recommendation: F** (ridge with a short, pre-declared list of curves and interactions). It gets
most of the trees' power on the patterns that matter, stays explainable, and keeps the cockpit's
what-if sliders. It also makes the contest with Nikita meaningful: **domain-built linear model vs
generic machine learning**. If ours wins, that's a story; if his wins, the gap tells us how much
non-linearity there is.

The ridge penalty (how much to shrink) is chosen automatically inside each training window, by
time-ordered cross-validation on past months only. That's not tuning on the scored data.

---

## 6. The hidden patterns this could uncover

The challenge is to make something invisible visible. Each of these is a specific, testable
claim. They are exploratory, with no pass mark, and are reported whether they come out or not.

1. **The head start.** Exports reveal each month's harvest before the official statistics
   (published on the 20th of the next month). We can show "here is October's harvest, today, 10 days after the month
   ended", then prove the track record on 2025-2026.
2. **Panic harvests.** When lice rise on farms with big fish, harvest share jumps and average
   weight drops. That's farmers dumping fish early. The *lice × weight* interaction measures it,
   in tonnes.
3. **Farmers respond to price.** Does a high price last month pull harvests forward? If the
   price coefficient is positive and clear, we have measured Norwegian salmon supply response from
   public data alone.
4. **Silent areas are predictable.** Fallow cycles make areas 1 and 13 look chaotic, but the share
   of empty sites tells you months ahead. The old model couldn't forecast those areas at all.
5. **The cohort clock.** Smolt released about 1.5 years earlier sets the size of the harvest wave
   coming now. This is the longest-range signal we have.

Each one also becomes a cockpit lever or explanation: "your forecast is up 8% because 60% of your
fish are above 4.5 kg and lice are high".

---

## 7. How we would score it (fixed before fitting)

- **Same timing as the nowcast:** forecast made on the 10th of month t+1, with only data public
  by then. Walk-forward, refitted every month.
- **Same rows as Nikita's contest:** all models scored where all of them have a forecast. We also
  report the new model alone on areas 1 and 13, since it's the only one that can forecast them.
- **Metrics:** MAE in log kg, log count and log average weight (comparable with F1), **plus MAE in
  tonnes** (which counts zero-harvest months fairly).
- **Development window 2021-2024** to compare against Drivers, B1 and Nikita's models. **Holdout
  2025-2026** run once, after 04:00, and shown whatever it says.
- **Ablation** (which inputs matter): refit without each group and report how much worse it gets.
- **Leakage alarm:** if the new model is more than 20% better than the best linear model on the
  development window, we check for leakage before publishing (Nikita's rule).

---

## 8. Decisions to make together

| # | Question | My recommendation |
|---|---|---|
| 1 | Target | The harvest share (decided: predict the share directly, zeros included) |
| 2 | Learner | F: ridge plus a short list of declared curves and interactions |
| 3 | Inputs | Everything in section 4: stock, momentum, fallow, lagged price, the current drivers, exports |
| 4 | Price timing | Last month's price for the behaviour story; also report a version with this month's price |
| 5 | Curves and interactions | Average weight above 4 kg, lice × average weight, fallow share |
| 6 | Areas | One model for all 13 areas, with each area's own baseline and season |
| 7 | Contest | Tell Nikita and add v2 to the winner rule before anyone sees v2 scores |

## 9. Time plan (it's about 23:15)

| By | Step |
|---|---|
| 23:45 | Agree the design; write and commit `prereg/PRODUCTION_V2.md` (locally) |
| 01:00 | Build v2 with tests (leakage test, stock-flow arithmetic, zero months) |
| 01:30 | Development-window run; compare with Drivers, B1 and Nikita's model |
| 02:30 | Cockpit uses v2 if it wins under the rule; levers updated |
| 04:00 | Holdout runs once for every model |
