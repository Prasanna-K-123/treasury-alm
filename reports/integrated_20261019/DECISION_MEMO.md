# Treasury ALM decision brief

Prasanna K | 19 October 2026 | Synthetic nominal USD benefit portfolio

## Decision

Take the development-selected covariance hedge forward as the supported
rate-risk candidate against the duration benchmark. Pair that decision with
explicit longevity and liquidity limits. Its historical RMSE improvement does
not eliminate benefit funding risk.

## Evidence supporting the rate hedge

The frozen 2019-2025 final evaluation covers 84 reset one-month hypothetical
hedge experiments, using a pinned revised vintage of official Fed curves.
The selected covariance hedge's surplus RMSE is 6.50 bp of initial liability
PV, versus 15.87 bp for a 5/20-year duration match: 59.03% lower. The paired
six-month block 95% interval for the difference is [-12.34, -6.02] bp. Selection
used only 2015-2018 development outcomes; covariance uses 2000-2014 training
data with fixed 25% diagonal shrinkage. No final-period retuning occurred.

The key-rate comparator has RMSE 7.68 bp; no separate statistical superiority
claim against it is made. These are synthetic fully funded zero-bond hedge
experiments, not executable returns, trading profits or a continuous strategy.

## The larger risks the hedge leaves behind

The 30 September 2026 case has 1,000 synthetic lives across four age/sex cohorts
and USD 12,000 annual survivor benefits. SSA 2023 period mortality gives liability
PV USD 119.38 million, duration 8.47 years and DV01 USD 101,157.93 per 1 bp. Fixed initial
asset faces are used in all stresses.

| Decision exposure | Observed model result | Interpretation |
| --- | --- | --- |
| Parallel 200 bp rate fall | Covariance surplus -USD 0.351 million | The rate hedge controls this declared stress, but has residual mismatch |
| Mortality force multiplied by 0.8 | Liability +USD 6.946 million; +5.82% | Equal funding and rate hedging do not offset imposed longevity sensitivity |
|2% liquidation haircut, base mortality/cash | Covariance year 10 net surplus -USD 0.705 million | Cash-flow mismatch and forced sales create a funding cost |
| Same haircut case, key-rate hedge | Year 10 net surplus -USD 0.641 million | The method with lower rate RMSE need not have the lowest liquidity cost |

The longevity multiplier, haircut and deterministic reinvestment paths are
assumptions. No calibrated probability, capital requirement or actual default
is estimated. All 108 runoff scenarios pay benefits to within USD 0.01; a negative
year-ten surplus means residual assets are below residual liability, not that
benefits necessarily went unpaid. Nominal haircut flow sums and horizon
funding stocks have different dates and must not be conflated.

## Controls and review trail

The original Fed CSV is hashed. All 313 historical month-end curves and the case
curve pass the unchanged 0.02 bp reconstruction rule; two other daily rows are
quarantined transparently. The historical final predictions were sealed before
scoring. A separate 50-digit Decimal ledger verifies 23,714 values. The seven-sheet workbook independently reconciles 22,166 values, including every current
stress and runoff case. Eight scientific files reproduce exactly in a clean
integrated run; the rebuilt workbook has equivalent formulas and contents.
Native desktop Excel and an external independent replication are not claimed.

## What would be needed for a real mandate

Actual plan benefit data and population-appropriate mortality; executable
assets and costs; explicit cash buffers and sale constraints; independent
governance approval and a forward monitoring policy. This portfolio research
supports a disciplined ALM discussion and model review, not a live mandate.

Technical report, source ledger, workbook and reproduction receipt accompany
this brief. Official sources: Federal Reserve GSW nominal curves
(https://www.federalreserve.gov/data/nominal-yield-curve.htm) and SSA period
mortality (https://www.ssa.gov/oact/STATS/table4c6.html).
