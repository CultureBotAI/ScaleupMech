"""Scale-transfer semantics and safe native authoring; all scientific fixtures are synthetic."""

import subprocess
from argparse import Namespace
from copy import deepcopy
from pathlib import Path

import pytest
from kg_microbe_history.scaffold import build_record

from scaleupmech.cli import new_history
from scaleupmech.validate import (
    load,
    validate_history_links,
    validate_record,
    validate_repository,
)


def evidence():
    return [
        {
            "reference": "https://example.org/source",
            "title": "Synthetic fixture source",
            "claim": "Test fixture only, not scientific evidence.",
            "locator": "fixture section",
        }
    ]


def quantity(value=2.0, unit="g/L"):
    return {
        "reported_value": str(value),
        "qualifier": "REPORTED",
        "value": value,
        "unit": unit,
        "basis": "Synthetic source-reported basis",
        "evidence": evidence(),
    }


@pytest.fixture
def record():
    return {
        "id": "ScaleupMech:fixture",
        "name": "Synthetic fixture",
        "record_kind": "SCALE_CONTEXT",
        "description": "Synthetic test, not a real cultivation.",
        "organism": {
            "reported_name": "Synthetic organism",
            "strain_label": "Fixture strain",
            "evidence": evidence(),
        },
        "process_context": {"summary": "Synthetic product cultivation", "evidence": evidence()},
        "conditions": [
            {
                "condition_id": "small",
                "name": "Synthetic small condition",
                "kind": "OBSERVED_CULTURE",
                "description": "Synthetic test",
                "volumes": [{"kind": "WORKING_VOLUME", "quantity": quantity(1.5, "L")}],
                "medium": {"summary": "Synthetic medium", "evidence": evidence()},
                "evidence": evidence(),
            }
        ],
        "measurements": [
            {
                "measurement_id": "small-titer",
                "condition_id": "small",
                "endpoint": "TITER",
                "name": "Synthetic product titer",
                "quantity": quantity(),
                "evidence_level": "OBSERVED",
                "sampling_context": "Synthetic reported endpoint",
            }
        ],
        "limitations": ["Synthetic fixture is not experimental evidence."],
        "evidence": evidence(),
        "research_gaps": [
            {"scope": scope, "reason": "Synthetic fixture has no external claim"}
            for scope in ("comparability", "pisces")
        ],
        "curation_history": [
            {
                "timestamp": "2026-11-08T12:00:00Z",
                "curator": "fixture",
                "action": "CREATE",
                "summary": "Create synthetic test",
                "history_file": "history/records/fixture/session.yaml",
            }
        ],
    }


def transfer(record):
    record["record_kind"] = "OBSERVED_SCALE_TRANSFER"
    second = deepcopy(record["conditions"][0])
    second.update(condition_id="large", name="Large")
    second["volumes"][0]["quantity"] = quantity(15.0, "L")
    record["conditions"].append(second)
    measurement = deepcopy(record["measurements"][0])
    measurement.update(measurement_id="large-titer", condition_id="large")
    record["measurements"].append(measurement)
    record["comparisons"] = [
        {
            "comparison_id": "transfer",
            "kind": "OBSERVED_TRANSFER",
            "condition_ids": ["small", "large"],
            "measurement_ids": ["small-titer", "large-titer"],
            "endpoint": "TITER",
            "comparability": "SOURCE_REPORTED_COMPARABLE",
            "comparability_basis": "Synthetic source comparison",
            "interpretation": "Synthetic comparison only",
            "evidence": evidence(),
        }
    ]
    return record


def scale_down(record):
    transfer(record)
    record["record_kind"] = "SCALE_DOWN_MODEL"
    condition = record["conditions"][1]
    condition["kind"] = "SCALE_DOWN_EXPERIMENT"
    condition["scale_down_target"] = {
        "summary": "Synthetic modeled large-scale gradient",
        "evidence": evidence(),
    }
    record["measurements"] = [
        {
            "measurement_id": "relative-loss",
            "condition_id": "large",
            "reference_condition_id": "small",
            "endpoint": "OTHER",
            "name": "Synthetic source-reported product loss",
            "quantity": quantity(30.0, "%"),
            "evidence_level": "REPORTED_CALCULATION",
            "sampling_context": "Synthetic endpoint against control",
        }
    ]
    record["comparisons"][0].update(
        kind="SCALE_DOWN_EVALUATION", endpoint="OTHER", measurement_ids=["relative-loss"]
    )
    return record


