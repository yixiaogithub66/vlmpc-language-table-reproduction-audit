# Reproduction Guide v1.0.8

## 1. Offline integrity check

From the package root:

    python scripts/verify_artifact.py

The expected result is ARTIFACT VERIFICATION PASSED. The check recomputes counts, means, sample standard deviations, threshold counts, request/selection success scope, event-control pairing, target-image outcomes, visual-feedback outcomes, robustness-edge rows and input paths, source hashes, required figures, exact release binding, complete manifest coverage, and removal of superseded artifacts.

## 2. Regenerate portable summaries

The import utility accepts the local root containing the dated experiment-output directories:

    python scripts/import_live_results_v9.py --source-root <stage_experiments> --event-result-dir <valid-worldscale-event-result-directory>

The utility copies only sanitized run-level fields and writes the v9 CSVs, including `data/robustness_edge_audit_v9.csv` and its four portable input images. The semantic importer marks only `mode=instruction` as `instruction_evaluable`; fixed-target, target-image, and scene-selection rows receive separate `evaluation_scope` labels and are not pooled into the instruction denominator. It does not copy credentials, raw transcripts, private URLs, or machine-local source paths.

## 3. Regenerate figures

    python scripts/plot_paper_figures.py

The script reads the portable v9 CSVs and writes the vector figures under figures/. The manuscript uses the v9 filenames explicitly.

## 4. Compile the manuscript

Run the normal IEEE LaTeX sequence from the package root:

    pdflatex -interaction=nonstopmode -halt-on-error main.tex
    bibtex main
    pdflatex -interaction=nonstopmode -halt-on-error main.tex
    pdflatex -interaction=nonstopmode -halt-on-error main.tex

The final PDF should be inspected visually after compilation. A successful LaTeX exit alone does not guarantee that a table or figure is readable.

## 5. Optional online reruns

A fresh online rerun requires the original simulator, dependencies, image assets, `codex` CLI, an isolated `CODEX_HOME` containing `config.toml`, and the locally configured GPT-5.5 access profile. The formal adapter invokes `codex exec` with prompt stdin, `-i` image attachments, and a temporary `-o` output file; non-ASCII image paths are staged to ASCII temporary names. The public package includes source snapshots and an environment template, but intentionally does not include credentials or private service settings. The direct HTTP-compatible backend is not the formal experiment path, and the sanitized package is not an offline copy of the external model backend.

## 6. Provenance

The source snapshot manifest records public-file SHA-256 values and distinguishes executed source from reviewer-facing snapshots with sanitized runtime defaults. The semantic event controls use `semantic_event_requery_window=4`, `semantic_event_requery_min_progress=0.002`, and `semantic_event_requery_progress_units=world_distance`; the generic original-planner event parameters are not used to interpret those controls. This package is the publicly tagged v1.0.8 release; verify the immutable tag binding before external submission.
