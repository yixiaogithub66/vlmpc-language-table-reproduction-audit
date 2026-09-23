# Data and Code Availability

The v1.0.8 revision artifact is provided as a portable, sanitized package alongside the manuscript. It is published as the GitHub release at:

https://github.com/yixiaogithub66/vlmpc-language-table-reproduction-audit

https://github.com/yixiaogithub66/vlmpc-language-table-reproduction-audit/releases/tag/v1.0.8

The package contains:

- the revised LaTeX manuscript and compiled PDF;
- the Python figure-generation, live-result import, and artifact-verification scripts;
- authoritative run-level CSV summaries for the fresh raw sweep, semantic suite, target-image matrix, event controls, visual-feedback test, and controlled semantic-fault audit;
- archived grounded-branch summaries and the 23/23 action-replacement record;
- a bounded root-cause factorization table pairing oracle versus visual feedback on six matched seeds and retaining the target-image selection failure;
- the detector-level robustness-edge CSV and four portable perturbation inputs;
- source snapshots with SHA-256 manifest entries and an explicit sanitized-main.py provenance note.

The package intentionally excludes API keys, private endpoint configuration, raw service transcripts, raw simulator videos, model checkpoints, and any non-portable local filesystem paths. The formal online language component uses the project's `CodexCLIClient` to launch local `codex exec -m gpt-5.5` calls under an isolated `CODEX_HOME`; prompts and staged image attachments are passed to the CLI, while the private `config.toml` is not published. The exact private runtime configuration is not part of the public artifact. The direct HTTP-compatible backend in the source tree was not used for the formal results.

The primary evidence files are:

- data/raw_controller_multiseed_runs_v9.csv
- data/semantic_mpc_live_runs_v9.csv
- data/threshold_sensitivity_v9.csv
- data/robustness_edge_audit_v9.csv
- supplement_v9_sanitized/data/revision_20260922/target_image_matrix_runs_v9.csv
- supplement_v9_sanitized/data/revision_20260922/event_requery_controls_v9.csv
- supplement_v9_sanitized/data/revision_20260922/visual_feedback_runs_v9.csv
- supplement_v9_sanitized/data/revision_20260922/event_fault_recovery_runs_v9.csv
- supplement_v9_sanitized/data/revision_20260922/root_cause_ablation_v9.csv
- supplement_v9_sanitized/data/revision_20260922/root_cause_ablation_v9.md
- scripts/derive_root_cause_ablation_v9.py
- supplement_v9_sanitized/data/revision_20260923/language_instruction_repeat_runs_v9.csv
- supplement_v9_sanitized/data/revision_20260923/language_instruction_repeat_aggregate_v9.csv
- supplement_v9_sanitized/data/revision_20260923/event_fault_recovery_codex_runs_v9.csv
- supplement_v9_sanitized/data/revision_20260923/event_fault_recovery_codex_aggregate_v9.csv

The scripts reproduce the reported aggregates and figures from the portable CSVs. Running the online experiments again requires the original simulator, local dependencies, the `codex` CLI, and an independently configured isolated `CODEX_HOME` profile for the GPT-5.5 CodexCLIClient path; those requirements are documented without publishing secrets.

The live semantic control count is explicitly conditional on the selected
target: 18/18 heterogeneous rows satisfy the selected-target distance
tolerance. The rows are reported by input/evaluation scope: 15/15 fixed-target
controls, 1/1 natural-language instruction joint success, 1/1 target-image
selected-target control, and 1/1 free scene-selection control. Only the
natural-language row contributes to instruction-level grounding metrics; the
target-image grounding claim comes from the independent nine-trial matrix
(8/9), not from the single semantic-suite target-image row. The robustness-edge
audit is detector-level boundary evidence, not a closed-loop or real-camera
benchmark.