def test_valid_context_transfer_and_relative_scale_down(record):
    validate_record(record)
    validate_record(transfer(deepcopy(record)))
    model = scale_down(deepcopy(record))
    validate_record(model)
    assert len(model["measurements"]) == 1  # No invented absolute value for the control.


@pytest.mark.parametrize(
    "location",
    [
        "root",
        "organism",
        "condition",
        "volume",
        "quantity",
        "measurement",
        "comparison",
        "evidence",
        "history",
        "pisces",
    ],
)
def test_unknown_fields_are_rejected_recursively(record, location):
    transfer(record)
    link = {
        "resource_identifier": "SFID-999999999",
        "label": "Synthetic PISCES fixture",
        "url": "https://projectpisces.org/flowsheets/999999999",
        "relation": "CONTEXT_ONLY",
        "scope": "Synthetic metadata only; no equivalence assertion",
        "accessed_at": "2026-11-09T00:00:00Z",
        "evidence": evidence(),
    }
    record["pisces_links"] = [link]
    targets = {
        "root": record,
        "organism": record["organism"],
        "condition": record["conditions"][0],
        "volume": record["conditions"][0]["volumes"][0],
        "quantity": record["measurements"][0]["quantity"],
        "measurement": record["measurements"][0],
        "comparison": record["comparisons"][0],
        "evidence": record["evidence"][0],
        "history": record["curation_history"][0],
        "pisces": link,
    }
    targets[location]["unknown_field"] = "must not pass"
    with pytest.raises(Exception, match="Additional properties"):
        validate_record(record)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("location", ["measurement", "volume", "range"])
def test_all_numeric_quantities_are_finite(record, value, location):
    q = (
        record["measurements"][0]["quantity"]
        if location != "volume"
        else record["conditions"][0]["volumes"][0]["quantity"]
    )
    if location == "range":
        q.pop("value")
        q.update(qualifier="RANGE", lower_bound=1.0, upper_bound=value)
    else:
        q["value"] = value
    with pytest.raises(Exception):
        validate_record(record)


@pytest.mark.parametrize(
    "edit",
    [
        "missing-value",
        "missing-unit",
        "missing-basis",
        "extra-bound",
        "backwards-range",
        "one-bound",
    ],
)
def test_quantity_shape_retains_reported_value_unit_and_basis(record, edit):
    q = record["measurements"][0]["quantity"]
    if edit.startswith("missing-"):
        q.pop(edit.removeprefix("missing-"))
    elif edit == "extra-bound":
        q["lower_bound"] = 0.1
    else:
        q.pop("value")
        q.update(qualifier="RANGE", lower_bound=3.0)
        if edit == "backwards-range":
            q["upper_bound"] = 1.0
    with pytest.raises(Exception):
        validate_record(record)


def test_scale_down_compartment_volumes_remain_distinct(record):
    scale_down(record)
    record["conditions"][1]["volumes"] = [
        {"kind": "WORKING_VOLUME", "component": "STR", "quantity": quantity(0.6, "L")},
        {"kind": "WORKING_VOLUME", "component": "PFR", "quantity": quantity(0.3, "L")},
    ]
    validate_record(record)
    record["conditions"][1]["volumes"].append(deepcopy(record["conditions"][1]["volumes"][0]))
    with pytest.raises(ValueError, match="duplicate volume kind/component"):
        validate_record(record)


def test_reported_ranges_and_separate_medium_inoculum_are_retained(record):
    q = record["measurements"][0]["quantity"]
    q.pop("value")
    q.update(qualifier="RANGE", lower_bound=1.0, upper_bound=3.0, reported_value="1 to 3")
    record["conditions"][0]["volumes"] = [
        {"kind": "INITIAL_MEDIUM_VOLUME", "quantity": quantity(2.5, "L")},
        {"kind": "INOCULUM_VOLUME", "quantity": quantity(400.0, "mL")},
    ]
    validate_record(record)
    assert all(v["kind"] != "WORKING_VOLUME" for v in record["conditions"][0]["volumes"])


@pytest.mark.parametrize("value", [0.0, -1.0])
def test_reported_volume_must_be_positive(record, value):
    record["conditions"][0]["volumes"][0]["quantity"]["value"] = value
    with pytest.raises(ValueError, match="volumes must be positive"):
        validate_record(record)


