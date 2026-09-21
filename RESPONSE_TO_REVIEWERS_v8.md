# Response to Reviewers v8

We thank the chair and reviewers for identifying weaknesses in reproducibility, controller description, statistical reporting, and claim boundaries. We revised the manuscript around the archived evidence and added two focused experiments using the same VLM configuration and strict no-cache execution. We do not convert privileged-feedback diagnostics into claims about successful unmodified VLMPC reproduction.

## Co-chair

### Comment: Correct language and make the evidence boundary explicit.

**Response:** We proofread the manuscript, repaired incomplete or compressed sentences, unified the primary success definition as $d_{\mathrm{world}}^{\mathrm{final}}\leq0.08$, and revised the Abstract, Introduction, Evaluation Setup, Results, Discussion, and Conclusion. The manuscript now states directly that the unmodified video-prediction MPC branch is 0/4 and 0/8, whereas the positive execution results come from privileged-feedback diagnostic branches. The new target-image and semantic-fault results are also labeled as diagnostic evidence with their failure cases retained.

**Location:** main.tex, Abstract, Introduction, Sec. III, Sec. V, and Conclusion.

## Reviewer 1

### Comment: Improve reproducibility and provide an availability statement.

**Response:** We updated the availability statement and v8 reproduction guide and created the public artifact repository at https://github.com/yixiaogithub66/vlmpc-language-table-reproduction-audit (release v1.0.0). It includes sanitized per-run and aggregate CSVs for the nine-run target-image matrix and paired semantic-fault audit, a source snapshot containing the two new audit drivers, exact parameter references, and updated code hashes. The guide maps every headline result to a submission-safe artifact and command. API credentials, private gateway addresses, absolute local paths, virtual environments, raw service logs, and third-party model weights are excluded. The reported aggregates can be audited from the included summaries; end-to-end reruns require independently obtained checkpoints and a separately configured compatible VLM backend.

**Location:** main.tex, Data and Code Availability; REPRODUCTION_GUIDE_v8.md; DATA_CODE_AVAILABILITY_v8.md; supplement_v8_sanitized/.

### Comment: Clarify the role of MPC in each branch.

**Response:** Table branchroles distinguishes: (i) unmodified VLMPC, where candidate video-prediction rollouts are cost-ranked and the raw action is executed; (ii) grounded original MPC, where raw calls are retained for traceability but privileged feedback determines execution; (iii) semantic MPC, where the outer loop is receding-horizon and logged but the final semantic push has zero active raw-sampling budget; and (iv) event controls, where query timing is tested rather than a new low-level optimizer being claimed.

**Location:** main.tex, Sec. III, Table branchroles.

### Comment: Report how often the grounded controller modifies or replaces raw planner actions.

**Response:** We report the exact log-derived result: all 12 grounded runs contain 23 raw planner actions and 23 feedback overrides, so the executed-action replacement rate is 23/23 (100%) in every run. The raw planner remains in the loop for traceability and comparison, but it is not the executed-action authority in that branch.

**Location:** main.tex, Sec. III and Table branchroles; supplement_v8_sanitized/data/grounded_action_replacement_summary_v7.csv.

### Comment: Add more target-image cases and repeated matched runs.

**Response:** We performed a focused end-to-end matrix with three target-image cases (red moon, blue cube, and yellow pentagon) and seeds 45, 46, and 47, for nine runs under the same model and strict no-cache policy. VLM semantic selection is correct in 8/9 runs. We report active control separately: one yellow-pentagon run was already within the terminal threshold before acting, so it is excluded from the active denominator; among the eight active trials, joint semantic-plus-control success is 7/8. The blue-cube seed-47 semantic error is retained and ends at distance 0.3644. We therefore strengthen the previous one-run end-to-end evidence without presenting the small matrix as a broad visual benchmark.

**Location:** main.tex, Sec. V, Revision Target-Image End-to-End Matrix, Table targetmatrix; supplement_v8_sanitized/data/revision_20260919/target_image_matrix_runs_v8.csv; target_image_matrix_aggregate_v8.csv.

## Reviewer 2

