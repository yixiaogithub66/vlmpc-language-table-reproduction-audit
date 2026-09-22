# Portable Data

This directory contains the CSVs used directly by the manuscript and its figure scripts.

- raw_controller_multiseed_runs_v9.csv: fresh raw four-variant sweep, 16 rows, seeds 45--48.
- raw_controller_multiseed_v9.csv: aggregate companion table for the fresh raw sweep.
- semantic_mpc_live_runs_v9.csv: 18 heterogeneous semantic diagnostic rows.
- robustness_edge_audit_v9.csv: seven-row detector-level boundary audit; the
  four perturbation input images are bundled under
  ../supplement_v9_sanitized/data/robustness_edge_audit/.
- threshold_sensitivity_v9.csv: threshold counts across the portable suites.
- archived_nonsemantic_branch_runs_v8.csv: explicitly archived non-semantic rows retained for comparison.
- method_parameter_table_v2.csv: parameter record used by the experiment descriptions.
- runtime_asset_manifest_v9.csv: runtime-asset provenance manifest.

Revision-specific rows are stored under ../supplement_v9_sanitized/data/revision_20260922/.
The robustness-edge audit is detector-level evidence only; it is not a
closed-loop or real-camera robustness benchmark. Do not combine the archived
rows with the fresh raw sweep when estimating seed-level variability.
