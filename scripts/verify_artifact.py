#!/usr/bin/env python3
import csv
import hashlib
import statistics
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
errors = []


def read_csv(relative_path):
    with (ROOT / relative_path).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def check(condition, message):
    if not condition:
        errors.append(message)


semantic_path = "data/semantic_mpc_authoritative_runs_v8.csv"
semantic = read_csv(semantic_path)
semantic_distances = [float(row["final_target_world_distance"]) for row in semantic]
check(len(semantic_distances) == 18, "Semantic MPC authoritative file must contain 18 rows")
check(sum(value <= 0.05 for value in semantic_distances) == 3, "Semantic MPC 0.05 count must be 3/18")
check(sum(value <= 0.08 for value in semantic_distances) == 18, "Semantic MPC 0.08 count must be 18/18")
check(abs(statistics.mean(semantic_distances) - 0.0641187511177527) < 1e-12, "Semantic MPC mean mismatch")
check(abs(statistics.stdev(semantic_distances) - 0.0150250791979494) < 1e-12, "Semantic MPC sample SD mismatch")

thresholds = read_csv("data/threshold_sensitivity_v8.csv")
semantic_thresholds = {
    row["threshold"]: row["success"]
    for row in thresholds
    if row["suite"] == "Semantic MPC"
}
check(semantic_thresholds == {"0.05": "3/18", "0.08": "18/18", "0.10": "18/18"}, "Threshold table does not match authoritative Semantic MPC runs")
check(
    all(
        row["authoritative_source"] == semantic_path
        for row in thresholds
        if row["suite"] == "Semantic MPC"
    ),
    "Semantic MPC threshold rows must name the authoritative source",
)

archived = read_csv("data/archived_nonsemantic_branch_runs_v8.csv")
check(all(row["suite"] != "Semantic MPC" for row in archived), "Archived nonsemantic file contains Semantic MPC rows")

conditions = read_csv("supplement_v8_sanitized/data/semantic_mpc_condition_statistics_v8.csv")
all_runs = next((row for row in conditions if row["condition"] == "all_authoritative_runs"), None)
check(all_runs is not None, "Missing all_authoritative_runs condition row")
if all_runs:
    check(all_runs["n"] == "18", "Condition summary n must be 18")
    check(all_runs["mean_final_world_distance"] == "0.064119", "Condition summary mean mismatch")
    check(all_runs["sample_sd_final_world_distance"] == "0.015025", "Condition summary sample SD mismatch")
    check(all_runs["success_005"] == "3/18", "Condition summary 0.05 count mismatch")
    check(all_runs["success_008"] == "18/18", "Condition summary 0.08 count mismatch")

target_matrix = read_csv("supplement_v8_sanitized/data/revision_20260919/target_image_matrix_runs_v8.csv")
check(len(target_matrix) == 9, "Target-image matrix must contain nine runs")
check(sum(row["semantic_match"] == "True" for row in target_matrix) == 8, "Target-image semantic count must be 8/9")
check(sum(row["pre_satisfied"] == "True" for row in target_matrix) == 1, "Target-image matrix must contain one pre-satisfied run")
active = [row for row in target_matrix if row["pre_satisfied"] != "True"]
check(len(active) == 8, "Target-image active denominator must be eight")
check(sum(row["joint_active_success"] == "True" for row in active) == 7, "Target-image joint active count must be 7/8")

fault = read_csv("supplement_v8_sanitized/data/revision_20260919/event_fault_recovery_runs_v8.csv")
treatment = [row for row in fault if row["case"] == "with_synthetic_requery"]
control = [row for row in fault if row["case"] == "no_requery"]
check(sum(row["semantic_recovered"] == "True" for row in treatment) == 3, "Synthetic re-query repair count must be 3/3")
check(sum(row["task_success"] == "True" for row in treatment) == 2, "Synthetic re-query true-target success must be 2/3")
check(sum(row["task_success"] == "True" for row in control) == 0, "No-requery control success must be 0/3")

matched = read_csv("supplement_v8_sanitized/data/revision_20260919/event_matched_controls_revision_v8.csv")
for seed in ("45", "46", "47"):
    rows = [row for row in matched if row["seed"] == seed]
    check(len(rows) == 2, f"Matched natural-event controls missing seed {seed}")
    if len(rows) == 2:
        check(rows[0]["final_distance"] == rows[1]["final_distance"], f"Natural-event final distances differ for seed {seed}")

manifest = read_csv("supplement_v8_sanitized/data/code_manifest_v8.csv")
for row in manifest:
    path = ROOT / row["relative_path"]
    check(path.is_file(), f"Missing public source snapshot: {row['relative_path']}")
    if path.is_file():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        check(digest == row["public_snapshot_sha256"], f"Public snapshot hash mismatch: {row['relative_path']}")
    if row["relationship"] == "byte-identical":
        check(
            row["executed_source_sha256"] == row["public_snapshot_sha256"],
            f"Byte-identical source hashes differ: {row['relative_path']}",
        )

legacy_files = [
    "data/historical_threshold_sensitivity.csv",
    "data/historical_unmodified_grounded_per_run_results.csv",
    "data/latest_semantic_suite_summary.csv",
    "data/opening_report_complete_summary_20260620_173545.csv",
    "data/checkpoint_and_code_manifest_v4.csv",
    "supplement_v8_sanitized/data/condition_statistics_v7.csv",
    "supplement_v8_sanitized/data/event_requery_controls_20260620_180646.csv",
]
for relative_path in legacy_files:
    check(not (ROOT / relative_path).exists(), f"Superseded or empty file still present: {relative_path}")

for path in ROOT.rglob("*"):
    if path.is_file() and path.suffix.lower() in {".csv", ".json", ".md", ".py"}:
        check(path.stat().st_size > 0, f"Zero-byte artifact: {path.relative_to(ROOT)}")

if errors:
    print("ARTIFACT VERIFICATION FAILED")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)

print("ARTIFACT VERIFICATION PASSED")
print("Semantic MPC: n=18, mean=0.064119, sample SD=0.015025, 3/18 at 0.05, 18/18 at 0.08")
print("Target-image matrix: 8/9 semantic matches, 7/8 joint active successes")
print("Semantic-fault audit: 3/3 repairs, 2/3 treatment successes, 0/3 control successes")
print(f"Source snapshot hashes verified: {len(manifest)} files")
