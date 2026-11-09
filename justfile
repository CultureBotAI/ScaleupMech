set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

check: lint validate audit-seed test

lint:
    uv run --locked ruff check src tests/test_native.py tests/test_seed_audit.py scripts/check_review_event_base.py tests/test_review_event_base.py

validate:
    uv run --locked scaleupmech validate

validate-schema:
    uv run --locked scaleupmech validate-schema

validate-data: validate

validate-all: validate

test:
    uv run --locked pytest -q

check-vendored:
    bash scripts/check_vendored_sync.sh

new-history *args:
    uv run --locked scaleupmech new-history {{args}}

validate-history:
    uv run --locked scaleupmech validate

check-review-event-base:
    uv run --locked python scripts/check_review_event_base.py

audit-seed:
    uv run --locked python -m scaleupmech.seed_audit
