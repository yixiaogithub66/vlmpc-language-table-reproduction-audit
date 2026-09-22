# Data and Code Availability

The v1.0.7 revision artifact is provided as a portable, sanitized package alongside the manuscript. The exact release is:

https://github.com/yixiaogithub66/vlmpc-language-table-reproduction-audit

https://github.com/yixiaogithub66/vlmpc-language-table-reproduction-audit/releases/tag/v1.0.7

The package contains:

- the revised LaTeX manuscript and compiled PDF;
- the Python figure-generation, live-result import, and artifact-verification scripts;
- authoritative run-level CSV summaries for the fresh raw sweep, semantic suite, target-image matrix, event controls, visual-feedback test, and controlled semantic-fault audit;
- archived grounded-branch summaries and the 23/23 action-replacement record;
- the detector-level robustness-edge CSV and four portable perturbation inputs;
- source snapshots with SHA-256 manifest entries and an explicit sanitized-main.py provenance note.

The package intentionally excludes API keys, private endpoint configuration, raw service transcripts, raw simulator videos, model checkpoints, and any non-portable local filesystem paths. The online language component is described in the manuscript as a GPT-5.5-based VLM accessed through an external Responses-compatible runtime/interface. The exact private runtime configuration is not part of the public artifact.

The primary evidence files are:

- data/raw_controller_multiseed_runs_v9.csv
- data/semantic_mpc_live_runs_v9.csv
- data/threshold_sensitivity_v9.csv
- data/robustness_edge_audit_v9.csv
- supplement_v9_sanitized/data/revision_20260922/target_image_matrix_runs_v9.csv
- supplement_v9_sanitized/data/revision_20260922/event_requery_controls_v9.csv
- supplement_v9_sanitized/data/revision_20260922/visual_feedback_runs_v9.csv
- supplement_v9_sanitized/data/revision_20260922/event_fault_recovery_runs_v9.csv

The scripts reproduce the reported aggregates and figures from the portable CSVs. Running the online experiments again requires the original simulator, local dependencies, and an independently configured external VLM service; those requirements are documented without publishing secrets.

The live semantic control count is explicitly conditional on the selected
target: 18/18 rows satisfy the selected-target distance tolerance. Among the
17 rows with an explicit requested target, 17/17 preserve the
requested-to-selected identity and satisfy the corresponding instruction-level
joint criterion; one free scene-selection row is reported separately as 1/1
selected-target control and is N/A for instruction metrics. The robustness-edge
audit is detector-level boundary evidence, not a closed-loop or real-camera
benchmark.
