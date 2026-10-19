"""Reproduce the current-case component in an isolated directory, without network."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def reproduce(project,source,evidence,temporary_parent):
    sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    manifest=json.loads((evidence/'current_case_manifest.json').read_text())
    files=['current_case.json','runoff_years.csv','current_case_manifest.json']
    expected={name:sha(evidence/name) for name in files}
    current=json.loads((evidence/'current_case.json').read_text())
    assert sha(source)==current['provenance']['source_csv_sha256']
    temporary_parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='treasury-current-',dir=temporary_parent) as directory:
        clean=Path(directory)
        method_names=list(current['provenance']['case_method_sha256'])
        method_names.extend(name for name in current['provenance']['historical_method_sha256'] if not name.startswith('../'))
        for name in sorted(set(method_names)):
            relative=Path('extensions/treasury_alm')/name
            (clean/relative).parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(project/relative,clean/relative)
        for relative in ('src/retirement_alm/engine.py','requirements.txt',
                         'extensions/treasury_alm/data/ssa_2023_period_qx.csv'):
            (clean/relative).parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(project/relative,clean/relative)
        history=clean/'reports/treasury_20261019'
        history.mkdir(parents=True)
        for name in ('source_audit.json','development_predictions.json','development_selection.json','development_freeze.json'):
            shutil.copyfile(project/'reports/treasury_20261019'/name,history/name)
        clean_source=clean/'feds200628.csv';shutil.copyfile(source,clean_source)
        assert sha(clean_source)==sha(source)
        env=os.environ.copy();env['PYTHONPATH']=str(clean/'src')+os.pathsep+str(clean/'extensions/treasury_alm')
        command=[sys.executable,str(clean/'extensions/treasury_alm/run_current_case.py'),
            '--source',str(clean_source),'--historical-evidence',str(history),
            '--output',str(clean/'output'),'--implementation-commit',manifest['implementation_commit']]
        run=subprocess.run(command,cwd=clean,env=env,text=True,capture_output=True,check=True,timeout=60)
        checks=[]
        for name in files:
            actual=sha(clean/'output'/name)
            assert actual==expected[name],name
            checks.append({'file':name,'sha256':actual,'byte_identical':True})
    receipt={'status':'passed','clean_directory':True,'same_environment':True,
        'source_copied_and_hash_checked':True,'network_calls':0,
        'files':checks,'generator_output':json.loads(run.stdout),
        'historical_final_predictions_or_metrics_recomputed':False,
        'external_independent_replication':False,'full_P4_gate_D_accepted':False,
        'reason':'Current numeric component reproduces; independent workbook and full release reports are still pending.'}
    with (evidence/'current_case_reproduction.json').open('x') as file:
        json.dump(receipt,file,indent=2);file.write('\n')
    print(json.dumps(receipt))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('project','source','evidence','temporary-parent'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    reproduce(args.project.resolve(),args.source.resolve(),args.evidence.resolve(),args.temporary_parent.resolve())
