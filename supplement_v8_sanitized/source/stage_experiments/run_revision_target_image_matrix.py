"""Run repeated end-to-end target-image controls for the revision audit."""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parents[2]
AUDIT_ROOT = PROJECT_ROOT / "stage_experiments" / "target_image_selection_audit" / "20260620_164822"
TARGET_CASES = [
    ("red_moon", "red moon", AUDIT_ROOT / "red_moon_init_crop.png"),
    ("blue_cube", "blue cube", AUDIT_ROOT / "blue_cube_init_crop.png"),
    ("yellow_pentagon", "yellow pentagon", AUDIT_ROOT / "yellow_pentagon_init_crop.png"),
]


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser("Run revision target-image matrix.")
    parser.add_argument("--python_bin", default=sys.executable)
    parser.add_argument("--checkpoint_file", default=str(WORKSPACE_ROOT / "dmvfn_221.pkl"))
    parser.add_argument("--det_path", default=str(WORKSPACE_ROOT / "detector_checkpoint.pt"))
    parser.add_argument(
        "--tracker_config",
        default=str(PROJECT_ROOT / "pysot_tracker" / "pysot" / "core" / "config.py"),
    )
    parser.add_argument("--tracker_model", default=str(WORKSPACE_ROOT / "model.pth"))
    parser.add_argument("--vlm_backend", choices=["codex", "openai"], default="openai")
    parser.add_argument("--openai_base_url", default=os.environ.get("VLMPC_OPENAI_BASE_URL"))
    parser.add_argument("--openai_model", default=os.environ.get("VLMPC_OPENAI_MODEL", "gpt-5.5"))
    parser.add_argument("--openai_wire_api", choices=["chat", "responses"], default="responses")
    parser.add_argument("--openai_api_key_env", default="VLMPC_OPENAI_API_KEY")
    parser.add_argument("--openai_timeout", type=int, default=600)
    parser.add_argument("--seeds", nargs="+", type=int, default=[45, 46, 47])
    parser.add_argument("--target_image_selector", choices=["auto", "vlm", "vision"], default="vlm")
    parser.add_argument("--max_traj_length", type=int, default=45)
    parser.add_argument("--success_distance_world", type=float, default=0.08)
    parser.add_argument("--log_root", default=str(PROJECT_ROOT / "logs" / "revision_target_image_matrix_20260918"))
    parser.add_argument(
        "--result_root",
        default=str(PROJECT_ROOT / "stage_experiments" / "revision_target_image_matrix"),
    )
    parser.add_argument("--continue_on_error", action="store_true")
    return parser.parse_args()


def find_new_run_dir(log_root: Path, tag: str, before: set[Path]) -> Path:
    candidates = sorted(
        (path.resolve() for path in log_root.glob(f"{tag}_*") if path.is_dir()),
        key=lambda path: path.stat().st_mtime,
    )
    for candidate in reversed(candidates):
        if candidate not in before:
            return candidate
    raise FileNotFoundError(f"No new run directory found for {tag}")


def build_command(args: argparse.Namespace, expected: str, image_path: Path, seed: int) -> list[str]:
    command = [
        str(Path(args.python_bin).resolve()),
        str(PROJECT_ROOT / "main.py"),
        "--checkpoint_file", str(Path(args.checkpoint_file).resolve()),
        "--det_path", str(Path(args.det_path).resolve()),
        "--tracker_config", str(Path(args.tracker_config).resolve()),
        "--tracker_model", str(Path(args.tracker_model).resolve()),
        "--vlm_backend", args.vlm_backend,
        "--openai_model", args.openai_model,
        "--openai_wire_api", args.openai_wire_api,
        "--openai_api_key_env", args.openai_api_key_env,
        "--openai_timeout", str(args.openai_timeout),
        "--task", "push_corner",
        "--seed", str(seed),
        "--zoom", "0.03",
        "--action_horizon", "20",
        "--history_rate", "0.5",
        "--ratio_tar_obj", "0.5",
        "--num_samples", "10",
        "--plan_freq", "2",
        "--max_traj_length", str(args.max_traj_length),
        "--success_distance_world", str(args.success_distance_world),
        "--controller_variant", "semantic_mpc",
        "--feedback_source", "oracle",
        "--semantic_contact_offset", "0.06",
        "--semantic_clearance", "0.12",
        "--semantic_move_step", "0.06",
        "--semantic_push_step", "0.075",
        "--target_image", str(image_path.resolve()),
        "--target_image_selector", args.target_image_selector,
        "--evaluation_target_object", expected,
    ]
    if args.openai_base_url:
        command.extend(["--openai_base_url", args.openai_base_url])
    return command


