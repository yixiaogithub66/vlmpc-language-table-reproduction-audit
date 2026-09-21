# Experiment Results Index v8

This index records the latest revision experiments and the paper artifacts that summarize them. Raw logs remain in the experiment project; the submission package contains sanitized derived tables only.

## Latest Revision Runs

| Experiment | Raw result directory | Main result |
| --- | --- | --- |
| Target-image end-to-end matrix | 01_实验源码_日志与模型/VLMPC/vlmpc-master/vlmpc-master/stage_experiments/revision_target_image_matrix_final/20260918_234725 | 9 runs; semantic selection 8/9; joint active success 7/8; one pre-satisfied run |
| Controlled semantic-fault audit | 01_实验源码_日志与模型/VLMPC/vlmpc-master/vlmpc-master/stage_experiments/revision_event_recovery_audit_final/20260918_234658 | forced semantic repair 3/3; true-target success 2/3; no-requery control 0/3 |
| Fresh matched natural-event controls | 01_实验源码_日志与模型/VLMPC/vlmpc-master/vlmpc-master/stage_experiments/event_requery_controls/revision_20260918/20260918_232627 | event trigger fires in 2/3 fresh event-enabled rows; final distances identical by matched seed |

## Submission-Safe Summaries

The sanitized copies used by the paper are under:

    00_最新成果_论文提交/paper_rewriting_output/final_paper_ieeetran_v8_20260919_1/supplement_v8_sanitized/data/revision_20260919/

Files:

    target_image_matrix_runs_v8.csv
    target_image_matrix_aggregate_v8.csv
    event_fault_recovery_runs_v8.csv
    event_fault_recovery_aggregate_v8.csv
    event_matched_controls_revision_v8.csv
    revision_experiment_manifest_v8.json

## Paper Package

The revised manuscript and response package are in:

    00_最新成果_论文提交/paper_rewriting_output/final_paper_ieeetran_v8_20260919_1/

Start with:

    main.pdf
    RESPONSE_TO_REVIEWERS_v8.md
    REPRODUCTION_GUIDE_v8.md
    DATA_CODE_AVAILABILITY_v8.md
    FINAL_MANIFEST_v8.md

The raw experiment logs may contain local paths and private runtime metadata; do not attach them to a submission. The paper intentionally makes no claim that the natural event trigger provides causal recovery benefit.