@pytest.mark.parametrize(
    "what", ["strain", "volumes", "media", "measurements", "pisces", "comparability"]
)
def test_missing_scientific_context_requires_explicit_gaps(record, what):
    if what == "strain":
        record["organism"].pop("strain_label")
    elif what == "volumes":
        record["conditions"][0].pop("volumes")
    elif what == "media":
        record["conditions"][0].pop("medium")
    elif what == "measurements":
        record.pop("measurements")
    else:
        record["research_gaps"] = [g for g in record["research_gaps"] if g["scope"] != what]
    with pytest.raises(ValueError):
        validate_record(record)
    gap = {"scope": what, "reason": "Synthetic missing-context fixture"}
    if what in {"volumes", "media", "measurements"}:
        gap["condition_id"] = "small"
    record["research_gaps"].append(gap)
    validate_record(record)


@pytest.mark.parametrize("what", ["condition", "measurement", "comparison"])
def test_duplicate_local_identifiers_are_rejected(record, what):
    transfer(record)
    key = {"condition": "conditions", "measurement": "measurements", "comparison": "comparisons"}[
        what
    ]
    record[key].append(deepcopy(record[key][0]))
    with pytest.raises(ValueError, match="duplicate"):
        validate_record(record)


@pytest.mark.parametrize(
    "edit",
    [
        "unknown-measurement-condition",
        "unknown-comparison-condition",
        "unknown-comparison-measurement",
        "uncovered-condition",
        "endpoint-mismatch",
        "name-mismatch",
        "duplicate-reference",
    ],
)
def test_comparisons_bind_known_conditions_and_shared_reported_endpoints(record, edit):
    transfer(record)
    comparison = record["comparisons"][0]
    if edit == "unknown-measurement-condition":
        record["measurements"][0]["condition_id"] = "missing"
    elif edit == "unknown-comparison-condition":
        comparison["condition_ids"][0] = "missing"
    elif edit == "unknown-comparison-measurement":
        comparison["measurement_ids"][0] = "missing"
    elif edit == "uncovered-condition":
        comparison["measurement_ids"] = ["small-titer"]
    elif edit == "endpoint-mismatch":
        record["measurements"][0]["endpoint"] = "YIELD"
    elif edit == "name-mismatch":
        record["measurements"][0]["name"] = "A different reported product"
    else:
        comparison["condition_ids"] = ["small", "small"]
    with pytest.raises(ValueError):
        validate_record(record)


def test_modeled_result_cannot_be_promoted_to_observed_transfer(record):
    transfer(record)
    record["measurements"][1]["evidence_level"] = "MODEL_PREDICTED"
    with pytest.raises(ValueError, match="modeled outcomes"):
        validate_record(record)


def test_scale_down_experiment_is_not_an_observed_scale_transfer(record):
    transfer(record)
    record["conditions"][1]["kind"] = "SCALE_DOWN_EXPERIMENT"
    record["conditions"][1]["scale_down_target"] = {
        "summary": "Synthetic target",
        "evidence": evidence(),
    }
    with pytest.raises(ValueError, match="actual culture conditions"):
        validate_record(record)


def test_scale_down_simulation_retains_model_status(record):
    scale_down(record)
    record["conditions"][1]["kind"] = "SCALE_DOWN_SIMULATION"
    with pytest.raises(ValueError, match="model predictions"):
        validate_record(record)
    record["measurements"][0]["evidence_level"] = "MODEL_PREDICTED"
    validate_record(record)
    record["conditions"][1]["volumes"][0]["kind"] = "ACTUAL_CULTURE_VOLUME"
    with pytest.raises(ValueError, match="actual or final broth"):
        validate_record(record)


@pytest.mark.parametrize("reference", ["large", "missing"])
def test_relative_measurements_reference_distinct_known_controls(record, reference):
    scale_down(record)
    record["measurements"][0]["reference_condition_id"] = reference
    with pytest.raises(ValueError, match="distinct known reference"):
        validate_record(record)


def test_relative_endpoint_cannot_claim_direct_observation(record):
    scale_down(record)
    record["measurements"][0]["evidence_level"] = "OBSERVED"
    with pytest.raises(ValueError, match="reported-calculation"):
        validate_record(record)


