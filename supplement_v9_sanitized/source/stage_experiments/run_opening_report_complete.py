import argparse
import csv
import json
import os
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = PROJECT_ROOT.parents[2]

ALL_TARGETS = [
    "red moon",
    "red pentagon",
    "blue moon",
    "blue cube",
    "green cube",
    "green star",
    "yellow star",
    "yellow pentagon",
]

SEMANTIC_PRESETS = [
    {
        "name": "semantic_default",
        "semantic_contact_offset": 0.06,
        "semantic_clearance": 0.12,
        "semantic_move_step": 0.06,
        "semantic_push_step": 0.075,
    },
    {
        "name": "semantic_precise",
        "semantic_contact_offset": 0.055,
        "semantic_clearance": 0.12,
        "semantic_move_step": 0.05,
        "semantic_push_step": 0.065,
    },
    {
        "name": "semantic_fast",
        "semantic_contact_offset": 0.065,
        "semantic_clearance": 0.13,
        "semantic_move_step": 0.07,
        "semantic_push_step": 0.08,
    },
]

DEFAULT_PARAMS = SEMANTIC_PRESETS[0]


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def default_python_bin():
    return Path(sys.executable)


def parse_args():
    parser = argparse.ArgumentParser(
        "Run the completed opening-report experiment suite with real simulator metrics."
    )
    parser.add_argument("--python_bin", type=str, default=str(default_python_bin()))
    parser.add_argument("--checkpoint_file", type=str, default=str(WORKSPACE_ROOT / "dmvfn_221.pkl"))
    parser.add_argument("--det_path", type=str, default=str(WORKSPACE_ROOT / "detector_checkpoint.pt"))
    parser.add_argument(
        "--tracker_config",
        type=str,
        default=str(
            WORKSPACE_ROOT / "pysot-master" / "experiments" / "siamrpn_alex_dwxcorr" / "config.yaml"
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
    parser.add_argument("--openai_base_url", type=str, default=os.environ.get("VLMPC_OPENAI_BASE_URL", "https://api.openai.com/v1"))
    parser.add_argument("--openai_model", type=str, default=os.environ.get("VLMPC_OPENAI_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--openai_wire_api", type=str, choices=["chat", "responses"], default=os.environ.get("VLMPC_OPENAI_WIRE_API", "chat"))
    parser.add_argument("--openai_api_key_env", type=str, default=os.environ.get("VLMPC_OPENAI_API_KEY_ENV", "OPENAI_API_KEY"))
    parser.add_argument("--openai_timeout", type=int, default=600)
    parser.add_argument(
        "--vlm_cache_dir",
        type=str,
        default=os.environ.get("VLMPC_VLM_CACHE_DIR") or None,
        help="Leave empty for strict no-cache VLM experiments.",
    )
    parser.add_argument("--task", type=str, default="push_corner")
    parser.add_argument("--target_object", type=str, default="red moon")
    parser.add_argument("--targets", nargs="+", default=ALL_TARGETS)
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 43, 44])
    parser.add_argument("--zoom", type=float, default=0.03)
    parser.add_argument("--action_horizon", type=int, default=20)
    parser.add_argument("--history_rate", type=float, default=0.5)
    parser.add_argument("--ratio_tar_obj", type=float, default=0.5)
    parser.add_argument("--num_samples", type=int, default=10)
    parser.add_argument("--plan_freq", type=int, default=2)
    parser.add_argument("--max_traj_length", type=int, default=45)
    parser.add_argument("--success_distance_world", type=float, default=0.08)
    parser.add_argument("--log_root", type=str, default=str(PROJECT_ROOT / "logs"))
    parser.add_argument(
        "--result_root",
        type=str,
        default=str(PROJECT_ROOT / "stage_experiments" / "opening_report_complete_results"),
    )
    parser.add_argument("--tag_prefix", type=str, default="opening_complete")
    parser.add_argument("--target_image", type=str, default=None)
    parser.add_argument(
        "--target_image_selector",
        type=str,
        choices=["auto", "vlm", "vision"],
        default=os.environ.get("VLMPC_TARGET_IMAGE_SELECTOR", "auto"),
    )
    parser.add_argument("--skip_input_forms", action="store_true")
    parser.add_argument("--skip_multi_target", action="store_true")
    parser.add_argument("--skip_multi_seed", action="store_true")
    parser.add_argument("--skip_ablation", action="store_true")
    parser.add_argument("--skip_target_image_form", action="store_true")
    parser.add_argument("--continue_on_error", action="store_true")
    parser.add_argument("--presentation_export", action="store_true")
    parser.add_argument("--presentation_width", type=int, default=1280)
    parser.add_argument("--presentation_height", type=int, default=720)
    parser.add_argument("--presentation_fps", type=int, default=2)
    parser.add_argument("--presentation_crop", type=str, default=None)
    return parser.parse_args()


def resolve_path(path_str):
    return Path(path_str).expanduser().resolve()


def safe_name(text):
    return text.replace(" ", "_")


def find_new_run_dir(log_root, tag, before_paths):
    candidates = sorted(
        [path.resolve() for path in log_root.glob(f"{tag}_*") if path.is_dir()],
        key=lambda item: item.stat().st_mtime,
    )
    for candidate in reversed(candidates):
        if candidate not in before_paths:
            return candidate
    if candidates:
        return candidates[-1]
    raise FileNotFoundError(f"Could not find a run directory for prefix: {tag}")


def append_optional_cache(command, args):
    if args.vlm_cache_dir:
        command.extend(["--vlm_cache_dir", str(resolve_path(args.vlm_cache_dir))])


def append_presentation(command, args, label):
    if not args.presentation_export:
        return
    command.extend(
        [
            "--presentation_export",
            "--presentation_width",
            str(args.presentation_width),
            "--presentation_height",
            str(args.presentation_height),
            "--presentation_fps",
            str(args.presentation_fps),
            "--presentation_label",
            label,
        ]
    )
    if args.presentation_crop:
        command.extend(["--presentation_crop", args.presentation_crop])


def build_base_command(args, case):
    params = dict(DEFAULT_PARAMS)
    params.update(case.get("semantic_params", {}))
    command = [
        str(resolve_path(args.python_bin)),
        str(PROJECT_ROOT / "main.py"),
        "--checkpoint_file",
        str(resolve_path(args.checkpoint_file)),
        "--det_path",
        str(resolve_path(args.det_path)),
        "--tracker_config",
        str(resolve_path(args.tracker_config)),
        "--tracker_model",
        str(resolve_path(args.tracker_model)),
        "--vlm_backend",
        args.vlm_backend,
        "--codex_home",
        str(resolve_path(args.codex_home)),
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
        args.task,
        "--seed",
        str(case.get("seed", 42)),
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
        "semantic_mpc",
        "--semantic_contact_offset",
        str(params["semantic_contact_offset"]),
        "--semantic_clearance",
        str(params["semantic_clearance"]),
        "--semantic_move_step",
        str(params["semantic_move_step"]),
        "--semantic_push_step",
        str(params["semantic_push_step"]),
    ]
    return command


def run_case(args, case):
    log_root = resolve_path(args.log_root)
    log_root.mkdir(parents=True, exist_ok=True)
    tag = f"{args.tag_prefix}_{case['suite']}_{case['name']}"
    before_paths = {path.resolve() for path in log_root.glob(f"{tag}_*") if path.is_dir()}

    command = build_base_command(args, case)
    command.extend(["--tag", tag, "--log_root", str(log_root)])

    mode = case.get("mode", "fixed")
    # Scene selection has no requested object. Do not backfill the suite
    # default, otherwise a free-selection run becomes a fake instruction row.
    target = case.get("target_object")
    if target is None and mode != "vlm_scene":
        target = args.target_object
    if mode == "fixed":
        command.extend(["--target_object", target])
    elif mode == "instruction":
        command.extend(["--target_instruction", f"Please push the {target} to the bottom right corner."])
    elif mode == "target_image":
        command.extend(
            [
                "--target_image",
                str(resolve_path(case["target_image"])),
                "--target_image_selector",
                args.target_image_selector,
            ]
        )
    elif mode == "vlm_scene":
        pass
    else:
        raise ValueError(f"Unknown case mode: {mode}")

    append_optional_cache(command, args)
    append_presentation(command, args, case["name"])

    print(f"[run] {case['suite']}/{case['name']} -> {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=str(PROJECT_ROOT), check=True)

    run_dir = find_new_run_dir(log_root, tag, before_paths)
    metrics_path = run_dir / "metrics.json"
    if not metrics_path.is_file():
        raise FileNotFoundError(f"Experiment finished but metrics file is missing: {metrics_path}")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    return {
        "status": "ok",
        "suite": case["suite"],
        "name": case["name"],
        "mode": mode,
        "target_object": target,
        "seed": case.get("seed", 42),
        "semantic_params": case.get("semantic_params", DEFAULT_PARAMS),
        "command": command,
        "run_dir": str(run_dir),
        "metrics_path": str(metrics_path),
        "metrics": metrics,
    }


def result_row(result):
    metrics = result.get("metrics") or {}
    params = result.get("semantic_params") or {}
    mode = result.get("mode")
    instruction_evaluable = mode == "instruction"
    request_type = {
        "fixed": "fixed_target",
        "instruction": "language_instruction",
        "target_image": "target_image",
        "vlm_scene": "scene_selection",
    }.get(mode, "diagnostic")
    evaluation_scope = {
        "fixed": "fixed_target_control",
        "instruction": "language_instruction",
        "target_image": "target_image_selected_target_control",
        "vlm_scene": "scene_selection_selected_target_control",
    }.get(mode, "diagnostic")
    selected_target = metrics.get("current_interactive_object")
    evaluation_target = metrics.get("evaluated_target_object") or selected_target
    return {
        "status": result.get("status"),
        "suite": result.get("suite"),
        "name": result.get("name"),
        "mode": result.get("mode"),
        "seed": result.get("seed"),
        "request_type": request_type,
        "evaluation_scope": evaluation_scope,
        "instruction_evaluable": instruction_evaluable,
        "fixed_target_control_success": (
            bool(metrics.get("target_success")) if mode == "fixed" else ""
        ),
        # Target-image and free-scene rows have no independent textual ground
        # truth; keep them outside the instruction denominator.
        "requested_target_object": (
            result.get("target_object") if mode in {"fixed", "instruction"} else ""
        ),
        "selected_target_object": selected_target,
        "evaluation_target_object": evaluation_target,
        "overall_success": metrics.get("overall_success"),
        "target_success": metrics.get("target_success"),
        "initial_target_world_distance": metrics.get("initial_target_world_distance"),
        "final_target_world_distance": metrics.get("final_target_world_distance"),
        "target_world_distance_delta": metrics.get("target_world_distance_delta"),
        "success_distance_world": metrics.get("success_distance_world"),
        "num_steps_executed": metrics.get("num_steps_executed"),
        "runtime_seconds_total": metrics.get("runtime_seconds_total"),
        "mean_step_duration": metrics.get("mean_step_duration"),
        "semantic_policy_calls": metrics.get("semantic_policy_calls"),
        "subtask_requests": metrics.get("subtask_requests"),
        "interactive_object_requests": metrics.get("interactive_object_requests"),
        "event_requeries": metrics.get("event_requeries"),
        "target_image_selector": metrics.get("target_image_selector"),
        "target_image_selection_rule": (
            (metrics.get("target_image_selection_details") or [{}])[-1].get("selection_rule")
            if metrics.get("target_image_selection_details")
            else None
        ),
        "semantic_contact_offset": params.get("semantic_contact_offset"),
        "semantic_clearance": params.get("semantic_clearance"),
        "semantic_move_step": params.get("semantic_move_step"),
        "semantic_push_step": params.get("semantic_push_step"),
        "run_dir": result.get("run_dir"),
        "metrics_path": result.get("metrics_path"),
        "error": result.get("error"),
    }


def write_csv(results, output_path):
    rows = [result_row(result) for result in results]
    fieldnames = list(rows[0].keys()) if rows else list(result_row({}).keys())
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def fmt(value):
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def write_markdown(results, output_path):
    ok_results = [item for item in results if item.get("status") == "ok"]
    success_results = [
        item
        for item in ok_results
        if (item.get("metrics") or {}).get("overall_success")
        and (item.get("metrics") or {}).get("target_success")
    ]
    failed = [item for item in results if item.get("status") != "ok" or item not in success_results]

    lines = [
        "# Opening Report Complete Experiment Suite",
        "",
        f"- total cases: {len(results)}",
        f"- successful target pushes: {len(success_results)} / {len(results)}",
        f"- failed or incomplete cases: {len(failed)}",
        "",
    ]
    suites = sorted({item.get("suite") for item in results})
    for suite in suites:
        suite_items = [item for item in results if item.get("suite") == suite]
        suite_success = [
            item
            for item in suite_items
            if item.get("status") == "ok"
            and (item.get("metrics") or {}).get("overall_success")
            and (item.get("metrics") or {}).get("target_success")
        ]
        lines.append(f"## {suite}")
        lines.append("")
        lines.append(f"- success: {len(suite_success)} / {len(suite_items)}")
        lines.append("")
        lines.append(
            "| case | mode | target | seed | success | final_world_distance | world_delta | steps | runtime_s | metrics |"
        )
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for item in suite_items:
            metrics = item.get("metrics") or {}
            success = bool(metrics.get("overall_success") and metrics.get("target_success"))
            metrics_path = item.get("metrics_path") or "-"
            lines.append(
                "| "
                + " | ".join(
                    [
                        item.get("name", "-"),
                        item.get("mode", "-"),
                        metrics.get("current_interactive_object") or item.get("target_object") or "-",
                        fmt(item.get("seed")),
                        str(success),
                        fmt(metrics.get("final_target_world_distance")),
                        fmt(metrics.get("target_world_distance_delta")),
                        fmt(metrics.get("num_steps_executed")),
                        fmt(metrics.get("runtime_seconds_total")),
                        metrics_path,
                    ]
                )
                + " |"
            )
        lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def build_cases(args):
    target = args.target_object
    cases = []
    if not args.skip_input_forms:
        cases.extend(
            [
                {"suite": "input_forms", "name": "fixed_target", "mode": "fixed", "target_object": target, "seed": 42},
                {
                    "suite": "input_forms",
                    "name": "language_instruction",
                    "mode": "instruction",
                    "target_object": target,
                    "seed": 42,
                },
                {"suite": "input_forms", "name": "vlm_scene_selection", "mode": "vlm_scene", "seed": 42},
            ]
        )
    if not args.skip_multi_target:
        for target_name in args.targets:
            cases.append(
                {
                    "suite": "multi_target",
                    "name": safe_name(target_name),
                    "mode": "fixed",
                    "target_object": target_name,
                    "seed": 42,
                }
            )
    if not args.skip_multi_seed:
        for seed in args.seeds:
            cases.append(
                {
                    "suite": "multi_seed",
                    "name": f"{safe_name(target)}_seed_{seed}",
                    "mode": "fixed",
                    "target_object": target,
                    "seed": seed,
                }
            )
    if not args.skip_ablation:
        for preset in SEMANTIC_PRESETS:
            cases.append(
                {
                    "suite": "semantic_ablation",
                    "name": preset["name"],
                    "mode": "fixed",
                    "target_object": target,
                    "seed": 42,
                    "semantic_params": preset,
                }
            )
    return cases


def main():
    load_dotenv(PROJECT_ROOT / ".env")
    args = parse_args()
    result_root = resolve_path(args.result_root) / datetime.now().strftime("%Y%m%d_%H%M%S")
    result_root.mkdir(parents=True, exist_ok=True)

    results = []
    target_image_reference = resolve_path(args.target_image) if args.target_image else None
    cases = build_cases(args)

    for case in cases:
        try:
            result = run_case(args, case)
        except Exception as exc:
            if not args.continue_on_error:
                raise
            traceback.print_exc()
            result = {
                "status": "error",
                "suite": case["suite"],
                "name": case["name"],
                "mode": case.get("mode"),
                "target_object": case.get("target_object"),
                "seed": case.get("seed", 42),
                "semantic_params": case.get("semantic_params", DEFAULT_PARAMS),
                "error": repr(exc),
            }
        results.append(result)
        if (
            target_image_reference is None
            and not args.skip_target_image_form
            and result.get("status") == "ok"
            and case.get("suite") == "input_forms"
            and case.get("name") == "fixed_target"
        ):
            final_frame = Path(result["run_dir"]) / "final_frame.png"
            if final_frame.is_file():
                target_image_reference = final_frame

    if not args.skip_target_image_form:
        if target_image_reference is None:
            raise FileNotFoundError("Target-image form requested, but no target image was provided or generated.")
        image_case = {
            "suite": "input_forms",
            "name": "target_image",
            "mode": "target_image",
            "target_image": str(target_image_reference),
            "seed": 42,
        }
        try:
            results.append(run_case(args, image_case))
        except Exception as exc:
            if not args.continue_on_error:
                raise
            traceback.print_exc()
            results.append(
                {
                    "status": "error",
                    "suite": image_case["suite"],
                    "name": image_case["name"],
                    "mode": image_case["mode"],
                    "seed": image_case["seed"],
                    "semantic_params": DEFAULT_PARAMS,
                    "error": repr(exc),
                }
            )

    write_csv(results, result_root / "summary.csv")
    write_markdown(results, result_root / "summary.md")
    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "project_root": str(PROJECT_ROOT),
        "args": vars(args),
        "results": results,
    }
    (result_root / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[done] results -> {result_root}", flush=True)


if __name__ == "__main__":
    main()
