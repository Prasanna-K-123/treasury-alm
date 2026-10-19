"""Package the saved Treasury evidence; does not calculate or fit a model."""
import csv
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
DOCS=ROOT/'docs'
DOCS.mkdir(exist_ok=True)
read=lambda path:json.loads((ROOT/path).read_text())
data={'historical':read('reports/treasury_20261019/final_results.json'),
      'case':read('reports/current_case_20261019/current_case.json')}
with (ROOT/'reports/current_case_20261019/runoff_years.csv').open() as file:
    rows=list(csv.DictReader(file))
data['annual']=[{k:(row[k] if k=='method' else float(row[k])) for k in
    ('case_id','method','year','benefits_due_usd','benefits_paid_usd','gross_bond_sales_usd',
     'haircut_cost_usd','closing_cash_usd','assets_usd','remaining_liability_usd',
     'unpaid_benefits_usd','surplus_after_unpaid_usd')} for row in rows]
assert len(data['annual'])==1080
for directory in ('exports',): (DOCS/directory).mkdir(exist_ok=True)
exports={'Treasury_ALM_Decision_Brief.pdf':'output/pdf/Treasury_ALM_Decision_Brief.pdf',
         'Treasury_ALM_Technical_Report.pdf':'output/pdf/Treasury_ALM_Technical_Report.pdf',
         'Treasury_ALM_Reconciliation.xlsx':'artifacts/Treasury_ALM_Reconciliation.xlsx',
         'runoff_years.csv':'reports/current_case_20261019/runoff_years.csv',
         'current_case.json':'reports/current_case_20261019/current_case.json',
         'historical_results.json':'reports/treasury_20261019/final_results.json',
         'final_predictions.json':'reports/treasury_20261019/final_predictions.json',
         'full_study_reproduction.json':'reports/integrated_20261019/full_study_reproduction.json'}
for name,relative in exports.items():shutil.copyfile(ROOT/relative,DOCS/'exports'/name)
shutil.copyfile(ROOT/'reports/integrated_20261019/diagnostics.png',DOCS/'diagnostics.png')
template=(ROOT/'tools/explorer.template.html').read_text()
page=template.replace('__EVIDENCE__',json.dumps(data,separators=(',',':')).replace('</','<\\/'))
(DOCS/'index.html').write_text(page)
receipt={'status':'built; live browser checks pending','embedded_annual_rows':1080,
    'embedded_instantaneous_results':56,'embedded_runoff_cases':108,
    'html_sha256':hashlib.sha256(page.encode()).hexdigest(),
    'exports':{name:hashlib.sha256((DOCS/'exports'/name).read_bytes()).hexdigest() for name in exports},
    'model_computation_performed':False}
(ROOT/'reports/integrated_20261019/explorer_build.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'status':'built','html_bytes':len(page.encode()),'exports':len(exports)}))
