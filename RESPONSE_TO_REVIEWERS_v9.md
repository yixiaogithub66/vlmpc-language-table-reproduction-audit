# Response to the Co-chair and Reviewers

We thank the co-chair and the three reviewers for their careful assessment. We revised the manuscript and evidence package around four principles: keep the fresh unsuccessful raw reproduction visible, separate privileged-feedback diagnostics from genuine original VLMPC evidence, make every reported number traceable to one authoritative file, and state clearly which requested validations remain outside the current study. The v1.0.6 package contains the revised manuscript, regenerated figures, sanitized run-level data, the robustness-edge CSV with portable inputs, source manifests, and an automated consistency check. The exact public artifact is bound to the immutable release https://github.com/yixiaogithub66/vlmpc-language-table-reproduction-audit/releases/tag/v1.0.6.

## Co-chair

### Comment E.1: Careful proofread and point-by-point response

**Response:** We performed a manuscript-wide language, numerical, cross-reference, and package-consistency pass. We repaired incomplete sentences, standardized terminology, unified the success rule, and added this separate response for every actionable editor and reviewer point. The final LaTeX build was checked for undefined citations and references, and `scripts/verify_artifact.py` checks the portable numeric, figure, path, and source-hash claims.

**Location:** Throughout the manuscript; `REPRODUCTION_GUIDE_v9.md`; `scripts/verify_artifact.py`.

### Comment E.2: Distinguish privileged-feedback success from genuine original VLMPC reproduction

**Response:** The Abstract and Introduction now report the fresh raw result first: 0/16 successes for four raw controller variants across seeds 45--48, with no privileged final-action state feedback. Every positive result is labelled as an oracle-feedback diagnostic or as a separate semantic/interface audit. The branch-responsibility table records state access and executed-action authority. In particular, the grounded branch replaces 23/23 raw planner actions in all 12 archived diagnostic runs, Semantic MPC uses no active raw video-prediction sampling, and the visual-feedback branch is tested without simulator-state access and obtains 0/6. The manuscript therefore does not present 4/4, 8/8, or 18/18 as successful unmodified VLMPC reproduction.

**Location:** Abstract (p. 1); Introduction (pp. 1--2); Table II (p. 5); Table IV (p. 6); Discussion (pp. 7--8); Conclusion (p. 8).

## Reviewer 1

### Comment R1.1: Availability statement, repository, and table-to-artifact traceability

**Response:** We added a Data and Code Availability statement, an experiment-results index, a reproduction guide, a complete final manifest, portable run-level CSVs, regenerated figure sources, and an automated verifier. The fresh raw sweep is in `data/raw_controller_multiseed_runs_v9.csv`; the live semantic suite is in `data/semantic_mpc_live_runs_v9.csv`; target-image, event, fault-audit, visual-feedback, and robustness-edge rows are in the package data directories, with the four robustness input images bundled under `supplement_v9_sanitized/data/robustness_edge_audit/`. The guide links the main experiment groups to their input conditions, commands, and aggregate files. The package excludes credentials, private endpoint configuration, raw online transcripts, simulator videos, checkpoints, and non-portable local paths. It is therefore a traceable sanitized evidence package rather than a claim of turnkey offline reproduction of an external VLM backend. The citation file and manuscript now point to the exact immutable v1.0.6 release.

**Location:** Data and Code Availability (p. 8); `EXPERIMENT_RESULTS_INDEX_v9.md`; `REPRODUCTION_GUIDE_v9.md`; `FINAL_MANIFEST_v9.md`; `scripts/verify_artifact.py`.

### Comment R1.2: Clarify the role of MPC in each diagnostic branch

**Response:** We now distinguish the branches explicitly. Unmodified VLMPC samples and ranks raw video-prediction action sequences and executes the first raw action. Grounded original MPC retains that planner for traceability, but privileged state feedback replaces the action at execution. Semantic MPC performs semantic target selection and receding-horizon logging, but uses N_raw = 0 active raw video-prediction samples; its state-feedback push law determines the executed action. Visual feedback replaces the simulator-state accessor with the detector/tracker path. Event controls alter VLM query timing and do not constitute a new low-level optimizer.

**Location:** Method (pp. 3--4); Table II (p. 5).

### Comment R1.3: Report how often the grounded controller replaces raw planner actions

**Response:** The log-derived record is now stated directly. All 12 grounded diagnostic runs contain 23 raw planner actions and 23 privileged-feedback overrides. The replacement rate is therefore 23/23, or 100 percent, in every run. The raw planner remains in the trace, but it does not determine the executed action in this branch.

**Location:** Method (p. 3); Diagnostic Results (p. 6); Table IV (p. 6); `supplement_v9_sanitized/data/grounded_action_replacement_summary_v9.csv`.

