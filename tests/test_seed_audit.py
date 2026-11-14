"""Source-binding tests use real alternative locators and distinct numeric inputs."""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from scaleupmech.seed_audit import audit, load_inputs, pointer
from scaleupmech.validate import validate_record

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def inputs():
    return copy.deepcopy(load_inputs(ROOT))


def record(inputs, suffix):
    return next(r for r in inputs[0] if r['id'].endswith(suffix))


def test_retained_initial_seed_passes(inputs):
    result = audit(*inputs)
    assert result == dict(records=3, conditions=8, measurements=17, comparisons=6,
                          sources=4, locators=27, source_bindings=71, scientific_pisces_links=0)


@pytest.mark.parametrize('which', ['medium_inoculum', 'bench_duration'])
def test_required_method_locator_cannot_be_removed_with_valid_numeric_source_remaining(inputs, which):
    r = record(inputs, 'zx01-gp1-kla-scale-transfer')
    if which == 'medium_inoculum':
        entries = r['conditions'][3]['medium']['evidence']
        locator = 'html:#sec4dot2-molecules-23-00125/p[1]'
    else:
        entries = r['measurements'][0]['quantity']['evidence']
        locator = 'html:#sec4dot7-molecules-23-00125'
    assert any(e['locator'] == locator for e in entries)
    entries[:] = [e for e in entries if e['locator'] != locator]
    assert entries  # The remaining locators genuinely exist in the same primary source.
    with pytest.raises(ValueError, match='field evidence coverage'):
        audit(*inputs)


@pytest.mark.parametrize('path,value', [
    ('/measurements/0/quantity/value', 4.03),  # Real value from the15L condition, not the5L one.
    ('/measurements/0/quantity/unit', 'g/L'),
    ('/measurements/0/condition_id', 'vessel-15l'),
    ('/measurements/6/quantity/reported_value', '4.2'),
    ('/conditions/0/volumes/1/kind', 'FINAL_BROTH_VOLUME'),
])
def test_real_value_scope_volume_kind_and_literal_precision_cannot_drift(inputs, path, value):
    r = record(inputs, 'zx01-gp1-kla-scale-transfer')
    parent, key = path.rsplit('/', 1)
    pointer(r, parent)[key] = value
    with pytest.raises(ValueError):
        audit(*inputs)


def test_yield_denominator_cannot_be_invented(inputs):
    r = record(inputs, 'cgl-ile8-isoleucine-scale-transfer')
    r['measurements'][1]['quantity']['basis'] = 'grams L-isoleucine per gram glucose consumed'
    with pytest.raises(ValueError, match='source fact'):
        audit(*inputs)


def test_other_valid_source_locator_does_not_support_this_measurement(inputs):
    r = record(inputs, 'zx01-gp1-kla-scale-transfer')
    r['measurements'][0]['quantity']['evidence'][0]['locator'] = 'html:#molecules-23-00125-t004'
    with pytest.raises(ValueError, match='field evidence coverage'):
        audit(*inputs)


def test_shifted_numeric_fact_evidence_pointer_is_refused(inputs):
    binding = next(b for b in inputs[3]['bindings'] if b['record_pointer'] == '/measurements/0')
    binding['evidence_pointer'] = '/measurements/1/quantity/evidence'
    with pytest.raises(ValueError, match='own field'):
        audit(*inputs)


def test_missing_binding_cannot_silently_reduce_scientific_coverage(inputs):
    inputs[3]['bindings'].pop()
    with pytest.raises(ValueError, match='binding coverage'):
        audit(*inputs)


def test_model_prediction_cannot_replace_observation(inputs):
    r = record(inputs, 'dm1945x3-cadaverine-physical-scale-down')
    r['measurements'][0]['evidence_level'] = 'MODEL_PREDICTED'
    with pytest.raises(ValueError, match='source fact'):
        audit(*inputs)


def test_pisces_navigation_rejects_payload_field(inputs):
    inputs[4]['flowsheet'] = {'units': []}
    with pytest.raises(ValueError, match='metadata only'):
        audit(*inputs)


@pytest.mark.parametrize('token', ['-1', '01', '+1', '-', '2'])
def test_source_pointer_has_canonical_bounded_array_indices(token):
    with pytest.raises(ValueError):
        pointer({'values': ['a', 'b']}, '/values/' + token)


SEED_SUFFIXES = [
    'zx01-gp1-kla-scale-transfer',
    'dm1945x3-cadaverine-physical-scale-down',
    'cgl-ile8-isoleucine-scale-transfer',
]


@pytest.mark.parametrize('suffix', SEED_SUFFIXES)
@pytest.mark.parametrize('change', ['remove', 'contradict'])
def test_reviewed_limitations_cannot_drift(inputs, suffix, change):
    r = record(inputs, suffix)
    if change == 'remove':
        r['limitations'].pop()
    else:
        r['limitations'][0] = (
            'All conditions are proven manufacturing-scale cultivation with fully resolved '
            'yield denominators.'
        )
    validate_record(r)  # Both alternatives remain valid under the general native schema.
    with pytest.raises(ValueError, match='reviewed seed limitations or research gaps'):
        audit(*inputs)


@pytest.mark.parametrize('suffix', SEED_SUFFIXES)
@pytest.mark.parametrize('change', ['remove', 'contradict'])
def test_reviewed_research_gaps_cannot_drift(inputs, suffix, change):
    r = record(inputs, suffix)
    if change == 'remove':
        # Keep schema-required media/PISCES gaps; the original audit accepted this deletion.
        gap = next(g for g in r['research_gaps'] if g['scope'] == 'measurements')
        r['research_gaps'].remove(gap)
    else:
        r['research_gaps'][0]['reason'] = (
            'All strain, volume and denominator questions have been resolved by complete '
            'primary evidence.'
        )
    validate_record(r)
    with pytest.raises(ValueError, match='reviewed seed limitations or research gaps'):
        audit(*inputs)


@pytest.mark.parametrize('suffix', SEED_SUFFIXES)
@pytest.mark.parametrize('field', ['limitations', 'research_gaps'])
def test_reviewed_limit_contract_cannot_omit_field(inputs, suffix, field):
    r = record(inputs, suffix)
    del inputs[3]['record_scope'][r['id']][field]
    with pytest.raises(ValueError, match='reviewed seed limitations or research gaps'):
        audit(*inputs)


@pytest.mark.parametrize('field,value', [
    ('scope', 'Verified scientific matches for all three studies and strain/scale equivalence.'),
    ('verification', 'Full SFF, unit-operation, stream and TEA payload imported and verified.'),
    ('accessed_at', 'not-a-timestamp'),
    ('accessed_at', '2026-11-10T03:25:33Z'),  # Valid syntax is not the reviewed access event.
])
def test_reviewed_navigation_context_and_provenance_cannot_drift(inputs, field, value):
    inputs[4][field] = value
    with pytest.raises(ValueError, match='navigation context or provenance'):
        audit(*inputs)


@pytest.mark.parametrize('field', [None, 'scope', 'verification', 'accessed_at'])
def test_reviewed_navigation_contract_cannot_be_omitted(inputs, field):
    if field is None:
        del inputs[3]['navigation']
    else:
        del inputs[3]['navigation'][field]
    with pytest.raises(ValueError, match='navigation context or provenance'):
        audit(*inputs)
