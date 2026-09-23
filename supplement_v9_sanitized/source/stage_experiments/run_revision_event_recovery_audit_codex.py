"""Run paired synthetic semantic-fault recovery audits for event re-query."""

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
CASES = [
    {"name": "fault_no_requery", "enable": False, "force_step": -1},
    {"name": "fault_with_requery", "enable": True, "force_step": 3},
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
    parser = argparse.ArgumentParser("Run paired synthetic event-recovery audits.")
    parser.add_argument("--python_bin", default=sys.executable)
    parser.add_argument("--checkpoint_file", default=str(WORKSPACE_ROOT / "dmvfn_221.pkl"))
    parser.add_argument("--det_path", default=str(WORKSPACE_ROOT / "detector_checkpoint.pt"))
    parser.add_argument("--tracker_config", default=str(PROJECT_ROOT / "pysot_tracker" / "pysot" / "core" / "config.py"))
    parser.add_argument("--tracker_model", default=str(WORKSPACE_ROOT / "model.pth"))
    parser.add_argument("--vlm_backend", choices=["codex", "openai"], default="codex")
    parser.add_argument("--codex_home", default=os.environ.get("VLMPC_CODEX_HOME", str(Path.home() / ".codex-vlmpc-eacase")))
    parser.add_argument("--codex_model", default=os.environ.get("VLMPC_CODEX_MODEL", "gpt-5.5"))
    parser.add_argument("--codex_timeout", type=int, default=600)
    parser.add_argument("--openai_base_url", default=os.environ.get("VLMPC_OPENAI_BASE_URL"))
    parser.add_argument("--openai_model", default=os.environ.get("VLMPC_OPENAI_MODEL", "gpt-5.5"))
    parser.add_argument("--openai_wire_api", choices=["chat", "responses"], default="responses")
    parser.add_argument("--openai_api_key_env", default="VLMPC_OPENAI_API_KEY")
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 43, 44, 45, 46, 47])
    parser.add_argument("--true_target", default="red moon")
    parser.add_argument("--fault_target", default="blue cube")
    parser.add_argument("--force_step", type=int, default=3)
    parser.add_argument("--max_traj_length", type=int, default=45)
    parser.add_argument("--log_root", default=str(PROJECT_ROOT / "logs" / "revision_event_recovery_audit_20260918"))
    parser.add_argument("--result_root", default=str(PROJECT_ROOT / "stage_experiments" / "revision_event_recovery_audit"))
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
    raise FileNotFoundError(tag)


def build_command(args: argparse.Namespace, case: dict, seed: int) -> list[str]:
    force_step = args.force_step if case["enable"] else -1
    command = [
        str(Path(args.python_bin).resolve()), str(PROJECT_ROOT / "main.py"),
        "--checkpoint_file", str(Path(args.checkpoint_file).resolve()),
        "--det_path", str(Path(args.det_path).resolve()),
        "--tracker_config", str(Path(args.tracker_config).resolve()),
        "--tracker_model", str(Path(args.tracker_model).resolve()),
        "--vlm_backend", args.vlm_backend,
        "--task", "push_corner", "--seed", str(seed),
        "--zoom", "0.03", "--action_horizon", "20", "--history_rate", "0.5",
        "--ratio_tar_obj", "0.5", "--num_samples", "10", "--plan_freq", "2",
        "--max_traj_length", str(args.max_traj_length), "--success_distance_world", "0.08",
        "--controller_variant", "semantic_mpc", "--feedback_source", "oracle",
        "--semantic_contact_offset", "0.06", "--semantic_clearance", "0.12",
        "--semantic_move_step", "0.06", "--semantic_push_step", "0.075",
        "--target_instruction", f"Please push the {args.true_target} to the reward target corner.",
        "--evaluation_target_object", args.true_target,
        "--audit_initial_target_object", args.fault_target,
        "--audit_force_event_requery_step", str(force_step),
    ]
    if args.vlm_backend == "codex":
        command.extend([
            "--codex_home", str(Path(args.codex_home).expanduser().resolve()),
            "--codex_model", args.codex_model,
            "--codex_timeout", str(args.codex_timeout),
        ])
    else:
        command.extend([
            "--openai_model", args.openai_model,
            "--openai_wire_api", args.openai_wire_api,
            "--openai_api_key_env", args.openai_api_key_env,
            "--openai_timeout", "600",
        ])
        if args.openai_base_url:
            command.extend(["--openai_base_url", args.openai_base_url])
    if case["enable"]:
        command.extend(["--enable_event_vlm_requery", "--event_requery_unblock_fixed_target"])
    return command


