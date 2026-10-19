# Current Treasury ALM case: longevity and liquidity exposures

As of30September2026. All amounts below are nominal USD for a synthetic benefit
portfolio, not a real employer, insurer or retirement plan. The separate
historical hedge experiment and its final selection remain unchanged.

## Liability and holdings

Four250-life cohorts receive12,000 annually in arrears while alive: male60,
female65, male70 and female75. SSA2023 period mortality is applied without
cohort improvement. The maximum paying age is120. The curve is the pinned
official GSW Svensson curve dated30September2026.

| Base liability measure | Value |
| --- | ---: |
| Present value |119,380,495.42 |
| Duration, years |8.473573 |
| Convexity, years squared |113.758999 |
| DV01, USD per1bp parallel rate increase |101,157.93 |
| PV after30years |583,401.06 |
| Share of PV after30years |0.48869% |

DV01 is a positive exposure magnitude. A small positive rate shift decreases
liability value. Each asset portfolio is fully funded at inception. All stress
calculations retain the same initial bond face amounts. No stress-specific
re-hedging or new selection is performed.

## Interest-rate hedging leaves longevity exposure

The covariance method remains the historical development-selected method. In
this current deterministic case, a200bp parallel fall produces a350,957.08
surplus deficit,0.2940% of the base liability. The largest absolute surplus over
the eight declared interest-rate stresses is:

| Fixed portfolio | Largest absolute stressed surplus, USD |
| --- | ---: |
| Five-year zero |10,742,223.23 |
|5/20-year duration match |370,779.15 |
| Constrained key-rate hedge |688,324.68 |
| Constrained covariance hedge |350,957.08 |

These eight scenarios are not a statistical sample or a new held-out test.
They do not prove that the covariance hedge dominates all future curves.

Reducing mortality force to0.8 increases liability PV to126,326,153.13, a
6,945,657.71 deficit against every equally funded fixed asset portfolio
(5.8181% of the initial liability). Increasing force to1.2 reduces liability
PV to113,491,792.81. Neither multiplier is a calibrated longevity forecast.
The rate hedge does not manufacture a mortality hedge.

Changing the maximum paying age from120 to110 reduces PV by49.79 in this
specific period-table case. Preserving the curve through30years and replacing
the extrapolated tail with the29–30year forward lowers PV by7,930.27; a flat
30year zero tail lowers it by21,482.99. These values describe sensitivity to
explicit long-end assumptions, not observations beyond the quoted range.

## Ten-year expected runoff

All108 combinations of4portfolios,3mortality forces,3liquidation haircuts and
3cash-rate sensitivities are retained. Zero bonds mature before benefits are
paid. Cash shortages trigger pro-rata sales at deterministic initial-curve
forward marks. Haircuts and reinvestment shifts are imposed assumptions.

At base mortality and base cash reinvestment, a2% haircut gives:

| Fixed portfolio | Gross sales, USD | Nominal haircut losses, USD | Year10 surplus after carried unpaid benefits, USD |
| --- | ---: | ---: | ---: |
| Five-year zero |46,745,289.45 |934,905.79 |−1,406,579.58 |
| Duration match |46,745,289.45 |934,905.79 |−1,406,579.58 |
| Key-rate hedge |24,633,163.36 |492,663.27 |−641,104.70 |
| Covariance hedge |26,333,767.98 |526,675.36 |−705,016.81 |

The nominal sum of haircut losses and year10 funding deficit use different
valuation dates. Lost proceeds also lose their forward accumulation. They
must not be compared as if they were the same quantity.

No benefit remains unpaid aboveUSD0.01 in this108-case grid. Raw floating-point
residuals are preserved, including a maximum cumulative unpaid value of
5.59e-9USD. This is not evidence of a real benefit default or a calibrated
shortfall probability. Separate synthetic boundary tests deliberately exhaust
assets and verify that unpaid obligations are carried rather than hidden.

## Verification and reproduction

Before executing this case on the official inputs, the calculation details,
engine, tests and driver were committed as
`f0168dd5a89af997e123ca2aabf06bf2e46d69e8`. The frozen historical method files
were not altered.

The independent verifier reads the raw CSV and mortality transcription. It
reconstructs Svensson discounts, each cohort's survival, all56 instantaneous
results and every1,080 annual runoff record using50-digit Decimal arithmetic.
All23,714 numeric comparisons pass aUSD0.0001 absolute financial tolerance,
with tighter separate risk-unit tolerances. The largest financial difference
is8.01e-8USD. Both current constrained optima also match independent exhaustive
enumeration of243 bound faces per objective. The largest discounted-wealth
conservation residual in the production run is4.47e-8USD.

`current_case.json`, `runoff_years.csv` and `current_case_manifest.json`
reproduce byte-for-byte in an isolated directory from copied, hash-checked
inputs and code. This is reproduction in the recorded environment, not external
independent replication. No historical final outcome is refitted or rescored.

From the repository root, with the pinned Python requirements installed:

```bash
PYTHONPATH=src:extensions/treasury_alm python extensions/treasury_alm/run_current_case.py \
  --source PATH_TO_PINNED_FED_CSV \
  --historical-evidence reports/treasury_20261019 \
  --output NEW_EMPTY_DIRECTORY \
  --implementation-commit f0168dd5a89af997e123ca2aabf06bf2e46d69e8

python extensions/treasury_alm/verify_current_case.py \
  --source PATH_TO_PINNED_FED_CSV --evidence NEW_EMPTY_DIRECTORY \
  --historical reports/treasury_20261019 \
  --mortality extensions/treasury_alm/data/ssa_2023_period_qx.csv

python extensions/treasury_alm/reproduce_current_case.py \
  --project PATH_TO_REPOSITORY --source PATH_TO_PINNED_FED_CSV \
  --evidence reports/current_case_20261019 --temporary-parent TEMP_DIRECTORY
```

The source CSV SHA256 is
`7286435090933f0df1dcaeb15629f3a9129c083baee4c42ae5df03d0bb89335c`.
The source and use/convention ledger is in the main treasury protocol. The
original CSV is available at
https://www.federalreserve.gov/data/yield-curve-tables/feds200628.csv.
The derived mortality transcription comes from
https://www.ssa.gov/oact/STATS/table4c6.html. The pinned2026 curve vintage can
contain retrospective revisions. SSA period mortality describes the Social
Security area population and does not establish Indian annuitant mortality.

## Remaining release requirements

The replacement's [independent formula workbook and validation](../workbook_20261019/WORKBOOK.md)
are now complete. They independently reconcile these results and selected
historical repricings, closing the valuation/workbook gate. Full-study
reproduction, technical/decision reports, the current explorer and clean public
release remain unfinished. Do not reuse the old Indian-case workbook as
evidence for these USD results or publish the old source history.