def test_pisces_payload_and_equivalence_are_not_in_the_native_schema(record):
    link = {
        "resource_identifier": "SFID-999999999",
        "label": "Synthetic external link",
        "url": "https://projectpisces.org/flowsheets/999999999",
        "relation": "CONTEXT_ONLY",
        "scope": "Metadata only; no equivalence",
        "accessed_at": "2026-11-09T00:00:00Z",
        "evidence": evidence(),
    }
    record["pisces_links"] = [link]
    validate_record(record)
    link["flowsheet"] = {"unit_operations": []}
    with pytest.raises(Exception, match="Additional properties"):
        validate_record(record)
    link.pop("flowsheet")
    link["relation"] = "EXACT_PROCESS_EQUIVALENT"
    with pytest.raises(Exception):
        validate_record(record)


@pytest.mark.parametrize(
    "timestamp",
    [
        "2206-11-08T12:00:00Z",
        "2026-11-08",
        "2026-11-08T12:00:00",
        "2026-02-30T12:00:00Z",
        "2026-11-08T12:00:00+01:00",
    ],
)
def test_invalid_timestamps(record, timestamp):
    record["curation_history"][0]["timestamp"] = timestamp
    with pytest.raises(Exception):
        validate_record(record)


def test_duplicate_yaml_keys_are_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        load("id: one\nid: two\n")


def test_missing_and_wrong_history_target_fail(tmp_path, record):
    with pytest.raises(FileNotFoundError):
        validate_history_links(tmp_path, record, "data/scale_transfers/fixture.yaml")
    sidecar = build_record(
        kind="record",
        slug="fixture",
        target_path="data/scale_transfers/other.yaml",
        session_id="session",
        timestamp="2026-11-08T12:00:00Z",
        summary="Create synthetic test",
        details="Synthetic fixture only",
        event="CREATE",
        actor_name="fixture",
        actor_type="human",
    )
    with pytest.raises(ValueError, match="target differs"):
        validate_history_links(
            tmp_path,
            record,
            "data/scale_transfers/fixture.yaml",
            {"history/records/fixture/session.yaml": sidecar},
        )


