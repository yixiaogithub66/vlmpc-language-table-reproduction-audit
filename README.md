# VLMPC Language-Table Reproduction Audit

This repository is the public revision artifact for Traceable Reproduction Audit and Feedback-Assisted Semantic-MPC for VLMPC-Style Language-Table Pushing by Xiao Yi and Yuanqiang Zhou.

The artifact preserves the negative unmodified-reproduction results, the privileged-feedback diagnostic results, and the focused target-image and semantic-fault experiments without presenting those branches as equivalent evidence.

Use release v1.0.4. Releases v1.0.0, v1.0.1, v1.0.2, and v1.0.3 are retained for provenance but are superseded. Version 1.0.0 included conflicting historical Semantic MPC rows and an ambiguous source-snapshot hash; version 1.0.1 corrected those issues but exposed a Windows/Git line-ending mismatch; version 1.0.2 fixed the line endings but retained one old aggregate summary; version 1.0.3 removed that final evidence conflict. Version 1.0.4 adds the revised publication figures and a reproducible figure-rendering script.

## Start Here

- main.pdf: compiled manuscript.
- main.tex: IEEEtran manuscript source.
- RESPONSE_TO_REVIEWERS_v8.md: point-by-point response.
- REPRODUCTION_GUIDE_v8.md: commands, environment assumptions, and artifact mapping.
- EXPERIMENT_RESULTS_INDEX_v8.md: result-file index.
- data/semantic_mpc_authoritative_runs_v8.csv: sole authoritative final 18-run Semantic MPC dataset.
- supplement_v8_sanitized/data/revision_20260919/: new per-run and aggregate evidence.
- supplement_v8_sanitized/source/: reviewer-facing source snapshot.
- scripts/plot_paper_figures.py: reproducible manuscript figure renderer.

## Headline Results

- Unmodified controller comparison: 0/4.
- Unmodified parameter ablation: 0/8.
- Grounded diagnostic branch: 23/23 raw actions replaced in every run.
- Semantic MPC diagnostic suite: 18/18 at 0.08 and 3/18 at 0.05, with final distance 0.064119 +/- 0.015025 sample SD.
- Target-image matrix: 8/9 semantic matches and 7/8 joint active successes.
- Forced semantic-fault audit: 3/3 semantic repairs and 2/3 true-target successes.
- Natural-event controls: matched final distances; no causal recovery benefit is claimed.

## Reproducibility Boundary

The included sanitized CSVs are sufficient to recompute and audit the manuscript aggregates. Full end-to-end execution additionally requires the Language-Table simulator, compatible Python dependencies, detector/tracker/video-prediction checkpoints obtained from their original distributions, and a separately configured compatible VLM backend.

The repository intentionally excludes API credentials, private gateway addresses, local absolute paths, virtual environments, raw service logs, and third-party model weights. Do not commit a local .env file. Expected checkpoint hashes and configuration paths are recorded in the manifests.

## Verify the Artifact

Run from the repository root:

    python scripts/verify_artifact.py

The script recomputes the headline statistics, checks the target-image and semantic-fault counts, validates every public source-snapshot hash, rejects superseded conflicting files, and detects zero-byte data or source artifacts.

## Citation

Citation metadata is provided in CITATION.cff. Use release v1.0.4 when referring to the exact revision artifact.

## Licensing Note

No project-wide open-source license is asserted for this collected revision artifact. Third-party files and dependencies retain their original notices and licenses; no third-party model weights are redistributed.