### Comment R1.4: Consolidate repeated methodological limitations

**Response:** We consolidated the detailed responsibility and state-access explanation in Table II and kept only short context-specific statements elsewhere. The Abstract frames the claim boundary, the Results interpret the measurements, and the Conclusion states the final evidence boundary. These are intentionally different functions rather than repeated copies of the same paragraph.

**Location:** Method (pp. 3--4); Table II (p. 5); Abstract (p. 1); Results (pp. 5--7); Conclusion (p. 8).

### Comment R1.5: Add target-image cases and matched repeated runs with variability

**Response:** We added a fresh nine-trial target-image end-to-end matrix covering red moon, blue cube, and yellow pentagon targets with seeds 42--44. No trial is pre-satisfied before active control. Semantic selection is correct in 8/9 trials, active control is successful in 8/9, and joint semantic-plus-control success is 8/9. The condition means and sample SDs are reported: red moon 0.0587 +/- 0.0233, blue cube 0.0623 +/- 0.0249, yellow pentagon 0.1640 +/- 0.1512, and all trials 0.0950 +/- 0.0932. The yellow-pentagon seed-42 selection error is retained as a negative case: the selector chose a yellow star and the requested object remained at distance 0.3386.

**Location:** Target-Image Selection Audit (Table IX, p. 7); End-to-End Matrix (Table X, p. 8); `supplement_v9_sanitized/data/revision_20260922/target_image_matrix_runs_v9.csv` and `target_image_matrix_aggregate_v9.csv`.

## Reviewer 2

### Comment R2.1: Typos and incomplete grammatical sentences

**Response:** We proofread the full manuscript and synchronized terminology across the text, tables, captions, data filenames, and response letter. The compiled PDF was checked after the v1.0.6 figures and tables were regenerated. The package verifier also rejects empty portable artifacts and credential-like strings.

**Location:** Throughout the manuscript; `scripts/verify_artifact.py`.

### Comment R2.2: Inconsistent success rates

**Response:** We use final target world distance <= 0.08 as the primary control rule and report 0.05 as a stricter auxiliary threshold. The authoritative 18-row semantic suite gives mean 0.064119, sample SD 0.015025, 3/18 selected-target controls at 0.05, and 18/18 selected-target controls at 0.08. The CSV now also records 17/18 requested-to-selected target matches and 17/18 instruction-level joint successes; the 18/18 value is not presented as end-to-end instruction success. The fresh raw sweep is separately reported as 0/16 at 0.05, 0/16 at 0.08, and 0/16 at 0.10. Superseded conflicting aggregate files were removed, the threshold table was regenerated, and the verifier recomputes these values.

**Location:** Evaluation Setup (p. 2); Tables III--V (pp. 5--6); Discussion (pp. 7--8); `data/semantic_mpc_live_runs_v9.csv`; `data/threshold_sensitivity_v9.csv`.

### Comment R2.3: Few seeds, zero variance, and mean plus or minus standard deviation

**Response:** We added a fresh four-variant raw sweep over seeds 45--48, yielding 16 raw runs and 0/16 successes. Its aggregate mean is 0.324472 with sample SD 0.108465. We also report variability for the 18-run semantic suite, the nine target-image trials, and the six visual-feedback trials. This addresses run-level descriptive variability, but does not establish broad independent-seed robustness: the semantic 18-run aggregate is heterogeneous rather than 18 independent seeds, its seed-only subset is n = 3 for seeds 42--44, and the fresh raw sweep provides four seeds per controller variant. The grounded zero variance is retained but explained by the shared terminal feedback law and identical 23/23 action replacement, not interpreted as evidence of raw-planner robustness. We therefore mark the stronger multi-seed generalization claim as unresolved rather than claiming that this revision fully satisfies it.

**Location:** Tables III--VI (pp. 5--6); Variability and Experimental Units (p. 6); `data/raw_controller_multiseed_runs_v9.csv`.

### Comment R2.4: Real robot and broader task validation

**Response:** We agree that real-robot validation and broader task families would strengthen external validity. They were not performed in this revision, so we do not imply otherwise. The manuscript states explicitly that the evidence is a local Language-Table simulation audit, that the positive oracle branches use privileged state, and that real-robot, broader-task, and visual-only validation remain future work.

**Location:** Evidence Boundary and Limitations and Future Work (p. 8).

### Comment R2.5: Targeted root-cause ablations

**Response:** We tightened the causal language and report observed symptoms as non-exclusive rather than as isolated root causes. The fresh raw 0/16 result across four variants and the visual-feedback 0/6 result strengthen the measured boundary, but they do not identify a unique mechanism. The action-authority audit shows that privileged feedback replaces 100 percent of grounded actions, and the retained yellow-pentagon failure shows that semantic selection can dominate the control outcome. A complete factorized root-cause study remains future work.

