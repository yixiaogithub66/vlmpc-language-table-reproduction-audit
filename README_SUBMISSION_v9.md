# Submission Readme v1.0.8

This directory is the v1.0.8 release package for the manuscript and response letter. The paper has been revised after a fresh complete experiment suite, not by replacing unsuccessful outcomes with positive claims.

## What changed

1. The fresh raw reproduction is now a four-variant, four-seed sweep: 0/16.
2. Oracle-feedback diagnostics, target-image grounding, event controls, and visual feedback are separated by state-access assumptions.
3. The target-image matrix includes nine active trials with the negative yellow-pentagon case retained.
4. Natural event re-query is reported as trigger execution only; matched final distances do not support a recovery-benefit claim.
5. The detector/tracker visual-feedback implementation is evaluated directly and reports 0/6.
6. Figures, tables, the evidence index, the data/code statement, and the point-by-point response letter have been regenerated together.
7. The release metadata targets v1.0.8; the robustness-edge CSV and four portable inputs are included and checked.
8. Semantic control success is explicitly scoped to the selected target: 15/15 fixed-target controls, 1/1 natural-language instruction joint success, 1/1 target-image selected-target control, and 1/1 free scene-selection control. Only the natural-language row is instruction-evaluable; the other three categories are reported separately.
9. The event-control rerun uses the corrected semantic detector scale: window 4 and minimum world-distance progress 0.002; paired final distances remain identical.

## Before submission

- Run python scripts/verify_artifact.py.
- Compile main.tex and confirm that main.pdf is the newly generated PDF.
- Check that the response letter refers to section and table names in this package, not superseded v1.0.4 labels.
- This directory is the publicly tagged v1.0.8 release. Verify that `CITATION.cff`, the manuscript, and the release URL point to the immutable tag.

## Scientific boundary

The manuscript's positive oracle rows are diagnostic stabilization results. They are not claimed as successful unmodified VLMPC reproduction. Real-robot validation, broader tasks, and complete root-cause isolation remain open limitations.
