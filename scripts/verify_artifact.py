#!/usr/bin/env python3
"""Verify the portable v1.0.8 evidence package."""
from __future__ import annotations
import csv, hashlib, json, re, statistics, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []
def read_csv(path: str) -> list[dict[str, str]]:
    with (ROOT / path).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))
def check(ok: bool, msg: str) -> None:
    if not ok: errors.append(msg)
def distances(rows, col): return [float(r[col]) for r in rows]

raw = read_csv("data/raw_controller_multiseed_runs_v9.csv")
rd = distances(raw, "final_target_world_distance")
check(len(raw) == 16, "raw sweep must contain 16 rows")
check(set(r["seed"] for r in raw) == {"45", "46", "47", "48"}, "raw seeds must be 45--48")
check(sum(r["target_success"] == "True" for r in raw) == 0, "raw success must be 0/16")
check(abs(statistics.mean(rd) - 0.32447217032313347) < 1e-12, "raw mean mismatch")
check(abs(statistics.stdev(rd) - 0.10846493708119562) < 1e-12, "raw SD mismatch")
for v in ("baseline", "improved", "literature", "literature_v2"):
    vr = [r for r in raw if r["controller_variant"] == v]
    check(len(vr) == 4 and sum(r["target_success"] == "True" for r in vr) == 0, f"raw variant {v} mismatch")

semantic = read_csv("data/semantic_mpc_live_runs_v9.csv")
sd = distances(semantic, "final_target_world_distance")
check(len(semantic) == 18, "semantic suite must contain 18 rows")
check(sum(x <= .05 for x in sd) == 3 and sum(x <= .08 for x in sd) == 18, "semantic threshold counts mismatch")
check(abs(statistics.mean(sd) - 0.0641187511177527) < 1e-12, "semantic mean mismatch")
check(abs(statistics.stdev(sd) - 0.0150250791979494) < 1e-12, "semantic SD mismatch")
instruction_rows = [r for r in semantic if r.get("instruction_evaluable") == "True"]
fixed_rows = [r for r in semantic if r.get("evaluation_scope") == "fixed_target_control"]
target_image_rows = [r for r in semantic if r.get("evaluation_scope") == "target_image_selected_target_control"]
scene_rows = [r for r in semantic if r.get("request_type") == "scene_selection"]
check(len(instruction_rows) == 1, "semantic instruction-evaluable subset must contain exactly the language-instruction row")
check(len(fixed_rows) == 15, "semantic fixed-target control subset must contain 15 rows")
check(len(target_image_rows) == 1, "semantic target-image control subset must contain one row")
check(len(scene_rows) == 1, "semantic suite must contain one free scene-selection row")
check(all(r.get("evaluation_scope") == "language_instruction" and r.get("request_type") == "language_instruction" for r in instruction_rows), "instruction scope label mismatch")
check(all(r.get("evaluation_scope") == "fixed_target_control" and r.get("request_type") == "fixed_target" for r in fixed_rows), "fixed-target scope label mismatch")
check(all(r.get("evaluation_scope") == "target_image_selected_target_control" and r.get("request_type") == "target_image" for r in target_image_rows), "target-image scope label mismatch")
check(all(r.get("evaluation_scope") == "scene_selection_selected_target_control" for r in scene_rows), "scene-selection scope label mismatch")
check(sum(r.get("requested_selected_match") == "True" for r in instruction_rows) == 1, "language-instruction request-selection match must be 1/1")
check(sum(r.get("instruction_joint_success") == "True" for r in instruction_rows) == 1, "language-instruction joint success must be 1/1")
check(all(r.get("requested_target_object", "").strip().lower() == r.get("selected_target_object", "").strip().lower() for r in fixed_rows), "fixed-target controls must preserve the configured target label")
check(sum(r.get("fixed_target_control_success") == "True" for r in fixed_rows) == 15, "fixed-target control success must be 15/15")
check(sum(r.get("target_success") == "True" for r in target_image_rows) == 1, "semantic target-image selected-target control must be 1/1")
check(all(r.get("requested_selected_match", "") == "" and r.get("instruction_joint_success", "") == "" for r in fixed_rows + target_image_rows + scene_rows), "non-language rows must be N/A for instruction metrics")
check(sum(r.get("scene_selection_control_success") == "True" for r in scene_rows) == 1, "scene-selection control result must be 1/1")
conds = read_csv("supplement_v9_sanitized/data/revision_20260922/semantic_mpc_condition_statistics_v9.csv")
all_live = next((r for r in conds if r["condition"] == "all_live_runs"), None)
check(all_live is not None and all_live["n"] == "18" and all_live["success_005"] == "3/18" and all_live["success_008"] == "18/18" and all_live["instruction_evaluable_n"] == "1" and all_live["scene_selection_n"] == "1" and all_live["fixed_target_n"] == "15" and all_live["fixed_target_control_success"] == "15/15" and all_live["language_instruction_n"] == "1" and all_live["language_instruction_joint_success"] == "1/1" and all_live["target_image_n"] == "1" and all_live["target_image_selected_target_control"] == "1/1" and all_live["requested_selected_match"] == "1/1" and all_live["instruction_joint_success"] == "1/1" and all_live["scene_selection_control_success"] == "1/1", "semantic condition summary mismatch")

