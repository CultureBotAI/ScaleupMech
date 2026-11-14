"""Bind canonical immutable-review checks to a verified GitHub event boundary."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ZERO_SHA = "0" * 40
SHA = re.compile(r"[0-9a-f]{40}")


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                            text=True, timeout=30)
    if result.returncode:
        raise ValueError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def verify_commit(root: Path, revision: str, *, fetch: bool) -> None:
    if not isinstance(revision, str) or not SHA.fullmatch(revision) or revision == ZERO_SHA:
        raise ValueError("event base must be a full nonzero commit SHA")
    try:
        resolved = git(root, "rev-parse", "--verify", "--end-of-options", revision + "^{commit}")
    except ValueError:
        if not fetch:
            raise ValueError("event base is unavailable; refusing to substitute HEAD") from None
        git(root, "fetch", "--no-tags", "origin", revision)
        resolved = git(root, "rev-parse", "--verify", "--end-of-options", revision + "^{commit}")
    if resolved != revision:
        raise ValueError("event base did not resolve to the exact requested commit")


def event_boundary(event_name: str, payload: dict) -> tuple[str, bool]:
    try:
        if event_name == "pull_request":
            revision = payload["pull_request"]["base"]["sha"]
        elif event_name == "merge_group":
            revision = payload["merge_group"]["base_sha"]
        elif event_name == "push":
            revision = payload["before"]
        else:
            raise ValueError("unsupported review-boundary event")
    except (KeyError, TypeError):
        raise ValueError("trusted event base is absent or malformed") from None
    if not isinstance(revision, str) or not SHA.fullmatch(revision):
        raise ValueError("trusted event base must be a full commit SHA")
    initial_push = event_name == "push" and revision == ZERO_SHA
    if revision == ZERO_SHA and not initial_push:
        raise ValueError("zero event base is only valid for a created branch push")
    if initial_push and (payload.get("created") is not True or payload.get("deleted") is True):
        raise ValueError("zero event base requires an explicit created, nondeleted branch")
    return revision, initial_push


def check_event(root: Path, event_name: str, payload: dict, env_file: Path,
                *, fetch: bool = True) -> dict:
    root = root.resolve()
    if Path(git(root, "rev-parse", "--show-toplevel")) != root:
        raise ValueError("root must be the exact Git worktree")
    head = git(root, "rev-parse", "HEAD")
    verify_commit(root, head, fetch=False)
    revision, initial_push = event_boundary(event_name, payload)
    if initial_push:
        if payload.get("after") != head:
            raise ValueError("created branch event after SHA must equal the checked-out head")
        revision = head  # No prior branch commit exists; ancestry is checked separately below.
    else:
        verify_commit(root, revision, fetch=fetch)
    if git(root, "rev-parse", "--is-shallow-repository") == "true":
        if not fetch:
            raise ValueError("complete reachable review history is required")
        git(root, "fetch", "--unshallow", "--no-tags", "origin")
        if git(root, "rev-parse", "--is-shallow-repository") != "false":
            raise ValueError("reachable history is still shallow after fetch")
    # Inspect only reachable commits that changed the exact governed review path.
    # The event base protects earlier publication; the range also protects a review
    # created and deleted between event endpoints. A first push examines ancestry.
    ancestry = [head] if initial_push else [head, "^" + revision]
    historical = git(root, "rev-list", "--full-history", *ancestry,
                     "--", "reviews/structured").splitlines()
    bases = list(dict.fromkeys([revision, *historical]))
    checker = Path(__file__).resolve().with_name("record_review.py")
    for base in bases:
        verify_commit(root, base, fetch=False)
        result = subprocess.run([sys.executable, str(checker), "--repo-root", str(root),
                                 "check", "--base", base], capture_output=True,
                                text=True, timeout=120)
        if result.returncode:
            raise ValueError(f"canonical review check failed at {base}: {result.stderr.strip()}")
    # Publish the boundary only after all checks succeed. The later canonical pytest
    # contract consumes this exact verified value rather than its HEAD default.
    with env_file.open("a", encoding="utf-8") as stream:
        stream.write(f"RECORD_REVIEW_BASE={revision}\n")
    return {"base": revision, "checked_bases": bases, "initial_branch_push": initial_push}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--event-name", default=os.environ.get("GITHUB_EVENT_NAME"))
    parser.add_argument("--event-path", type=Path, default=os.environ.get("GITHUB_EVENT_PATH"))
    parser.add_argument("--env-file", type=Path, default=os.environ.get("GITHUB_ENV"))
    parser.add_argument("--no-fetch", action="store_true",
                        help="refuse unavailable history without network access")
    args = parser.parse_args(argv)
    if not args.event_name or args.event_path is None or args.env_file is None:
        parser.error("event name, event path and GitHub environment file are required")
    try:
        payload = json.loads(args.event_path.read_text())
        if not isinstance(payload, dict):
            raise ValueError("event payload must be an object")
        print(json.dumps(check_event(args.root, args.event_name, payload, args.env_file,
                                    fetch=not args.no_fetch), sort_keys=True))
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"review event boundary failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
