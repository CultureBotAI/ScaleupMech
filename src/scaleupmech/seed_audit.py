"""Read-only provenance binding for the bounded, independently reviewed initial seed.

The fact projections are curator transcriptions with precise source locators and
raw-source digests. Equality checks prevent unreviewed drift; they do not replace
scientific review, authenticate upstream servers, or infer missing denominators.
No PISCES flowsheet payload is read, downloaded or reconstructed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from .validate import load, validate_path_components, validate_record


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pointer(value, path):
    require(path.startswith('/'), 'binding must use an absolute JSON Pointer')
    for part in path[1:].split('/'):
        require(bool(part) and re.search(r'~(?![01])', part) is None, 'invalid JSON Pointer token')
        key = part.replace('~1', '/').replace('~0', '~')
        if isinstance(value, list):
            require(re.fullmatch(r'0|[1-9][0-9]*', key), 'noncanonical JSON Pointer array index')
            require(int(key) < len(value), 'JSON Pointer array index out of bounds')
            value = value[int(key)]
        else:
            require(isinstance(value, dict) and key in value, 'JSON Pointer field is absent')
            value = value[key]
    return value


def strip_evidence(value):
    if isinstance(value, dict):
        return {k: strip_evidence(v) for k, v in value.items() if k not in {'evidence', 'curation_history'}}
    if isinstance(value, list):
        return [strip_evidence(v) for v in value]
    return value


def evidence_entries(value):
    if isinstance(value, dict):
        if {'reference', 'title', 'claim', 'locator'} <= value.keys():
            yield value
        else:
            for child in value.values():
                yield from evidence_entries(child)
    elif isinstance(value, list):
        for child in value:
            yield from evidence_entries(child)


def binding_paths(record):
    paths = {'/name', '/record_kind', '/description', '/organism', '/process_context'}
    for i, condition in enumerate(record['conditions']):
        base = f'/conditions/{i}'
        paths.add(base)
        paths.update(f'{base}/volumes/{j}' for j in range(len(condition.get('volumes', []))))
        paths.update(f'{base}/{key}' for key in ('medium', 'scale_down_target') if key in condition)
    for field in ('measurements', 'comparisons'):
        paths.update(f'/{field}/{i}' for i in range(len(record.get(field, []))))
    return paths


def expected_evidence_pointer(path):
    if path in {'/name', '/record_kind', '/description'}:
        return '/evidence'
    if re.fullmatch(r'/measurements/[0-9]+', path) or re.fullmatch(r'/conditions/[0-9]+/volumes/[0-9]+', path):
        return path + '/quantity/evidence'
    return path + '/evidence'


def audit(records, catalogue, projections, bindings, navigation):
    require(catalogue.get('format_version') == 1 and bindings.get('format_version') == 1,
            'unsupported seed provenance format')
    sources = {}
    source_ids = set()
    for source in catalogue['sources']:
        require(source['reference'] not in sources and source['source_id'] not in source_ids,
                'duplicate source reference or identifier')
        require(re.fullmatch(r'[0-9a-f]{64}', source['original_sha256'])
                and source['original_bytes'] > 0, 'invalid raw source receipt')
        require(source['source_license'] == 'CC-BY-4.0', 'unexpected primary source rights')
        projection = projections[source['projection']]
        require(projection['source_id'] == source['source_id'] and projection['reference'] == source['reference'],
                'projection identity differs')
        for loc, entry in projection['locators'].items():
            require(loc == entry['source_locator'] and loc.startswith(('html:#', 'docx:')),
                    'unsupported or inconsistent retained source locator')
            if loc.startswith('html:#'):
                require(re.fullmatch(r'[0-9a-f]{64}', entry['selected_text_sha256']),
                        'retained HTML selector lacks source-text digest')
        source_ids.add(source['source_id'])
        sources[source['reference']] = projection
    by_id = {}
    for record in records:
        validate_record(record)
        rid = record['id']
        require(rid not in by_id, 'duplicate seed record')
        by_id[rid] = record
        for entry in evidence_entries(record):
            require(entry['reference'] in sources, 'evidence source not retained')
            require(entry['source_license'] == 'CC-BY-4.0', 'evidence source rights differ')
            require(entry['locator'] in sources[entry['reference']]['locators'], 'evidence locator not retained')
        require(not record.get('pisces_links'), 'initial seed has no verified scientific PISCES matches')
    require(set(by_id) == set(bindings['record_ids']) == set(bindings['record_scope']),
            'initial seed identity coverage differs')
    actual = {rid: set() for rid in by_id}
    for bound in bindings['bindings']:
        rid, path = bound['record_id'], bound['record_pointer']
        require(rid in by_id and path not in actual[rid], 'duplicate or unknown record binding')
        require(path in binding_paths(by_id[rid]), 'binding path outside reviewed scientific fields')
        require(bound['evidence_pointer'] == expected_evidence_pointer(path),
                'binding evidence pointer does not identify its own field')
        actual[rid].add(path)
        require(bound['source_reference'] in sources, 'binding source not retained')
        locators = sources[bound['source_reference']]['locators']
        require(bound['source_locator'] in locators, 'binding locator not retained')
        facts = locators[bound['source_locator']]['facts']
        require(bound['fact_key'] in facts, 'source fact not retained')
        value = strip_evidence(pointer(by_id[rid], path))
        if re.fullmatch(r'/conditions/[0-9]+', path):
            value = {k: v for k, v in value.items() if k not in {'volumes', 'medium', 'scale_down_target'}}
        require(value == facts[bound['fact_key']], 'scientific field differs from its retained source fact')
        entries = pointer(by_id[rid], bound['evidence_pointer'])
        actual_evidence = [(e['reference'], e['locator']) for e in entries]
        required_evidence = [(e['reference'], e['locator']) for e in bound['required_evidence']]
        require(len(actual_evidence) == len(set(actual_evidence))
                and set(actual_evidence) == set(required_evidence),
                'field evidence coverage differs from reviewed source bindings')
        require(any(e['reference'] == bound['source_reference'] and e['locator'] == bound['source_locator']
                    for e in entries), 'field evidence does not select its own source fact')
    for rid, record in by_id.items():
        require(actual[rid] == binding_paths(record), 'scientific field binding coverage differs')
        scope = bindings['record_scope'][rid]
        for group, key in [('conditions', 'condition_id'), ('measurements', 'measurement_id'), ('comparisons', 'comparison_id')]:
            require([item[key] for item in record.get(group, [])] == scope[key + 's'],
                    'condition, measurement or comparison scope differs')
    require(set(navigation) == {'format_version', 'resource_identifier', 'label', 'url', 'accessed_at', 'verification', 'scope'},
            'PISCES navigation must retain metadata only')
    require(navigation['format_version'] == 1 and navigation['resource_identifier'] == 'SFID-413'
            and navigation['url'] == 'https://projectpisces.org/flowsheets/413'
            and navigation['label'] == 'Corn Stover → Ethanol', 'unreviewed PISCES navigation metadata')
    return {'records': len(records), 'conditions': sum(len(r['conditions']) for r in records),
            'measurements': sum(len(r['measurements']) for r in records),
            'comparisons': sum(len(r['comparisons']) for r in records), 'sources': len(sources),
            'locators': sum(len(p['locators']) for p in sources.values()),
            'source_bindings': len(bindings['bindings']), 'scientific_pisces_links': 0}


def load_inputs(root):
    def read(relative):
        validate_path_components(root, relative)
        return load((root / relative).read_text())
    catalogue = read('curation/source-catalogue.json')
    projections = {}
    for source in catalogue['sources']:
        relative = source['projection']
        validate_path_components(root, relative)
        payload = (root / relative).read_bytes()
        require(hashlib.sha256(payload).hexdigest() == source['projection_sha256'], 'source projection checksum differs')
        projections[relative] = load(payload.decode())
    paths = sorted((root / 'data/scale_transfers').glob('*.yaml'))
    records = [read(str(path.relative_to(root))) for path in paths]
    return records, catalogue, projections, read('curation/seed-bindings.json'), read('curation/pisces-navigation.json')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        print(json.dumps(audit(*load_inputs(args.root.resolve())), sort_keys=True))
    except (OSError, KeyError, IndexError, TypeError, ValueError) as exc:
        print(f'seed audit failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