thresholds = read_csv("data/threshold_sensitivity_v9.csv")
check(len(thresholds) == 18, "threshold table must contain 18 rows")
sem_thr = {r["threshold"]: r["success"] for r in thresholds if r["suite"] == "Semantic MPC"}
check(sem_thr == {"0.05": "3/18", "0.08": "18/18", "0.10": "18/18"}, "semantic threshold table mismatch")
archived = read_csv("data/archived_nonsemantic_branch_runs_v8.csv")
check(all(r["suite"] != "Semantic MPC" for r in archived), "archived file contains semantic rows")

target = read_csv("supplement_v9_sanitized/data/revision_20260922/target_image_matrix_runs_v9.csv")
check(len(target) == 9 and set(r["seed"] for r in target) == {"42", "43", "44"}, "target matrix size or seeds mismatch")
check(sum(r["semantic_match"] == "True" for r in target) == 8, "target semantic count mismatch")
check(sum(r["pre_satisfied"] == "True" for r in target) == 0, "target matrix has pre-satisfied row")
check(sum(r["joint_active_success"] == "True" for r in target) == 8, "target joint count mismatch")

language_repeats = read_csv("supplement_v9_sanitized/data/revision_20260923/language_instruction_repeat_runs_v9.csv")
check(len(language_repeats) == 9 and set(r["seed"] for r in language_repeats) == {"42", "43", "44"}, "language repeat size or seeds mismatch")
check(all(r["vlm_backend"] == "codex" and r["model"] == "gpt-5.5" for r in language_repeats), "language repeats must use Codex gpt-5.5")
check(sum(r["selection_match"] == "True" for r in language_repeats) == 9, "language repeat selection count mismatch")
check(sum(r["target_success"] == "True" for r in language_repeats) == 9, "language repeat control count mismatch")
check(sum(int(r["cache_hits"]) for r in language_repeats) == 0 and sum(int(r["fresh_vlm_responses"]) for r in language_repeats) == 9, "language repeat cache/response audit mismatch")
language_aggregate = read_csv("supplement_v9_sanitized/data/revision_20260923/language_instruction_repeat_aggregate_v9.csv")
language_all = next((r for r in language_aggregate if r["case"] == "all_cases"), None)
check(language_all is not None and language_all["n"] == "9" and language_all["selection_matches"] == "9/9" and language_all["joint_successes"] == "9/9" and language_all["control_successes_at_threshold"] == "9/9", "language repeat aggregate mismatch")

events = read_csv("supplement_v9_sanitized/data/revision_20260922/event_requery_controls_v9.csv")
no_event = [r for r in events if r["case"] == "matched_no_event_instruction"]
enabled = [r for r in events if r["case"] == "matched_event_instruction"]
forced = [r for r in events if r["case"] == "scene_forced_requery_audit"]
check(len(events) == 9 and len(no_event) == len(enabled) == len(forced) == 3, "event case sizes mismatch")
check(sum(int(r["natural_event_requeries"]) > 0 for r in enabled) == 3 and sum(int(r["natural_event_requeries"]) > 0 for r in no_event) == 0, "event trigger counts mismatch")
check(sum(int(r["cache_hits_in_log"]) for r in events) == 0, "event cache hits are nonzero")
check(all(r.get("semantic_event_requery_window") == "4" and r.get("semantic_event_requery_min_progress") == "0.002" and r.get("semantic_event_requery_progress_units") == "world_distance" for r in events), "event controls do not record the corrected world-distance detector parameters")
for seed in ("42", "43", "44"):
    a = next(r for r in no_event if r["seed"] == seed); b = next(r for r in enabled if r["seed"] == seed)
    check(a["final_target_world_distance"] == b["final_target_world_distance"], f"event final distance differs for seed {seed}")