def selection_rule(metrics: dict) -> str | None:
    details = metrics.get("target_image_selection_details") or []
    return details[-1].get("selection_rule") if details else None


def run_case(args: argparse.Namespace, name: str, expected: str, image_path: Path, seed: int) -> dict:
    if not image_path.is_file():
        raise FileNotFoundError(image_path)
    log_root = Path(args.log_root).resolve()
    log_root.mkdir(parents=True, exist_ok=True)
    tag = f"revision_target_image_{name}_seed{seed}"
    before = {path.resolve() for path in log_root.glob(f"{tag}_*") if path.is_dir()}
    command = build_command(args, expected, image_path, seed)
    command.extend(["--tag", tag, "--log_root", str(log_root)])
    print(f"[run] {name} seed={seed}", flush=True)
    subprocess.run(command, cwd=str(PROJECT_ROOT), check=True)
    run_dir = find_new_run_dir(log_root, tag, before)
    metrics_path = run_dir / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    selected = metrics.get("current_interactive_object")
    semantic_match = selected == expected
    initial_distance = metrics.get("initial_target_world_distance")
    terminal_threshold_satisfied = bool(metrics.get("overall_success"))
    steps = int(metrics.get("num_steps_executed") or 0)
    pre_satisfied = (
        initial_distance is not None
        and float(initial_distance) <= args.success_distance_world
    )
    active_control_success = terminal_threshold_satisfied and steps > 0 and not pre_satisfied
    return {
        "status": "ok",
        "case": name,
        "expected_object": expected,
        "target_image": str(image_path.resolve()),
        "seed": seed,
        "selected_object": selected,
        "semantic_match": semantic_match,
        "pre_satisfied": pre_satisfied,
        "terminal_threshold_satisfied": terminal_threshold_satisfied,
        "active_control_success": active_control_success,
        "joint_active_success": semantic_match and active_control_success,
        "selection_rule": selection_rule(metrics),
        "initial_target_world_distance": initial_distance,
        "final_target_world_distance": metrics.get("final_target_world_distance"),
        "num_steps_executed": steps,
        "runtime_seconds_total": metrics.get("runtime_seconds_total"),
        "run_dir": str(run_dir),
        "metrics_path": str(metrics_path),
        "error": "",
    }


def mean_std(values: list[float]) -> tuple[float | None, float | None]:
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return None, None
    return statistics.mean(clean), statistics.stdev(clean) if len(clean) > 1 else 0.0