def run_case(args: argparse.Namespace, case: dict, seed: int) -> dict:
    log_root = Path(args.log_root).resolve()
    log_root.mkdir(parents=True, exist_ok=True)
    tag = f"revision_event_recovery_{case['name']}_seed{seed}"
    before = {path.resolve() for path in log_root.glob(f"{tag}_*") if path.is_dir()}
    command = build_command(args, case, seed)
    command.extend(["--tag", tag, "--log_root", str(log_root)])
    print(f"[run] {case['name']} seed={seed}", flush=True)
    subprocess.run(command, cwd=str(PROJECT_ROOT), check=True)
    run_dir = find_new_run_dir(log_root, tag, before)
    metrics_path = run_dir / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    triggers = metrics.get("event_requery_triggers") or []
    return {
        "status": "ok", "case": case["name"], "seed": seed,
        "true_target": args.true_target, "injected_fault_target": args.fault_target,
        "event_enabled": case["enable"], "forced_requery_step": args.force_step if case["enable"] else None,
        "final_controller_target": metrics.get("current_interactive_object"),
        "target_sequence": "|".join(metrics.get("interactive_objects", [])),
        "event_requeries": metrics.get("event_requeries"),
        "natural_event_requeries": metrics.get("natural_event_requeries"),
        "trigger_types": "|".join(str(item.get("trigger_type")) for item in triggers),
        "requery_reasons": "|".join(metrics.get("requery_reasons", [])),
        "semantic_recovered": metrics.get("current_interactive_object") == args.true_target,
        "task_success": bool(metrics.get("overall_success")),
        "initial_true_target_distance": metrics.get("initial_target_world_distance"),
        "final_true_target_distance": metrics.get("final_target_world_distance"),
        "num_steps_executed": metrics.get("num_steps_executed"),
        "runtime_seconds_total": metrics.get("runtime_seconds_total"),
        "run_dir": str(run_dir), "metrics_path": str(metrics_path), "error": "",
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def mean_std(values: list[float]) -> tuple[float | None, float | None]:
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return None, None
    return statistics.mean(clean), statistics.stdev(clean) if len(clean) > 1 else 0.0


def aggregate(rows: list[dict]) -> list[dict]:
    output = []
    for case_name in ("fault_no_requery", "fault_with_requery"):
        subset = [row for row in rows if row.get("status") == "ok" and row["case"] == case_name]
        final_mean, final_std = mean_std([row["final_true_target_distance"] for row in subset])
        step_mean, step_std = mean_std([row["num_steps_executed"] for row in subset])
        output.append(
            {
                "case": case_name,
                "n": len(subset),
                "semantic_recoveries": sum(bool(row["semantic_recovered"]) for row in subset),
                "task_successes": sum(bool(row["task_success"]) for row in subset),
                "final_distance_mean": final_mean,
                "final_distance_std": final_std,
                "steps_mean": step_mean,
                "steps_std": step_std,
            }
        )
    return output


def write_report(path: Path, rows: list[dict], aggregates: list[dict]) -> None:
    lines = [
        "# Synthetic Semantic-Fault Event Re-query Audit", "",
        "This is a paired mechanism audit, not a natural-failure benchmark. Each run deliberately replaces the correct initial semantic target with a wrong object. The treatment forces one explicitly labeled synthetic event re-query; the control does not. Success is always measured on the independent true target.", "",
        "| seed | case | final target | synthetic query | natural queries | task success | final true-target distance | steps |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        distance = row.get("final_true_target_distance")
        lines.append(
            f"| {row['seed']} | {row['case']} | {row.get('final_controller_target') or '-'} | "
            f"{'synthetic_audit' in (row.get('trigger_types') or '')} | {row.get('natural_event_requeries')} | "
            f"{row.get('task_success')} | {distance:.4f} | {row.get('num_steps_executed')} |"
            if distance is not None else
            f"| {row['seed']} | {row['case']} | - | - | - | - | - | - |"
        )
    lines.extend(
        [
            "", "## Aggregate", "",
            "| condition | semantic recovery | true-target success | final distance mean +/- SD | steps mean +/- SD |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for item in aggregates:
        lines.append(
            f"| {item['case']} | {item['semantic_recoveries']}/{item['n']} | "
            f"{item['task_successes']}/{item['n']} | "
            f"{item['final_distance_mean']:.4f} +/- {item['final_distance_std']:.4f} | "
            f"{item['steps_mean']:.2f} +/- {item['steps_std']:.2f} |"
        )
    lines.extend(
        [
            "",
            "- Interpretation boundary: this tests whether re-query can repair a known semantic-target corruption. It does not establish the sensitivity or benefit of the natural stagnation detector.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    args = parse_args()
    result_dir = Path(args.result_root).resolve() / datetime.now().strftime("%Y%m%d_%H%M%S")
    result_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for seed in args.seeds:
        for case in CASES:
            try:
                rows.append(run_case(args, case, seed))
            except Exception as exc:
                traceback.print_exc()
                rows.append(
                    {
                        "status": "error", "case": case["name"], "seed": seed,
                        "true_target": args.true_target, "injected_fault_target": args.fault_target,
                        "event_enabled": case["enable"], "forced_requery_step": args.force_step if case["enable"] else None,
                        "final_controller_target": None, "target_sequence": "", "event_requeries": None,
                        "natural_event_requeries": None, "trigger_types": "", "requery_reasons": "",
                        "semantic_recovered": False, "task_success": False,
                        "initial_true_target_distance": None, "final_true_target_distance": None,
                        "num_steps_executed": None, "runtime_seconds_total": None,
                        "run_dir": None, "metrics_path": None, "error": repr(exc),
                    }
                )
                if not args.continue_on_error:
                    raise
    aggregates = aggregate(rows)
    write_csv(result_dir / "runs.csv", rows)
    write_csv(result_dir / "aggregate.csv", aggregates)
    write_report(result_dir / "report.md", rows, aggregates)
    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "audit_type": "synthetic_semantic_target_fault",
        "backend": args.vlm_backend,
        "model": args.codex_model if args.vlm_backend == "codex" else args.openai_model,
        "wire_api": args.openai_wire_api if args.vlm_backend == "openai" else None,
        "strict_no_cache": True, "seeds": args.seeds,
        "true_target": args.true_target, "fault_target": args.fault_target,
        "forced_requery_step": args.force_step, "rows": rows, "aggregates": aggregates,
    }
    (result_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[done] results -> {result_dir}", flush=True)


if __name__ == "__main__":
    main()
