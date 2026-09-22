#!/usr/bin/env python3
"""Import the 2026-09-22 live experiment outputs into a portable package.

The source root is supplied at runtime. Machine-local paths, credentials, and
raw service configuration are intentionally excluded from the exported CSVs.
"""

from __future__ import annotations

import argparse
import csv
import shutil
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SUPPLEMENT = ROOT / "supplement_v9_sanitized" / "data" / "revision_20260922"
ROBUSTNESS_OUTPUT = ROOT / "supplement_v9_sanitized" / "data" / "robustness_edge_audit"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def truth(value: str) -> bool:
    return value.strip().lower() == "true"


def normalized_target(value: str) -> str:
    return " ".join(value.strip().lower().split())


def resolve_source_path(source: Path, value: str) -> Path:
    path = Path(value)
    return (source / path).resolve() if not path.is_absolute() else path.resolve()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument(
        "--event-result-dir",
        type=Path,
        default=Path("stage_experiments/live_event_requery_controls_20260922/20260922_122054"),
        help="Relative or absolute result directory containing event_requery_controls.csv.",
    )
    args = parser.parse_args()
    source = args.source_root.resolve()

    opening = read_csv(
        source / "live_opening_report_complete_20260922" / "20260922_112519" / "summary.csv"
    )
    opening_fields = [
        "status", "suite", "name", "mode", "seed", "request_type",
        "instruction_evaluable", "requested_target_object", "selected_target_object",
        "evaluation_target_object", "overall_success", "target_success",
        "initial_target_world_distance", "final_target_world_distance",
        "target_world_distance_delta", "success_distance_world",
        "num_steps_executed", "runtime_seconds_total", "mean_step_duration",
        "semantic_policy_calls", "subtask_requests", "interactive_object_requests",
        "event_requeries", "target_image_selector", "target_image_selection_rule",
        "semantic_contact_offset", "semantic_clearance", "semantic_move_step",
        "semantic_push_step", "error",
    ]
    semantic_rows: list[dict[str, object]] = []
    for row in opening:
        exported = dict(row)
        is_scene_selection = row.get("mode") == "vlm_scene" or row.get("name") == "vlm_scene_selection"
        request_type = {
            "fixed": "fixed_target",
            "instruction": "language_instruction",
            "target_image": "target_image",
            "vlm_scene": "scene_selection",
        }.get(row.get("mode", ""), "diagnostic")
        exported["request_type"] = request_type
        exported["instruction_evaluable"] = str(not is_scene_selection)
        exported["requested_target_object"] = "" if is_scene_selection else row.get("requested_target_object", "")
        exported["evaluation_target_object"] = row.get("selected_target_object", "")
        requested = normalized_target(row.get("requested_target_object", ""))
        selected = normalized_target(row.get("selected_target_object", ""))
        if not is_scene_selection and requested and selected:
            matches = requested == selected
            exported["requested_selected_match"] = str(matches)
            exported["instruction_joint_success"] = str(matches and truth(row["target_success"]))
        else:
            exported["requested_selected_match"] = ""
            exported["instruction_joint_success"] = ""
        exported["control_success_reference"] = "selected_target"
        exported["scene_selection_control_success"] = (
            str(truth(row["target_success"])) if is_scene_selection else ""
        )
        semantic_rows.append(exported)
    semantic_fields = opening_fields + [
        "requested_selected_match",
        "instruction_joint_success",
        "control_success_reference",
        "scene_selection_control_success",
    ]
    write_csv(DATA / "semantic_mpc_live_runs_v9.csv", semantic_fields, semantic_rows)

    conditions: list[dict[str, object]] = []
    for condition in ("input_forms", "multi_target", "multi_seed", "semantic_ablation"):
        condition_rows = [
            row for row in semantic_rows if row["suite"] == condition
        ]
        values = [
            float(row["final_target_world_distance"])
            for row in condition_rows
        ]
        evaluable_rows = [row for row in condition_rows if row["instruction_evaluable"] == "True"]
        scene_rows = [row for row in condition_rows if row["request_type"] == "scene_selection"]
        conditions.append(
            {
                "condition": condition,
                "n": len(values),
                "mean_final_world_distance": f"{statistics.mean(values):.6f}",
                "sample_sd_final_world_distance": f"{statistics.stdev(values):.6f}",
                "success_005": f"{sum(value <= 0.05 for value in values)}/{len(values)}",
                "success_008": f"{sum(value <= 0.08 for value in values)}/{len(values)}",
                "instruction_evaluable_n": len(evaluable_rows),
                "scene_selection_n": len(scene_rows),
                "requested_selected_match": f"{sum(row['requested_selected_match'] == 'True' for row in evaluable_rows)}/{len(evaluable_rows)}" if evaluable_rows else "N/A",
                "instruction_joint_success": f"{sum(row['instruction_joint_success'] == 'True' for row in evaluable_rows)}/{len(evaluable_rows)}" if evaluable_rows else "N/A",
                "scene_selection_control_success": f"{sum(row['scene_selection_control_success'] == 'True' for row in scene_rows)}/{len(scene_rows)}" if scene_rows else "N/A",
            }
        )
    values = [float(row["final_target_world_distance"]) for row in opening]
    evaluable_rows = [row for row in semantic_rows if row["instruction_evaluable"] == "True"]
    scene_rows = [row for row in semantic_rows if row["request_type"] == "scene_selection"]
    conditions.append(
        {
            "condition": "all_live_runs",
            "n": len(values),
            "mean_final_world_distance": f"{statistics.mean(values):.6f}",
            "sample_sd_final_world_distance": f"{statistics.stdev(values):.6f}",
            "success_005": f"{sum(value <= 0.05 for value in values)}/{len(values)}",
            "success_008": f"{sum(value <= 0.08 for value in values)}/{len(values)}",
            "instruction_evaluable_n": len(evaluable_rows),
            "scene_selection_n": len(scene_rows),
            "requested_selected_match": f"{sum(row['requested_selected_match'] == 'True' for row in evaluable_rows)}/{len(evaluable_rows)}",
            "instruction_joint_success": f"{sum(row['instruction_joint_success'] == 'True' for row in evaluable_rows)}/{len(evaluable_rows)}",
            "scene_selection_control_success": f"{sum(row['scene_selection_control_success'] == 'True' for row in scene_rows)}/{len(scene_rows)}" if scene_rows else "N/A",
        }
    )
    write_csv(
        SUPPLEMENT / "semantic_mpc_condition_statistics_v9.csv",
        [
            "condition", "n", "mean_final_world_distance",
            "sample_sd_final_world_distance", "success_005", "success_008",
            "instruction_evaluable_n", "scene_selection_n",
            "requested_selected_match", "instruction_joint_success",
            "scene_selection_control_success",
        ],
        conditions,
    )

    raw = read_csv(
        source / "rerun_20260922_core_multiseed" / "20260922_025958"
        / "combined_four_seed_summary.csv"
    )
    write_csv(DATA / "raw_controller_multiseed_v9.csv", list(raw[0]), raw)

    raw_runs: list[dict[str, object]] = []
    multiseed_root = (
        source / "rerun_20260922_core_multiseed" / "20260922_025958" / "per_seed"
    )
    for result_dir in sorted(path for path in multiseed_root.iterdir() if path.is_dir()):
        for row in read_csv(result_dir / "summary.csv"):
            raw_runs.append(
                {
                    "seed": row["tag"].split("_s", 1)[1].split("_", 1)[0],
                    "controller_variant": row["controller_variant"],
                    "target_success": row["target_success"],
                    "final_target_world_distance": row["final_target_world_distance"],
                    "final_target_pixel_distance": row["final_target_distance"],
                    "num_steps_executed": row["num_steps_executed"],
                    "runtime_seconds_total": row["runtime_seconds_total"],
                    "plan_calls": row["plan_calls"],
                }
            )
    seed48 = read_csv(source / "rerun_20260922_core" / "20260922_023034" / "summary.csv")
    for row in seed48:
        raw_runs.append(
            {
                "seed": "48",
                "controller_variant": row["controller_variant"],
                "target_success": row["target_success"],
                "final_target_world_distance": row["final_target_world_distance"],
                "final_target_pixel_distance": row["final_target_distance"],
                "num_steps_executed": row["num_steps_executed"],
                "runtime_seconds_total": row["runtime_seconds_total"],
                "plan_calls": row["plan_calls"],
            }
        )
    raw_run_fields = [
        "seed", "controller_variant", "target_success",
        "final_target_world_distance", "final_target_pixel_distance",
        "num_steps_executed", "runtime_seconds_total", "plan_calls",
    ]
    write_csv(DATA / "raw_controller_multiseed_runs_v9.csv", raw_run_fields, raw_runs)

    target_runs = read_csv(
        source / "live_target_image_matrix_20260922" / "20260922_114159" / "runs.csv"
    )
    target_fields = [
        "status", "case", "expected_object", "seed", "selected_object",
        "semantic_match", "pre_satisfied", "terminal_threshold_satisfied",
        "active_control_success", "joint_active_success", "selection_rule",
        "initial_target_world_distance", "final_target_world_distance",
        "num_steps_executed", "runtime_seconds_total", "error",
    ]
    write_csv(SUPPLEMENT / "target_image_matrix_runs_v9.csv", target_fields, target_runs)
    target_aggregate = read_csv(
        source / "live_target_image_matrix_20260922" / "20260922_114159" / "aggregate.csv"
    )
    write_csv(
        SUPPLEMENT / "target_image_matrix_aggregate_v9.csv",
        list(target_aggregate[0]),
        target_aggregate,
    )

    target_audit = read_csv(
        source / "live_target_image_selection_audit_20260922" / "20260922_113819"
        / "target_image_selection_audit.csv"
    )
    audit_fields = [
        "case", "expected_object", "full_frame_corner_heuristic_choice",
        "full_frame_corner_heuristic_match", "crop_corner_heuristic_choice",
        "crop_visual_match_choice", "vlm_semantic_choice", "vlm_semantic_match",
        "vlm_raw_response", "vlm_error", "crop_corner_heuristic_match",
        "crop_visual_match", "detected_objects_full_frame",
    ]
    write_csv(SUPPLEMENT / "target_image_selection_audit_v9.csv", audit_fields, target_audit)

    event_dir = resolve_source_path(source, str(args.event_result_dir))
    events = read_csv(event_dir / "event_requery_controls.csv")
    event_fields = [
        "status", "case", "description", "seed", "controller_variant",
        "feedback_source", "vlm_model_alias", "vlm_interface", "target_instruction",
        "event_enabled", "event_unblocked_fixed_target", "forced_initial_requery",
        "event_requery_window", "event_requery_min_progress", "event_requery_min_step",
        "semantic_event_requery_window", "semantic_event_requery_min_progress",
        "semantic_event_requery_progress_units",
        "overall_success", "final_target_world_distance", "target_world_distance_delta",
        "runtime_seconds_total", "num_steps_executed", "event_requeries",
        "natural_event_requeries", "requery_reasons", "accepted_subtask_sources",
        "interactive_objects", "cache_hits_in_log", "fresh_vlm_responses_in_log",
        "strict_no_cache_vlm", "error",
    ]
    event_export: list[dict[str, object]] = []
    for row in events:
        exported = dict(row)
        exported["vlm_model_alias"] = "gpt-5.5"
        exported["vlm_interface"] = "responses-compatible"
        event_export.append(exported)
    write_csv(SUPPLEMENT / "event_requery_controls_v9.csv", event_fields, event_export)

    event_summary: list[dict[str, object]] = []
    for case in (
        "matched_no_event_instruction",
        "matched_event_instruction",
        "scene_forced_requery_audit",
    ):
        rows = [row for row in events if row["case"] == case]
        distances = [float(row["final_target_world_distance"]) for row in rows]
        event_summary.append(
            {
                "condition": case,
                "n": len(rows),
                "success_008": f"{sum(truth(row['overall_success']) for row in rows)}/{len(rows)}",
                "natural_requeries": f"{sum(int(row['natural_event_requeries']) > 0 for row in rows)}/{len(rows)}",
                "mean_final_world_distance": f"{statistics.mean(distances):.6f}",
                "sample_sd_final_world_distance": f"{statistics.stdev(distances):.6f}",
                "min_final": f"{min(distances):.6f}",
                "max_final": f"{max(distances):.6f}",
                "cache_hits": sum(int(row["cache_hits_in_log"]) for row in rows),
                "fresh_vlm_responses": sum(int(row["fresh_vlm_responses_in_log"]) for row in rows),
                "semantic_event_requery_window": rows[0].get("semantic_event_requery_window", ""),
                "semantic_event_requery_min_progress": rows[0].get("semantic_event_requery_min_progress", ""),
                "semantic_event_requery_progress_units": rows[0].get("semantic_event_requery_progress_units", ""),
            }
        )
    write_csv(SUPPLEMENT / "event_requery_statistics_v9.csv", list(event_summary[0]), event_summary)

    visual = read_csv(
        source / "rerun_20260922_visual_feedback" / "20260922_013901" / "summary.csv"
    )
    visual_fields = [
        "status", "seed", "target_object", "overall_success", "target_success",
        "initial_target_world_distance", "final_target_world_distance",
        "target_world_distance_delta", "num_steps_executed", "runtime_seconds_total",
        "mean_step_duration", "visual_detection_fallbacks", "collision_proxy_events",
        "interference_proxy_events", "min_target_obstacle_distance",
        "min_effector_non_target_distance", "error",
    ]
    write_csv(SUPPLEMENT / "visual_feedback_runs_v9.csv", visual_fields, visual)
    distances = [float(row["final_target_world_distance"]) for row in visual]
    visual_summary = [
        {
            "condition": "detector_tracker_visual_feedback",
            "n": len(visual),
            "success_008": f"{sum(truth(row['overall_success']) for row in visual)}/{len(visual)}",
            "mean_final_world_distance": f"{statistics.mean(distances):.6f}",
            "sample_sd_final_world_distance": f"{statistics.stdev(distances):.6f}",
            "min_final": f"{min(distances):.6f}",
            "max_final": f"{max(distances):.6f}",
        }
    ]
    write_csv(SUPPLEMENT / "visual_feedback_statistics_v9.csv", list(visual_summary[0]), visual_summary)

    # Derive one threshold table from the portable run-level sources.  This
    # keeps the figure, manuscript, and verifier on the same numerical path.
    archived = read_csv(DATA / "archived_nonsemantic_branch_runs_v8.csv")
    threshold_sources = [
        ("Fresh raw MPC", raw_runs, "final_target_world_distance", "data/raw_controller_multiseed_runs_v9.csv"),
        ("Archived ablation", [r for r in archived if r["suite"] == "Unmodified ablation"], "final_distance", "data/archived_nonsemantic_branch_runs_v8.csv"),
        ("Grounded diagnostics", [r for r in archived if r["suite"] in {"Grounded controller", "Grounded ablation"}], "final_distance", "data/archived_nonsemantic_branch_runs_v8.csv"),
        ("Semantic MPC", opening, "final_target_world_distance", "data/semantic_mpc_live_runs_v9.csv"),
        ("Target image", target_runs, "final_target_world_distance", "supplement_v9_sanitized/data/revision_20260922/target_image_matrix_runs_v9.csv"),
        ("Visual feedback", visual, "final_target_world_distance", "supplement_v9_sanitized/data/revision_20260922/visual_feedback_runs_v9.csv"),
    ]
    threshold_rows: list[dict[str, object]] = []
    for suite, rows, column, source_path in threshold_sources:
        distances = [float(row[column]) for row in rows]
        for threshold in (0.05, 0.08, 0.10):
            count = sum(distance <= threshold for distance in distances)
            threshold_rows.append(
                {
                    "suite": suite,
                    "threshold": f"{threshold:.2f}",
                    "success": f"{count}/{len(distances)}",
                    "success_rate": f"{count / len(distances):.6f}",
                    "authoritative_source": source_path,
                }
            )
    write_csv(
        DATA / "threshold_sensitivity_v9.csv",
        ["suite", "threshold", "success", "success_rate", "authoritative_source"],
        threshold_rows,
    )

    # Export the archived detector-level robustness audit without leaking the
    # original machine-local paths.  The four perturbation images are small,
    # static inputs and are copied into the portable supplement so each CSV
    # image reference resolves inside the release artifact.
    robustness_source_dir = source / "robustness_edge_audit" / "20260606_203525"
    robustness_rows = read_csv(robustness_source_dir / "robustness_edge_audit.csv")
    ROBUSTNESS_OUTPUT.mkdir(parents=True, exist_ok=True)
    robustness_export: list[dict[str, object]] = []
    for row in robustness_rows:
        exported = dict(row)
        image_name = Path(row.get("image_path", "")).name if row.get("image_path") else ""
        if image_name:
            source_image = robustness_source_dir / image_name
            destination = ROBUSTNESS_OUTPUT / image_name
            if not source_image.is_file():
                raise FileNotFoundError(source_image)
            shutil.copy2(source_image, destination)
            exported["portable_image_path"] = (
                f"supplement_v9_sanitized/data/robustness_edge_audit/{image_name}"
            )
        else:
            exported["portable_image_path"] = ""
        exported["source_record"] = "archived_robustness_edge_audit_20260606_203525"
        exported.pop("image_path", None)
        robustness_export.append(exported)
    robustness_fields = [
        "case", "status", "target_object", "target_detected", "target_confidence",
        "visible_objects", "portable_image_path", "interpretation", "source_record",
    ]
    write_csv(DATA / "robustness_edge_audit_v9.csv", robustness_fields, robustness_export)

    print(f"Imported {len(opening)} semantic, {len(target_runs)} target-image, "
          f"{len(events)} event, and {len(visual)} visual-feedback rows.")


if __name__ == "__main__":
    main()
