"""Trusted event boundaries exercised with real committed review histories."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from test_record_review_contract import reviews as canonical_reviews
from test_record_review_contract import sample as canonical_sample

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/check_review_event_base.py"


@pytest.fixture(scope="module")
def reviews():
    return canonical_reviews.__wrapped__()


@pytest.fixture
def sample(tmp_path, reviews):
    return canonical_sample.__wrapped__(tmp_path, reviews)


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def commit(root, message):
    git(root, "add", "-A")
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD")


def event(name, base, head):
    if name == "pull_request":
        return {"pull_request": {"base": {"sha": base}}}
    if name == "merge_group":
        return {"merge_group": {"base_sha": base}}
    return {"before": base, "after": head, "created": base == "0" * 40, "deleted": False}


def invoke(root, name, payload):
    event_path = root.parent / "event.json"
    event_path.write_text(json.dumps(payload))
    env_file = root.parent / "github-env"
    result = subprocess.run([sys.executable, str(HELPER), "--root", str(root),
                             "--event-name", name, "--event-path", str(event_path),
                             "--env-file", str(env_file), "--no-fetch"],
                            capture_output=True, text=True,
                            env={**os.environ, "RECORD_REVIEW_BASE": "HEAD"})
    return result, env_file


@pytest.fixture
def committed_review(sample, reviews):
    root, record = sample
    initial = git(root, "rev-parse", "HEAD")
    record["source"]["state"] = "git_commit"
    reviews.save_review(root, record)
    reviewed = commit(root, "Commit immutable review pair")
    return root, initial, reviewed


@pytest.mark.parametrize("name", ["pull_request", "merge_group", "push"])
def test_verified_event_base_is_exported_before_native_checks(committed_review, name):
    root, initial, head = committed_review
    result, env_file = invoke(root, name, event(name, initial, head))
    assert result.returncode == 0, result.stderr
    assert env_file.read_text() == f"RECORD_REVIEW_BASE={initial}\n"
    assert json.loads(result.stdout)["base"] == initial


@pytest.mark.parametrize("name", ["pull_request", "merge_group", "push"])
def test_committed_review_deletion_fails_at_trusted_event_base(committed_review, name):
    root, _, reviewed = committed_review
    shutil.rmtree(root / "reviews")  # Fresh checkout does not retain empty directories.
    head = commit(root, "Delete previously committed review")
    default = subprocess.run([sys.executable, str(ROOT / "scripts/record_review.py"),
                              "--repo-root", str(root), "check", "--base", "HEAD"],
                             capture_output=True, text=True)
    assert default.returncode == 0  # The event boundary, not current-file validation, matters.
    result, env_file = invoke(root, name, event(name, reviewed, head))
    assert result.returncode != 0
    assert not env_file.exists()


def test_first_branch_push_checks_earlier_review_ancestry(committed_review):
    root, _, _ = committed_review
    shutil.rmtree(root / "reviews")
    commit(root, "Delete review before first publication")
    (root / "unrelated.txt").write_text("A later commit conceals deletion from HEAD parent checks.\n")
    head = commit(root, "Unrelated later work")
    result, env_file = invoke(root, "push", event("push", "0" * 40, head))
    assert result.returncode != 0
    assert not env_file.exists()


def test_first_branch_push_without_review_history_is_explicitly_valid(sample):
    root, _ = sample
    head = git(root, "rev-parse", "HEAD")
    result, env_file = invoke(root, "push", event("push", "0" * 40, head))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["initial_branch_push"] is True
    assert env_file.read_text() == f"RECORD_REVIEW_BASE={head}\n"


@pytest.mark.parametrize("payload", [
    {}, {"pull_request": {"base": {"sha": "main"}}},
    {"pull_request": {"base": {"sha": "0" * 40}}},
    {"pull_request": {"base": {"sha": "e" * 40}}},
])
def test_absent_malformed_zero_or_unavailable_pr_base_fails_closed(sample, payload):
    root, _ = sample
    result, env_file = invoke(root, "pull_request", payload)
    assert result.returncode != 0
    assert not env_file.exists()


def test_zero_push_without_created_branch_attestation_fails(sample):
    root, _ = sample
    payload = event("push", "0" * 40, git(root, "rev-parse", "HEAD"))
    payload["created"] = False
    result, env_file = invoke(root, "push", payload)
    assert result.returncode != 0
    assert not env_file.exists()


def test_initial_push_requires_complete_history(sample):
    root, _ = sample
    head = git(root, "rev-parse", "HEAD")
    (root / ".git/shallow").write_text(head + "\n")
    result, env_file = invoke(root, "push", event("push", "0" * 40, head))
    assert result.returncode != 0
    assert not env_file.exists()


def test_review_base_workflow_binding_is_unconditional_and_precedes_gate():
    workflow = yaml.load((ROOT / ".github/workflows/validate-strict.yaml").read_text(),
                         Loader=yaml.BaseLoader)
    steps = workflow["jobs"]["validate-strict"]["steps"]
    bindings = [i for i, step in enumerate(steps) if step.get("run") == "just check-review-event-base"]
    assert len(bindings) == 1
    assert "if" not in steps[bindings[0]]
    assert bindings[0] < next(i for i, step in enumerate(steps) if step.get("run") == "just check")
    recipe = (ROOT / "justfile").read_text().split("check-review-event-base:", 1)[1].split("\n\n", 1)[0]
    assert "uv run --locked python scripts/check_review_event_base.py" in recipe


def test_unavailable_event_base_fetches_and_reverifies_exact_commit(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("native_review_event", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    revision = "a" * 40
    calls = []

    def fake_git(root, *args):
        calls.append(args)
        if len(calls) == 1:
            raise ValueError("not fetched")
        return revision if args[0] == "rev-parse" else ""

    monkeypatch.setattr(module, "git", fake_git)
    module.verify_commit(tmp_path, revision, fetch=True)
    assert calls == [
        ("rev-parse", "--verify", "--end-of-options", revision + "^{commit}"),
        ("fetch", "--no-tags", "origin", revision),
        ("rev-parse", "--verify", "--end-of-options", revision + "^{commit}"),
    ]


def test_fetch_success_without_exact_commit_is_not_accepted(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("native_review_event_wrong_fetch", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []

    def fake_git(root, *args):
        calls.append(args)
        if len(calls) == 1:
            raise ValueError("not fetched")
        return "b" * 40 if args[0] == "rev-parse" else ""

    monkeypatch.setattr(module, "git", fake_git)
    with pytest.raises(ValueError, match="exact requested commit"):
        module.verify_commit(tmp_path, "a" * 40, fetch=True)