def aggregate(rows: list[dict]) -> list[dict]:
    groups = [(name, expected) for name, expected, _ in TARGET_CASES] + [("overall", "all")]
    output = []
    for name, expected in groups:
        subset = [row for row in rows if row.get("status") == "ok" and (name == "overall" or row["case"] == name)]
        final_mean, final_std = mean_std([row["final_target_world_distance"] for row in subset])
        active_trials = [row for row in subset if not row["pre_satisfied"]]
        step_mean, step_std = mean_std([row["num_steps_executed"] for row in active_trials])
        count = len(subset)
        active_count = len(active_trials)
        output.append(
            {
                "case": name,
                "expected_object": expected,
                "n": count,
                "semantic_correct": sum(bool(row["semantic_match"]) for row in subset),
                "semantic_accuracy": (sum(bool(row["semantic_match"]) for row in subset) / count) if count else None,
                "pre_satisfied": sum(bool(row["pre_satisfied"]) for row in subset),
                "terminal_threshold_satisfied": sum(bool(row["terminal_threshold_satisfied"]) for row in subset),
                "active_trials": active_count,
                "active_control_successes": sum(bool(row["active_control_success"]) for row in active_trials),
                "active_control_success_rate": (sum(bool(row["active_control_success"]) for row in active_trials) / active_count) if active_count else None,
                "joint_active_successes": sum(bool(row["joint_active_success"]) for row in active_trials),
                "joint_active_success_rate": (sum(bool(row["joint_active_success"]) for row in active_trials) / active_count) if active_count else None,
                "final_distance_mean": final_mean,
                "final_distance_std": final_std,
                "steps_mean": step_mean,
                "steps_std": step_std,
            }
        )
    return output


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def write_markdown(path: Path, rows: list[dict], aggregates: list[dict]) -> None:
    lines = [
        "# Revision Target-Image End-to-End Matrix",
        "",
        "Each run uses a labeled target-object crop, strict VLM target-image matching, and an independent ground-truth object for task evaluation. Task success therefore cannot be obtained by pushing a wrongly selected object.",
        "",
        "| target | seed | selected | semantic | pre-satisfied | active-control success | final distance | steps |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['expected_object']} | {row['seed']} | {row.get('selected_object') or '-'} | "
            f"{row.get('semantic_match')} | {row.get('pre_satisfied')} | {row.get('joint_active_success')} | "
            f"{fmt(row.get('final_target_world_distance'))} | {fmt(row.get('num_steps_executed'))} |"
        )
    lines.extend(["", "## Aggregate", "", "| condition | n | semantic | pre-satisfied | active joint success | final distance mean +/- SD | active-trial steps mean +/- SD |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for item in aggregates:
        lines.append(
            f"| {item['case']} | {item['n']} | {item['semantic_correct']}/{item['n']} | "
            f"{item['pre_satisfied']} | {item['joint_active_successes']}/{item['active_trials']} | "
            f"{fmt(item['final_distance_mean'])} +/- {fmt(item['final_distance_std'])} | "
            f"{fmt(item['steps_mean'])} +/- {fmt(item['steps_std'])} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    args = parse_args()
    result_dir = Path(args.result_root).resolve() / datetime.now().strftime("%Y%m%d_%H%M%S")
    result_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, expected, image_path in TARGET_CASES:
        for seed in args.seeds:
            try:
                rows.append(run_case(args, name, expected, image_path, seed))
            except Exception as exc:
                traceback.print_exc()
                rows.append(
                    {
                        "status": "error", "case": name, "expected_object": expected,
                        "target_image": str(image_path.resolve()), "seed": seed,
                        "selected_object": None, "semantic_match": False, "pre_satisfied": False,
                        "terminal_threshold_satisfied": False, "active_control_success": False,
                        "joint_active_success": False, "selection_rule": None,
                        "initial_target_world_distance": None, "final_target_world_distance": None,
                        "num_steps_executed": None, "runtime_seconds_total": None,
                        "run_dir": None, "metrics_path": None, "error": repr(exc),
                    }
                )
                if not args.continue_on_error:
                    raise
    aggregates = aggregate(rows)
    write_csv(result_dir / "runs.csv", rows)
    write_csv(result_dir / "aggregate.csv", aggregates)
    write_markdown(result_dir / "report.md", rows, aggregates)
    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "model": args.openai_model,
        "wire_api": args.openai_wire_api,
        "strict_no_cache": True,
        "selector": args.target_image_selector,
        "seeds": args.seeds,
        "success_distance_world": args.success_distance_world,
        "rows": rows,
        "aggregates": aggregates,
    }
    (result_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[done] results -> {result_dir}", flush=True)


if __name__ == "__main__":
    main()
