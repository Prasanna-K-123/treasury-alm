# Treasury ALM, interest-rate hedging and liquidity risk — revision 1

Decision frozen 19 October 2026 before computing any new hedge-performance result. This is the replacement P4 design. It remains private and incomplete. The earlier Indian retirement illustration is a historical study, not evidence for this revision.

## Decision and distinct contribution

For a defined nominal liability, does a constrained key-rate or covariance hedge improve out-of-sample surplus stability over a simple duration match? When do longevity, illiquidity or long-end model assumptions overwhelm that improvement? Deliver an auditable balance-sheet decision, Python engine, independent spreadsheet, held-out historical comparison and static scenario explorer.

This slot serves treasury, interest-rate/model risk, insurance ALM and retirement consulting. It adds term-structure valuation and balance-sheet hedging to a portfolio already covering credit, insurance pricing/reserving, causal decisions, supply chains and macro forecasting. It is not a trading-return project or a claim of Indian regulatory compliance.

## Free sources and conventions

Use only the Federal Reserve's published Gürkaynak–Sack–Wright nominal curve data, its paper and documented convention table, and SSA's 2023 period table used in the 2026 Trustees Report. Board/SSA staff material has explicit public-domain policies. No FRG/CCIL curve trace or IAI mortality numbers enter the new release. No emails, accounts, paid services or paid API inference are required.

GSW SVENY is continuously compounded percent per annum; discount factors are exp(-t*y/100). SVENPY is coupon-equivalent and must never be substituted. BETA parameters are percent, TAU parameters years. Reconstruct the Svensson curve and reconcile all 30 published zero yields to within 0.02 basis points. The current published historical vintage can be revised. Call the historical experiment a retrospective test using a pinned downloaded vintage, not an immutable point-in-time market backtest.

Source URLs:
- https://www.federalreserve.gov/data/nominal-yield-curve.htm
- https://www.federalreserve.gov/data/yield-curve-tables/feds200628.csv
- https://www.federalreserve.gov/data/yield-curve-tables/feds200628_1.html
- https://www.federalreserve.gov/pubs/feds/2006/200628/index.html
- https://www.federalreserve.gov/disclaimer.htm
- https://www.ssa.gov/oact/STATS/table4c6.html
- https://www.ssa.gov/policy/accessibility.html

Initial intake contained one authentic GSW curve row plus all120 SSA qx rows,
retrieved through normalized official web tables. Those remain clearly labelled
fixtures/transcriptions. The complete original official GSW CSV has subsequently
been acquired and byte-verified; the source-audit amendment below governs its use.

### Source-audit amendment,19October2026, before any hedge outcome

The complete original official CSV has now been downloaded:16,657,704bytes,
SHA2567286435090933f0df1dcaeb15629f3a9129c083baee4c42ae5df03d0bb89335c.
Across6,712 complete daily parameter/zero rows in the input window,2 exceed the
fixed0.02bp reconstruction tolerance:2008-07-16(0.029257354bp) and
2013-10-16(0.037964987bp). Do not increase the tolerance. Explicitly quarantine
every daily row that fails the same reconstruction rule, retain all raw rows and
the audit ledger, and select month-ends only from accepted complete curves.
Both observed exceptions are outside the last observation of their month;
verify that all313 required month-ends and the September2026 curve still pass.
A missing/stale month continues to fail acceptance. This amendment responds
only to source reconciliation, before any development/final hedge result;
it changes neither candidate definitions nor performance selection rules.

## Historical design

Universe: a December 1999 starting anchor plus complete monthly curve observations January 2000–December 2025. This provides313 monthly curves and312 one-month observations labelled by ending month (180 train,48 development,84 final). Select the last complete published curve on or before each calendar month-end, at most seven calendar days stale. Never interpolate across missing months. Record missing and rejected rows and fail the full-window acceptance gate if a required month cannot be justified.