def test_deleted_inventory_directory_is_not_an_empty_corpus(tmp_path):
    with pytest.raises(ValueError, match="required inventory"):
        validate_repository(tmp_path)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    for args in (
        ["init"],
        ["config", "user.name", "Fixture"],
        ["config", "user.email", "fixture@example.invalid"],
        ["remote", "add", "origin", "https://github.com/CultureBotAI/ScaleupMech.git"],
        ["commit", "--allow-empty", "-m", "Fixture"],
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    (root / "data/scale_transfers").mkdir(parents=True)
    (root / "history").mkdir()
    return root


def test_history_writer_dry_run_apply_and_append_only(repo, record):
    import json

    record.pop("curation_history")
    source = repo / "input.yaml"
    source.write_text(json.dumps(record))
    args = Namespace(
        record="data/scale_transfers/fixture.yaml",
        input=str(source),
        actor="fixture",
        actor_type="human",
        summary="Create synthetic test",
        details="Fixture only",
        action="CREATE",
        model=None,
        agent_tool=None,
        apply=False,
    )
    result = new_history(repo, args)
    assert result["applied"] is False
    assert not (repo / args.record).exists()
    assert not list((repo / "history").rglob("*.yaml"))
    args.apply = True
    new_history(repo, args)
    assert validate_repository(repo) == 1
    saved = load((repo / args.record).read_text())
    assert {key: value for key, value in saved.items() if key != "curation_history"} == record
    original_event = deepcopy(saved["curation_history"][0])
    source.write_text(json.dumps(saved))
    args.action = "EDIT"
    new_history(repo, args)
    updated = load((repo / args.record).read_text())
    assert updated["curation_history"][0] == original_event
    assert len(updated["curation_history"]) == 2
    assert validate_repository(repo) == 1
    updated["curation_history"] = []
    source.write_text(json.dumps(updated))
    with pytest.raises(ValueError, match="preserve existing"):
        new_history(repo, args)
    assert len(list((repo / "history").rglob("*.yaml"))) == 2


def test_history_writer_invalid_input_changes_nothing(repo, record):
    import json

    record.pop("curation_history")
    record["evidence"] = []
    source = repo / "input.yaml"
    source.write_text(json.dumps(record))
    args = Namespace(
        record="data/scale_transfers/fixture.yaml",
        input=str(source),
        actor="fixture",
        actor_type="human",
        summary="Create synthetic test",
        details="Fixture only",
        action="CREATE",
        model=None,
        agent_tool=None,
        apply=True,
    )
    with pytest.raises(Exception):
        new_history(repo, args)
    assert not (repo / args.record).exists()
    assert not list((repo / "history").rglob("*.yaml"))


def test_native_ci_runs_required_gate_on_pr_push_and_merge_group():
    root = Path(__file__).resolve().parents[1]
    # BaseLoader retains YAML's literal 'on' key.
    import yaml

    workflow = yaml.load(
        (root / ".github/workflows/validate-strict.yaml").read_text(), Loader=yaml.BaseLoader
    )
    assert set(workflow["on"]) == {"pull_request", "push", "merge_group"}
    assert workflow["on"]["pull_request"] == {}
    assert workflow["on"]["merge_group"]["types"] == ["checks_requested"]
    job = workflow["jobs"]["validate-strict"]
    assert "if" not in job
    commands = [step.get("run") for step in job["steps"]]
    assert "just check" in commands and "just check-vendored" in commands


def test_pin_and_installed_dependency_share_revision():
    import tomllib

    root = Path(__file__).resolve().parents[1]
    config = tomllib.loads((root / "pyproject.toml").read_text())
    assert (
        config["tool"]["uv"]["sources"]["kg-microbe-orchestration"]["rev"]
        == (root / "scripts/.vendored_canon_ref").read_text().strip()
    )


@pytest.mark.parametrize("relative", ["data", "data/scale_transfers", "history"])
@pytest.mark.parametrize("external", [False, True])
def test_symlinked_inventory_and_history_roots_are_rejected(tmp_path, relative, external):
    root = tmp_path / "repo"
    (root / "data/scale_transfers").mkdir(parents=True)
    (root / "history").mkdir()
    source = root / relative
    destination = tmp_path / "outside" if external else root / "alternate"
    source.rename(destination)
    source.symlink_to(destination, target_is_directory=True)
    assert source.is_symlink() and source.is_dir()
    assert source.resolve().is_relative_to(root) is not external
    with pytest.raises(ValueError, match="must not be a symlink or escape"):
        validate_repository(root)


def test_valid_empty_scaffold_directories_pass(tmp_path):
    (tmp_path / "data/scale_transfers").mkdir(parents=True)
    (tmp_path / "history").mkdir()
    assert validate_repository(tmp_path) == 0


@pytest.mark.parametrize(
    "relative",
    ["data", "data/scale_transfers", "history", "history/records", "history/records/fixture"],
)
@pytest.mark.parametrize("external", [False, True])
@pytest.mark.parametrize("apply", [False, True])
def test_history_writer_rejects_all_symlink_directories_before_staging(
    repo, record, relative, external, apply
):
    import json

    source_directory = repo / relative
    source_directory.mkdir(parents=True, exist_ok=True)
    alternate = repo.parent / "external-alternate" if external else repo / "internal-alternate"
    source_directory.rename(alternate)
    source_directory.symlink_to(alternate, target_is_directory=True)
    assert source_directory.is_symlink() and source_directory.is_dir()
    record.pop("curation_history")
    source = repo / "input.yaml"
    source.write_text(json.dumps(record))
    args = Namespace(
        record="data/scale_transfers/fixture.yaml",
        input=str(source),
        actor="fixture",
        actor_type="human",
        summary="Create synthetic test",
        details="Fixture only",
        action="CREATE",
        model=None,
        agent_tool=None,
        apply=apply,
    )
    with pytest.raises(Exception):  # Refusal and unchanged state, not exception wording.
        new_history(repo, args)
    assert not (repo / args.record).exists()
    assert not list(alternate.rglob("*.yaml"))
    assert not list((repo / "history").rglob("*.yaml"))
    assert not (repo / "workspace").exists()


@pytest.mark.parametrize(
    "url,identifier",
    [
        ("https://example.org/flowsheets/999999999", "SFID-999999999"),
        ("https://projectpisces.org/flowsheets/999999999", "SFID-999999998"),
        ("https://projectpisces.org/flowsheets/0", "SFID-0"),
        ("https://projectpisces.org/flowsheets/999999999?copy=true", "SFID-999999999"),
    ],
)
def test_pisces_links_require_supported_host_path_and_matching_resource(record, url, identifier):
    record["pisces_links"] = [
        {
            "resource_identifier": identifier,
            "label": "Synthetic syntax fixture only",
            "url": url,
            "relation": "CONTEXT_ONLY",
            "scope": "No real resource asserted",
            "accessed_at": "2026-11-09T00:00:00Z",
            "evidence": evidence(),
        }
    ]
    with pytest.raises(Exception):
        validate_record(record)
