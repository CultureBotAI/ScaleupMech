"""Closed LinkML validation plus offline provenance and history invariants."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timedelta
from functools import lru_cache
from importlib.resources import files
from pathlib import Path, PurePosixPath

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from linkml.generators.jsonschemagen import JsonSchemaGenerator


class StrictLoader(yaml.SafeLoader):
    """Reject duplicate keys and retain timestamp strings for schema validation."""


StrictLoader.yaml_implicit_resolvers = {
    key: [(tag, pattern) for tag, pattern in values if tag != "tag:yaml.org,2002:timestamp"]
    for key, values in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str) or key in result:
            raise ValueError(f"duplicate or non-string YAML key: {key!r}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load(text: str) -> dict:
    value = yaml.load(text, Loader=StrictLoader)
    if not isinstance(value, dict):
        raise ValueError("document must be an object")
    return value


@lru_cache(maxsize=2)
def validator(kind: str = "ScaleTransferRecord") -> Draft202012Validator:
    schema = files("scaleupmech").joinpath("schema/scaleupmech.yaml")
    generated = json.loads(
        JsonSchemaGenerator(
            str(schema), top_class=kind, not_closed=False, include_null=False
        ).serialize()
    )
    Draft202012Validator.check_schema(generated)
    return Draft202012Validator(generated, format_checker=FormatChecker())


def relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        not value
        or not path.parts
        or path.is_absolute()
        or ".." in path.parts
        or str(path) != value
        or any(c in value for c in "\\\n\r?#")
    ):
        raise ValueError(f"unsafe repository-relative path: {value!r}")
    return path


def utc_timestamp(value: str) -> None:
    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)", value):
        raise ValueError(f"timestamp must be a full UTC timestamp in 2000..2099: {value}")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() != timedelta(0):
        raise ValueError("timestamp must use UTC")


def _nonempty(value) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("numeric values must be finite")
    if isinstance(value, str) and not value.strip():
        raise ValueError("strings must not be empty or whitespace")
    if isinstance(value, dict):
        for item in value.values():
            _nonempty(item)
    elif isinstance(value, list):
        for item in value:
            _nonempty(item)


def validate_history(record: dict) -> None:
    validator("HistoryRecord").validate(record)
    _nonempty(record)
    if record["history_version"] != 1:
        raise ValueError("history_version must be 1")
    utc_timestamp(record["session"]["timestamp"])
    relative_path(record["target"]["path"])


def validate_quantity(quantity: dict, *, positive=False) -> None:
    fields = {key for key in ("value", "lower_bound", "upper_bound") if key in quantity}
    expected = {"lower_bound", "upper_bound"} if quantity["qualifier"] == "RANGE" else {"value"}
    if fields != expected:
        raise ValueError("quantity numeric fields must match its reported qualifier")
    if (
        fields == {"lower_bound", "upper_bound"}
        and quantity["lower_bound"] > quantity["upper_bound"]
    ):
        raise ValueError("reported quantity range must be ordered")
    if positive and any(quantity[key] <= 0 for key in fields):
        raise ValueError("reported volumes must be positive")


def validate_record(record: dict) -> None:
    validator().validate(record)
    _nonempty(record)
    conditions = {item["condition_id"]: item for item in record["conditions"]}
    if len(conditions) != len(record["conditions"]):
        raise ValueError("duplicate condition identifier")
    gaps = record.get("research_gaps", [])
    for gap in gaps:
        if gap.get("condition_id") and gap["condition_id"] not in conditions:
            raise ValueError("research gap references an unknown condition")

    def missing(scope, condition=None):
        return not any(g["scope"] == scope and g.get("condition_id") == condition for g in gaps)

    if not record["organism"].get("strain_label") and missing("strain"):
        raise ValueError("missing strain label requires an explicit research gap")
    if record["organism"].get("strain_identifier") and not record["organism"].get("strain_label"):
        raise ValueError("strain identifier requires its reported strain label")
    for cid, condition in conditions.items():
        volumes = condition.get("volumes", [])
        if not volumes and missing("volumes", cid):
            raise ValueError("missing condition volumes require an explicit condition gap")
        if not condition.get("medium") and missing("media", cid):
            raise ValueError("missing condition media require an explicit condition gap")
        kinds = [(v["kind"], v.get("component")) for v in volumes]
        if len(kinds) != len(set(kinds)):
            raise ValueError("duplicate volume kind/component within a condition")
        for volume in volumes:
            validate_quantity(volume["quantity"], positive=True)
            if condition["kind"] in {"MODELED_REFERENCE", "SCALE_DOWN_SIMULATION"} and volume[
                "kind"
            ] in {"ACTUAL_CULTURE_VOLUME", "FINAL_BROTH_VOLUME"}:
                raise ValueError("modeled reference cannot claim actual or final broth volume")
        if condition["kind"] in {
            "SCALE_DOWN_EXPERIMENT",
            "SCALE_DOWN_SIMULATION",
        } and not condition.get("scale_down_target"):
            raise ValueError("scale-down experiment requires a sourced target description")
    measurements = record.get("measurements", [])
    by_id = {item["measurement_id"]: item for item in measurements}
    if len(by_id) != len(measurements):
        raise ValueError("duplicate measurement identifier")
    for measurement in measurements:
        cid = measurement["condition_id"]
        if cid not in conditions:
            raise ValueError("measurement references an unknown condition")
        reference = measurement.get("reference_condition_id")
        if reference is not None:
            if reference not in conditions or reference == cid:
                raise ValueError(
                    "relative measurement requires a distinct known reference condition"
                )
            if measurement["evidence_level"] == "OBSERVED":
                raise ValueError(
                    "relative measurement must retain reported-calculation or modeled status"
                )
        validate_quantity(measurement["quantity"])
        if (
            conditions[cid]["kind"] in {"MODELED_REFERENCE", "SCALE_DOWN_SIMULATION"}
            and measurement["evidence_level"] != "MODEL_PREDICTED"
        ):
            raise ValueError("modeled reference measurements must remain model predictions")
    for cid in conditions:
        if not any(
            cid in (m["condition_id"], m.get("reference_condition_id")) for m in measurements
        ) and missing("measurements", cid):
            raise ValueError("missing condition measurements require an explicit condition gap")
    comparisons = record.get("comparisons", [])
    seen = set()
    for comparison in comparisons:
        if comparison["comparison_id"] in seen:
            raise ValueError("duplicate comparison identifier")
        seen.add(comparison["comparison_id"])
        cids, mids = comparison["condition_ids"], comparison["measurement_ids"]
        if len(cids) != len(set(cids)) or len(mids) != len(set(mids)):
            raise ValueError("comparison references must be distinct")
        if not set(cids) <= conditions.keys() or not set(mids) <= by_id.keys():
            raise ValueError("comparison references unknown conditions or measurements")
        selected = [by_id[mid] for mid in mids]
        covered = {m["condition_id"] for m in selected}
        covered.update(
            m["reference_condition_id"] for m in selected if "reference_condition_id" in m
        )
        if covered != set(cids):
            raise ValueError("comparison measurements must cover exactly its conditions")
        if len({m["name"] for m in selected}) != 1:
            raise ValueError("comparison measurements must share their reported endpoint name")
        if any(m["endpoint"] != comparison["endpoint"] for m in selected):
            raise ValueError("comparison measurements must share the declared endpoint")
        if comparison["kind"] == "OBSERVED_TRANSFER":
            if any(conditions[cid]["kind"] != "OBSERVED_CULTURE" for cid in cids):
                raise ValueError("observed transfer requires actual culture conditions")
            if any(m["evidence_level"] == "MODEL_PREDICTED" for m in selected):
                raise ValueError("observed transfer cannot use modeled outcomes")
        elif comparison["kind"] == "SCALE_DOWN_EVALUATION":
            if not any(
                conditions[cid]["kind"] in {"SCALE_DOWN_EXPERIMENT", "SCALE_DOWN_SIMULATION"}
                for cid in cids
            ):
                raise ValueError("scale-down evaluation requires a scale-down condition")
    if record["record_kind"] == "OBSERVED_SCALE_TRANSFER":
        if not any(c["kind"] == "OBSERVED_TRANSFER" for c in comparisons):
            raise ValueError("observed scale transfer requires an explicit observed comparison")
    elif any(c["kind"] == "OBSERVED_TRANSFER" for c in comparisons):
        raise ValueError("observed transfer comparisons require observed-transfer record kind")
    if record["record_kind"] == "SCALE_DOWN_MODEL":
        if not any(
            c["kind"] in {"SCALE_DOWN_EXPERIMENT", "SCALE_DOWN_SIMULATION"}
            for c in conditions.values()
        ):
            raise ValueError("scale-down record requires a sourced scale-down condition")
    elif any(
        c["kind"] in {"SCALE_DOWN_EXPERIMENT", "SCALE_DOWN_SIMULATION"} for c in conditions.values()
    ):
        raise ValueError("scale-down conditions require scale-down record kind")
    if not comparisons and missing("comparability"):
        raise ValueError("absent comparability requires an explicit research gap")
    links = record.get("pisces_links", [])
    if not links and missing("pisces"):
        raise ValueError("PISCES links need verified metadata or an explicit gap")
    identifiers = set()
    for link in links:
        if link["url"].rsplit("/", 1)[1] != link["resource_identifier"].removeprefix("SFID-"):
            raise ValueError("PISCES URL must match its SFID resource identifier")
        utc_timestamp(link["accessed_at"])
        if link["resource_identifier"] in identifiers:
            raise ValueError("duplicate PISCES resource identifier")
        identifiers.add(link["resource_identifier"])
    seen_history = set()
    for event in record["curation_history"]:
        utc_timestamp(event["timestamp"])
        path = relative_path(event["history_file"])
        if path.parts[:2] != ("history", "records") or path.suffix != ".yaml":
            raise ValueError("history_file must name a record sidecar under history/records")
        if event["history_file"] in seen_history:
            raise ValueError("duplicate curation history sidecar")
        seen_history.add(event["history_file"])


def validate_path_components(root: Path, relative: str) -> None:
    """Reject directory aliases before reading or staging a corpus path."""
    path = relative_path(relative)
    current = root
    for index, part in enumerate(path.parts):
        current = current / part
        if current.is_symlink() or not current.resolve().is_relative_to(root.resolve()):
            raise ValueError(
                f"record/history path must not include a symlink or escape: {relative}"
            )
        if index < len(path.parts) - 1 and current.exists() and not current.is_dir():
            raise ValueError(f"record/history parent must be a directory: {relative}")


def validate_inventory_roots(root: Path) -> None:
    for relative in ("data", "data/scale_transfers", "history"):
        directory = root / relative
        if directory.is_symlink() or not directory.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"inventory/history root must not be a symlink or escape: {relative}")
        if not directory.is_dir():
            raise ValueError(f"required inventory or history directory is missing: {relative}")


def validate_history_links(root: Path, record: dict, record_path: str, proposed=None) -> set[str]:
    proposed = proposed or {}
    referenced = set()
    for event in record["curation_history"]:
        relative = event["history_file"]
        validate_path_components(root, relative)
        source = root / relative
        sidecar = proposed.get(relative)
        if sidecar is None:
            sidecar = load(source.read_text())
        validate_history(sidecar)
        if sidecar["target"]["path"] != record_path:
            raise ValueError("history sidecar target differs from record path")
        if sidecar["session"]["id"] != Path(relative).stem:
            raise ValueError("history session ID differs from filename")
        if sidecar["session"]["timestamp"] != event["timestamp"]:
            raise ValueError("inline event and history timestamp differ")
        if event["curator"] not in {actor["name"] for actor in sidecar["session"]["actors"]}:
            raise ValueError("inline curator missing from history actors")
        if not any(
            item["summary"] == event["summary"] and item["type"] == event["action"]
            for item in sidecar["events"]
        ):
            raise ValueError("inline event differs from canonical history event")
        referenced.add(relative)
    return referenced


def validate_repository(root: Path) -> int:
    validator()
    validator("HistoryRecord")
    validate_inventory_roots(root)
    ids = set()
    referenced = set()
    paths = sorted((root / "data/scale_transfers").glob("*.yaml"))
    for path in paths:
        if path.is_symlink():
            raise ValueError(f"record must not be a symlink: {path}")
        record = load(path.read_text())
        validate_record(record)
        if record["id"] in ids:
            raise ValueError(f"duplicate record identifier: {record['id']}")
        if path.stem != record["id"].split(":", 1)[1]:
            raise ValueError("record filename must match its identifier slug")
        ids.add(record["id"])
        referenced |= validate_history_links(root, record, str(path.relative_to(root)))
    sidecars = {str(path.relative_to(root)) for path in (root / "history").rglob("*.yaml")}
    if sidecars != referenced:
        raise ValueError(
            f"unreferenced or missing history sidecars: {sorted(sidecars ^ referenced)}"
        )
    return len(paths)
