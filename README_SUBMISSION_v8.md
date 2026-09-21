# Submission Bundle v8

This is the clean manuscript package for the current revision. It contains the compiled paper, source needed for a local LaTeX build, the point-by-point response, the reproduction guide, and sanitized derived evidence.

Public artifact: https://github.com/yixiaogithub66/vlmpc-language-table-reproduction-audit (release v1.0.1).

The raw experiment logs are intentionally outside this bundle. The supplement source and CSVs omit API keys, gateway addresses, absolute local paths, raw prompts, and model weights.

Primary entry points:

    main.pdf
    RESPONSE_TO_REVIEWERS_v8.md
    REPRODUCTION_GUIDE_v8.md
    data/semantic_mpc_authoritative_runs_v8.csv
    supplement_v8_sanitized/data/revision_20260919/
    scripts/verify_artifact.py

The authoritative Semantic MPC suite reports 3/18 at 0.05 and 18/18 at 0.08, with final distance 0.064119 +/- 0.015025 sample SD. The target-image matrix reports 8/9 semantic matches and 7/8 joint active successes after separating one pre-satisfied run. The semantic-fault audit reports 3/3 semantic repairs and 2/3 true-target successes under an explicitly forced synthetic re-query. No causal benefit is claimed for natural event re-query.
