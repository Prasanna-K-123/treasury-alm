"""Run only the deterministic current case from hash-pinned public inputs."""
import argparse
import csv
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import platform
import numpy as np

from current_case import evaluate_current_case
from gsw import read_ssa_qx
from hedging import train_covariance
from run_study import checked_source,load_freeze,method_hashes,SOURCE_SHA256


HERE=Path(__file__).resolve().parent
SSA_SHA256='1cc6300b231972794d25dbf8ed53f559ffe2557c2082e52d9e8774b66e41ae35'
CASE_FILES=('CURRENT_CASE_METHODS.md','current_case.py','test_current_case.py','run_current_case.py')


def sha(raw):return hashlib.sha256(raw).hexdigest()


def write_json_new(path,data):
    with path.open('x',encoding='utf-8') as out:
        json.dump(data,out,indent=2,allow_nan=False)
        out.write('\n')


def run(source,historical,output,implementation_commit):
    if output.exists() and any(output.iterdir()):
        raise ValueError('Existing current-case evidence retained; choose a new empty directory')
    if len(implementation_commit)!=40 or any(c not in '0123456789abcdef' for c in implementation_commit):
        raise ValueError('Actual pre-execution implementation commit required')
    freeze=load_freeze(historical)
    monthly,current,audit=checked_source(source)
    mortality_raw=(HERE/'data/ssa_2023_period_qx.csv').read_bytes()
    if sha(mortality_raw)!=SSA_SHA256:
        raise ValueError('Mortality transcription hash differs from accepted source')
    mortality=read_ssa_qx(mortality_raw.decode('utf-8'))
    development=json.loads((historical/'development_selection.json').read_text())
    covariance=train_covariance(monthly)
    if not np.array_equal(covariance,np.array(development['covariance'])):
        raise ValueError('Fixed training covariance differs from sealed development evidence')
    result=evaluate_current_case(current,mortality,covariance)
    if freeze['selected_method']!=result['historically_selected_method']:
        raise ValueError('Historical selection differs; current case cannot override it')
    if result['scenario_counts']!={'instantaneous_axis_cases':14,'instantaneous_portfolio_results':56,'runoff_cases':108}:
        raise ValueError('Changed declared scenario grid')
    rows=[]
    for index,case in enumerate(result['runoff_scenarios']):
        years=case.pop('years')
        case['case_id']=index
        for year in years:
            row={'case_id':index,'method':case['method'],'mortality_force':case['mortality_force'],
                 'haircut':case['haircut'],'cash_rate_shift_decimal':case['cash_rate_shift_decimal'],**year}
            faces=row.pop('remaining_faces_usd')
            for key,face in zip((1,5,10,20,30),faces):row[f'remaining_face_{key}y_usd']=face
            rows.append(row)
    text=io.StringIO(newline='')
    writer=csv.DictWriter(text,fieldnames=list(rows[0]),lineterminator='\n')
    writer.writeheader();writer.writerows(rows)
    raw=text.getvalue().encode('utf-8')
    result['provenance']={'source_csv_sha256':SOURCE_SHA256,'source_csv_bytes':source.stat().st_size,
        'ssa_transcription_sha256':SSA_SHA256,'case_implementation_pre_execution_commit':implementation_commit,
        'case_method_sha256':{name:sha((HERE/name).read_bytes()) for name in CASE_FILES},
        'historical_method_sha256':method_hashes(),
        'historical_development_freeze_sha256':sha((historical/'development_freeze.json').read_bytes()),
        'train_covariance':covariance.tolist(),'train_covariance_last_end_month':'2014-12',
        'current_curve_staleness_days':0,'required_historical_months':len(monthly),
        'accepted_daily_source_rows':audit['valid_rows'],
        'source_reconstruction_quarantines':audit['quarantined_reconstruction_rows'],
        'runoff_year_rows':len(rows),'runoff_year_csv_sha256':sha(raw),
        'environment':{'python':platform.python_version(),'numpy':importlib.metadata.version('numpy'),
                       'scipy':importlib.metadata.version('scipy')},
        'final_hedge_evidence_read_or_recomputed':False}
    output.mkdir(parents=True,exist_ok=True)
    with (output/'runoff_years.csv').open('xb') as out:out.write(raw)
    write_json_new(output/'current_case.json',result)
    files=['current_case.json','runoff_years.csv']
    write_json_new(output/'current_case_manifest.json',{'implementation_commit':implementation_commit,
        'scientific_outputs':{name:{'sha256':sha((output/name).read_bytes()),'bytes':(output/name).stat().st_size} for name in files},
        'history_unchanged':True,'whole_project_gates_earned_by_this_component':0})
    print(json.dumps({'curve_date':result['curve_date'],'liability_pv_usd':result['base_liability_risk']['pv'],
        'scenario_counts':result['scenario_counts'],'annual_runoff_rows':len(rows),
        'largest_wealth_conservation_error_usd':max(x['discounted_wealth_max_abs_error_usd'] for x in result['runoff_scenarios'])}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--historical-evidence',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--implementation-commit',required=True)
    args=parser.parse_args()
    run(args.source,args.historical_evidence,args.output,args.implementation_commit)
