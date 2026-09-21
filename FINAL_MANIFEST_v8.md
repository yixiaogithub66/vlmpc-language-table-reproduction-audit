# Final Manifest v8

## Public Release

- Repository: https://github.com/yixiaogithub66/vlmpc-language-table-reproduction-audit
- Corrected immutable release: v1.0.1
- Superseded release retained for provenance: v1.0.0

## Manuscript

- main.tex: revised IEEEtran manuscript.
- main.pdf: compiled nine-page PDF.
- refs.bib, IEEEtran.cls, and figures/: compilation inputs.

## Revision Materials

- RESPONSE_TO_REVIEWERS_v8.md: complete point-by-point response.
- REPRODUCTION_GUIDE_v8.md: commands and evidence mapping.
- DATA_CODE_AVAILABILITY_v8.md: public availability statement and access boundaries.
- EXPERIMENT_RESULTS_INDEX_v8.md: public artifact-to-claim index.
- supplement_v8_sanitized/: sanitized derived statistics and source snapshot.
- scripts/verify_artifact.py: executable consistency checks.

## Evidence Boundaries

- Unmodified controller comparison: 0/4.
- Unmodified parameter ablation: 0/8.
- Grounded diagnostic action replacement: 23/23 in all 12 runs.
- Authoritative Semantic MPC suite: 18/18 at final distance <= 0.08 and 3/18 at <= 0.05, with mean 0.064119 and sample SD 0.015025.
- Target-image matrix: 8/9 semantic matches and 7/8 joint active successes, with one pre-satisfied run separated.
- Semantic-fault audit: 3/3 forced repairs and 2/3 true-target treatment successes versus 0/3 controls.
- Natural event controls: trigger execution checked; causal recovery benefit not claimed.

## Pre-submission Gate

- Run python scripts/verify_artifact.py and require a passing result.
- Confirm that the repository and v1.0.1 release resolve publicly.
- Confirm zero undefined citations and references after the final LaTeX build.
- Do not add raw logs, API credentials, private gateway addresses, local absolute paths, virtual environments, or third-party model weights.
