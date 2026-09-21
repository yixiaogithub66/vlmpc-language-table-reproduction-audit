# Reproduction Guide v8

This guide accompanies the revised manuscript and defines the artifact-to-table mapping, environment assumptions, and commands used for the revision experiments. The public artifact is available at https://github.com/yixiaogithub66/vlmpc-language-table-reproduction-audit (release v1.0.3). Commands use paths relative to the source snapshot and symbolic local paths for runtime assets that are not redistributed.

## Scope and Evidence Boundary

The paper reports two separate evidence groups:

- Unmodified reproduction: the video-prediction MPC chain without final-action simulator-state feedback. The archived controller comparison is 0/4 and the parameter ablation is 0/8 at d_world_final <= 0.08.
- Feedback-assisted diagnostics: grounded original MPC and semantic MPC use privileged simulator state for execution. Their execution success is not unmodified VLMPC reproduction success.

The revision adds:

- A nine-run target-image end-to-end matrix over red moon, blue cube, and yellow pentagon, with seeds 45, 46, and 47. Semantic selection is 8/9; joint active success is 7/8 after excluding one pre-satisfied run.
- A paired semantic-fault audit over seeds 45, 46, and 47. A wrong initial target is injected deliberately. The synthetic re-query treatment repairs the semantic target in 3/3 runs and reaches the independent true-target threshold in 2/3, versus 0/3 without re-query.
- Fresh matched natural-event controls. Event-enabled and no-event rows have identical final distances by seed; the natural trigger fires in 2/3 fresh event-enabled rows. No natural causal recovery claim is made.

## Directory Map

From this manuscript directory:

    main.tex                         revised manuscript
    refs.bib                         bibliography
    data/                            authoritative and archived sanitized evidence
    supplement_v8_sanitized/data/    submission-safe derived summaries
    supplement_v8_sanitized/source/  source snapshot and environment template
    figures/                         manuscript figures

The public artifact contains a reviewer-facing source snapshot under supplement_v8_sanitized/source/, including main.py, vlmpc.py, vlm_client.py, and the revision experiment drivers. This snapshot supports inspection and static validation. End-to-end execution also requires the third-party simulator dependencies and checkpoints listed below. Never add a local .env, virtual environment, raw service logs, private gateway configuration, or model weights to the repository.

## Environment

- Windows PowerShell
- Python 3.12.x (local .venv312)
- Language-Table simulator and archived detector, tracker, and video-prediction checkpoints
- An OpenAI-compatible VLM backend for semantic and event experiments

Set credentials through an environment variable only. The repository must contain a redacted environment template, never a real environment file:

    $env:VLMPC_OPENAI_API_KEY = "<private-key-set-outside-the-package>"
    $env:VLMPC_OPENAI_BASE_URL = "<private-endpoint-set-outside-the-package>"

The paper records the model alias gpt-5.5 and responses wire protocol because they affect reproducibility. The gateway address and API key are intentionally omitted.

## Static Checks

Run the package-level consistency audit from the repository root:

    python scripts/verify_artifact.py

Run source syntax checks from supplement_v8_sanitized/source:

    python -m py_compile main.py vlmpc.py vlm_client.py stage_experiments\run_opening_report_complete.py stage_experiments\run_event_requery_controls.py stage_experiments\run_revision_target_image_matrix.py stage_experiments\run_revision_event_recovery_audit.py
    python stage_experiments\run_revision_target_image_matrix.py --help
    python stage_experiments\run_revision_event_recovery_audit.py --help

## Revision Target-Image Matrix

The target-image driver uses the VLM selector explicitly and runs seeds 45, 46, and 47. Supply local checkpoint paths and the private endpoint through environment variables or command-line arguments outside the package:

    python stage_experiments\run_revision_target_image_matrix.py --checkpoint_file "<PATH>\dmvfn_221.pkl" --det_path "<PATH>\detector_checkpoint.pt" --tracker_config "<PATH>\pysot-master\experiments\siamrpn_r50_l234_dwxcorr\config.yaml" --tracker_model "<PATH>\model.pth" --vlm_backend openai --openai_base_url $env:VLMPC_OPENAI_BASE_URL --openai_wire_api responses --openai_model gpt-5.5 --openai_api_key_env VLMPC_OPENAI_API_KEY --target_image_selector vlm --seeds 45 46 47 --success_distance_world 0.08 --continue_on_error

