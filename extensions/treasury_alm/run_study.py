"""Separate development, sealed final predictions and final scoring phases.

No network calls. Existing evidence is never overwritten. Source/code hashes
must match the saved development freeze before either final phase is allowed.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform

from gsw import read_gsw_csv, month_ends
from hedging import (METHODS, train_covariance, experiments, arrays_by_method,
                     select_development, summarize, paired_rmse_bootstrap)
import numpy as np


HERE=Path(__file__).resolve().parent
SOURCE_SHA256='7286435090933f0df1dcaeb15629f3a9129c083baee4c42ae5df03d0bb89335c'
METHOD_FILES=('PROTOCOL.md','gsw.py','hedging.py','run_study.py','test_sources.py','test_hedging.py')


def sha(raw):return hashlib.sha256(raw).hexdigest()


def write_new(path,data):
    with path.open('x') as output:
        json.dump(data,output,indent=2,allow_nan=False)
        output.write('\n')


def method_hashes():
    files={name:sha((HERE/name).read_bytes()) for name in METHOD_FILES}
    engine=HERE.parents[1]/'src/retirement_alm/engine.py'
    files['../../src/retirement_alm/engine.py']=sha(engine.read_bytes())
    return files


def checked_source(path):
    raw=path.read_bytes()
    if sha(raw)!=SOURCE_SHA256:raise ValueError('Actual pinned official CSV hash differs')
    curves,audit=read_gsw_csv(raw.decode('utf-8-sig'),quarantine_reconstruction=True)
    monthly=month_ends(curves,'1999-12','2025-12')
    current=month_ends(curves,'2026-09','2026-09')['2026-09']
    if len(monthly)!=313:raise ValueError('Changed313-month source universe')
    return monthly,current,audit


def load_freeze(folder):
    freeze=json.loads((folder/'development_freeze.json').read_text())
    if freeze['method_sha256']!=method_hashes():raise ValueError('Method changed after development freeze')
    for name,digest in freeze['development_file_sha256'].items():
        if sha((folder/name).read_bytes())!=digest:raise ValueError('Development evidence changed')
    if freeze['selected_method'] not in METHODS:raise ValueError('Unknown frozen selection')
    return freeze


def development(source,folder):
    if folder.exists() and any(folder.iterdir()):raise ValueError('Use a new empty evidence directory; no overwrite')
    monthly,current,audit=checked_source(source)
    covariance=train_covariance(monthly)
    rows=experiments(monthly,covariance,first_end='2015-01',last_end='2018-12')
    selected,scores=select_development(rows)
    folder.mkdir(parents=True,exist_ok=True)
    write_new(folder/'source_audit.json',{'source_sha256':SOURCE_SHA256,'monthly_curves':313,
        'end_labelled_intervals':{'train':180,'development':48,'final':84},
        'current_case_curve':str(current.asof),'daily_audit':audit})
    write_new(folder/'development_predictions.json',rows)
    write_new(folder/'development_selection.json',{'selected_method':selected,'scores':scores,
        'rule':'Within1% of minimum development RMSE, prefer five_year/duration_match/key_rate/covariance',
        'covariance_train_end':'2014-12','covariance':covariance.tolist()})
    sealed=('source_audit.json','development_predictions.json','development_selection.json')
    write_new(folder/'development_freeze.json',{'source_sha256':SOURCE_SHA256,
        'created_utc':datetime.now(timezone.utc).isoformat(),'selected_method':selected,
        'method_sha256':method_hashes(),'development_file_sha256':{name:sha((folder/name).read_bytes()) for name in sealed},
        'environment':{'python':platform.python_version(),'numpy':importlib.metadata.version('numpy'),
                       'scipy':importlib.metadata.version('scipy')},
        'final_predictions_computed':False,'final_metrics_computed':False})
    print(json.dumps({'phase':'development','observations':48,'selected_method':selected,
                      'final_predictions_computed':False}))


def predict(source,folder):
    freeze=load_freeze(folder)
    if (folder/'final_prediction_seal.json').exists() or (folder/'final_predictions.json').exists():
        raise ValueError('Existing final prediction evidence retained; no overwrite')
    monthly,_,_=checked_source(source)
    selection=json.loads((folder/'development_selection.json').read_text())
    rows=experiments(monthly,np.array(selection['covariance']),first_end='2019-01',last_end='2025-12')
    arrays_by_method(rows,84)
    write_new(folder/'final_predictions.json',rows)
    write_new(folder/'final_prediction_seal.json',{'source_sha256':SOURCE_SHA256,
        'prediction_sha256':sha((folder/'final_predictions.json').read_bytes()),
        'development_freeze_sha256':sha((folder/'development_freeze.json').read_bytes()),
        'selected_method':freeze['selected_method'],'observations_per_candidate':84,
        'candidates':list(METHODS),'created_utc':datetime.now(timezone.utc).isoformat(),
        'final_metrics_computed':False})
    print(json.dumps({'phase':'final_prediction','observations_per_candidate':84,
                      'candidates':4,'predictions_sealed_before_scoring':True}))


def score(folder):
    freeze=load_freeze(folder)
    seal=json.loads((folder/'final_prediction_seal.json').read_text())
    if seal['development_freeze_sha256']!=sha((folder/'development_freeze.json').read_bytes()):
        raise ValueError('Development freeze changed after final prediction')
    if seal['prediction_sha256']!=sha((folder/'final_predictions.json').read_bytes()):
        raise ValueError('Final predictions changed')
    rows=json.loads((folder/'final_predictions.json').read_text())
    arrays=arrays_by_method(rows,84)
    primary=paired_rmse_bootstrap(arrays[freeze['selected_method']],arrays['duration_match'])
    report={'selected_method':freeze['selected_method'],'selection_used_final_outcomes':False,
        'primary_benchmark':'duration_match','source_sha256':SOURCE_SHA256,
        'prediction_sha256':seal['prediction_sha256'],
        'final_scores':{name:summarize(values) for name,values in arrays.items()},
        'primary_comparison':primary,
        'supported_superiority':primary['ci95'][1]<0,
        'units':'Surplus changes and RMSE are fractions of initial liability PV; multiply10000 for basis points.',
        'scope':'Retrospective pinned revised-curve vintage; hypothetical reset one-month liability/zero-bond experiments; no executable trades or realized profit.'}
    write_new(folder/'final_results.json',report)
    print(json.dumps(report,indent=2))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('phase',choices=['development','predict-final','score-final'])
    parser.add_argument('--source',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.phase!='score-final' and args.source is None:parser.error('--source is required before scoring')
    if args.phase=='development':development(args.source,args.output)
    elif args.phase=='predict-final':predict(args.source,args.output)
    else:score(args.output)


if __name__=='__main__':main()
