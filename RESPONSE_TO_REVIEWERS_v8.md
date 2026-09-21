# Response to the Co-chair and Reviewers

We thank the co-chair and three reviewers for their careful assessment. We revised the manuscript and public artifact around four principles: preserve the unsuccessful unmodified reproduction, separate privileged-feedback diagnostics from original VLMPC evidence, make every reported number traceable to one authoritative file, and state clearly which requested experiments remain future work. The corrected public artifact is available at https://github.com/yixiaogithub66/vlmpc-language-table-reproduction-audit, release v1.0.1.

## Co-chair

### Comment E.1

The manuscript still contains typos and grammatical issues requiring a careful proofread. The authors should address the issues one by one and provide point-by-point responses.

**Response:** We performed a complete language and consistency pass, repaired incomplete or compressed sentences, checked all cross-references, and unified the reported statistics. This letter now answers every actionable editor and reviewer point separately. The final LaTeX build has no undefined citations or references, and the public artifact includes an automated consistency check.

**Location:** Throughout the manuscript; public artifact, scripts/verify_artifact.py.

### Comment E.2

The distinction between privileged-feedback-assisted success and genuine original VLMPC reproduction should be highlighted more prominently in the abstract and introduction.

**Response:** We revised the Abstract and Introduction to state the negative unmodified results first, 0/4 controller-comparison successes and 0/8 ablation successes. We identify every positive controller result as a privileged-feedback diagnostic result. Table II records action authority and state access for every branch, and Table IV labels the positive branches as feedback-assisted diagnostics.

**Location:** Abstract, p. 1; Introduction, pp. 1-2; Table II, p. 5; Table IV, p. 6; Discussion, pp. 7-8; Conclusion, pp. 8-9.

## Reviewer 1

### Comment R1.1

Since traceability is a central contribution, please provide a clear availability statement and an accessible repository or supplementary-package reference. A short guide linking the main tables to the corresponding configurations, logs, and execution commands would make the reported audit easier to reproduce.

**Response:** We added a public repository, a fixed v1.0.1 release, a Data and Code Availability subsection, a reproduction guide, and an experiment-results index. The artifact contains one authoritative 18-run Semantic MPC file, regenerated threshold and condition statistics, sanitized revision CSVs, experiment drivers, exact method parameters, separate runtime-asset and source-snapshot manifests, and an automated verification script. Credentials, private endpoints, machine-local paths, raw service logs, and third-party model weights are excluded. End-to-end reruns therefore require independently obtained checkpoints and a separately configured compatible VLM backend.

**Location:** Data and Code Availability, p. 8; REPRODUCTION_GUIDE_v8.md; EXPERIMENT_RESULTS_INDEX_v8.md; DATA_CODE_AVAILABILITY_v8.md; scripts/verify_artifact.py.

### Comment R1.2

Please clarify the role of MPC in each diagnostic branch, particularly Semantic MPC, which is described as using state-feedback pushing without active raw action sampling.

**Response:** We now distinguish four branches. Unmodified VLMPC ranks video-prediction rollouts and executes the first raw action. Grounded original MPC retains the raw planner for traceability, but privileged feedback replaces its action at execution. Semantic MPC retains receding-horizon execution and logging but uses zero active raw video-prediction sampling, so the state-feedback push law determines the action. The event-control branch changes VLM query timing rather than the low-level optimizer.

**Location:** Method, pp. 3-4; Table II, p. 5.

### Comment R1.3

Reporting how often the grounded controller modifies or replaces the raw planner action would help readers understand the planner's contribution.

**Response:** We report the exact log-derived action authority. Every one of the 12 grounded runs contains 23 raw planner actions and 23 feedback overrides. The executed-action replacement rate is therefore 23/23, or 100 percent, in every run. The raw planner remains present for traceability, but it does not control the executed action in this branch.

**Location:** Grounded Original MPC, p. 3; Table II, p. 5; supplement_v8_sanitized/data/grounded_action_replacement_summary_v7.csv.

### Comment R1.4

Repeated explanations of the same methodological limitations could also be consolidated.

**Response:** We consolidated the detailed branch-responsibility explanation in Table II and removed two repeated Method statements that restated the same grounded-controller limitation. Short statements remain in the Abstract, Results, and Conclusion because they serve different functions: framing the claim, interpreting the evidence, and stating the final boundary.

**Location:** Method, pp. 3-4; Table II, p. 5; Abstract, p. 1; Conclusion, pp. 8-9.

### Comment R1.5

Please consider adding a few more target-image cases and repeated runs under matched task settings, with variability reported for each condition.

**Response:** We added a nine-run end-to-end matrix using red moon, blue cube, and yellow pentagon target images with seeds 45, 46, and 47. Semantic selection is correct in 8/9 runs. One yellow-pentagon run is already within the terminal threshold before acting and is separated from the active denominator. Joint semantic-plus-control success is 7/8 among active trials. Table X reports mean and sample SD for each image condition and retains the blue-cube seed-47 failure.

**Location:** Revision Target-Image End-to-End Matrix, pp. 7-8; Table X, p. 8; supplement_v8_sanitized/data/revision_20260919/target_image_matrix_runs_v8.csv and target_image_matrix_aggregate_v8.csv.

## Reviewer 2

### Comment R2.1

Some typos and incomplete grammatical sentences remain and a careful proofread is needed.

**Response:** We proofread the full manuscript, repaired incomplete sentences, standardized terminology, and checked the compiled nine-page PDF. The final build contains no undefined citations or references.

**Location:** Throughout the manuscript.

### Comment R2.2

