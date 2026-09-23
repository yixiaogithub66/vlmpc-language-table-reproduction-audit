# Experiment Results Index v1.0.8

All primary numbers in the revised manuscript are traceable to the files below. The project threshold is final target world distance <= 0.08. The 0.05 threshold is reported as an auxiliary stricter threshold.

## Fresh raw reproduction

Source: data/raw_controller_multiseed_runs_v9.csv

- Four variants: baseline, improved, literature, and literature-v2.
- Seeds 45, 46, 47, and 48; four runs per variant; 16 runs total.
- Success: 0/16 at 0.05, 0/16 at 0.08, and 0/16 at 0.10.
- Aggregate final distance: mean 0.324472, sample SD 0.108465, range 0.163--0.436.
- This is the primary reproduction result. It is not pooled with the archived parameter ablation.

## Archived non-semantic comparisons

Source: data/archived_nonsemantic_branch_runs_v8.csv

These rows preserve earlier grounded and parameter-ablation diagnostics. They are explicitly archived and are not presented as fresh independent seeds or as raw-MPC successes. The grounded rows are accompanied by supplement_v9_sanitized/data/grounded_action_replacement_summary_v9.csv.

## Live semantic suite

Sources: data/semantic_mpc_live_runs_v9.csv and supplement_v9_sanitized/data/revision_20260922/semantic_mpc_condition_statistics_v9.csv

- 18 heterogeneous diagnostic runs, not 18 independent random seeds.
- Overall selected-target control distance: mean 0.064119, sample SD 0.015025; 3/18 at 0.05 and 18/18 at 0.08.
- Seed-only subset: n=3 for seeds 42--44; it is reported separately from the heterogeneous aggregate.
- The selected target is the target used for the corresponding diagnostic condition. The run-level scopes are 15 fixed-target controls (15/15), one natural-language instruction (1/1 request-selection match and instruction-level joint success), one target-image interface row (1/1 selected-target control, not an independent image-grounding test), and one free scene-selection row (1/1 selected-target control). Only the natural-language row is instruction-evaluable. The 18/18 value is therefore not relabeled as end-to-end instruction or target-image grounding success.

## Robustness-edge boundary audit

Sources: data/robustness_edge_audit_v9.csv and supplement_v9_sanitized/data/robustness_edge_audit/

- Four detector-level cases retain the red-moon detection under the tested occlusion, viewpoint-proxy, and brightness-shift inputs.
- Three unsupported target names are safely rejected by canonicalization.
- The four input images are included in the supplement. This is a small detector-level boundary audit, not a closed-loop robustness benchmark or real-camera validation.

## Target-image evidence

Sources: supplement_v9_sanitized/data/revision_20260922/target_image_selection_audit_v9.csv and target_image_matrix_runs_v9.csv

- Selection audit: 4/4 in the audit table, consisting of three live crop cases and one archived full-frame comparator.
- End-to-end matrix: three target objects x seeds 42--44, 9 active trials, zero pre-satisfied trials.
- Semantic selection: 8/9; active control: 8/9; joint success: 8/9.
- Overall final distance: mean 0.095024, sample SD 0.093199.
- Yellow-pentagon seed 42 is retained as a negative case: the selector chose a yellow star and the requested target remained at distance 0.338607.

## Event controls

Source: supplement_v9_sanitized/data/revision_20260922/event_requery_controls_v9.csv

- Three matched no-event rows, three matched event-enabled rows, and three forced-scene audit rows.
- Natural re-query: 0/3 no-event and 3/3 event-enabled.
- Cache hits: 0 across all nine rows.
- Matched no-event and event-enabled final distances are identical seed by seed.
- Semantic event detector parameters: window 4; minimum progress 0.002 in world-distance units.
- Forced-scene rows include the explicitly forced audit re-query and a natural event; they are not pooled with the matched natural-event comparison.

The original three-seed semantic-fault audit remains archived in event_fault_recovery_runs_v9.csv. The fresh CodexCLIClient six-seed audit is in supplement_v9_sanitized/data/revision_20260923/event_fault_recovery_codex_runs_v9.csv: treatment repairs the injected semantic state in 6/6 and reaches the independent true target in 5/6; the no-requery control reaches 0/6. This is an intervention audit, not evidence of natural-event causal benefit.

## Visual-feedback boundary

Source: supplement_v9_sanitized/data/revision_20260922/visual_feedback_runs_v9.csv

- Six seeds, detector/tracker feedback, no simulator-state accessor.
- Success: 0/6.
- Final distance: mean 0.316042, sample SD 0.143929.

## Root-cause factorization

Sources: `supplement_v9_sanitized/data/revision_20260922/root_cause_ablation_v9.csv` and `root_cause_ablation_v9.md`

- Raw planner tuning remains negative (0/8 archived parameter settings; fresh raw anchor 0/16).
- The archived grounded branch replaces 23/23 raw actions in each of 12 diagnostic rows, so its positive outcome cannot be attributed to raw planner authority.
- A matched fixed-target feedback-source comparison uses identical semantic-controller settings and seeds 45--50: oracle state succeeds in 6/6, visual detector/tracker feedback in 0/6; visual minus oracle final-distance gap is 0.254801 +/- 0.145339 (sample SD), with all six paired gaps positive.
- The independent target-image matrix retains 8/9 joint active successes, with one target-selection error. These are bounded factor-isolating diagnostics, not an exhaustive causal decomposition.
- The 2026-09-23 CodexCLIClient language-repeat audit adds three independent instructions x three seeds: 9/9 target-selection matches and 9/9 joint controls under strict no-cache (`supplement_v9_sanitized/data/revision_20260923/language_instruction_repeat_aggregate_v9.csv`).

## Reproduction path

Use scripts/import_live_results_v9.py to refresh the portable summaries from a local experiment-output root, scripts/plot_paper_figures.py to regenerate figures, and scripts/verify_artifact.py to validate the final package.
