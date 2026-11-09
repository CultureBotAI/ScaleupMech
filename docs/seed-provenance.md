# Initial scale-transfer evidence

The initial seed contains three primary studies, eight conditions, seventeen
measurements and six explicit comparisons. Each record separates the reported
vessel capacity from working, medium and inoculum volumes. Values and units are
transcribed; no new yield, rate, scale ratio or uncertainty is calculated.

| Study | Retained scope | Important limitation |
| --- | --- | --- |
| Zhou et al., 2018, DOI 10.3390/molecules23010125 | ZX01 GP-1 concentrations and kLa across nominal 5, 15, 70 and 500 L vessels; four-batch verification averages | Similar kLa does not make vessel geometry, agitation or inoculum identical. |
| Olughu et al., 2019 online/2020 issue, DOI 10.1002/jctb.6248 | DM1945x3 physical scale-down control versus SDR 12, with final cadaverine concentrations and reported relative loss | This is an experiment simulating heterogeneity, not an observed manufacturing-scale cultivation. Table 1 PFR 0.3 L conflicts with Methods 320 mL. |
| Cao et al., 2026, DOI 10.1186/s40104-026-01459-y | Optimized cgl-Ile8 nominal 5/50 L concentration, volumetric productivity and source-labelled yield | The g/g substrate denominator remains unresolved; no formal yield comparison. The 50 L working volume and complete operating equivalence remain gaps. |

The published strain labels are retained. No taxonomic identity beyond what the
primary source establishes is invented. The source catalogue retains retrieval
times, raw-source hashes, rights and bounded fact projections. Full articles and
the supplementary document remain in the private durable research workspace;
they are not copied into this repository.

## Source audit and its limits

`just audit-seed` validates the reviewed selection, every typed scientific field,
condition/measurement/comparison bindings, exact evidence-locator coverage,
source projection hashes and metadata-only PISCES navigation. Its 71 bindings
are a reviewed seed contract, not a general literature parser. A projection is
a curator transcription or paraphrase, not a claimed verbatim quotation.
The source-text digest identifies the private upstream selector bytes and is
not an online authenticity guarantee. Scientific correctness is separately
reviewed against the primary sources. Updating this initial seed requires
updating and independently reviewing its source contract.

The audit rejects real alternative-source mutations: a 15 L result attached to
5 L, a valid pilot-duration locator substituted for the bench method, removal of
the inoculum-method citation while retaining the medium citation, invented
yield denominators and PISCES payload fields. Issue 1 records the initially
missing GP-1 method citations and their corrected coverage.

## PISCES boundary

[Project PISCES](https://projectpisces.org/) and
[DSP Designer](https://dspdesigner.lbl.gov/) provide external process context.
The verified [Corn Stover → Ethanol, SFID-413](https://projectpisces.org/flowsheets/413)
page is a navigation example unrelated to these three seed studies. Each
scientific record therefore has an explicit unmatched-PISCES gap. The link does
not establish strain identity, experimental equivalence or a scale comparison.
No SFF, flowsheet, unit-operation, stream or techno-economic content is imported
or reconstructed here. PISCES metadata remains subject to its source's rights;
our CC-BY data attribution does not relicense it.

## Initial validation receipt

The initial seed gate passed 217 tests with 3 expected governed skips before the
scaffold's separate URL-validation follow-up. All 22 governed artifacts matched
the immutable pin. Issue 1's two removal controls were run in separate Python
processes with distinct bytecode caches: repaired: 2 pass, coverage guard removed: 2 fail (both invalid inputs were accepted), restored: 2 pass. The remaining numeric
source was valid in both negative controls, so the checks distinguish evidence
coverage from mere citation existence. The private mutation logs remain under
`~/agent-work/ScaleupMech/evidence/issue1-mutation*.log`.
