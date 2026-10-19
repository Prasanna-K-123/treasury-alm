# Treasury ALM formula workbook

The [standalone workbook](../../artifacts/Treasury_ALM_Reconciliation.xlsx)
independently calculates the current benefit liability, Svensson discounts,
rate exposures, fixed-asset valuations and ten-year expected runoff. It also
reprices three observed historical curve pairs for all four portfolios and
recalculates the four RMSEs from the sealed 84-month final predictions.

## Use and interpretation

Open **ALM review** for the balance sheet, key exposures and runoff summary.
Change the blue entries in **Controls**. Rates are entered in basis points,
liquidation haircut as a fraction, and mortality as a positive force multiplier.
Zero annual benefit is valid. A missing or invalid required driver produces an
error instead of a fabricated zero.

The source observations and original face amounts remain on **Sources**.
Holdings are fixed at their original, fully funded inception values. Changing
mortality or benefits changes the liability; it does not create new capital or
re-optimise the assets. The default portfolio remains the covariance hedge
selected using the historical development period.

Instantaneous rate shifts and alternative curve tails affect the current
valuation. The runoff retains the base Svensson curve's deterministic forwards.
Mortality, benefits, haircut and cash-reinvestment controls affect that runoff.
The source period mortality is not an annuitant or cohort forecast. All benefits,
assets, haircuts and cash-rate sensitivities are synthetic or imposed assumptions.

**Historical** has a single active repricing build. Its month control selects
January 2019, March 2020 or September 2022, using the actual source observation
dates and elapsed calendar days divided by 365.25. The final-prediction table is
an input. Its four RMSEs are independently aggregated in the workbook. Portfolio
weights and initial face amounts are imported from the sealed model evidence,
not independently optimised in Excel. The optimisers have separate analytical
and exhaustive active-face verification.

## Validation completed

- All 56 instantaneous portfolio results reconcile to the current-case evidence.
- All 108 runoff scenarios, including all 1,080 annual records, reconcile.
- Twelve historical portfolio-month combinations independently reprice the
  liability and rolled zero bonds. Surplus fractions agree within 2e-12.
- Four 84-month final RMSEs and biases reconcile. All 30 current published zero
  yields reconcile to the parameter reconstruction within the fixed 0.02bp rule.
- Duration, convexity, DV01, key exposures and long-end value reconcile.
- Zero benefit, missing benefit, invalid mortality and invalid haircut boundaries
  are checked. A missing historical selector does not disable the unrelated
  current valuation.
- All seven sheets are rendered and visually reviewed. The exported ZIP has no
  corrupt member or error-typed formula cell. Frozen rows and columns survive
  export. The saved XLSX is reopened, recalculated and checked after changing
  mortality in that disposable copy.

There are 22,166 numeric comparisons. The financial absolute tolerance is
USD0.0001, and the largest observed financial difference is
USD0.0000001341104507446289. Risk-unit and historical-fraction tolerances are
specified separately in the executable builder. No source observations,
historical method, development selection or sealed final result is changed.

The formula engine and saved-file reimport/recalculation are verified. Native
desktop Excel has not been executed. The delivered workbook uses ordinary
spreadsheet formulas and contains the required inputs. The two JSON validation
records in this directory provide the detailed evidence.

## Rebuild

The preparer copies only hash-verified source parameters, mortality observations
and sealed reference outputs. It performs no model fitting or outcome search:

```bash
python extensions/treasury_alm/prepare_workbook_inputs.py \
  --project PATH_TO_REPOSITORY --source PATH_TO_PINNED_FED_CSV \
  --output PATH_TO_TEMP_INPUTS_JSON
```

The workbook builder uses the Artifact Tool runtime provided by the authoring
environment. Copy `tools/build_treasury_reconciliation.mjs` to a separate
temporary directory with its `node_modules` linked to the supplied runtime
dependencies. Set `TREASURY_WORKBOOK_INPUT` to the generated JSON and
`TREASURY_WORKBOOK_OUTPUT` to a new output directory, then execute the builder
with that runtime's Node executable. It runs the full reconciliations before
export and records the final workbook hash. Opening and using the delivered
workbook does not require that authoring runtime, a model account or a paid API.

This workbook closes the independent mathematical-reconciliation requirement.
The full-study reproduction, technical/decision reports and clean public release
are separate remaining requirements.