Train January 2000–December 2014; development January 2015–December 2018; final January 2019–December 2025. The label is the END month of each one-month observation. Consequently a development observation may start at December 2014 and a final observation at December 2018. Boundaries and raw-vintage hash must be checked explicitly. Some 2024 curve inputs were viewed while establishing source conventions; no hedge outcome or candidate comparison has been computed. Do not claim complete blindness to public historical rates.

Each start date defines a new synthetic liability paying 100 nominal currency units at years 1–30, and fully funded hypothetical zero-coupon assets at years 1, 5, 10, 20 and 30. Advance every maturity by actual calendar days/365.25 and value both sides on the next observed curve. The one-month interval is shorter than the first payment/maturity. Define surplus change as (next asset PV - next liability PV)/initial liability PV. This is a series of reset one-month hedge experiments, not a continuously financed wealth strategy. There are no actual bond trades, executable quotes, observed transaction costs or realized profits.

Four candidates, all with weight sum 1:
1. All assets in a 5-year zero.
2. Analytic nonnegative 5/20-year duration match, failing visibly if liability duration is outside [5,20].
3. Five-node key-rate hedge: minimize squared key-duration mismatch; long-only, each weight <=60%.
4. Covariance hedge: minimize exposure' * Sigma * exposure plus 1e-8*sum(weight^2), same long-only/cap constraints. Sigma uses train-period monthly changes in the five zero yields, with fixed 25% diagonal shrinkage. No train covariance update after 2014.

Liability key durations use piecewise-linear rate-bump hats at the same five nodes, partitioning a parallel shift, with exact continuous-compounding derivatives checked against central differences. Candidate 4 is a local-risk approximation, not a guarantee of minimum realized surplus variance.

Selection: lowest development surplus RMSE; within 1% of that minimum prefer candidates in the order 1,2,3,4. Freeze code, selection, inputs and predictions before final scoring. Primary final comparison is selected candidate minus duration-match surplus RMSE. Also report bias, mean absolute surplus change, worst surplus, 5% empirical lower tail and every individual month. Use paired circular six-month block bootstrap, 5,000 draws, seed 20261019, for the primary difference. Report uncertainty and the limited number of calendar regimes. No superiority claim if unsupported. Do not retune on final results or force a complex winner.

## Current balance-sheet and stress case

Use the latest complete curve on or before 30 September 2026 with the same stale-data rule; no later curve. Mortality is the published SSA 2023 PERIOD table, not historically available in 2023 and not an annuitant/cohort longevity forecast. Synthetic USD annual-in-arrears life-only benefits of 12,000; four groups of 250 lives: male age60, female65, male70, female75. Force terminal death at age120 as a disclosed modelling assumption; source qx covers ages0–119. Show terminal-age110/120 and post-30-year present-value sensitivity, and distinguish curve extrapolation from observed maturities.

Predeclared stresses: parallel +/-50/100/200bp; opposite-signed +/-50bp short/long twists; mortality force multipliers0.8/1.0/1.2; and explicit 0/1/2% asset-liquidation haircuts. Report baseline funding, key exposures, cash-flow coverage and ten-year deterministic runoff under stated reinvestment assumptions. Separate interest-rate, longevity and liquidity effects. A deterministic shortfall is a scenario result, not a calibrated probability or solvency capital number.

## Six finite acceptance gates, 2 points each

A. Complete hashed official GSW history/current curve and SSA transcription, source-use and compounding evidence, date/unit/row audit; no unresolved external consent.
B. Valuation/hedge/annuity and calendar logic, finite-difference/analytic boundaries, independent spreadsheet reconciliations.
C. Frozen train/development/final protocol, fixed development selection, final paired evidence and failure ledger.
D. Reproduction from the pinned public inputs in a clean directory; numeric comparison tolerances documented.
E. Complete technical report, decision memo, reproducible workbook and recruiter explanation; all empirical and synthetic claims distinguished.
F. Clean public repository/history, actual live explorer QA, supported release tag and linked evidence.

Old P4 gates are historical. Reassess every affected gate; do not carry eight points into this replacement by renaming it. An authentic source fixture or passing unit tests alone earns no empirical gate.
