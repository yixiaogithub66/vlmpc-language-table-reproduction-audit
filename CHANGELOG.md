# Changelog

## v1.0.2

- Enforced LF line endings for public Python sources through .gitattributes.
- Verified that source hashes match files after Git archive extraction, not only the local Windows working tree.
- Retained all v1.0.1 evidence, response-letter, and attachment-cleanup corrections.

## v1.0.1

- Removed superseded Semantic MPC rows and the conflicting 5/18 threshold table.
- Added a single authoritative 18-run data file and regenerated threshold and condition statistics.
- Separated executed-source hashes from public-snapshot hashes and documented the main.py sanitization.
- Completed the point-by-point response and replaced internal LaTeX labels with rendered table numbers and pages.
- Removed inaccessible local paths and an empty duplicate CSV from the public package.
- Added an automated artifact verification script.

This release is retained for provenance but superseded by v1.0.2 because Git archive line-ending conversion caused its public source-snapshot hashes to differ after extraction.

## v1.0.0

Initial public revision artifact. Superseded because its evidence package retained conflicting historical Semantic MPC rows and an ambiguous main.py hash.
