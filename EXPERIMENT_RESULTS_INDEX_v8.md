# Experiment Results Index v8

This index maps every manuscript result family to a file that exists in the public v1.0.2 artifact. Raw service logs are not redistributed because they contain machine-local runtime metadata.

## Authoritative Evidence

| Result family | Public artifact | Reported result |
| --- | --- | --- |
| Final Semantic MPC suite | data/semantic_mpc_authoritative_runs_v8.csv | 18 runs; mean final distance 0.064119; sample SD 0.015025; 3/18 at 0.05; 18/18 at 0.08 |
| Unified threshold sensitivity | data/threshold_sensitivity_v8.csv | One table regenerated from the authoritative Semantic MPC runs and archived nonsemantic branches |
| Unmodified and grounded branches | data/archived_nonsemantic_branch_runs_v8.csv | Unmodified 0/4 and 0/8; grounded 4/4 and 8/8 at 0.08 |
| Semantic condition variability | supplement_v8_sanitized/data/semantic_mpc_condition_statistics_v8.csv | Sample-SD summaries by input form, target, seed, and ablation |
| Grounded action authority | supplement_v8_sanitized/data/grounded_action_replacement_summary_v7.csv | 23/23 raw actions replaced in every grounded run |
| Target-image matrix | supplement_v8_sanitized/data/revision_20260919/target_image_matrix_runs_v8.csv | 8/9 semantic matches; 7/8 joint active successes; one pre-satisfied run |
| Controlled semantic-fault audit | supplement_v8_sanitized/data/revision_20260919/event_fault_recovery_runs_v8.csv | 3/3 forced repairs; 2/3 treatment successes; 0/3 control successes |
| Fresh matched natural-event controls | supplement_v8_sanitized/data/revision_20260919/event_matched_controls_revision_v8.csv | Trigger in 2/3 event-enabled runs; matched final distances unchanged |

## Source and Runtime Provenance

- supplement_v8_sanitized/data/code_manifest_v8.csv records both executed-source and public-snapshot SHA-256 values.
- supplement_v8_sanitized/SOURCE_SNAPSHOT_PROVENANCE_v8.md explains the one sanitized main.py difference.
- data/runtime_asset_manifest_v8.csv records hashes and sizes for required but non-redistributed checkpoints.
- data/method_parameter_table_v2.csv records recovered implementation parameters.

## Package Entry Points

- main.pdf
- RESPONSE_TO_REVIEWERS_v8.md
- REPRODUCTION_GUIDE_v8.md
- DATA_CODE_AVAILABILITY_v8.md
- FINAL_MANIFEST_v8.md
- scripts/verify_artifact.py

Run python scripts/verify_artifact.py from the repository root before submission. The paper intentionally makes no claim that the natural event trigger provides causal recovery benefit.
