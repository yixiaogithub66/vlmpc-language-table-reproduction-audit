# Root-Cause Ablation (v1.0.7)

This table factorizes the observed failure boundary using already completed, sanitized runs. It is an attribution aid, not a claim of exhaustive causal identification.

- `execution_authority`: raw planner versus archived grounded execution; the grounded branch records 23/23 action replacements in every run.
- `feedback_source`: six fixed-target seeds are paired by seed between simulator-state and detector/tracker feedback.
- `target_grounding`: the independent Codex language-repeat matrix and target-image matrix hold the semantic controller and privileged execution path fixed while retaining explicit selection outcomes.
- `planner_tuning`: the archived budget/cost sweep tests whether common raw-planner settings rescue the negative reproduction.

The paired feedback runs use `controller_variant=semantic_mpc`, fixed target `red moon`, seeds 45--50, `max_traj_length=45`, `num_samples=10`, `plan_freq=2`, semantic parameters `(contact_offset, clearance, move_step, push_step)=(0.06, 0.12, 0.06, 0.075)`, success distance 0.08, and strict no-cache mode. The only intended factor change is `feedback_source=oracle` versus `feedback_source=visual`. Because the target is supplied explicitly, this pair isolates low-level state feedback and does not exercise Codex target parsing.

The paired visual gap is defined as `final_world_distance(visual) - final_world_distance(oracle)` for the same seed; positive values indicate worse visual-feedback distance. All 6/6 paired visual runs have a larger final distance (range 0.0406--0.4106). Archived grounded rows are intentionally labelled as historical protocol evidence and are not pooled with the fresh raw seed sweep.

| factor | condition | n | success | mean final world distance | sample SD | paired gap vs oracle | paired gap SD | matching scope |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| planner_tuning | raw_parameter_ablation | 8 | 0/8 | 0.253366 | 0.030358 | - | - | eight archived budget/cost settings |
| execution_authority | raw_video_mpc_fresh | 16 | 0/16 | 0.324472 | 0.108465 | - | - | fresh 4-variant x 4-seed sweep |
| execution_authority | grounded_original_archived | 12 | 12/12 | 0.064266 | 0.000000 | - | - | 4 controller + 8 ablation rows; archived, not a fresh seed extension |
| feedback_source | semantic_oracle_fixed_target | 6 | 6/6 | 0.061241 | 0.020632 | - | - | six fixed-target repeats |
| feedback_source | semantic_visual_fixed_target | 6 | 0/6 | 0.316042 | 0.143929 | 0.254801 | 0.145339 | paired by seed with semantic_oracle_fixed_target; visual path only |
| target_grounding | language_instruction_codex_repeat | 9 | 9/9 | 0.066129 | 0.019081 | - | - | 3 instruction cases x 3 seeds; Codex gpt-5.5; strict no-cache |
| target_grounding | target_image_matrix | 9 | 8/9 | 0.095024 | 0.093199 | - | - | 3 target cases x 3 seeds; all active |

## Interpretation

The strongest controlled comparison is the paired oracle-versus-visual row: the same fixed target and seeds retain 6/6 oracle successes but produce 0/6 visual-feedback successes. The independent Codex language-repeat matrix is 9/9 for selection and joint control, while the target-image matrix separately retains an 8/9 semantic-and-control result with one known target-selection error. Together with 0/16 raw-MPC success and 23/23 grounded action replacement, these results localize the current boundary to execution-state estimation and semantic grounding rather than proving a single universal root cause.

The table does not establish real-robot transfer, broad task generalization, or a causal benefit from event re-query. Those claims require new matched experiments.