The submission-safe output is:

    supplement_v8_sanitized/data/revision_20260919/target_image_matrix_runs_v8.csv
    supplement_v8_sanitized/data/revision_20260919/target_image_matrix_aggregate_v8.csv

The aggregate uses sample standard deviation. A run with pre_satisfied=True is not counted in the active-control denominator.

## Controlled Semantic-Fault Audit

This driver deliberately injects a wrong initial target and forces one explicitly labeled synthetic re-query at step 3 in the treatment. It is not a natural-event benchmark:

    python stage_experiments\run_revision_event_recovery_audit.py --checkpoint_file "<PATH>\dmvfn_221.pkl" --det_path "<PATH>\detector_checkpoint.pt" --tracker_config "<PATH>\pysot-master\experiments\siamrpn_r50_l234_dwxcorr\config.yaml" --tracker_model "<PATH>\model.pth" --openai_base_url $env:VLMPC_OPENAI_BASE_URL --openai_wire_api responses --openai_model gpt-5.5 --openai_api_key_env VLMPC_OPENAI_API_KEY --true_target "red moon" --fault_target "blue cube" --force_step 3 --seeds 45 46 47 --continue_on_error

The submission-safe output is:

    supplement_v8_sanitized/data/revision_20260919/event_fault_recovery_runs_v8.csv
    supplement_v8_sanitized/data/revision_20260919/event_fault_recovery_aggregate_v8.csv

Success is measured against the independent true target. Synthetic re-query counts and natural event counts are kept separate.

## Matched Natural-Event Controls

The existing control driver remains the source for the no-event/event comparison. Use strict no-cache mode and matched seeds. Do not combine forced queries with a causal comparison. The revision run used seeds 45, 46, and 47; its sanitized digest is in:

    supplement_v8_sanitized/data/revision_20260919/event_matched_controls_revision_v8.csv

The archived nine-row control file is retained for provenance. The revision controls show identical final distances by seed and therefore do not support a natural recovery-benefit claim.

## Artifact Mapping

| Paper claim | Submission-safe artifact |
| --- | --- |
| Unmodified 0/4 and 0/8 | data/archived_nonsemantic_branch_runs_v8.csv and data/threshold_sensitivity_v8.csv |
| Authoritative 18-row Semantic MPC suite | data/semantic_mpc_authoritative_runs_v8.csv |
| Semantic MPC mean, sample SD, and threshold counts | supplement_v8_sanitized/data/semantic_mpc_condition_statistics_v8.csv and data/threshold_sensitivity_v8.csv |
| 23/23 grounded action replacement | supplement_v8_sanitized/data/grounded_action_replacement_summary_v8.csv |
| Archived 4/4 target-image semantic audit | supplement_v8_sanitized/data/target_image_claim_boundary_v8.csv |
| Revision target-image matrix | supplement_v8_sanitized/data/revision_20260919/target_image_matrix_runs_v8.csv and target_image_matrix_aggregate_v8.csv |
| Revision semantic-fault audit | supplement_v8_sanitized/data/revision_20260919/event_fault_recovery_runs_v8.csv and event_fault_recovery_aggregate_v8.csv |
| Revision natural-event controls | supplement_v8_sanitized/data/revision_20260919/event_matched_controls_revision_v8.csv |
| Parameters and file hashes | data/method_parameter_table_v2.csv, data/runtime_asset_manifest_v8.csv, supplement_v8_sanitized/data/code_manifest_v8.csv, and supplement_v8_sanitized/SOURCE_SNAPSHOT_PROVENANCE_v8.md |

All means and standard deviations in the revised tables use the sample SD convention. Superseded Semantic MPC rows and the conflicting 5/18 threshold table are excluded from v1.0.3. The package-level verification script fails if those files reappear.

## Reproducibility Limits

The current evidence is a local simulator audit, not a real-robot or broad-task benchmark. The semantic and event branches depend on an external VLM service, and the required model weights are not redistributed in this package. The included summaries are sufficient to audit the reported aggregates. A complete rerun requires independently obtained runtime assets and a separately configured compatible VLM backend. The manuscript reports exact seeds, thresholds, action counts, parameter values, cache status, and file hashes while keeping the availability statement honest.
