"""Prepare hash-checked inputs for the independent formula workbook.

This script copies source parameters, observed qx and sealed reference results.
It does not fit models or generate any scientific outcomes.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path


SOURCE_SHA='7286435090933f0df1dcaeb15629f3a9129c083baee4c42ae5df03d0bb89335c'
SSA_SHA='1cc6300b231972794d25dbf8ed53f559ffe2557c2082e52d9e8774b66e41ae35'
PREDICTION_SHA='b166252af3a7cf8a3ed64981ac96baddefefc07a124190268ac269de37beefc9'
METHODS=('five_year','duration_match','key_rate','covariance')
HISTORICAL_MONTHS=('2019-01','2020-03','2022-09')


def prepare(project,source,output):
    sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    history=project/'reports/treasury_20261019'
    case=project/'reports/current_case_20261019'
    mortality=project/'extensions/treasury_alm/data/ssa_2023_period_qx.csv'
    assert sha(source)==SOURCE_SHA
    assert sha(mortality)==SSA_SHA
    assert sha(history/'final_predictions.json')==PREDICTION_SHA
    read=lambda path:json.loads(path.read_text())
    current=read(case/'current_case.json')
    predictions=read(history/'final_predictions.json')
    scores=read(history/'final_results.json')
    manifest=read(case/'current_case_manifest.json')
    for name,record in manifest['scientific_outputs'].items():assert sha(case/name)==record['sha256']
    assert read(case/'current_case_verification.json')['status']=='passed'
    assert read(case/'current_case_reproduction.json')['status']=='passed'
    lines=source.read_text(encoding='utf-8-sig').splitlines()
    start=next(i for i,line in enumerate(lines) if line.lower().startswith('date,'))
    rows={row['Date']:row for row in csv.DictReader(io.StringIO('\n'.join(lines[start:])))}
    def parameters(day):
        row=rows[day]
        return {'date':day,'beta':[float(row['BETA'+str(i)]) for i in range(4)],
            'tau1':float(row['TAU1']),'tau2':float(row['TAU2']),
            'quoted_zeros_percent':[float(row[f'SVENY{i:02d}']) for i in range(1,31)]}
    mortality_rows=[{k:(int(v) if k=='age' else float(v)) for k,v in row.items()}
                    for row in csv.DictReader(io.StringIO(mortality.read_text()))]
    assert len(mortality_rows)==120 and [r['age'] for r in mortality_rows]==list(range(120))
    historical=[]
    for month in HISTORICAL_MONTHS:
        selected=[row for row in predictions if row['end_month']==month]
        assert len(selected)==4 and {r['method'] for r in selected}==set(METHODS)
        first=selected[0]
        assert all((r['start_date'],r['end_date'])==(first['start_date'],first['end_date']) for r in selected)
        historical.append({'end_month':month,'start':parameters(first['start_date']),
            'end':parameters(first['end_date']),'methods':{r['method']:r for r in selected}})
    months=sorted({row['end_month'] for row in predictions})
    assert len(months)==84 and months[0]=='2019-01' and months[-1]=='2025-12'
    prediction_table=[]
    for month in months:
        values={row['method']:row['surplus_change_fraction'] for row in predictions if row['end_month']==month}
        assert len(values)==4
        prediction_table.append([month]+[values[m] for m in METHODS])
    annual=list(csv.DictReader(io.StringIO((case/'runoff_years.csv').read_text())))
    assert len(annual)==1080
    for record in current['runoff_scenarios']:
        selected=[row for row in annual if int(row['case_id'])==record['case_id']]
        assert [int(row['year']) for row in selected]==list(range(1,11))
        record['annual_rows']=[{k:(v if k=='method' else float(v)) for k,v in row.items()} for row in selected]
    data={'schema':'treasury-workbook-inputs-v1','methods':list(METHODS),
        'method_labels':['Five-year zero','Duration match','Key-rate hedge','Covariance hedge'],
        'current_curve':parameters(current['curve_date']),'mortality':mortality_rows,
        'current_reference':current,'historical_cases':historical,
        'final_prediction_table':prediction_table,'historical_final_reference':scores,
        'provenance':{'fed_csv_sha256':SOURCE_SHA,'ssa_transcription_sha256':SSA_SHA,
            'final_predictions_sha256':PREDICTION_SHA,
            'current_scientific_output_sha256':{n:r['sha256'] for n,r in manifest['scientific_outputs'].items()},
            'source_version':'Pinned downloaded2026vintage; revised historical curves',
            'fed_url':'https://www.federalreserve.gov/data/yield-curve-tables/feds200628.csv',
            'ssa_url':'https://www.ssa.gov/oact/STATS/table4c6.html',
            'historical_weights_imported_not_optimised_in_workbook':True,
            'current_faces_imported_fixed_not_rehedged':True,
            'scientific_outcomes_recomputed':False}}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'output':str(output),'bytes':output.stat().st_size,'historical_repricing_cases':3,
        'final_months':84,'current_instantaneous_results':56,'runoff_years':1080,'source_hashes_checked':True}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('project','source','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    prepare(args.project.resolve(),args.source.resolve(),args.output.resolve())
