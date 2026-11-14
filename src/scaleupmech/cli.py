"""Scale-transfer validation and dry-run-first history authoring."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from kg_microbe_history.scaffold import build_record, new_history_path
from kg_microbe_write import ValidatedWriteTransaction
from plugins.lock_manager import LockManager
from plugins.repository_settings import RepositorySettings

from .validate import (
    load,
    relative_path,
    validate_history,
    validate_history_links,
    validate_inventory_roots,
    validate_path_components,
    validate_record,
    validate_repository,
    validator,
)


def repository_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], check=True, capture_output=True, text=True
    )
    return Path(result.stdout.strip()).resolve()


def new_history(root: Path, args) -> dict:
    target_path = relative_path(args.record)
    if target_path.parts[:2] != ("data", "scale_transfers") or len(target_path.parts) != 3:
        raise ValueError("record must name data/scale_transfers/<slug>.yaml")
    if target_path.suffix != ".yaml":
        raise ValueError("record must use .yaml")
    target = root / target_path
    if target.is_symlink():
        raise ValueError("record must not be a symlink")
    settings = RepositorySettings.from_environment(environ={"SCALEUPMECH_ROOT": str(root)})
    settings.get_target("scaleupmech").open()
    # One native lock across worktrees of this Git repository.
    common = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--git-common-dir"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    lock_root = (root / common).resolve() / "scaleupmech-locks"
    with LockManager({"locks_dir": str(lock_root)}).lock("scaleupmech", "new-history"):
        validate_inventory_roots(root)
        validate_path_components(root, str(target_path))
        record = load(Path(args.input).read_text())
        if record.get("id") != f"ScaleupMech:{target_path.stem}":
            raise ValueError("record ID must match target filename")
        old = load(target.read_text()) if target.exists() else None
        if old is not None:
            validate_record(old)
            validate_history_links(root, old, str(target_path))
            if record.get("curation_history", []) != old["curation_history"]:
                raise ValueError("input must preserve existing curation history exactly")
            if args.action == "CREATE":
                raise ValueError("CREATE cannot replace an existing record")
        elif record.get("curation_history"):
            raise ValueError("new records must not import an unauthored history")
        history_path, session_id, timestamp = new_history_path(
            Path("history"), "record", target_path.stem, args.actor
        )
        validate_path_components(root, str(history_path))
        if (root / history_path).exists():
            raise ValueError("refusing to overwrite an existing history sidecar")
        sidecar = build_record(
            kind="record",
            slug=target_path.stem,
            target_path=str(target_path),
            session_id=session_id,
            timestamp=timestamp,
            summary=args.summary,
            details=args.details,
            event=args.action,
            actor_name=args.actor,
            actor_type=args.actor_type,
            model=args.model,
            agent_tool=args.agent_tool,
        )
        event = {
            "timestamp": timestamp,
            "curator": args.actor,
            "action": args.action,
            "summary": args.summary,
            "history_file": str(history_path),
        }
        record.setdefault("curation_history", []).append(event)
        validate_record(record)
        validate_history(sidecar)
        validate_history_links(root, record, str(target_path), {str(history_path): sidecar})

        def validate_staged(path: Path, text: str) -> None:
            value = load(text)
            if path == target:
                validate_record(value)
            else:
                validate_history(value)

        # JSON is a strict YAML subset: deterministic native serialization preserves
        # all values, without claiming an unmeasured shared YAML emit profile.
        tx = ValidatedWriteTransaction(
            root, validator=validate_staged, journal_dir=root / "workspace/write-journals"
        )
        tx.stage(str(target_path), json.dumps(record, indent=2, ensure_ascii=False) + "\n")
        tx.stage(str(history_path), json.dumps(sidecar, indent=2, ensure_ascii=False) + "\n")
        result = tx.commit(apply=args.apply)
        return result.as_dict()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="scaleupmech")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    sub.add_parser("validate-schema")
    history = sub.add_parser("new-history")
    for name in ("record", "input", "summary", "details", "actor"):
        history.add_argument(f"--{name}", required=True)
    history.add_argument(
        "--actor-type", choices=["human", "ai_agent", "automation", "other"], default="human"
    )
    history.add_argument("--model")
    history.add_argument("--agent-tool")
    history.add_argument("--action", choices=["CREATE", "EDIT", "REVIEW", "AUDIT"], default="EDIT")
    history.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-schema":
            validator()
            validator("HistoryRecord")
            print("Closed LinkML schemas validated")
        elif args.command == "validate":
            print(f"Validated {validate_repository(repository_root())} scale-transfer records")
        else:
            print(json.dumps(new_history(repository_root(), args), indent=2))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
