# ScaleupMech

ScaleupMech curates organism- and strain-level evidence about transferring cultivation between scales: reported titer, rate and yield, oxygen transfer (OTR and kLa), scale-down models and media at scale. The repository is private for now. The initial seed contains three primary studies, eight conditions, seventeen measurements and six explicitly scoped comparisons.

Each record preserves named experimental conditions, the source-reported biological identity, measurement units and denominator/basis, and explicit limitations. Nominal vessel volume, working volume, initial medium, inoculum and final broth are distinct observations. Reported measurements are kept separate from model predictions; experimental scale-down systems do not establish an observed manufacturing-scale transfer. Comparisons reference actual condition and measurement identifiers and preserve the source's comparability statement. Missing values, strain information and unsupported comparisons remain explicit gaps.

## PISCES boundary

ScaleupMech complements [Project PISCES](https://projectpisces.org/) and its LBNL process flowsheets in SFF/DSP Designer. **PISCES integration is links only: never copy flowsheet, unit-operation or TEA content into ScaleupMech.** Records may retain verified flowsheet identifiers, labels, source citations and external URLs as context. A PISCES link does not imply that a cultivation experiment is equivalent to the flowsheet or that experimental endpoints validate its economics. Missing verified matches are recorded as gaps.

The initial supported link format is `https://projectpisces.org/flowsheets/<positive integer>` with its matching `SFID-<integer>` identifier. Format validation does not establish that a resource exists or is scientifically relevant; both require source review. The closed schema has no field for importing a flowsheet or its contents.

## Development

Install uv and just, then run:

```sh
uv sync --locked
just check
just check-vendored
```

`just check` runs native lint, closed LinkML schema/data/history validation, the bounded source-binding audit and tests. `just check-vendored` verifies canonical files against the immutable claw pin and requires access to their public upstream source. CI runs both on unconditional pull requests, pushes and merge groups. Its additional event-boundary step verifies immutable reviews against the actual GitHub event base, including earlier review ancestry on first branch pushes.

Records live at `data/scale_transfers/<slug>.yaml`, with schema `src/scaleupmech/schema/scaleupmech.yaml`. Numeric fields must be finite; volumes must be positive. Quantity literals, units and bases are retained as reported, without new unit conversions, ratios or inferred missing results. These structural checks do not establish scientific truth.

Prepare a complete draft outside the record inventory and author its canonical history through:

```sh
just new-history --record data/scale_transfers/example.yaml --input workspace/example.json --summary "Describe the change" --details "Sources inspected and what changed" --actor curator --action CREATE
just new-history --record data/scale_transfers/example.yaml --input workspace/example.json --summary "Describe the change" --details "Sources inspected and what changed" --actor curator --action CREATE --apply
```

The first command validates without writing. Apply stages the record and canonical history sidecar together through the repository lock and recoverable transaction, preserving existing history. Native serialization is deterministic JSON as a YAML subset; no unmeasured shared YAML emit profile is claimed.

## Governance and release state

The scaffold uses immutable claw bootstrap pin `88e719d5480d0008d6ce082510dcd066775f232b`, also used by the installed dependency and lockfile. This is a local bootstrap, not a completed fleet release. Registration, private-repository audit support, the active release lane and common-pin committed-main audit remain separate gates.

Independent adversarial review, issues for confirmed findings, fixes, re-review and green hosted checks precede the user's merge decision. Merge queue automation remains paused. Native CI invokes no research provider. Original code and schemas use CC0; scientific records use CC-BY-4.0 while cited sources and governed files retain their own rights and notices.

See [initial seed provenance](docs/seed-provenance.md) and [scientific data attribution](LICENSE-DATA). A verified [PISCES Corn Stover → Ethanol example](https://projectpisces.org/flowsheets/413) provides external navigation only; it is unrelated to the initial seed studies, which retain explicit unmatched-PISCES gaps.
