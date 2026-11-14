---
name: curate-scale-transfer
description: "Curate organism- and strain-level scale-transfer evidence with exact reported quantities and scoped external links."
---

Read `AGENTS.md`, the source record and primary evidence. Keep actual scale transfer separate from experimental or simulated scale-down. Preserve reported biological identity, volume kind/component, quantity literal, unit, basis and sampling context. Do not calculate missing results or imply a comparison the source does not support.

For PISCES, verify the external flowsheet metadata and retain only its matching identifier, label, citation and URL with context-only scope. Never copy flowsheet, unit-operation or TEA content.

Prepare the complete record and use `just new-history` in dry-run mode before authorized apply. Run `just check` and `just check-vendored`. Scientific reviews must follow `docs/record-reviews.md` and `docs/record-review-profile.md` and persist a validated bundle through `scripts/record_review.py`. Prose alone is not a completed structured review. Independent PR review and user merge decisions remain separate.
