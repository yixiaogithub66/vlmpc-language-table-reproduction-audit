# Sanitized Supplement v1.0.7

This supplement contains the portable source snapshot and revision experiment summaries. It is intentionally separated from private runtime configuration.

The revision_20260922 directory contains semantic condition statistics, target-image selection and end-to-end matrices, matched event controls, the controlled semantic-fault audit, and visual-feedback runs. The event-control CSVs record the corrected semantic detector configuration (window 4, minimum world-distance progress 0.002). The sibling `robustness_edge_audit` directory contains the four portable detector-audit input images and its provenance note. The data are sufficient to reproduce the manuscript's reported aggregate numbers and figures.

The source directory contains the experiment scripts and the runtime-independent snapshots used for provenance. See SOURCE_SNAPSHOT_PROVENANCE_v9.md and data/code_manifest_v9.csv for the hash relationship between executed and public files.

The public supplement does not contain credentials, raw online transcripts, model checkpoints, raw videos, or private local paths. It should therefore be read as a traceable summary artifact, not as a complete turnkey recreation of every external runtime dependency.
