# Source Snapshot Provenance

The public source snapshot is compared against the source tree used for the v1.0.8 revision experiments.

- Three listed Python files are byte-identical: vlm_client.py, run_revision_target_image_matrix.py, and run_revision_event_recovery_audit.py.
- The remaining listed files are reviewer-facing snapshots. Their relationships and both SHA-256 values are recorded in data/code_manifest_v9.csv.
- main.py retains the experiment logic while replacing a drive-local dependency fallback with the VLMPC_EXTRA_SITE_DIR environment variable and a repository-local inert fallback.
- vlmpc.py records the corrected semantic event detector parameters: a four-step window, a 0.002 world-distance threshold, and explicit world-distance units.
- run_event_requery_controls.py records the corrected semantic event arguments and the fresh matched-control output schema.
- run_opening_report_complete.py preserves the distinction between the single explicit instruction trial and the fixed-target, target-image, and free scene-selection controls; it does not backfill a requested target into the latter two interface rows or inflate the instruction denominator.
- Public Python snapshot hashes are computed on LF line endings. The repository enforces this representation through .gitattributes so that cloned and release-archive files retain the recorded bytes.

This distinction prevents an executed-source hash from being misrepresented as the hash of a reviewer-facing public file.
