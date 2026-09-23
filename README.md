# VLMPC Language-Table Reproduction Audit

## Revision artifact v1.0.8

This package accompanies the revised manuscript **Traceable Reproduction Audit and Feedback-Assisted Diagnostics for VLMPC-Style Language-Table Pushing**. It contains the manuscript source, regenerated figures, sanitized experiment summaries, portable source snapshots, and verification scripts for the complete revision experiment suite.

The package is an evidence-bound audit. It does not claim that the unmodified VLMPC video-prediction MPC chain was successfully reproduced. The fresh raw sweep contains 16 runs across four controller variants and seeds 45--48, with 0/16 runs meeting the project success threshold. Positive oracle-feedback results are reported separately as diagnostic stabilization, because privileged simulator state determines the executed action in those branches.

## Main results

- Fresh raw MPC sweep: 0/16 successes; mean final distance 0.3245 +/- 0.1085, sample SD.
- Grounded diagnostic branches: 4/4 controller runs and 8/8 ablation runs; all 12 runs replaced 23/23 raw planner actions with the privileged feedback action.
- Live semantic suite: 18 heterogeneous diagnostic runs; 3/18 at distance 0.05 and 18/18 selected-target controls at distance 0.08; the run-level breakdown is 15/15 fixed-target controls, 1/1 natural-language instruction joint success, 1/1 target-image selected-target control, and 1/1 free scene-selection control. Only the language row is instruction-evaluable; mean 0.0641 +/- 0.0150.
- Robustness edge audit: 4/4 detector cases retained under the tested perturbation proxies and 3/3 unsupported target names safely rejected; four portable input images are bundled with the CSV.
- Target-image matrix: 9 active trials over three targets and seeds 42--44; semantic selection and joint control each succeed in 8/9, with no pre-satisfied trial.
- Event controls: with the corrected semantic detector settings (window 4, minimum world-distance progress 0.002), natural re-query fires in 3/3 event-enabled runs and 0/3 no-event runs, but matched final distances are identical; this demonstrates trigger execution, not causal recovery benefit.
- Visual-feedback boundary: the implemented detector/tracker path achieves 0/6, mean final distance 0.3160 +/- 0.1439.
- Root-cause factorization: matched fixed-target oracle versus visual feedback is 6/6 versus 0/6, with a paired final-distance gap of 0.2548 +/- 0.1453; the independent target-image matrix remains 8/9. This is bounded factor-isolating evidence, not an exhaustive causal decomposition.
- Independent Codex language-repeat audit (revision 2026-09-23): three instructions x three seeds, 9/9 specified-target selections and 9/9 joint controls under strict no-cache.

## Contents

- main.tex and main.pdf: revised manuscript source and compiled paper.
- figures/: regenerated vector figures and visual assets used by the manuscript.
- data/: primary portable CSV summaries and threshold table.
- supplement_v9_sanitized/: source snapshots, revision CSVs, manifests, controlled fault-audit data, and robustness-audit inputs.
- scripts/: import, plotting, and artifact-verification utilities.
- RESPONSE_TO_REVIEWERS_v9.md: point-by-point response to the editor and reviewers.
- REPRODUCTION_GUIDE_v9.md: offline verification and optional rerun instructions.

## Scope and limitations

The package does not include credentials, private service configuration, raw online logs, video recordings, model checkpoints, or simulator redistribution. The formal runs used `CodexCLIClient` and local `codex exec -m gpt-5.5` calls with an isolated `CODEX_HOME`; prompts were sent on stdin and image attachments were staged at ASCII temporary paths. The package reports the adapter-level experiment outputs without claiming that it reproduces a proprietary model backend offline. The direct HTTP-compatible backend exists in the source tree but was not used for the formal results.

Real-robot validation, broader task families, and an exhaustive causal root-isolation study were not performed in this revision. A bounded factor-isolating audit is included under `supplement_v9_sanitized/data/revision_20260922/root_cause_ablation_v9.{csv,md}`; it does not identify every factor interaction. These remain explicit limitations rather than implied successes. The natural event-control experiment also does not show a recovery advantage; the separate forced semantic-fault audit only shows that a deliberately injected semantic error can be repaired under the tested intervention.

## Verification

From this directory, run:

    python scripts/verify_artifact.py

The verifier checks the authoritative counts and statistics, request/selection success scope, robustness-audit inputs, source-snapshot hashes, required figures, exact release binding, complete manifest coverage, superseded-file removal, empty-file removal, and credential-like-string exclusion. It is a package-integrity check, not a replacement for rerunning online experiments.
