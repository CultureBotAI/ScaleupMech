set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

check: lint validate test

lint:
    uv run --locked ruff check src tests/test_native.py scripts/check_review_event_base.py tests/test_review_event_base.py

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

# Template tooling is independently pinned; the governed project dependency is unchanged.
check-template:
    uv run --isolated --no-project --with "kg-microbe-orchestration @ git+https://github.com/CultureBotAI/culturebotai-claw.git@f6a00874ed153154feb26918933f2cd8110c5ec8" python -m kg_microbe_skills.template_cli check --target-root . --config workflow/mech-template.json
    uv run --isolated --no-project --with "kg-microbe-orchestration @ git+https://github.com/CultureBotAI/culturebotai-claw.git@f6a00874ed153154feb26918933f2cd8110c5ec8" python -m kg_microbe_workflows validate --profile workflow/mech-workflow.yaml --parent workflow/parent/mech-cycle.yaml --schema workflow/parent/workflow.yaml --repository-key scaleupmech