**Location:** Observed Failure Symptoms (p. 7); Tables XI--XII (p. 8); Evidence Boundary (p. 7).

### Comment R2.6: Redesign the re-query experiment so its benefit is measurable

**Response:** We added two complementary controls and keep their interpretation separate. In fresh matched natural-event controls, no-event and event-enabled runs use seeds 42--44 with cache disabled. Natural re-query fires in 3/3 enabled runs and 0/3 no-event runs, but the paired final distances are identical seed by seed; this supports trigger execution, not a causal recovery benefit. Separately, the controlled semantic-fault audit injects a wrong initial target. The forced-requery treatment repairs the semantic state in 3/3 and reaches the independent true-target threshold in 2/3, whereas the no-requery control reaches 0/3. This establishes repair under the tested intervention, but it does not satisfy the stronger request to demonstrate a natural failure-conditioned recovery benefit; that causal question remains open and is stated as a limitation.

**Location:** Event-Triggered VLM Re-query (p. 4); Tables VII--VIII (p. 6); `supplement_v9_sanitized/data/revision_20260922/event_requery_controls_v9.csv`; `event_fault_recovery_runs_v9.csv`.

## Reviewer 3

### Comment R3.1: Make the privileged-feedback boundary prominent

**Response:** We now place the negative raw result before the diagnostic positives in both the Abstract and Introduction. The branch table records state source and executed-action authority, and every result table labels oracle-feedback rows separately from the visual-only branch. The manuscript never treats 4/4, 8/8, or 18/18 diagnostic outcomes as successful unmodified VLMPC reproduction.

**Location:** Abstract (p. 1); Introduction (pp. 1--2); Table II (p. 5); Table IV (p. 6); Discussion (p. 7); Conclusion (p. 8).

### Comment R3.2: Concrete visual-state-estimator metrics and implementation roadmap

**Response:** The revision goes beyond a purely prospective roadmap by evaluating the implemented detector/tracker visual-feedback path on six seeds. It obtains 0/6 successes with mean final distance 0.3160 and sample SD 0.1439, so the oracle-to-vision gap remains measured rather than assumed closed. We retain a concrete next milestone: estimate target centroid, end-effector pose, target visibility/confidence, and goal-relative distance from RGB. Planned metrics are centroid error in pixels and normalized table coordinates, end-effector position error, goal-distance MAE, visibility F1, one-step temporal consistency, final distance, success at 0.05 and 0.08, recovery latency after an induced tracking jump, action-replacement rate, and runtime per step. The implementation sequence is synchronized RGB/state export, detector-tracker calibration on held-out seeds and perturbations, interface replacement, confidence gating, and matched visual-only/oracle evaluation.

**Location:** Visual-Feedback Boundary (pp. 6--7); Limitations and Future Work (p. 8); `supplement_v9_sanitized/data/revision_20260922/visual_feedback_runs_v9.csv`.

### Comment R3.3: Check errors in the manuscript

**Response:** We ran a manuscript-wide language, numerical, cross-reference, and artifact audit after regenerating the v1.0.6 figures. We removed superseded aggregate files and an empty event artifact, separated executed-source and public-snapshot hashes, exported the robustness-edge CSV and four portable inputs, corrected stale package paths, bound `CITATION.cff` to the exact v1.0.6 release, and verified the authoritative counts. The final integrity check covers the raw 16-run sweep, semantic thresholds and request-selection scope, target-image outcomes, event pairing, fault audit, visual-feedback result, robustness-edge rows and input paths, source hashes, complete manifest coverage, required figures, and forbidden credential-like strings.

**Location:** Throughout the manuscript; Data and Code Availability (p. 8); `scripts/verify_artifact.py`; `CHANGELOG.md`.

## Summary of the revision boundary

The revision now provides a larger and more internally coherent evidence chain, but its scientific conclusion remains deliberately bounded: the unmodified raw VLMPC-style chain is executable yet unsuccessful in the fresh 16-run sweep; privileged feedback stabilizes several diagnostic branches; selected-target semantic control is 18/18 but requested-to-selected matching and instruction-level joint success are 17/18; target-image grounding is imperfect; natural event re-query has no demonstrated recovery benefit in the matched controls; and the first detector/tracker visual-feedback implementation does not close the oracle-to-vision gap. The package-level release and robustness-traceability issues are fixed in v1.0.6. Real-robot validation, broader tasks, stronger independent-seed coverage, natural failure-conditioned re-query benefit, and complete causal root isolation remain open.
