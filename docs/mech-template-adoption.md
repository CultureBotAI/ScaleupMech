# Mech template candidate

This branch prepares ScaleupMech's reusable infrastructure from immutable CLAW source
`f6a00874ed153154feb26918933f2cd8110c5ec8`. The adoption receipt records candidate state and exact
component/configuration hashes. It is not proof of adoption on main or runtime
installation. New merge, governance release and runtime activation decisions are
separate.

The six shared skills provide queue review, authorized issue resolution,
workflow adaptation, identifier policy and structured record/cohort review. Native scientific
curation remains in `.claude/skills/curate-scale-transfer/SKILL.md`; its identifiers, evidence,
schemas, writers and history are unchanged. `workflow/mech-template.json` records
an explicit decision and prerequisite evidence for every canonical component.
The stale sealed fleet capability declarations are not rewritten by this PR.

`workflow/mech-workflow.yaml` binds native skills to hash-pinned parent/schema
snapshots. Graph and protein-example stages are blocked on native adapters.
Enabled stage bindings describe candidate applicability, not authorization to
execute them. No runtime service or cycle is installed or activated. Existing
freshness artifacts, pending work, governance pin/dependency and release policy
remain separate and unchanged.

Run `just check-template` for source/currentness, managed content and profile
validation. It uses the separately pinned template tool in an isolated uv
environment, leaving the governed project dependency untouched. Native gates
remain `just check` and `just check-vendored`. CI runs both independently.

For an update, inspect the new immutable canonical source and its baseline,
review component decisions, preview the plan, apply through the shared tool,
review the diff, run native checks and hosted CI, prove an unchanged repeat run,
and obtain independent review. A conflict in an owned managed region must be
resolved through canonical review; local scientific extensions stay outside it.
Keep source_ref, this guide and the check-template recipe synchronized in the
reviewed update. Do not move the governed pin for a template-only update.

Rollback by reverting the reviewed adoption/update commit on an owned branch
and rerunning native gates. Preserve all scientific changes made since adoption;
never reset the checkout or remove unrelated records/history. Parent/profile
changes need their own next-cycle activation decision if a runtime is later
adopted. This PR grants no merge or activation authority.
