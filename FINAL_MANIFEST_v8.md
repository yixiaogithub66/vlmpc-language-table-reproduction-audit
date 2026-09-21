# Final Manifest v8

## Manuscript

- main.tex: revised IEEEtran manuscript.
- main.pdf: compiled v8 PDF after the final LaTeX build.
- refs.bib, IEEEtran.cls, and figures/: compilation inputs.

## Revision materials

- RESPONSE_TO_REVIEWERS_v8.md: point-by-point response.
- REPRODUCTION_GUIDE_v8.md: commands and evidence mapping.
- DATA_CODE_AVAILABILITY_v8.md: availability statement and packaging note.
- supplement_v8_sanitized/: submission-safe derived statistics and source snapshot.

## Evidence boundaries preserved

- Unmodified controller comparison: 0/4.
- Unmodified parameter ablation: 0/8.
- Grounded diagnostic action replacement: 23/23 in all 12 runs.
- Latest archived semantic diagnostic suite: 18/18 at d_world_final <= 0.08, 3/18 at <= 0.05.
- Revision target-image matrix: 8/9 semantic matches; 7/8 joint active successes; one pre-satisfied run separated.
- Revision semantic-fault audit: 3/3 semantic repairs; 2/3 true-target successes under synthetic re-query; 0/3 without re-query.
- Natural event controls: trigger execution checked; causal recovery benefit not claimed.

## Pre-submission check

Replace the author-on-request availability wording with a public repository or archival identifier if the conference requires public access. Do not upload raw local CSVs containing gateway URLs, absolute paths, or credential-presence metadata.

