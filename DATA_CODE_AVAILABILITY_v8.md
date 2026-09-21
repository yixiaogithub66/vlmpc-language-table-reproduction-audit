# Data and Code Availability v8

## Ready-to-use manuscript statement

The public revision artifact is available at https://github.com/yixiaogithub66/vlmpc-language-table-reproduction-audit (release v1.0.3). It includes the manuscript source, a single authoritative 18-run Semantic MPC file, regenerated threshold and condition statistics, the repeated target-image matrix, the controlled semantic-fault audit, exact method parameters, separate runtime-asset and source-snapshot manifests, and a reviewer-facing source snapshot. It deliberately excludes API credentials, private gateway addresses, local absolute paths, virtual environments, raw service logs, and third-party model weights. The reported aggregates and table values can be recomputed from the included summaries without relying on cached VLM responses. End-to-end reruns additionally require independently obtained detector, tracker, and video-prediction checkpoints and a separately configured compatible VLM backend, as documented in the reproduction guide.

## Package contents

- REPRODUCTION_GUIDE_v8.md: environment, commands, artifact mapping, and limitations.
- supplement_v8_sanitized/data/: submission-safe derived statistics, including the revision_20260919 directory.
- supplement_v8_sanitized/source/: source snapshot, two new audit drivers, and redacted environment template.
- supplement_v8_sanitized/data/grounded_action_replacement_summary_v8.csv: grounded action-authority summary.
- supplement_v8_sanitized/data/target_image_claim_boundary_v8.csv: archived target-image claim boundary.
- supplement_v8_sanitized/data/event_requery_statistics_v8.csv: matched event-control statistics.
- data/semantic_mpc_authoritative_runs_v8.csv: sole authoritative 18-run Semantic MPC dataset.
- data/threshold_sensitivity_v8.csv: unified threshold table regenerated from authoritative sources.
- data/method_parameter_table_v2.csv: recovered implementation parameters.
- data/runtime_asset_manifest_v8.csv: hashes for required non-redistributed runtime assets.
- supplement_v8_sanitized/data/code_manifest_v8.csv: executed-source and public-snapshot hashes.
- scripts/verify_artifact.py: automated numeric, hash, and package-integrity checks.
- RESPONSE_TO_REVIEWERS_v8.md: point-by-point revision record.

## Revision evidence

- Target-image matrix: 9 end-to-end runs, 8/9 semantic matches, 7/8 joint active successes, and one pre-satisfied run reported separately.
- Semantic-fault audit: 3/3 semantic repairs and 2/3 true-target threshold successes under explicitly forced synthetic re-query, versus 0/3 without re-query.
- Fresh matched natural-event controls: identical final distances by seed; no natural recovery-benefit claim.

## Public release status

The repository URL is now fixed in the manuscript, response letter, and reproduction guide. Before final submission, verify that the repository remains public and that release v1.0.3 resolves. A DOI may be added later through an archival service, but no DOI is claimed in this version.


