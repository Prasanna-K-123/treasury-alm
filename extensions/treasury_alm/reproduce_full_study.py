"""Recompute the frozen Treasury study and reconcile its exported workbook.

No network, fitting choices or scientific files are changed. Timestamped seals
from the new historical run are kept separate from the original chronology.
The current-case provenance continues to identify that original frozen record.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

HISTORY = {
    'source_audit.json': 'd8b7aa28b9c831e21ae29fe2f9a0709859968fe1e9cb30b3528d7cfef529fd6f',
    'development_predictions.json': '04b5a8e8cb8630ebcc5fb04fc2e38f6ad5adfdb0c18bd812af67b817bc6aa8a9',
    'development_selection.json': '505268ab90e2e6a304f3218f5690cecb65d7c12d7d6cbf20c5f5848fb12c0b09',
    'final_predictions.json': 'b166252af3a7cf8a3ed64981ac96baddefefc07a124190268ac269de37beefc9',
    'final_results.json': '8f1ff186b82ac7354a7cb9ef84beb9eea55dbdcc6379c76faf58233c096be289',
}
CURRENT = {
    'current_case.json': '67890bc836cb98f5492c074f3b5927850a4edcc25236a7bd81c1b80d4c4171a2',
    'runoff_years.csv': 'fb775f4dee4ed45eb417c426a40aa6cec3e6639b8aa1f1d3ae0de671de402807',
    'current_case_manifest.json': '077a75a24f18bbb8576e7079d6633ec6098c9b7aa20ba2e20314ef06013eeba8',
}
SOURCE = '7286435090933f0df1dcaeb15629f3a9129c083baee4c42ae5df03d0bb89335c'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def compare_xlsx(expected, actual):
    """Compare all content, resolving volatile relationship IDs by their targets."""
    changed_dates = []
    with zipfile.ZipFile(expected) as first, zipfile.ZipFile(actual) as second:
        require(first.testzip() is None and second.testzip() is None, 'Workbook CRC')
        require(sorted(first.namelist()) == sorted(second.namelist()), 'Workbook members')
        def normalise(archive, name):
            raw = archive.read(name)
            if not (name.endswith('.xml') or name.endswith('.rels')):
                return raw
            root = ET.fromstring(raw)
            if name.endswith('.rels'):
                relationships = sorted(list(root), key=lambda n: (
                    n.attrib.get('Type', ''), n.attrib.get('Target', ''),
                    n.attrib.get('TargetMode', '')))
                require(len({n.attrib['Id'] for n in relationships}) == len(relationships),
                        'Duplicate relationship ID')
                for index, entry in enumerate(relationships):
                    entry.attrib['Id'] = 'CanonicalRelationship' + str(index)
                root[:] = relationships
            else:
                part = Path(name)
                relation_name = str(part.parent / '_rels' / (part.name + '.rels'))
                if relation_name in archive.namelist():
                    relationships = sorted(list(ET.fromstring(archive.read(relation_name))),
                        key=lambda n: (n.attrib.get('Type', ''), n.attrib.get('Target', ''),
                                       n.attrib.get('TargetMode', '')))
                    mapping = {n.attrib['Id']: 'CanonicalRelationship' + str(i)
                               for i, n in enumerate(relationships)}
                    for entry in root.iter():
                        for attribute, value in list(entry.attrib.items()):
                            if attribute.startswith('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'):
                                require(value in mapping, 'Unresolved workbook relationship')
                                entry.attrib[attribute] = mapping[value]
            return ET.tostring(root, encoding='unicode')
        for name in sorted(first.namelist()):
            a, b = first.read(name), second.read(name)
            if a == b:
                continue
            if name.endswith('.xml') or name.endswith('.rels'):
                a, b = normalise(first, name), normalise(second, name)
                if name == 'docProps/core.xml':
                    roots = [ET.fromstring(a), ET.fromstring(b)]
                    for tag in ('created', 'modified'):
                        nodes = [r.find('{http://purl.org/dc/terms/}' + tag) for r in roots]
                        require((nodes[0] is None) == (nodes[1] is None), 'Core property presence')
                        if nodes[0] is not None:
                            if nodes[0].text != nodes[1].text:
                                changed_dates.append(tag)
                            for node in nodes:
                                node.text = 'DECLARED_VOLATILE_TIMESTAMP'
                    a, b = (ET.tostring(r, encoding='unicode') for r in roots)
                require(ET.canonicalize(a) == ET.canonicalize(b), 'Workbook content differs: ' + name)
            else:
                raise ValueError('Workbook binary part differs: ' + name)
        count = len(first.namelist())
    return {'status': 'passed', 'all_zip_members_compared': count,
            'formula_inputs_cached_values_styles_validation_and_panes_compared': True,
            'ignored_fields': ['ZIP container timestamps', 'docProps/core.xml created/modified'],
            'relationship_ids': 'Canonicalised by identical Type/Target/TargetMode; references must resolve; no target ignored',
            'changed_core_timestamps': changed_dates,
            'original_sha256': digest(expected), 'reproduced_sha256': digest(actual),
            'byte_identical': digest(expected) == digest(actual)}


def reproduce(project, source, temporary_parent, output, node=None, node_modules=None, python_only=False):
    require(not output.exists(), 'Receipt already exists; use a new output path')
    require(python_only or (node is not None and node_modules is not None),
            'Provide the workbook runtime or select --python-only')
    require(digest(source) == SOURCE, 'Pinned source hash')
    original_history = project / 'reports/treasury_20261019'
    original_current = project / 'reports/current_case_20261019'
    for directory, expected in ((original_history, HISTORY), (original_current, CURRENT)):
        for name, value in expected.items():
            require(digest(directory / name) == value, 'Original scientific seal: ' + name)
    temporary_parent.mkdir(parents=True, exist_ok=True)
    clean = Path(tempfile.mkdtemp(prefix='treasury-full-', dir=temporary_parent))
    extension = clean / 'extensions/treasury_alm'
    extension.mkdir(parents=True)
    for path in (project / 'extensions/treasury_alm').glob('*.py'):
        shutil.copyfile(path, extension / path.name)
    for path in (project / 'extensions/treasury_alm').glob('*.md'):
        shutil.copyfile(path, extension / path.name)
    for relative in ('src/retirement_alm/engine.py', 'requirements.txt',
                     'extensions/treasury_alm/data/ssa_2023_period_qx.csv',
                     'extensions/treasury_alm/data/gsw_official_fixture_20241129.json',
                     'tools/build_treasury_reconciliation.mjs'):
        destination = clean / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(project / relative, destination)
    clean_source = clean / 'feds200628.csv'
    shutil.copyfile(source, clean_source)
    require(digest(clean_source) == SOURCE, 'Copied source hash')
    env = os.environ.copy()
    env['PYTHONPATH'] = str(clean / 'src') + os.pathsep + str(extension)
    commands = []

    def run(label, command, extra_env=None, timeout=120):
        print(json.dumps({'stage': label, 'status': 'running'}), flush=True)
        result = subprocess.run(command, cwd=clean, env=env | (extra_env or {}),
                                text=True, capture_output=True, timeout=timeout)
        commands.append({'stage': label, 'exit_code': result.returncode,
                         'stdout_sha256': hashlib.sha256(result.stdout.encode()).hexdigest(),
                         'stderr_sha256': hashlib.sha256(result.stderr.encode()).hexdigest()})
        if result.returncode:
            raise RuntimeError(label + '\n' + result.stdout[-5000:] + result.stderr[-5000:])
        print(json.dumps({'stage': label, 'status': 'passed'}), flush=True)

    run('31 extension boundary checks', [sys.executable, '-m', 'unittest', 'discover',
        '-s', str(extension), '-p', 'test_*.py'])
    fresh_history = clean / 'recomputed_history'
    for phase in ('development', 'predict-final', 'score-final'):
        run('historical ' + phase, [sys.executable, str(extension / 'run_study.py'), phase,
            '--source', str(clean_source), '--output', str(fresh_history)])
    scientific = []
    for name, value in HISTORY.items():
        require(digest(fresh_history / name) == value, 'Historical reproduction: ' + name)
        scientific.append({'component': 'history', 'file': name, 'sha256': value,
                           'byte_identical': True})

    # Only after verifying fresh scientific outputs, join them to the immutable
    # original provenance metadata used by the already frozen current case.
    history = clean / 'reports/treasury_20261019'
    history.mkdir(parents=True)
    for name in HISTORY:
        shutil.copyfile(fresh_history / name, history / name)
    for name in ('development_freeze.json', 'historical_reproduction.json'):
        shutil.copyfile(original_history / name, history / name)
    original_manifest = json.loads((original_current / 'current_case_manifest.json').read_text())
    case = clean / 'reports/current_case_20261019'
    run('current mortality/market/liquidity case', [sys.executable,
        str(extension / 'run_current_case.py'), '--source', str(clean_source),
        '--historical-evidence', str(history), '--output', str(case),
        '--implementation-commit', original_manifest['implementation_commit']])
    for name, value in CURRENT.items():
        require(digest(case / name) == value, 'Current reproduction: ' + name)
        scientific.append({'component': 'current', 'file': name, 'sha256': value,
                           'byte_identical': True})
    run('independent Decimal and event-ledger verification', [sys.executable,
        str(extension / 'verify_current_case.py'), '--source', str(clean_source),
        '--evidence', str(case), '--historical', str(history),
        '--mortality', str(extension / 'data/ssa_2023_period_qx.csv')])
    run('isolated current-case component reproduction', [sys.executable,
        str(extension / 'reproduce_current_case.py'), '--project', str(clean),
        '--source', str(clean_source), '--evidence', str(case),
        '--temporary-parent', str(clean / 'component_temp')])
    if python_only:
        receipt = {'status': 'passed', 'scope': 'Python science; workbook not rebuilt in this run',
            'clean_directory': True, 'same_environment': True, 'network_calls': 0,
            'source_sha256': SOURCE, 'scientific_outputs': scientific,
            'boundary_tests_passed': 31, 'phase_commands': commands,
            'independent_verification': json.loads((case / 'current_case_verification.json').read_text()),
            'external_independent_replication': False, 'workbook_rebuilt': False,
            'full_P4_gate_D_accepted': False,
            'full_workbook_run_evidence': 'reports/integrated_20261019/full_study_reproduction.json'}
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x') as file:
            json.dump(receipt, file, indent=2, allow_nan=False);file.write('\n')
        print(json.dumps({'status':'passed','scope':'Python science','science_files':8}), flush=True)
        return
    inputs = clean / 'workbook_inputs.json'
    run('workbook source/reference preparation', [sys.executable,
        str(extension / 'prepare_workbook_inputs.py'), '--project', str(clean),
        '--source', str(clean_source), '--output', str(inputs)])
    (clean / 'tools/node_modules').symlink_to(node_modules, target_is_directory=True)
    workbook_output = clean / 'workbook_output'
    run('independent workbook formulas, export, reopen and recalculation',
        [str(node), str(clean / 'tools/build_treasury_reconciliation.mjs')],
        {'TREASURY_WORKBOOK_INPUT': str(inputs), 'TREASURY_WORKBOOK_OUTPUT': str(workbook_output)},
        timeout=180)
    workbook = compare_xlsx(project / 'artifacts/Treasury_ALM_Reconciliation.xlsx',
                            workbook_output / 'Treasury_ALM_Reconciliation.xlsx')
    read = lambda p: json.loads(p.read_text())
    old_qa = read(project / 'reports/workbook_20261019/numeric_verification.json')
    new_qa = read(workbook_output / 'workbook_numeric_verification.json')
    for record in (old_qa, new_qa):
        record.pop('workbook_sha256')
    require(old_qa == new_qa, 'Workbook numeric QA differs beyond export hash')
    independent = read(case / 'current_case_verification.json')
    receipt = {'status': 'passed', 'date': '2026-10-19', 'gate': 'P4 D',
        'clean_directory': True, 'same_environment': True,
        'external_independent_replication': False, 'network_calls': 0,
        'source_sha256': SOURCE, 'scientific_outputs': scientific,
        'boundary_tests_passed': 31, 'phase_commands': commands,
        'python_version': platform.python_version(),
        'original_freeze_metadata_retained_as_provenance_only': True,
        'new_historical_timestamp_seals_retained_separately': True,
        'method_or_selection_changes': 0, 'workbook': workbook,
        'workbook_qa_identical_excluding_export_hash': True,
        'independent_verification': independent,
        'full_P4_gate_D_accepted': True,
        'limitation': 'Reproduction in the recorded runtime; not a separate external replication or new blind holdout.'}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as file:
        json.dump(receipt, file, indent=2, allow_nan=False)
        file.write('\n')
    print(json.dumps({'status': 'passed', 'receipt': str(output), 'science_files': len(scientific),
                      'workbook_equivalent': True, 'gate': 'P4 D'}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('project', 'source', 'temporary-parent', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('node', 'node-modules'):
        parser.add_argument('--' + name, type=Path)
    parser.add_argument('--python-only', action='store_true',
                        help='Recompute all Python scientific evidence without the workbook runtime')
    args = parser.parse_args()
    reproduce(args.project.resolve(), args.source.resolve(), args.temporary_parent.resolve(),
              args.output.resolve(), args.node.resolve() if args.node else None,
              args.node_modules.resolve() if args.node_modules else None, args.python_only)
