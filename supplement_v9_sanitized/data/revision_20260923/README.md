# Revision 2026-09-23: independent language and Codex fault audits

These files are sanitized summaries of fresh local runs through the project's
`CodexCLIClient`: `codex exec -m gpt-5.5`, an isolated `CODEX_HOME`, and strict
no-cache mode. Credentials, local log paths, raw transcripts, and checkpoints
are intentionally omitted.

## Language repeats

Three target objects were evaluated with one natural-language instruction each
and seeds 42--44 (nine independent simulator runs). The VLM selected the
independently specified target in 9/9 trials and the target reached the 0.08
distance threshold in 9/9. Per-object means and sample SDs are in the aggregate
CSV. This is a small repeated-instruction audit, not broad language or
real-robot generalization.

## Failure-conditioned re-query

Six paired seeds deliberately replace the correct initial semantic target with
`blue cube`. The treatment forces one explicitly labeled semantic-fault
re-query at step 3; the control never re-queries. Evaluation uses the
independent true target (`red moon`). The treatment repairs the semantic state
in 6/6 and reaches the true-target threshold in 5/6; the control reaches 0/6.
This is an intervention audit of a known semantic fault, not evidence that a
natural stagnation event always predicts or repairs a failure.