The reported success rates are inconsistent across the manuscript; please unify the numbers.

**Response:** We use final world distance at or below 0.08 as the primary success rule throughout. The final Semantic MPC suite has one authoritative 18-run source. It gives mean final distance 0.064119, sample SD 0.015025, 3/18 successes at 0.05, and 18/18 at 0.08. We removed superseded Semantic MPC rows and the conflicting 5/18 table from the public artifact, regenerated the threshold table, and added a verification script that fails if the conflict reappears.

**Location:** Abstract, p. 1; Evaluation Setup, p. 2; Tables IV-V, p. 6; Discussion, pp. 7-8; Conclusion, pp. 8-9; data/semantic_mpc_authoritative_runs_v8.csv; data/threshold_sensitivity_v8.csv.

### Comment R2.3

The runs use very few seeds and some results show zero variance; reporting multiple seeds with mean plus or minus standard deviation would be more convincing.

**Response:** We retain seeds 42, 43, and 44 for the archived seed subset and add seeds 45, 46, and 47 for the target-image and semantic-fault experiments. Table V reports sample SD by Semantic MPC condition, and Table X reports sample SD by target-image condition. The grounded zero variance remains visible and is explained as an effect of the shared terminal feedback law and identical 23-step action replacement, not as evidence that raw-planner parameters are irrelevant.

**Location:** Tables IV-V, p. 6; Table X, p. 8; Feedback-Assisted Diagnostic Results, pp. 4-6.

### Comment R2.4

The paper could be strengthened by validating the controllers on a real robot and testing a broader set of tasks and instructions, since all results come from simulation with privileged feedback.

**Response:** We agree that real-robot and broader-task validation would strengthen external validity. These experiments were not available for this revision, so we do not claim they were performed. We identify the current study as a local Language-Table simulator audit and list real-robot, broader-task, and visual-only feedback evaluation as future work.

**Location:** Evidence Boundary and Limitations and Future Work, p. 8.

### Comment R2.5

The analysis could go deeper by isolating the root causes through targeted ablations.

**Response:** We narrowed the causal language rather than presenting symptoms as isolated root causes. Table XI labels tracker jumps, parameter non-rescue, and feedback sensitivity as non-exclusive observations. The strongest mechanism-level result is reported directly: privileged feedback replaces 100 percent of grounded raw actions. The retained blue-cube target-image failure further shows that a semantic selection error can dominate the control outcome. A complete root-cause isolation study remains future work.

**Location:** Table II, p. 5; Observed Failure Symptoms and Table XI, p. 8; Evidence Boundary, p. 8.

### Comment R2.6

The re-query experiment could be redesigned so its benefit is actually measurable.

**Response:** We added a paired controlled semantic-fault audit. For each of seeds 45, 46, and 47, the correct red-moon target is deliberately replaced by blue cube. The control retains the wrong target. The treatment performs one explicitly labeled forced re-query at step 3 and is evaluated against the independently recorded true target. The treatment repairs the semantic target in 3/3 runs and reaches the true-target threshold in 2/3, versus 0/3 controls. Seed 47 ends at 0.0808 and is correctly counted as a failure. This establishes repair under an injected semantic fault, but not causal benefit for the natural stagnation trigger. Fresh matched natural-event controls still have identical final distances by seed.

**Location:** Event-Triggered VLM Re-query, p. 4; Tables VII-VIII, p. 6; Limitations and Future Work, p. 8; supplement_v8_sanitized/data/revision_20260919/event_fault_recovery_runs_v8.csv.

## Reviewer 3

### Comment R3.1

The distinction between privileged feedback assisted success and genuine original VLMPC reproduction should be highlighted more prominently in abstract and introduction, to prevent readers from misinterpreting diagnostic results as original method reproduction.

**Response:** We state the unmodified failures before the diagnostic successes in both the Abstract and Introduction. We identify the positive branches as privileged-feedback diagnostics, report action authority and state access in Table II, and repeat the evidence boundary when interpreting the results. We never present the 4/4, 8/8, or 18/18 diagnostic numbers as successful unmodified VLMPC reproduction.

**Location:** Abstract, p. 1; Introduction, pp. 1-2; Table II, p. 5; Table IV, p. 6; Discussion, pp. 7-8; Conclusion, pp. 8-9.

### Comment R3.2

Specify concrete metrics and implementation roadmap for future visual-state-estimator research.

**Response:** We specify a first visual-state-estimator milestone that predicts target centroid, end-effector pose, target visibility or confidence, and goal-relative distance from RGB observations. Planned estimator metrics are centroid error in pixels and normalized table coordinates, end-effector position error, goal-distance mean absolute error, visibility F1, and one-step temporal consistency. Matched visual-only and oracle-feedback trials will report final distance, success at 0.05 and 0.08, action-replacement rate, recovery latency after an induced tracking jump, and runtime per step. The implementation path is synchronized RGB/state export, detector-plus-tracker calibration with held-out seeds and perturbations, interface replacement, and confidence-gated matched evaluation.

**Location:** Limitations and Future Work, p. 8.

### Comment R3.3

Check out errors in the manuscript.

**Response:** We conducted a manuscript-wide language, numerical, cross-reference, and artifact-consistency audit. We corrected grammar, unified the success statistics, removed inaccessible package paths and an empty CSV, separated executed-source from public-snapshot hashes, and verified the compiled PDF. The final LaTeX build has no undefined citations or references, and python scripts/verify_artifact.py checks the public numeric and hash claims.

**Location:** Throughout the manuscript; Data and Code Availability, p. 8; public artifact, scripts/verify_artifact.py and CHANGELOG.md.
