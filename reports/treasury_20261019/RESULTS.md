# Historical treasury hedge comparison — component result

19 October2026. This completes the predeclared historical comparison component. The full P4 project is still private and incomplete; the current mortality/liquidity case, independent workbook, complete reports and publication remain open.

## Design and decision

Train2000–2014; development2015–2018; final2019–2025. The48-month development rule selected the covariance hedge before the84 final monthly outcomes were scored. All four final prediction sets were committed and sealed first. The fixed primary comparator is the fully funded5/20-year duration match.

| Candidate | Final months | Surplus RMSE (bp of initial liability PV) | Worst monthly surplus (bp of initial liability PV) |
|---|---:|---:|---:|
| five_year | 84 | 203.2079 | -551.6807 |
| duration_match | 84 | 15.8651 | -58.1037 |
| key_rate | 84 | 7.6795 | -27.4918 |
| covariance | 84 | 6.4994 | -22.8528 |

The selected hedge's RMSE is 59.03% lower than the duration-match comparator. Primary covariance-minus-duration RMSE difference: -9.3656bp, paired six-month circular-block bootstrap95% interval[-12.3423,-6.0242]bp (5,000 draws; seed20261019). This supports lower RMSE within this specified experiment. The key-rate candidate is reported in full; no separate superiority claim against it is pre-awarded.

## What this establishes and what remains limited

The evidence concerns reset one-month synthetic liabilities paying100 annually at years1–30, funded with hypothetical zero-coupon assets. Maturities roll by actual days/365.25. Each interval begins with equal asset/liability value. This is surplus-risk validation, not executable bond trades, a continuous wealth backtest, observed transaction costs, real profit or guaranteed future performance. Basis points here measure a fraction of initial liability value, not a yield change.

The source is the pinned19October2026 vintage of the Federal Reserve staff-research curve. Historical values may have been revised; immutable historical publication vintages are not available in this study. All313 required month-ends pass the original0.02bp parameter-reconstruction rule. Two non-month-end source exceptions are quarantined and preserved in the raw snapshot; they do not change the month grid. The2019–2025 evaluation spans only84 dependent monthly observations. The block-bootstrap interval is conditional on the fixed development selection and observed calendar; it does not establish universal hedge dominance.

## Verification

The final336 candidate-month records,84 per candidate, retain weights, dates and initial liability values. Independent50-digit Decimal arithmetic verifies each RMSE, all calendars, full-funding and cap constraints, and the development selection. A clean directory reproduced all three phases from the pinned raw CSV and copied source code; five scientific outputs are byte-identical. This is same-environment reproduction, not independent external replication. The full P4 reproduction gate remains open until the remaining components are finished.

Core evidence: development_freeze.json, development_selection.json, final_prediction_seal.json, final_predictions.json, final_results.json, holdout_verification.json and historical_reproduction.json.

Source URL: https://www.federalreserve.gov/data/yield-curve-tables/feds200628.csv
Source SHA256: 7286435090933f0df1dcaeb15629f3a9129c083baee4c42ae5df03d0bb89335c
Prediction SHA256: b166252af3a7cf8a3ed64981ac96baddefefc07a124190268ac269de37beefc9
Recorded environment: {"numpy": "2.3.5", "python": "3.12.14", "scipy": "1.17.0"}
