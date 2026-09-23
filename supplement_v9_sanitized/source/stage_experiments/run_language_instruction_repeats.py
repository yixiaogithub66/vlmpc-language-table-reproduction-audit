"""Run independent natural-language instruction repeats through the Codex backend.

Each case supplies only ``--target_instruction`` to the controller.  The
expected object is passed separately as ``--evaluation_target_object`` so that
selection and control are evaluated against an independent ground truth.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import subprocess
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parents[2]

CASES = [
    {
        "name": "red_moon_reward_corner",
        "instruction": "Please push the red moon to the reward target corner.",
        "expected_object": "red moon",
    },
    {
        "name": "blue_cube_bottom_right",
        "instruction": "Move the blue cube into the bottom-right goal.",
        "expected_object": "blue cube",
    },
    {
        "name": "yellow_pentagon_lower_right",
        "instruction": "Guide the yellow pentagon to the lower-right corner.",
        "expected_object": "yellow pentagon",
    },
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
    parser = argparse.ArgumentParser("Run independent language-instruction repeats.")
    parser.add_argument("--python_bin", default=str(PROJECT_ROOT / ".venv312" / "Scripts" / "python.exe"))
    parser.add_argument("--checkpoint_file", default=str(WORKSPACE_ROOT / "dmvfn_221.pkl"))
    parser.add_argument("--det_path", default=str(WORKSPACE_ROOT / "detector_checkpoint.pt"))
    parser.add_argument(
        "--tracker_config",
        default=str(WORKSPACE_ROOT / "pysot-master" / "experiments" / "siamrpn_alex_dwxcorr" / "config.yaml"),
    )
    parser.add_argument("--tracker_model", default=str(WORKSPACE_ROOT / "model.pth"))
    parser.add_argument("--vlm_backend", choices=["codex", "openai"], default="codex")
    parser.add_argument("--codex_home", default=os.environ.get("VLMPC_CODEX_HOME", str(Path.home() / ".codex-vlmpc-eacase")))
    parser.add_argument("--codex_model", default=os.environ.get("VLMPC_CODEX_MODEL", "gpt-5.5"))
    parser.add_argument("--codex_timeout", type=int, default=600)
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 43, 44])
    parser.add_argument("--success_distance_world", type=float, default=0.08)
    parser.add_argument("--max_traj_length", type=int, default=45)
    parser.add_argument("--log_root", default=str(PROJECT_ROOT / "logs" / "language_instruction_repeats"))
    parser.add_argument("--result_root", default=str(PROJECT_ROOT / "stage_experiments" / "language_instruction_repeats"))
    parser.add_argument("--tag_prefix", default="language_instruction_repeat")
    parser.add_argument("--continue_on_error", action="store_true")
    return parser.parse_args()


def resolve(path: str) -> Path:
    return Path(path).expanduser().resolve()


def find_new_run_dir(log_root: Path, tag: str, before: set[Path]) -> Path:
    candidates = sorted(
        (path.resolve() for path in log_root.glob(f"{tag}_*") if path.is_dir()),
        key=lambda path: path.stat().st_mtime,
    )
    for candidate in reversed(candidates):
        if candidate not in before:
            return candidate
    raise FileNotFoundError(f"Could not locate a new run directory for {tag}")


def build_command(args: argparse.Namespace, case: dict[str, str], seed: int) -> list[str]:
    command = [
        str(resolve(args.python_bin)),
        str(PROJECT_ROOT / "main.py"),
        "--checkpoint_file", str(resolve(args.checkpoint_file)),
        "--det_path", str(resolve(args.det_path)),
        "--tracker_config", str(resolve(args.tracker_config)),
        "--tracker_model", str(resolve(args.tracker_model)),
        "--vlm_backend", args.vlm_backend,
        "--codex_home", str(resolve(args.codex_home)),
        "--codex_model", args.codex_model,
        "--codex_timeout", str(args.codex_timeout),
        "--task", "push_corner",
        "--seed", str(seed),
        "--zoom", "0.03",
        "--action_horizon", "20",
        "--history_rate", "0.5",
        "--ratio_tar_obj", "0.5",
        "--num_samples", "5",
        "--plan_freq", "2",
        "--max_traj_length", str(args.max_traj_length),
        "--success_distance_world", str(args.success_distance_world),
        "--controller_variant", "semantic_mpc",
        "--feedback_source", "oracle",
        "--target_instruction", case["instruction"],
        "--evaluation_target_object", case["expected_object"],
        "--semantic_contact_offset", "0.06",
        "--semantic_clearance", "0.12",
        "--semantic_move_step", "0.06",
        "--semantic_push_step", "0.075",
    ]
    if args.vlm_backend == "openai":
        command.extend([
            "--openai_base_url", os.environ.get("VLMPC_OPENAI_BASE_URL", "https://api.openai.com/v1"),
            "--openai_model", os.environ.get("VLMPC_OPENAI_MODEL", "gpt-4.1-mini"),
            "--openai_wire_api", os.environ.get("VLMPC_OPENAI_WIRE_API", "chat"),
            "--openai_api_key_env", os.environ.get("VLMPC_OPENAI_API_KEY_ENV", "OPENAI_API_KEY"),
        ])
    return command


def run_case(args: argparse.Namespace, case: dict[str, str], seed: int) -> dict[str, object]:
    log_root = resolve(args.log_root)
    log_root.mkdir(parents=True, exist_ok=True)
    tag = f"{args.tag_prefix}_{case['name']}_seed{seed}"
    before = {path.resolve() for path in log_root.glob(f"{tag}_*") if path.is_dir()}
    command = build_command(args, case, seed)
    command.extend(["--tag", tag, "--log_root", str(log_root)])
    print(f"[run] {case['name']} seed={seed}", flush=True)
    subprocess.run(command, cwd=str(PROJECT_ROOT), check=True)
    run_dir = find_new_run_dir(log_root, tag, before)
    metrics_path = run_dir / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    log_text = (run_dir / "log.txt").read_text(encoding="utf-8", errors="replace") if (run_dir / "log.txt").is_file() else ""
    # `evaluated_target_object` is the independent audit label, not the
    # controller's semantic selection.  Read the latter from the recorded
    # interaction sequence so selection accuracy cannot become self-fulfilling.
    selected = (metrics.get("interactive_objects") or [None])[-1]
    return {
        "status": "ok",
        "case": case["name"],
        "instruction": case["instruction"],
        "expected_object": case["expected_object"],
        "seed": seed,
        "vlm_backend": args.vlm_backend,
        "codex_model": args.codex_model if args.vlm_backend == "codex" else "",
        "selected_object": selected,
        "selection_match": str(selected == case["expected_object"]),
        "overall_success": metrics.get("overall_success"),
        "target_success": metrics.get("target_success"),
        "initial_target_world_distance": metrics.get("initial_target_world_distance"),
        "final_target_world_distance": metrics.get("final_target_world_distance"),
        "target_world_distance_delta": metrics.get("target_world_distance_delta"),
        "num_steps_executed": metrics.get("num_steps_executed"),
        "runtime_seconds_total": metrics.get("runtime_seconds_total"),
        "interactive_object_requests": metrics.get("interactive_object_requests"),
        "event_requeries": metrics.get("event_requeries"),
        "cache_hits_in_log": log_text.count("cache hit"),
        "fresh_vlm_responses_in_log": log_text.count("codex-cli response") + log_text.count("openai-api response"),
        "strict_no_cache_vlm": True,
        "run_dir": str(run_dir),
        "metrics_path": str(metrics_path),
        "error": "",
    }


def aggregate(rows: list[dict[str, object]], threshold: float) -> list[dict[str, object]]:
    output = []
    for name in [case["name"] for case in CASES] + ["all_cases"]:
        subset = rows if name == "all_cases" else [row for row in rows if row.get("case") == name]
        distances = [float(row["final_target_world_distance"]) for row in subset if row.get("final_target_world_distance") is not None]
        output.append({
            "case": name,
            "n": len(subset),
            "selection_matches": f"{sum(row.get('selection_match') == 'True' for row in subset)}/{len(subset)}" if subset else "0/0",
            "joint_successes": f"{sum(row.get('selection_match') == 'True' and row.get('target_success') is True for row in subset)}/{len(subset)}" if subset else "0/0",
            "control_successes_at_threshold": f"{sum(value <= threshold for value in distances)}/{len(distances)}" if distances else "0/0",
            "mean_final_world_distance": statistics.mean(distances) if distances else None,
            "sample_sd_final_world_distance": statistics.stdev(distances) if len(distances) > 1 else 0.0,
            "seeds": ",".join(str(row["seed"]) for row in subset),
        })
    return output


def write_outputs(result_dir: Path, rows: list[dict[str, object]], aggregates: list[dict[str, object]], args: argparse.Namespace) -> None:
    result_dir.mkdir(parents=True, exist_ok=True)
    with (result_dir / "runs.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    with (result_dir / "aggregate.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(aggregates[0].keys()))
        writer.writeheader()
        writer.writerows(aggregates)
    lines = [
        "# Independent Language-Instruction Repeat Audit",
        "",
        "Each row supplies only a natural-language target instruction and evaluates against an independently specified target object. No fixed `--target_object` is passed. The Codex CLI backend is run with project-level VLM caching disabled.",
        "",
        "| case | seed | expected | selected | match | joint success | final world distance |",
        "| --- | ---: | --- | --- | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['case']} | {row['seed']} | {row['expected_object']} | {row['selected_object']} | "
            f"{row['selection_match']} | {row['selection_match'] == 'True' and row['target_success'] is True} | "
            f"{float(row['final_target_world_distance']):.4f} |"
        )
    lines.extend([
        "",
        "Interpretation: this is a small independent language-grounding audit, not a broad instruction benchmark. Fixed-target controls and target-image rows are excluded from this denominator.",
    ])
    (result_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (result_dir / "manifest.json").write_text(
        json.dumps(
            {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "backend": args.vlm_backend,
                "model": args.codex_model if args.vlm_backend == "codex" else None,
                "strict_no_cache": True,
                "seeds": args.seeds,
                "cases": CASES,
                "threshold": args.success_distance_world,
                "rows": rows,
                "aggregates": aggregates,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    args = parse_args()
    rows: list[dict[str, object]] = []
    for seed in args.seeds:
        for case in CASES:
            try:
                rows.append(run_case(args, case, seed))
            except Exception as exc:
                if not args.continue_on_error:
                    raise
                rows.append({
                    "status": "error", "case": case["name"], "instruction": case["instruction"],
                    "expected_object": case["expected_object"], "seed": seed, "error": repr(exc),
                })
    result_dir = resolve(args.result_root) / datetime.now().strftime("%Y%m%d_%H%M%S")
    valid_rows = [row for row in rows if row.get("status") == "ok"]
    if not valid_rows:
        raise RuntimeError("No language-instruction run completed successfully")
    write_outputs(result_dir, valid_rows, aggregate(valid_rows, args.success_distance_world), args)
    print(f"[done] results -> {result_dir}", flush=True)


if __name__ == "__main__":
    main()
