# Source Snapshot Provenance

The public source snapshot is compared against the source tree used for the reported revision experiments.

- Five listed Python files are byte-identical. Their executed-source and public-snapshot SHA-256 values therefore match.
- main.py is a sanitized derivative. Its executed-source SHA-256 is d8078e7cba86a7da0ae26d6cf00a8505842ef840b9763fc7272af066eaf4a6d9. Its public-snapshot SHA-256 is f98caece7442d677223baa6ba54a6dd9f2a650a5744684c8825b8864fc8a6a50.
- The only main.py change replaces a drive-local dependency fallback with the VLMPC_EXTRA_SITE_DIR environment variable and a repository-local inert fallback. Controller logic, experiment arguments, and reported computations are unchanged.
- The complete two-hash mapping is in data/code_manifest_v8.csv.
- Public Python snapshot hashes are computed on LF line endings. The repository enforces this representation through .gitattributes so that cloned and release-archive files retain the recorded bytes.

This distinction prevents the executed source hash from being misrepresented as the hash of the sanitized public file.
