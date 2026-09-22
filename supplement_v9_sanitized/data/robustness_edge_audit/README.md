# Robustness-Edge Audit

This directory contains the portable inputs for the archived detector-level
robustness-edge audit dated 2026-06-06. The audit covers one unmodified frame,
an occlusion proxy, a viewpoint/crop/resize proxy, a brightness-shift proxy,
and three unsupported target names. It is a small boundary check for object
mapping; it is not a real-camera robustness benchmark and it is not a
closed-loop control experiment.

The sanitized summary is `data/robustness_edge_audit_v9.csv`. Its
`portable_image_path` values resolve to the four PNG inputs in this directory;
`manifest_v9.json` records their SHA-256 values.
The original machine-local paths and raw runtime configuration are intentionally
omitted. `source_record` identifies the archived experiment record from which
the portable rows were exported.
