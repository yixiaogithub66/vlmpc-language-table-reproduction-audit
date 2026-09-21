# Evidence Data Map

The v1.0.4 artifact uses one authoritative source for each reported result family.

## Authoritative files

- semantic_mpc_authoritative_runs_v8.csv contains the final 18-run Semantic MPC suite used by the manuscript.
- threshold_sensitivity_v8.csv is regenerated from that 18-run file and archived_nonsemantic_branch_runs_v8.csv.
- archived_nonsemantic_branch_runs_v8.csv contains the unmodified, grounded, and single archived event branches only. It intentionally excludes the superseded 2026-06-06 Semantic MPC rows.
- supplement_v8_sanitized/data/semantic_mpc_condition_statistics_v8.csv contains sample-SD condition summaries regenerated from the authoritative 18 rows.
- supplement_v8_sanitized/data/revision_20260919 contains the target-image, semantic-fault, and fresh matched event-control results.

The authoritative Semantic MPC values are n=18, mean final distance 0.064119, sample SD 0.015025, 3/18 successes at 0.05, and 18/18 successes at 0.08.

Superseded Semantic MPC rows, the old 5/18 threshold table, and the old aggregate summary with mean 0.059996 are not included in this release. Raw logs are not redistributed because they contain machine-local runtime metadata; sanitized run identifiers are retained where needed for provenance.
