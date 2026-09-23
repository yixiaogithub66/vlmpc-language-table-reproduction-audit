#!/usr/bin/env python3
"""Derive the factor-isolating root-cause table from portable v1.0.7 CSVs.

The table is deliberately descriptive.  It separates planner authority,
feedback source, target grounding, and raw-planner parameter tuning, while
retaining the matching scope and the limits of each comparison.
"""
from __future__ import annotations

import csv
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REV = ROOT / "supplement_v9_sanitized" / "data" / "revision_20260922"
REV23 = ROOT / "supplement_v9_sanitized" / "data" / "revision_20260923"
OUT_CSV = REV / "root_cause_ablation_v9.csv"
OUT_MD = REV / "root_cause_ablation_v9.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def values(rows: list[dict[str, str]], key: str) -> list[float]:
    return [float(row[key]) for row in rows]


def fmt(value: float | None) -> str:
    return "" if value is None else f"{value:.6f}"


def stats(rows: list[dict[str, str]], key: str) -> tuple[float, float]:
    numbers = values(rows, key)
    return statistics.mean(numbers), statistics.stdev(numbers) if len(numbers) > 1 else 0.0


def success_count(rows: list[dict[str, str]], key: str = "target_success") -> str:
    return f"{sum(row.get(key) == 'True' for row in rows)}/{len(rows)}"


def row(
    *,
    factor: str,
    condition: str,
    runs: list[dict[str, str]],
    seeds: str,
    target_reference: str,
    feedback_source: str,
    planner_authority: str,
    selection_success: str,
    control_success: str,
    joint_success: str,
    evidence: str,
    matching_scope: str,
    interpretation: str,
    distance_key: str = "final_target_world_distance",
    paired_gap: float | None = None,
    paired_gap_sd: float | None = None,
) -> dict[str, str]:
    mean, sd = stats(runs, distance_key)
    return {
        "factor": factor,
        "condition": condition,
        "n": str(len(runs)),
        "seeds_or_protocol": seeds,
        "target_reference": target_reference,
        "feedback_source": feedback_source,
        "planner_authority": planner_authority,
        "selection_success": selection_success,
        "control_success": control_success,
        "joint_success": joint_success,
        "mean_final_world_distance": fmt(mean),
        "sample_sd_final_world_distance": fmt(sd),
        "paired_gap_vs_oracle": fmt(paired_gap),
        "paired_gap_sample_sd": fmt(paired_gap_sd),
        "matching_scope": matching_scope,
        "interpretation": interpretation,
        "evidence": evidence,
    }