check(all(r.get("forced_initial_requery") == "True" and int(r["event_requeries"]) >= 1 for r in forced), "forced audit query marker/count mismatch")
event_stats = read_csv("supplement_v9_sanitized/data/revision_20260922/event_requery_statistics_v9.csv")
check(len(event_stats) == 3, "event statistics must contain three separated conditions")
check(all(r.get("semantic_event_requery_window") == "4" and r.get("semantic_event_requery_min_progress") == "0.002" and r.get("semantic_event_requery_progress_units") == "world_distance" for r in event_stats), "event statistics parameter metadata mismatch")

fault = read_csv("supplement_v9_sanitized/data/revision_20260922/event_fault_recovery_runs_v9.csv")
treat = [r for r in fault if r["case"] == "with_synthetic_requery"]
control = [r for r in fault if r["case"] == "no_requery"]
check(len(treat) == len(control) == 3, "fault audit sizes mismatch")
check(sum(r["semantic_recovered"] == "True" for r in treat) == 3 and sum(r["task_success"] == "True" for r in treat) == 2 and sum(r["task_success"] == "True" for r in control) == 0, "fault audit counts mismatch")

codex_fault = read_csv("supplement_v9_sanitized/data/revision_20260923/event_fault_recovery_codex_runs_v9.csv")
codex_treat = [r for r in codex_fault if r["case"] == "fault_with_requery"]
codex_control = [r for r in codex_fault if r["case"] == "fault_no_requery"]
check(len(codex_fault) == 12 and len(codex_treat) == len(codex_control) == 6, "Codex fault audit sizes mismatch")
check(all(r["backend"] == "codex" and r["model"] == "gpt-5.5" for r in codex_fault), "Codex fault audit backend metadata mismatch")
check(sum(r["semantic_recovered"] == "True" for r in codex_treat) == 6 and sum(r["task_success"] == "True" for r in codex_treat) == 5 and sum(r["task_success"] == "True" for r in codex_control) == 0, "Codex fault audit counts mismatch")
check(sum(int(r["cache_hits"]) for r in codex_fault) == 0, "Codex fault audit cache hits are nonzero")

visual = read_csv("supplement_v9_sanitized/data/revision_20260922/visual_feedback_runs_v9.csv")
vd = distances(visual, "final_target_world_distance")
check(len(visual) == 6 and sum(r["overall_success"] == "True" for r in visual) == 0, "visual feedback must be 0/6")
check(abs(statistics.mean(vd) - 0.31604154283801716) < 1e-12, "visual mean mismatch")
check(abs(statistics.stdev(vd) - 0.14392881447322622) < 1e-12, "visual SD mismatch")

robust = read_csv("data/robustness_edge_audit_v9.csv")
check(len(robust) == 7, "robustness edge audit must contain 7 rows")
check(sum(r["status"] == "ok" for r in robust) == 4, "robustness detector cases must be 4/4")
check(sum(r["status"] == "safe_reject" for r in robust) == 3, "robustness unknown-target rejects must be 3/3")
for row in robust:
    image = row.get("portable_image_path", "")
    if image:
        check((ROOT / image).is_file(), f"missing robustness input image: {image}")
robust_manifest_path = ROOT / "supplement_v9_sanitized/data/robustness_edge_audit/manifest_v9.json"
check(robust_manifest_path.is_file(), "missing robustness audit manifest")
if robust_manifest_path.is_file():
    robust_manifest = json.loads(robust_manifest_path.read_text(encoding="utf-8"))
    for image in robust_manifest.get("portable_input_images", []):
        image_path = robust_manifest_path.parent / image["path"]
        check(image_path.is_file(), f"missing robustness manifest image: {image['path']}")
        if image_path.is_file():
            check(hashlib.sha256(image_path.read_bytes()).hexdigest() == image["sha256"], f"robustness image hash mismatch: {image['path']}")

