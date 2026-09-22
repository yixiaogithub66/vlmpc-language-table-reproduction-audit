"""Run matched controls for event-triggered VLM re-query.

The original final package contains one natural event-triggered re-query run.
This supplement adds a matched no-event control and, optionally, a forced VLM
audit control.  The goal is not to prove recovery causality from a large
benchmark, but to make the evidence boundary explicit and reproducible.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parents[2]


MATCHED_CASES = [
    {
        "name": "matched_no_event_instruction",
        "description": "Same instruction, seed and semantic-MPC oracle execution, but natural event re-query disabled.",
        "target_instruction": "Please push the red moon to the reward target corner.",
        "enable_event_vlm_requery": False,
        "event_requery_unblock_fixed_target": False,
        "force_vlm_requery_once": False,
    },
    {
        "name": "matched_event_instruction",
        "description": "Same instruction, seed and semantic-MPC oracle execution, with natural event re-query enabled.",
        "target_instruction": "Please push the red moon to the reward target corner.",
        "enable_event_vlm_requery": True,
        "event_requery_unblock_fixed_target": True,
        "force_vlm_requery_once": False,
    },
]

FORCED_CASE = {
    "name": "scene_forced_requery_audit",
    "description": "Scene-selection audit: force one second VLM query with the first object excluded.",
    "target_instruction": None,
    "enable_event_vlm_requery": False,
    "event_requery_unblock_fixed_target": False,
    "force_vlm_requery_once": True,
}


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def default_python_bin() -> Path:
    return Path(sys.executable)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser("Run event re-query control experiments.")
    parser.add_argument("--python_bin", type=str, default=str(default_python_bin()))
    parser.add_argument("--checkpoint_file", type=str, default=str(WORKSPACE_ROOT / "dmvfn_221.pkl"))
    parser.add_argument("--det_path", type=str, default=str(WORKSPACE_ROOT / "detector_checkpoint.pt"))
    parser.add_argument(
        "--tracker_config",
        type=str,
        default=str(
            WORKSPACE_ROOT
            / "pysot-master"
            / "experiments"
            / "siamrpn_r50_l234_dwxcorr"
            / "config.yaml"
        ),
    )
    parser.add_argument("--tracker_model", type=str, default=str(WORKSPACE_ROOT / "model.pth"))
    parser.add_argument(
        "--vlm_backend",
        type=str,
        choices=["codex", "openai"],
        default=os.environ.get("VLMPC_VLM_BACKEND", "openai"),
    )
    parser.add_argument("--codex_home", type=str, default=str(Path.home() / ".codex-vlmpc-gwen"))
    parser.add_argument("--codex_timeout", type=int, default=600)
    parser.add_argument(
        "--openai_base_url",
        type=str,
        default=os.environ.get("VLMPC_OPENAI_BASE_URL", "https://api.openai.com/v1"),
    )
    parser.add_argument(
        "--openai_model",
        type=str,
        default=os.environ.get("VLMPC_OPENAI_MODEL", "gpt-4.1-mini"),
    )
    parser.add_argument(
        "--openai_wire_api",
        type=str,
        choices=["chat", "responses"],
        default=os.environ.get("VLMPC_OPENAI_WIRE_API", "chat"),
    )
    parser.add_argument(
        "--openai_api_key_env",
        type=str,
        default=os.environ.get("VLMPC_OPENAI_API_KEY_ENV", "OPENAI_API_KEY"),
    )
    parser.add_argument("--openai_timeout", type=int, default=600)
    parser.add_argument(
        "--vlm_cache_dir",
        type=str,
        default=None,
        help="Project-level VLM cache directory. Default None means strict no-cache calls.",
    )
    parser.add_argument("--seeds", type=str, default=None, help="Comma-separated seeds. Overrides --seed.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--zoom", type=float, default=0.02)
    parser.add_argument("--action_horizon", type=int, default=20)
    parser.add_argument("--history_rate", type=float, default=0.5)
    parser.add_argument("--ratio_tar_obj", type=float, default=0.5)
    parser.add_argument("--num_samples", type=int, default=5)
    parser.add_argument("--plan_freq", type=int, default=2)
    parser.add_argument("--max_traj_length", type=int, default=35)
    parser.add_argument("--success_distance_world", type=float, default=0.08)
    parser.add_argument("--controller_variant", type=str, default="semantic_mpc")
    parser.add_argument("--feedback_source", type=str, default="oracle", choices=["oracle", "visual"])
    parser.add_argument("--event_requery_window", type=int, default=2)
    parser.add_argument("--event_requery_min_progress", type=float, default=25.0)
    parser.add_argument("--event_requery_min_step", type=int, default=3)
    parser.add_argument("--log_root", type=str, default=str(PROJECT_ROOT / "logs"))
    parser.add_argument(
        "--result_root",
        type=str,
        default=str(PROJECT_ROOT / "stage_experiments" / "event_requery_controls"),
    )
    parser.add_argument("--tag_prefix", type=str, default="strict_event_control")
    parser.add_argument("--include_forced", action="store_true")
    parser.add_argument("--continue_on_error", action="store_true")
    return parser.parse_args()


def resolve(path: str) -> Path:
    return Path(path).expanduser().resolve()


def find_new_run_dir(log_root: Path, tag: str, before: set[Path]) -> Path:
    candidates = sorted(
        [path.resolve() for path in log_root.glob(f"{tag}_*") if path.is_dir()],
        key=lambda path: path.stat().st_mtime,
    )
    for candidate in reversed(candidates):
        if candidate not in before:
            return candidate
    if candidates:
        return candidates[-1]
    raise FileNotFoundError(f"Could not locate run directory for {tag}")


def build_command(args: argparse.Namespace, case: dict[str, object]) -> list[str]:
    command = [
        str(resolve(args.python_bin)),
        str(PROJECT_ROOT / "main.py"),
        "--checkpoint_file",
        str(resolve(args.checkpoint_file)),
        "--det_path",
        str(resolve(args.det_path)),
        "--tracker_config",
        str(resolve(args.tracker_config)),
        "--tracker_model",
        str(resolve(args.tracker_model)),
        "--vlm_backend",
        args.vlm_backend,
        "--codex_home",
        str(resolve(args.codex_home)),
        "--codex_timeout",
        str(args.codex_timeout),
        "--openai_base_url",
        args.openai_base_url,
        "--openai_model",
        args.openai_model,
        "--openai_wire_api",
        args.openai_wire_api,
        "--openai_api_key_env",
        args.openai_api_key_env,
        "--openai_timeout",
        str(args.openai_timeout),
        "--task",
        "push_corner",
        "--seed",
        str(args.seed),
        "--zoom",
        str(args.zoom),
        "--action_horizon",
        str(args.action_horizon),
        "--history_rate",
        str(args.history_rate),
        "--ratio_tar_obj",
        str(args.ratio_tar_obj),
        "--num_samples",
        str(args.num_samples),
        "--plan_freq",
        str(args.plan_freq),
        "--max_traj_length",
        str(args.max_traj_length),
        "--success_distance_world",
        str(args.success_distance_world),
        "--controller_variant",
        args.controller_variant,
        "--feedback_source",
        args.feedback_source,
        "--event_requery_window",
        str(args.event_requery_window),
        "--event_requery_min_progress",
        str(args.event_requery_min_progress),
        "--event_requery_min_step",
        str(args.event_requery_min_step),
    ]
    if args.controller_variant != "semantic_mpc":
        command.append("--grounded_original_mpc")
    if args.vlm_cache_dir:
        command.extend(["--vlm_cache_dir", str(resolve(args.vlm_cache_dir))])
    if case.get("target_instruction"):
        command.extend(["--target_instruction", str(case["target_instruction"])])
    if case.get("enable_event_vlm_requery"):
        command.append("--enable_event_vlm_requery")
    if case.get("event_requery_unblock_fixed_target"):
        command.append("--event_requery_unblock_fixed_target")
    if case.get("force_vlm_requery_once"):
        command.append("--force_vlm_requery_once")
    return command


def run_case(args: argparse.Namespace, case: dict[str, object]) -> dict[str, object]:
    log_root = resolve(args.log_root)
    log_root.mkdir(parents=True, exist_ok=True)
    tag = f"{args.tag_prefix}_{case['name']}"
    before = {path.resolve() for path in log_root.glob(f"{tag}_*") if path.is_dir()}
    command = build_command(args, case)
    command.extend(["--tag", tag, "--log_root", str(log_root)])
    print(f"[run] {case['name']} -> {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=str(PROJECT_ROOT), check=True)
    run_dir = find_new_run_dir(log_root, tag, before)
    metrics_path = run_dir / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    return {
        "status": "ok",
        "case": case,
        "seed": args.seed,
        "command": command,
        "run_dir": str(run_dir),
        "metrics_path": str(metrics_path),
        "metrics": metrics,
    }


def row_from_result(result: dict[str, object], args: argparse.Namespace) -> dict[str, object]:
    metrics = result.get("metrics") or {}
    case = result.get("case") or {}
    run_dir = Path(str(result.get("run_dir"))) if result.get("run_dir") else None
    log_text = ""
    if run_dir is not None and (run_dir / "log.txt").is_file():
        log_text = (run_dir / "log.txt").read_text(encoding="utf-8", errors="replace")
    cache_hits = log_text.count("cache hit")
    fresh_responses = log_text.count("codex-cli response") + log_text.count("openai-api response")
    return {
        "status": result.get("status"),
        "case": case.get("name"),
        "description": case.get("description"),
        "seed": result.get("seed", args.seed),
        "controller_variant": args.controller_variant,
        "feedback_source": args.feedback_source,
        "vlm_backend": args.vlm_backend,
        "openai_model": args.openai_model if args.vlm_backend == "openai" else "",
        "openai_wire_api": args.openai_wire_api if args.vlm_backend == "openai" else "",
        "openai_endpoint_configured": bool(args.openai_base_url) if args.vlm_backend == "openai" else False,
        "openai_api_key_present": bool(os.environ.get("VLMPC_OPENAI_API_KEY") or os.environ.get(args.openai_api_key_env)),
        "target_instruction": case.get("target_instruction") or "",
        "event_enabled": bool(case.get("enable_event_vlm_requery")),
        "event_unblocked_fixed_target": bool(case.get("event_requery_unblock_fixed_target")),
        "forced_initial_requery": bool(case.get("force_vlm_requery_once")),
        "event_requery_window": args.event_requery_window,
        "event_requery_min_progress": args.event_requery_min_progress,
        "event_requery_min_step": args.event_requery_min_step,
        "overall_success": metrics.get("overall_success"),
        "final_target_world_distance": metrics.get("final_target_world_distance"),
        "target_world_distance_delta": metrics.get("target_world_distance_delta"),
        "runtime_seconds_total": metrics.get("runtime_seconds_total"),
        "num_steps_executed": metrics.get("num_steps_executed"),
        "event_requeries": metrics.get("event_requeries"),
        "natural_event_requeries": metrics.get("natural_event_requeries"),
        "requery_reasons": "|".join(metrics.get("requery_reasons", [])),
        "accepted_subtask_sources": "|".join(metrics.get("accepted_subtask_sources", [])),
        "interactive_objects": "|".join(metrics.get("interactive_objects", [])),
        "raw_mpc_action_count": len(metrics.get("raw_mpc_actions", [])),
        "grounded_original_overrides": metrics.get("grounded_original_overrides"),
        "project_cache_dir": args.vlm_cache_dir or "",
        "cache_hits_in_log": cache_hits,
        "fresh_vlm_responses_in_log": fresh_responses,
        "strict_no_cache_vlm": not bool(args.vlm_cache_dir),
        "run_dir": result.get("run_dir"),
        "metrics_path": result.get("metrics_path"),
        "error": result.get("error", ""),
    }


def write_outputs(result_dir: Path, results: list[dict[str, object]], args: argparse.Namespace) -> None:
    rows = [row_from_result(result, args) for result in results]
    csv_path = result_dir / "event_requery_controls.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Event Re-query Control Supplement",
        "",
        "This supplement compares matched semantic-MPC oracle runs with and without the natural event trigger. The forced case, when enabled, is an initial scene-selection audit rather than a matched recovery ablation.",
        "",
        "| case | event enabled | natural re-query | success | final world distance | reasons |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['case']} | {row['event_enabled']} | {row['natural_event_requeries']} | "
            f"{row['overall_success']} | {row['final_target_world_distance']} | {row['requery_reasons']} |"
        )
    lines.extend(
        [
            "",
            "Interpretation: this file supports the implementation claim that the trigger can fire in a matched setting. It is still too small to claim a statistically validated recovery benefit.",
        ]
    )
    (result_dir / "event_requery_controls.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (result_dir / "manifest.json").write_text(
        json.dumps(
            {
                "created_at": datetime.now().isoformat(),
                "project_root": str(PROJECT_ROOT),
                "workspace_root": str(WORKSPACE_ROOT),
                "vlm_backend": args.vlm_backend,
                "openai_model": args.openai_model if args.vlm_backend == "openai" else None,
                "openai_wire_api": args.openai_wire_api if args.vlm_backend == "openai" else None,
                "vlm_cache_dir": args.vlm_cache_dir,
                "cases": [result.get("case") for result in results],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    args = parse_args()
    cases = list(MATCHED_CASES)
    if args.include_forced:
        cases.append(FORCED_CASE)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_dir = resolve(args.result_root) / stamp
    result_dir.mkdir(parents=True, exist_ok=True)

    seed_values = (
        [int(value.strip()) for value in args.seeds.split(",") if value.strip()]
        if args.seeds
        else [args.seed]
    )
    results: list[dict[str, object]] = []
    for seed in seed_values:
        args.seed = seed
        for case in cases:
            try:
                results.append(run_case(args, case))
            except Exception as exc:
                if not args.continue_on_error:
                    raise
                results.append(
                    {
                        "status": "error",
                        "case": case,
                        "seed": seed,
                        "metrics": {},
                        "error": repr(exc),
                    }
                )
    write_outputs(result_dir, results, args)
    print(f"[done] wrote {result_dir}", flush=True)


if __name__ == "__main__":
    main()
