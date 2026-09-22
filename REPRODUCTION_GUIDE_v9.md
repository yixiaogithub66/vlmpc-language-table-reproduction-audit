# Reproduction Guide v1.0.5

## 1. Offline integrity check

From the package root:

    python scripts/verify_artifact.py

The expected result is ARTIFACT VERIFICATION PASSED. The check recomputes counts, means, sample standard deviations, threshold counts, event-control pairing, target-image outcomes, visual-feedback outcomes, source hashes, required figures, and removal of superseded artifacts.

## 2. Regenerate portable summaries

The import utility accepts the local root containing the dated experiment-output directories:

    python scripts/import_live_results_v9.py --source-root <stage_experiments>

The utility copies only sanitized run-level fields and writes the v9 CSVs. It does not copy credentials, raw transcripts, private URLs, or machine-local source paths.

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

A fresh online rerun requires the original simulator, dependencies, image assets, and an independently configured external VLM runtime. The public package includes source snapshots and an environment template, but intentionally does not include credentials or private service settings. The manuscript identifies the model family as GPT-5.5-based VLM and does not represent the sanitized package as an offline copy of the external backend.

## 6. Provenance

The source snapshot manifest records public-file SHA-256 values. main.py is explicitly documented as a sanitized derivative because its drive-local dependency fallback was replaced with an environment-variable/local fallback. The controller logic and reported computations are unchanged by that packaging edit.
