# Revision Experiment Outputs

These CSVs are the sanitized outputs of the 2026-09-22 revision experiment suite.

- semantic_mpc_condition_statistics_v9.csv: condition-level aggregates for the 18-run semantic suite, including 17/18 request-selection matches and instruction-level joint successes overall.
- target_image_selection_audit_v9.csv: live target-image selection audit plus the explicitly labelled archived comparator.
- target_image_matrix_runs_v9.csv and target_image_matrix_aggregate_v9.csv: nine active target-image trials and aggregates.
- event_requery_controls_v9.csv and event_requery_statistics_v9.csv: matched no-event, event-enabled, and forced-scene controls.
- event_fault_recovery_runs_v9.csv and event_fault_recovery_aggregate_v9.csv: controlled injected semantic-fault intervention.
- visual_feedback_runs_v9.csv and visual_feedback_statistics_v9.csv: detector/tracker visual-feedback boundary test.

The event-control files separate natural event counts from explicitly forced audit events. The fault-recovery files are not evidence of natural-event causal benefit.
