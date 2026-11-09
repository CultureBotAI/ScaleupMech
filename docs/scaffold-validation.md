# Native scaffold validation

The scaffold contains no scientific records. Fixtures in `tests/test_native.py` are synthetic and are not evidence for an organism or PISCES resource.

The native gate covers closed nested objects, finite quantities and positive volumes, range/qualifier consistency, explicit missing-context gaps, distinct volume components, identity-bound measurement/comparison references, modeled versus observed outcomes, scale-down context and PISCES metadata-only host/SFID binding. Separate tests preserve canonical history, reject inventory/path symlinks before staging, and verify trusted GitHub event bases for immutable review checks.

The source-bound history writer and CI helper reuse the independently reviewed Cofactor/Assay engineering pattern. Canonical governed files are installed only by supported sync, with no manual payload edits. Mutation runs are retained under the durable agent-work root; the scaffold PR records the observed gate and mutation results. Structural validation does not substitute for independent scientific review.

Native records use deterministic JSON, a strict YAML subset. This is an explicit new-format writer contract, not a fabricated verified profile for claw's shared YAML serializer. The native writer uses RepositorySettings, a repository-wide lock and ValidatedWriteTransaction. Shared cross-corpus authoring still follows claw's measured serializer contract.