### Comment: Fix typos, incomplete grammar, and inconsistent success rates.

**Response:** We performed another full pass over the manuscript and made the threshold convention explicit. Every primary success count uses the same $d_{\mathrm{world}}^{\mathrm{final}}\leq0.08$ rule. We now distinguish terminal threshold success, active control success, joint active success, and pre-satisfied runs. The stricter 0.05 audit remains 3/18 for the archived semantic suite, while the unmodified branches remain 0/4 and 0/8.

**Location:** Abstract, Evaluation Setup, diagnostic tables, target-image matrix, Discussion, and Conclusion.

### Comment: Few seeds and zero variance weaken the results.

**Response:** We retain the archived seed set 42/43/44 and add independent revision runs at seeds 45/46/47 for the target-image matrix and semantic-fault audit. Means and sample SDs are reported in the new aggregate files. The grounded zero variance remains visible and is explained as a consequence of the shared terminal feedback law and identical 23-step execution, not as evidence that raw planner parameters are irrelevant.

**Location:** main.tex, Evaluation Setup, Table variance, Table targetmatrix, Table eventfault; supplement_v8_sanitized/data/revision_20260919/.

### Comment: Add a real robot or broader task evaluation.

**Response:** We agree that this would strengthen the study, but no real-robot or broad-task experiment was available for this revision. The manuscript explicitly identifies the current package as a local Language-Table simulator audit and lists real-robot and broader-task evaluation as future work. We do not claim those experiments were performed.

### Comment: Add deeper root-cause ablations.

**Response:** We retain the symptom taxonomy and narrow its interpretation: tracker jumps, parameter non-rescue, and feedback sensitivity are observations, not single-cause proof. The branch table makes the strongest actionable mechanism visible: in the grounded diagnostic branch, feedback replaces 100% of raw actions. The new blue-cube target-image failure is also retained as direct evidence that semantic errors can dominate the control outcome.

### Comment: Redesign event re-query so its benefit is measurable.

**Response:** We added a paired controlled semantic-fault audit. For each of seeds 45/46/47, the correct red-moon target is deliberately replaced by blue cube. The no-requery control keeps the wrong target; the treatment forces one explicitly labeled synthetic re-query at step 3 and is evaluated against the independent true target. Semantic repair is 3/3 and true-target threshold success is 2/3, versus 0/3 in the control. The treatment seed 47 ends at 0.0808, so it is not counted as a success. This experiment demonstrates repair of a known semantic corruption, but it does not establish natural stagnation-detector sensitivity or causal benefit in ordinary successful runs. Fresh matched natural-event controls still have identical no-event/event final distances by seed. We therefore report the stronger controlled result with its boundary instead of claiming an unproven natural-event improvement.

**Location:** main.tex, Sec. III, Sec. V, Table eventfault, and Limitations and Future Work; supplement_v8_sanitized/data/revision_20260919/event_fault_recovery_runs_v8.csv; event_fault_recovery_aggregate_v8.csv.

## Reviewer 3

### Comment: Distinguish privileged feedback from genuine original VLMPC more prominently.

**Response:** The distinction is stated in the Abstract, Introduction, branch-responsibility table, diagnostic-result caption, Discussion, and Conclusion. The headline positive numbers are labeled execution or semantic-selection results for diagnostic branches, never as successful unmodified VLMPC reproduction.

### Comment: Give a concrete visual-state-estimator roadmap.

**Response:** We retain and sharpen the measurable roadmap. The first estimator milestone predicts target centroid, end-effector pose, visibility/confidence, and goal-relative distance from RGB. Planned metrics are centroid error in pixels and normalized table coordinates, end-effector error, goal-distance MAE, visibility F1, and one-step temporal consistency. Matched visual/oracle trials will report final distance, success at 0.05/0.08, action-replacement rate, recovery latency after induced tracking jumps, and per-step runtime. The implementation path is synchronized RGB/state export, detector-plus-tracker calibration with held-out seeds and perturbations, interface replacement, then confidence-gated matched evaluation.

**Location:** main.tex, Limitations and Future Work.
