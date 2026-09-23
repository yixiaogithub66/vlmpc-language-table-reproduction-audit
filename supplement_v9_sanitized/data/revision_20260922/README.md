# Revision Experiment Outputs

These CSVs are the sanitized outputs of the 2026-09-22 revision experiment suite.

- semantic_mpc_condition_statistics_v9.csv: condition-level aggregates for the 18-run semantic suite, separating 15 fixed-target controls, the single natural-language instruction row, the single target-image interface row, and the single free scene-selection row. Only the natural-language row contributes to instruction-level metrics.
- target_image_selection_audit_v9.csv: live target-image selection audit plus the explicitly labelled archived comparator.
- target_image_matrix_runs_v9.csv and target_image_matrix_aggregate_v9.csv: nine active target-image trials and aggregates.
- event_requery_controls_v9.csv and event_requery_statistics_v9.csv: matched no-event, event-enabled, and forced-scene controls.
- event_fault_recovery_runs_v9.csv and event_fault_recovery_aggregate_v9.csv: controlled injected semantic-fault intervention.
- visual_feedback_runs_v9.csv and visual_feedback_statistics_v9.csv: detector/tracker visual-feedback boundary test.
- semantic_oracle_feedback_runs_v9.csv: six fixed-target oracle-state repeats paired by seed with the visual-feedback boundary runs.
- root_cause_ablation_v9.csv and root_cause_ablation_v9.md: derived factor-isolation table for planner authority, feedback source, target grounding, and raw-planner tuning.

The root-cause table is descriptive and retains protocol labels. Archived grounded rows are not pooled with the fresh raw sweep; the paired oracle/visual comparison is the strongest feedback-source isolation in this package.

The event-control files separate natural event counts from explicitly forced audit events. The fault-recovery files are not evidence of natural-event causal benefit.
