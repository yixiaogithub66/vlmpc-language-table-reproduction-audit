# Revision experiment summaries

These files are derived from the raw logs generated on 2026-09-18 and are safe to distribute with the manuscript. They intentionally omit API keys, gateway addresses, absolute local paths, raw prompts, and raw logs.

The target-image matrix contains three target-image cases and seeds 45, 46, and 47. `pre_satisfied=True` means that the true target was already within the terminal threshold before any action; it is counted separately from active control success. `joint_active_success` requires both correct semantic selection and active control success.

The event-fault audit deliberately injects a wrong initial semantic target. Its treatment uses one explicitly labeled synthetic re-query, so it tests repair of a known semantic fault. It does not measure the sensitivity or causal benefit of the natural stagnation detector.

All means and standard deviations in these files use the sample standard deviation convention.
