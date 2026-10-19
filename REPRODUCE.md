# Reproduce the Treasury study

## Python science

Use Python3.12.14 and `pip install -r requirements.txt`. The recorded numeric
versions are NumPy2.3.5 and SciPy1.17.0. From the repository root, set
`PYTHONPATH=src:extensions/treasury_alm` for the historical/current drivers.

The pinned original CSV is `feds200628.csv`, SHA256
`7286435090933f0df1dcaeb15629f3a9129c083baee4c42ae5df03d0bb89335c`.
The source script rejects other bytes; a later download from the live official
URL may have changed. The SSA transcription is in
`extensions/treasury_alm/data/ssa_2023_period_qx.csv`.

```bash
python extensions/treasury_alm/reproduce_full_study.py \
  --project . --source feds200628.csv --python-only \
  --temporary-parent NEW_TEMP_DIRECTORY --output NEW_RECEIPT.json
```

This command uses only the pinned public Python dependencies, runs all 31
boundary checks and recomputes all eight scientific outputs in an isolated
directory. It verifies the independent Decimal ledger too. It does not rebuild
the workbook and labels that limit in its own receipt. No published evidence
is overwritten; use new temporary/output paths. Repeating the calculation does
not create a new unseen holdout.

## Independent workbook

Open `artifacts/Treasury_ALM_Reconciliation.xlsx`. Blue controls drive
independent formulas. Current initial faces and historical weights are fixed
imports; the workbook does not optimise them. Its guide describes every
check, input boundary and tolerance. Saved-file import/recalculation was tested
with the Artifact Tool engine; native desktop Excel was not executed.

Rebuilding the workbook additionally requires the Artifact Tool JavaScript
runtime used for its source builder. It is separate from the public Python
dependencies. The saved workbook's formulas are available for inspection and
recalculation without the builder. No claim that an ordinary pip installation
supplies that JavaScript runtime is made.

## Complete recorded orchestration

With that runtime available, supply its Node executable and node_modules path:

```bash
python extensions/treasury_alm/reproduce_full_study.py \
  --project . --source feds200628.csv \
  --temporary-parent NEW_TEMP_DIRECTORY --output NEW_RECEIPT.json \
  --node PATH_TO_RUNTIME_NODE --node-modules PATH_TO_RUNTIME_NODE_MODULES
```

The orchestration copies only the required code/data to an isolated directory,
runs 31 boundary checks, recomputes all historical phases, regenerates the current
case, runs independent verification and rebuilds the workbook. Five historical
and three current scientific hashes must match exactly. Original historical
freeze metadata remains the current-case provenance; new-run seal timestamps
are kept separately. XLSX relationship IDs are resolved by identical targets;
ZIP/core timestamps may vary. Formulas, inputs, cached values, styles,
validations and panes must match. No numeric field is ignored.

See `reports/integrated_20261019/full_study_reproduction.json` for the actual
successful run. This is reproduction in the recorded environment, not external
independent replication. The report renderer additionally uses ReportLab and
PyMuPDF; they do not enter the scientific calculation.