manifest = read_csv("supplement_v9_sanitized/data/code_manifest_v9.csv")
for row in manifest:
    p = ROOT / row["relative_path"]
    check(p.is_file(), f"missing source snapshot: {row['relative_path']}")
    if p.is_file():
        check(hashlib.sha256(p.read_bytes()).hexdigest() == row["public_snapshot_sha256"], f"snapshot hash mismatch: {row['relative_path']}")
    if row["relationship"] == "byte-identical": check(row["executed_source_sha256"] == row["public_snapshot_sha256"], f"byte-identical hash mismatch: {row['relative_path']}")

required = ["figures/final_distance_distribution_v9.pdf", "figures/threshold_sensitivity_v9.pdf", "figures/target_event_audit_v9.pdf", "figures/method_pipeline_v9.pdf", "figures/qualitative_frames_v9.png", "scripts/plot_paper_figures.py", "scripts/import_live_results_v9.py"]
for path in required: check((ROOT / path).is_file(), f"missing artifact: {path}")
for path in ["data/semantic_mpc_authoritative_runs_v8.csv", "data/threshold_sensitivity_v8.csv", "data/event_requery_controls_20260620_180646.csv", "data/target_image_selection_audit_20260620_164822.csv", "supplement_v8_sanitized", "supplement_v9_sanitized/data/revision_20260919", "figures/final_distance_distribution_v5.pdf", "figures/threshold_sensitivity_v5.pdf", "figures/target_event_audit_v5.pdf", "figures/method_pipeline_v7.pdf"]:
    check(not (ROOT / path).exists(), f"superseded artifact still present: {path}")

citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
check("version: 1.0.8" in citation, "CITATION.cff version is not 1.0.8")
check("releases/tag/v1.0.8" in citation, "CITATION.cff must point to the v1.0.8 release URL")

manifest_text = (ROOT / "FINAL_MANIFEST_v9.md").read_text(encoding="utf-8")
marker = "## Complete tracked-file list\n"
check(marker in manifest_text, "final manifest lacks complete tracked-file list")
if marker in manifest_text:
    listed = []
    for line in manifest_text.split(marker, 1)[1].split("\n## ", 1)[0].splitlines():
        if line.startswith("- "):
            listed.append(line[2:].strip())
    ignored_suffixes = {".aux", ".bbl", ".blg", ".fdb_latexmk", ".fls", ".log", ".out", ".synctex.gz"}
    actual = []
    for p in ROOT.rglob("*"):
        if not p.is_file() or ".git" in p.parts or "tmp" in p.parts or "__pycache__" in p.parts:
            continue
        if any(str(p).lower().endswith(s) for s in ignored_suffixes):
            continue
        actual.append(p.relative_to(ROOT).as_posix())
    check(sorted(listed) == sorted(actual), "final manifest does not match the portable file set")
for p in ROOT.rglob("*"):
    if p.is_file() and ".git" not in p.parts and "tmp" not in p.parts and "__pycache__" not in p.parts and p.suffix.lower() in {".csv", ".json", ".md", ".py", ".tex", ".cff"}:
        check(p.stat().st_size > 0, f"zero-byte artifact: {p.relative_to(ROOT)}")
        check(not re.search(r"sk-[A-Za-z0-9]{20,}", p.read_text(encoding="utf-8", errors="ignore")), f"credential-like string: {p.relative_to(ROOT)}")

if errors:
    print("ARTIFACT VERIFICATION FAILED")
    for e in errors: print("-", e)
    sys.exit(1)
print("ARTIFACT VERIFICATION PASSED")
print("Raw MPC: 0/16, mean=0.324472, sample SD=0.108465")
print("Semantic MPC: 3/18 at 0.05, 18/18 selected-target control at 0.08; 1/1 language instruction, 15/15 fixed-target controls, 1 target-image and 1 scene-selection control")
print("Target image: 8/9 semantic, 8/9 joint, no pre-satisfied runs")
print("Events: natural trigger 3/3 enabled under window=4, min_progress=0.002 world distance; matched distances identical, cache hits 0")
print("Visual feedback: 0/6, mean=0.316042, sample SD=0.143929")
print(f"Source snapshot hashes verified: {len(manifest)}")
