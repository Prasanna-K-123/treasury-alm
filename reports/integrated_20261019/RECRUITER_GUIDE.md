# Treasury ALM: reviewer guide

## Evidence in one paragraph

Built a Treasury ALM research system combining official Fed term structures,
constrained interest-rate hedges and a synthetic benefit runoff ledger.
The development-selected covariance hedge reduced final-period surplus RMSE
by 59.03% against duration matching across 84 monthly tests, with a paired block
interval supporting the comparison. A separate USD 119.38 million synthetic liability
case demonstrates remaining longevity and liquidation exposures. An independent
formula workbook and Decimal ledger reconcile the results; the complete study
reproduces from pinned inputs.

## Five-minute review

1. Read the decision brief for the recommendation, tradeoff and boundaries.
2. Compare all four historical methods and the stated confidence interval in
   the technical report; note how development selection precedes final scoring.
3. Change mortality force and haircut in the workbook or inspect the saved
   scenarios in the explorer. Lower rate RMSE is not a universal ALM optimum.
4. Open the raw annual ledger, source audit and clean-reproduction receipt.

## Interview discussion

- Why duration matching leaves curve-shape risk, and what the five-node
  covariance objective approximates.
- How training-only covariance, development simplicity selection and a sealed
  final comparison limit evaluation leakage.
- Why the covariance hedge's best final rate RMSE does not imply the lowest
  deterministic liquidation cost.
- Why mortality-force sensitivity is not a probability or an Indian annuitant
  forecast, and why revised curves are not immutable point-in-time data.
- How cash-flow timing, forward marks, nominal sale losses and horizon funding
  deficits differ, and how unpaid obligations are carried rather than hidden.
- What an independent formula workbook verifies and which optimiser outputs
  are imported; what same-environment reproduction cannot establish.

## Presentation boundaries

Use the actual study labels, population, dates and units. Do not describe the
RMSE reduction as investment return, savings, a live portfolio, regulatory
approval or universal dominance. The case uses public US sources with explicit
synthetic contracts.