def main() -> None:
    raw = read_csv(ROOT / "data" / "raw_controller_multiseed_runs_v9.csv")
    archived = read_csv(ROOT / "data" / "archived_nonsemantic_branch_runs_v8.csv")
    grounded = [
        item
        for item in archived
        if item.get("group") == "feedback-assisted diagnostics"
        and item.get("suite") in {"Grounded controller", "Grounded ablation"}
    ]
    raw_ablation = [item for item in archived if item.get("group") == "unmodified reproduction" and item.get("suite") == "Unmodified ablation"]
    oracle = read_csv(REV / "semantic_oracle_feedback_runs_v9.csv")
    visual = read_csv(REV / "visual_feedback_runs_v9.csv")
    target_aggregate = read_csv(REV / "target_image_matrix_aggregate_v9.csv")
    target_overall = next(item for item in target_aggregate if item.get("case") == "overall")
    language_repeats = read_csv(REV23 / "language_instruction_repeat_runs_v9.csv")

    oracle_by_seed = {item["seed"]: item for item in oracle}
    visual_by_seed = {item["seed"]: item for item in visual}
    paired_seeds = sorted(set(oracle_by_seed) & set(visual_by_seed))
    paired_gaps = [
        float(visual_by_seed[seed]["final_target_world_distance"])
        - float(oracle_by_seed[seed]["final_target_world_distance"])
        for seed in paired_seeds
    ]
    paired_gap = statistics.mean(paired_gaps)
    paired_gap_sd = statistics.stdev(paired_gaps)

    # Reconstruct exact moments from nine per-run rows, rather than averaging
    # the case-level aggregate rows.
    target_runs = read_csv(REV / "target_image_matrix_runs_v9.csv")

    rows = [
        row(
            factor="planner_tuning",
            condition="raw_parameter_ablation",
            runs=raw_ablation,
            seeds="archived parameter settings",
            target_reference="fixed target",
            feedback_source="none; raw RGB/video-prediction chain",
            planner_authority="raw planner",
            selection_success="fixed-by-design",
            control_success=success_count(raw_ablation),
            joint_success="N/A",
            evidence="data/archived_nonsemantic_branch_runs_v8.csv",
            matching_scope="eight archived budget/cost settings",
            interpretation="Budget and cost changes did not rescue the unmodified chain; this is a tuning boundary, not a proof that every parameter is exhausted.",
            distance_key="final_distance",
        ),
        row(
            factor="execution_authority",
            condition="raw_video_mpc_fresh",
            runs=raw,
            seeds="45,46,47,48",
            target_reference="fixed red moon",
            feedback_source="none; raw RGB/video-prediction chain",
            planner_authority="raw planner action executed",
            selection_success="fixed-by-design",
            control_success=success_count(raw),
            joint_success="N/A",
            evidence="data/raw_controller_multiseed_runs_v9.csv",
            matching_scope="fresh 4-variant x 4-seed sweep",
            interpretation="The negative anchor is reproduced before adding privileged state feedback.",
        ),
        row(
            factor="execution_authority",
            condition="grounded_original_archived",
            runs=grounded,
            seeds="archived fixed-target protocol",
            target_reference="fixed target",
            feedback_source="privileged simulator state",
            planner_authority="feedback override; 23/23 raw actions replaced",
            selection_success="fixed-by-design",
            control_success="12/12",
            joint_success="N/A",
            evidence="data/archived_nonsemantic_branch_runs_v8.csv; supplement_v9_sanitized/data/grounded_action_replacement_summary_v9.csv",
            matching_scope="4 controller + 8 ablation rows; archived, not a fresh seed extension",
            interpretation="Positive behavior is attributable to the executed feedback correction in this branch, not to raw planner authority; 100% replacement prevents a clean raw-planner attribution.",
            distance_key="final_distance",
        ),
        row(
            factor="feedback_source",
            condition="semantic_oracle_fixed_target",
            runs=oracle,
            seeds="45,46,47,48,49,50",
            target_reference="fixed red moon",
            feedback_source="privileged simulator state",
            planner_authority="semantic state-feedback law; N_raw=0",
            selection_success="fixed-by-design",
            control_success=success_count(oracle),
            joint_success=success_count(oracle),
            evidence="supplement_v9_sanitized/data/revision_20260922/semantic_oracle_feedback_runs_v9.csv",
            matching_scope="six fixed-target repeats",
            interpretation="Oracle state is sufficient for this semantic-control baseline under the project tolerance; it does not test visual estimation.",
        ),
        row(
            factor="feedback_source",
            condition="semantic_visual_fixed_target",
            runs=visual,
            seeds="45,46,47,48,49,50",
            target_reference="fixed red moon",
            feedback_source="detector/tracker visual estimate",
            planner_authority="semantic state-feedback law; N_raw=0",
            selection_success="fixed-by-design",
            control_success=success_count(visual),
            joint_success=success_count(visual),
            paired_gap=paired_gap,
            paired_gap_sd=paired_gap_sd,
            evidence="supplement_v9_sanitized/data/revision_20260922/visual_feedback_runs_v9.csv",
            matching_scope="paired by seed with semantic_oracle_fixed_target; visual path only",
            interpretation="Replacing oracle state with the implemented visual estimate changes 6/6 successes to 0/6; paired final-distance gap is visual minus oracle.",
        ),
        row(
            factor="target_grounding",
            condition="language_instruction_codex_repeat",
            runs=language_repeats,
            seeds="42,43,44",
            target_reference="three independent natural-language instructions",
            feedback_source="privileged simulator state",
            planner_authority="semantic state-feedback law; N_raw=0",
            selection_success=success_count(language_repeats, "selection_match"),
            control_success=success_count(language_repeats),
            joint_success=success_count(language_repeats),
            evidence="supplement_v9_sanitized/data/revision_20260923/language_instruction_repeat_runs_v9.csv; language_instruction_repeat_aggregate_v9.csv",
            matching_scope="3 instruction cases x 3 seeds; Codex gpt-5.5; strict no-cache",
            interpretation="Independent language requests select the specified object and complete the selected-target control in all nine runs; this is still a small simulator audit, not broad language generalization.",
        ),
        row(
            factor="target_grounding",
            condition="target_image_matrix",
            runs=target_runs,
            seeds="42,43,44",
            target_reference="three target-image crops",
            feedback_source="privileged simulator state",
            planner_authority="semantic state-feedback law; N_raw=0",
            selection_success=f"{target_overall['semantic_correct']}/9",
            control_success=target_overall["active_control_successes"] + "/9",
            joint_success=target_overall["joint_active_successes"] + "/9",
            evidence="supplement_v9_sanitized/data/revision_20260922/target_image_matrix_runs_v9.csv; target_image_matrix_aggregate_v9.csv",
            matching_scope="3 target cases x 3 seeds; all active",
            interpretation="The retained yellow-pentagon semantic miss produces the only joint failure; this isolates target grounding as a separate failure surface from oracle execution.",
        ),
    ]

    fields = list(rows[0].keys())
    with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Root-Cause Ablation (v1.0.7)",
        "",
        "This table factorizes the observed failure boundary using already completed, sanitized runs. It is an attribution aid, not a claim of exhaustive causal identification.",
        "",
        "- `execution_authority`: raw planner versus archived grounded execution; the grounded branch records 23/23 action replacements in every run.",
        "- `feedback_source`: six fixed-target seeds are paired by seed between simulator-state and detector/tracker feedback.",
        "- `target_grounding`: the independent Codex language-repeat matrix and target-image matrix hold the semantic controller and privileged execution path fixed while retaining explicit selection outcomes.",
        "- `planner_tuning`: the archived budget/cost sweep tests whether common raw-planner settings rescue the negative reproduction.",
        "",
        "The paired feedback runs use `controller_variant=semantic_mpc`, fixed target `red moon`, seeds 45--50, `max_traj_length=45`, `num_samples=10`, `plan_freq=2`, semantic parameters `(contact_offset, clearance, move_step, push_step)=(0.06, 0.12, 0.06, 0.075)`, success distance 0.08, and strict no-cache mode. The only intended factor change is `feedback_source=oracle` versus `feedback_source=visual`. Because the target is supplied explicitly, this pair isolates low-level state feedback and does not exercise Codex target parsing.",
        "",
        f"The paired visual gap is defined as `final_world_distance(visual) - final_world_distance(oracle)` for the same seed; positive values indicate worse visual-feedback distance. All {sum(gap > 0 for gap in paired_gaps)}/{len(paired_gaps)} paired visual runs have a larger final distance (range {min(paired_gaps):.4f}--{max(paired_gaps):.4f}). Archived grounded rows are intentionally labelled as historical protocol evidence and are not pooled with the fresh raw seed sweep.",
        "",
        "| factor | condition | n | success | mean final world distance | sample SD | paired gap vs oracle | paired gap SD | matching scope |",
        "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    item["factor"],
                    item["condition"],
                    item["n"],
                    item["joint_success"] if item["joint_success"] != "N/A" else item["control_success"],
                    item["mean_final_world_distance"],
                    item["sample_sd_final_world_distance"],
                    item["paired_gap_vs_oracle"] or "-",
                    item["paired_gap_sample_sd"] or "-",
                    item["matching_scope"],
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The strongest controlled comparison is the paired oracle-versus-visual row: the same fixed target and seeds retain 6/6 oracle successes but produce 0/6 visual-feedback successes. The independent Codex language-repeat matrix is 9/9 for selection and joint control, while the target-image matrix separately retains an 8/9 semantic-and-control result with one known target-selection error. Together with 0/16 raw-MPC success and 23/23 grounded action replacement, these results localize the current boundary to execution-state estimation and semantic grounding rather than proving a single universal root cause.",
            "",
            "The table does not establish real-robot transfer, broad task generalization, or a causal benefit from event re-query. Those claims require new matched experiments.",
        ]
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT_CSV}")
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
