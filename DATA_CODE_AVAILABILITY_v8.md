# Data and Code Availability v8

## Ready-to-use manuscript statement

The public revision artifact is available at https://github.com/yixiaogithub66/vlmpc-language-table-reproduction-audit (release v1.0.0). It includes the manuscript source, sanitized per-run and aggregate CSVs, the repeated target-image matrix, the controlled semantic-fault audit, condition-wise statistics, exact method parameters, the reproduction guide, a checkpoint/code hash manifest, and a reviewer-facing source snapshot. It deliberately excludes API credentials, private gateway addresses, local absolute paths, virtual environments, raw service logs, and third-party model weights. The reported aggregates and table values can be recomputed from the included summaries without relying on cached VLM responses. End-to-end reruns additionally require independently obtained detector, tracker, and video-prediction checkpoints and a separately configured compatible VLM backend, as documented in the reproduction guide.

## Package contents

- REPRODUCTION_GUIDE_v8.md: environment, commands, artifact mapping, and limitations.
- supplement_v8_sanitized/data/: submission-safe derived statistics, including the revision_20260919 directory.
- supplement_v8_sanitized/source/: source snapshot, two new audit drivers, and redacted environment template.
- data/method_parameter_table_v2.csv: recovered implementation parameters.
- data/checkpoint_and_code_manifest_v4.csv: checkpoint and historical active-code hash prefixes.
- RESPONSE_TO_REVIEWERS_v8.md: point-by-point revision record.

## Revision evidence

- Target-image matrix: 9 end-to-end runs, 8/9 semantic matches, 7/8 joint active successes, and one pre-satisfied run reported separately.
- Semantic-fault audit: 3/3 semantic repairs and 2/3 true-target threshold successes under explicitly forced synthetic re-query, versus 0/3 without re-query.
- Fresh matched natural-event controls: identical final distances by seed; no natural recovery-benefit claim.

## Public release status

The repository URL is now fixed in the manuscript, response letter, and reproduction guide. Before final submission, verify that the repository remains public and that release v1.0.0 resolves. A DOI may be added later through an archival service, but no DOI is claimed in this version.


