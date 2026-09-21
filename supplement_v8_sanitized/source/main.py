import argparse
import json
import os
import pathlib
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
ARCHIVED_SITE_PACKAGES = PROJECT_ROOT / ".venv312" / "Lib" / "site-packages"
EXTRA_SITE_PACKAGES = Path(
    os.environ["VLMPC_EXTRA_SITE_DIR"]
    if os.environ.get("VLMPC_EXTRA_SITE_DIR")
    else PROJECT_ROOT / "__optional_extra_site_packages__"
)
sys.path = [path for path in sys.path if "vlmpcdeps" not in str(path).lower()]
pythonpath = os.environ.get("PYTHONPATH")
if pythonpath:
    os.environ["PYTHONPATH"] = os.pathsep.join(
        path for path in pythonpath.split(os.pathsep) if "vlmpcdeps" not in path.lower()
    )
if ARCHIVED_SITE_PACKAGES.is_dir() and str(ARCHIVED_SITE_PACKAGES) not in sys.path:
    # Reuse archived pure-Python dependencies such as absl while keeping the
    # active interpreter's compiled packages ahead of the archived environment.
    sys.path.append(str(ARCHIVED_SITE_PACKAGES))
os.environ.setdefault(
    "YOLO_CONFIG_DIR",
    str(PROJECT_ROOT / "stage_experiments" / ".ultralytics"),
)

import cv2
import imageio
import matplotlib.pyplot as plt
import numpy as np
import torch
from PIL import Image

from detect_bbx import det_bbox
from logger import setup_logger
from tools import cv2_write_image, seed_all
from video_interface import DMVFNActModel
from vlm_client import create_vlm_client
from vlmpc import VLMPC

PYSOT_ROOT = PROJECT_ROOT / "pysot_tracker"
if str(PYSOT_ROOT) not in sys.path:
    sys.path.insert(0, str(PYSOT_ROOT))

if os.name == "nt":
    pathlib.PosixPath = pathlib.WindowsPath

blocks = None
language_table = None
block1_to_corner = None


def add_extra_site_packages():
    if EXTRA_SITE_PACKAGES.is_dir() and str(EXTRA_SITE_PACKAGES) not in sys.path:
        # Keep this late-bound: the directory is useful for simulator-only
        # packages such as pybullet, but can pollute audit/plotting scripts.
        sys.path.append(str(EXTRA_SITE_PACKAGES))


def import_language_table_runtime():
    """Import the simulator stack only when a run actually needs it."""
    global blocks, language_table, block1_to_corner
    if language_table is not None:
        return
    add_extra_site_packages()
    from language_table.environments import blocks as blocks_module
    from language_table.environments import language_table as language_table_module
    from language_table.environments.rewards import block1_to_corner as reward_module

    blocks = blocks_module
    language_table = language_table_module
    block1_to_corner = reward_module


def load_dotenv(dotenv_path):
    dotenv_path = Path(dotenv_path)
    if not dotenv_path.is_file():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def resolve_path(path_str, base_dir=PROJECT_ROOT):
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def validate_runtime(args):
    required_files = {}
    if args.controller_variant != "semantic_mpc":
        required_files.update(
            {
                "video checkpoint": args.checkpoint_file,
                "tracker config": args.tracker_config,
                "tracker model": args.tracker_model,
            }
        )
    if needs_detector(args):
        required_files["detector checkpoint"] = args.det_path
    for label, path in required_files.items():
        if not path.is_file():
            raise FileNotFoundError(f"Missing {label}: {path}")

    if needs_detector(args) and not args.yolo_repo.is_dir():
        raise FileNotFoundError(f"Missing YOLO repository directory: {args.yolo_repo}")

    if args.vlm_backend == "codex" and shutil.which(args.codex_bin) is None:
        raise FileNotFoundError(
            f"Cannot find codex executable '{args.codex_bin}'. "
            "Install codex-cli or pass --codex_bin with the full path."
        )

    if args.target_image and not args.target_image.is_file():
        raise FileNotFoundError(f"Missing target image: {args.target_image}")

    if args.task != "push_corner":
        raise NotImplementedError(
            f"Task '{args.task}' is not implemented end-to-end in this repository. "
            "Use --task push_corner."
        )


def safe_mean(values):
    if not values:
        return None
    return float(sum(values) / len(values))


def block_key_from_object(object_name):
    if not object_name:
        return None
    return "block_" + object_name.replace(" ", "_") + "_translation"


def target_world_distance(state, object_name):
    if block1_to_corner is None:
        import_language_table_runtime()
    key = block_key_from_object(object_name)
    if not key or key not in state:
        return None
    obj_pos = np.asarray(state[key], dtype=np.float32)
    target = np.asarray(block1_to_corner.ABSOLUTE_LOCATIONS["bottom_left"], dtype=np.float32)
    return float(np.linalg.norm(obj_pos - target))


def block_positions_from_state(state):
    positions = {}
    if not state:
        return positions
    prefix = "block_"
    suffix = "_translation"
    for key, value in state.items():
        if not key.startswith(prefix) or not key.endswith(suffix):
            continue
        object_name = key[len(prefix) : -len(suffix)].replace("_", " ")
        positions[object_name] = np.asarray(value, dtype=np.float32)
    return positions


def world_interference_stats(
    state,
    target_object,
    collision_distance_world,
    interference_distance_world,
):
    block_positions = block_positions_from_state(state)
    target_pos = block_positions.get(target_object)
    end_effector_pos = None
    if state and "effector_target_translation" in state:
        end_effector_pos = np.asarray(state["effector_target_translation"], dtype=np.float32)
    non_target_positions = {
        name: pos for name, pos in block_positions.items() if name != target_object
    }

    target_obstacle_distances = []
    effector_non_target_distances = []
    for name, pos in non_target_positions.items():
        if target_pos is not None:
            target_obstacle_distances.append(
                (name, float(np.linalg.norm(target_pos - pos)))
            )
        if end_effector_pos is not None:
            effector_non_target_distances.append(
                (name, float(np.linalg.norm(end_effector_pos - pos)))
            )

    target_obstacle_min = (
        min(distance for _, distance in target_obstacle_distances)
        if target_obstacle_distances
        else None
    )
    effector_non_target_min = (
        min(distance for _, distance in effector_non_target_distances)
        if effector_non_target_distances
        else None
    )

    return {
        "target_object": target_object,
        "visible_block_count": len(block_positions),
        "non_target_count": len(non_target_positions),
        "target_obstacle_min_distance": target_obstacle_min,
        "effector_non_target_min_distance": effector_non_target_min,
        "collision_proxy_count": sum(
            1
            for _, distance in target_obstacle_distances
            if distance <= collision_distance_world
        ),
        "interference_proxy_count": sum(
            1
            for _, distance in effector_non_target_distances
            if distance <= interference_distance_world
        ),
    }


def needs_detector(args):
    return (
        args.controller_variant != "semantic_mpc"
        or bool(args.target_image)
        or bool(getattr(args, "load_detector_for_semantic", False))
    )


def draw_presentation_label(frame, label, step=None):
    canvas = frame.copy()
    height, width = canvas.shape[:2]
    pad = max(8, width // 80)
    bar_h = max(34, height // 12)
    overlay = canvas.copy()
    cv2.rectangle(overlay, (0, 0), (width, bar_h), (18, 54, 90), -1)
    canvas = cv2.addWeighted(overlay, 0.82, canvas, 0.18, 0)
    text = label if step is None else f"{label} | step {step}"
    font_scale = max(0.55, width / 1200)
    thickness = max(1, width // 520)
    cv2.putText(
        canvas,
        text,
        (pad, int(bar_h * 0.68)),
        cv2.FONT_HERSHEY_SIMPLEX,
        font_scale,
        (255, 255, 255),
        thickness,
        cv2.LINE_AA,
    )
    return canvas


def parse_presentation_crop(crop_text):
    if not crop_text:
        return None
    try:
        values = [int(part.strip()) for part in crop_text.split(",")]
    except ValueError as exc:
        raise ValueError(
            "--presentation_crop must be formatted as x,y,width,height"
        ) from exc
    if len(values) != 4:
        raise ValueError("--presentation_crop must contain four integers: x,y,width,height")
    x, y, width, height = values
    if width <= 0 or height <= 0:
        raise ValueError("--presentation_crop width and height must be positive")
    return x, y, width, height


def crop_resize_presentation_frame(frame, args):
    crop = parse_presentation_crop(getattr(args, "presentation_crop", None))
    if crop is not None:
        x, y, width, height = crop
        frame_h, frame_w = frame.shape[:2]
        x0 = max(0, min(frame_w - 1, x))
        y0 = max(0, min(frame_h - 1, y))
        x1 = max(x0 + 1, min(frame_w, x + width))
        y1 = max(y0 + 1, min(frame_h, y + height))
        frame = frame[y0:y1, x0:x1]
    target_size = (args.presentation_width, args.presentation_height)
    if frame.shape[1] != target_size[0] or frame.shape[0] != target_size[1]:
        frame = cv2.resize(frame, target_size, interpolation=cv2.INTER_CUBIC)
    return frame


def write_gif_pil(path, frames, duration_ms):
    images = [Image.fromarray(frame) for frame in frames]
    if not images:
        return
    images[0].save(
        path,
        save_all=True,
        append_images=images[1:],
        duration=duration_ms,
        loop=0,
        optimize=False,
    )


def write_mp4_cv2(path, frames, fps):
    if not frames:
        return
    height, width = frames[0].shape[:2]
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        float(fps),
        (width, height),
    )
    if not writer.isOpened():
        return
    try:
        for frame in frames:
            writer.write(frame[..., ::-1])
    finally:
        writer.release()


def write_presentation_assets(args, raw_frames, boxed_frames, highres_frames, label):
    if not getattr(args, "presentation_export", False):
        return {}

    fps = max(1, int(args.presentation_fps))
    duration_ms = int(round(1000 / fps))
    output = {}

    presentation_frames = []
    source_frames = highres_frames if highres_frames else raw_frames
    for idx, frame in enumerate(source_frames):
        hi = crop_resize_presentation_frame(frame, args)
        hi = draw_presentation_label(hi, label, idx)
        presentation_frames.append(hi)
        frame_path = args.log_dir / f"presentation_frame_{idx:02d}.png"
        cv2_write_image(frame_path, hi[..., ::-1])

    if presentation_frames:
        gif_path = args.log_dir / "presentation_output.gif"
        write_gif_pil(str(gif_path), presentation_frames, duration_ms)
        mp4_path = args.log_dir / "presentation_output.mp4"
        write_mp4_cv2(mp4_path, presentation_frames, fps)
        output["presentation_output_gif"] = str(gif_path)
        output["presentation_output_mp4"] = str(mp4_path)
        output["presentation_frame_count"] = len(presentation_frames)
        output["presentation_frame_size"] = list(presentation_frames[0].shape[:2])

    presentation_boxed = []
    for idx, frame in enumerate(boxed_frames):
        hi = cv2.resize(frame, (args.presentation_width, args.presentation_height), interpolation=cv2.INTER_LINEAR)
        hi = crop_resize_presentation_frame(hi, args)
        hi = draw_presentation_label(hi, f"{label} boxed", idx)
        presentation_boxed.append(hi)
        frame_path = args.log_dir / f"presentation_frame_bbx_{idx:02d}.png"
        cv2_write_image(frame_path, hi[..., ::-1])

    if presentation_boxed:
        gif_path = args.log_dir / "presentation_output_with_boxes.gif"
        write_gif_pil(str(gif_path), presentation_boxed, duration_ms)
        mp4_path = args.log_dir / "presentation_output_with_boxes.mp4"
        write_mp4_cv2(mp4_path, presentation_boxed, fps)
        output["presentation_output_with_boxes_gif"] = str(gif_path)
        output["presentation_output_with_boxes_mp4"] = str(mp4_path)

    key_indices = sorted({0, max(0, len(presentation_frames) // 2), max(0, len(presentation_frames) - 1)})
    key_frames = [presentation_frames[i] for i in key_indices if presentation_frames]
    if key_frames:
        gap = 16
        h, w = key_frames[0].shape[:2]
        sheet = np.full((h, w * len(key_frames) + gap * (len(key_frames) - 1), 3), 245, dtype=np.uint8)
        for idx, frame in enumerate(key_frames):
            x = idx * (w + gap)
            sheet[:, x : x + w] = frame
        sheet_path = args.log_dir / "presentation_contact_sheet.png"
        cv2_write_image(sheet_path, sheet[..., ::-1])
        output["presentation_contact_sheet"] = str(sheet_path)

    return output


def mpc_loop(vlmpc, init_frame, frame, env, args, logger):
    last_frame = init_frame
    current_frame = frame
    loop_obs = [init_frame, frame]
    highres_obs = []
    if args.presentation_export:
        highres_size = (args.presentation_height, args.presentation_width)
        highres_obs = [
            env._render_camera(image_size=highres_size),
            env._render_camera(image_size=highres_size),
        ]
    frames = torch.cat(
        [torch.from_numpy(last_frame[None]), torch.from_numpy(current_frame[None])]
    )
    run_metrics = {
        "step_durations": [],
        "executed_actions": [],
        "overall_success": False,
        "terminated_early": False,
        "initial_target_distance": None,
        "final_target_distance": None,
        "distance_delta": None,
        "initial_target_world_distance": None,
        "final_target_world_distance": None,
        "target_world_distance_delta": None,
        "target_world_distance_history": [],
        "target_success": False,
        "success_distance_world": args.success_distance_world,
        "initial_scene_distance_sum": None,
        "final_scene_distance_sum": None,
        "scene_distance_delta": None,
        "initial_scene_distance_mean": None,
        "final_scene_distance_mean": None,
        "scene_distance_mean_delta": None,
        "scene_visible_count_initial": None,
        "scene_visible_count_final": None,
        "collision_distance_world": args.collision_distance_world,
        "interference_distance_world": args.interference_distance_world,
        "collision_proxy_events": 0,
        "interference_proxy_events": 0,
        "min_target_obstacle_distance": None,
        "min_effector_non_target_distance": None,
        "interference_history": [],
        "evaluated_target_object": args.evaluation_target_object,
        "controller_declared_complete": False,
    }

    def evaluated_target_object():
        return args.evaluation_target_object or getattr(vlmpc, "current_interactive_object", None)

    def record_interference_state(state):
        stats = world_interference_stats(
            state,
            getattr(vlmpc, "current_interactive_object", None),
            args.collision_distance_world,
            args.interference_distance_world,
        )
        run_metrics["interference_history"].append(stats)
        if stats["collision_proxy_count"] > 0:
            run_metrics["collision_proxy_events"] += 1
        if stats["interference_proxy_count"] > 0:
            run_metrics["interference_proxy_events"] += 1
        if stats["target_obstacle_min_distance"] is not None:
            previous = run_metrics["min_target_obstacle_distance"]
            run_metrics["min_target_obstacle_distance"] = (
                stats["target_obstacle_min_distance"]
                if previous is None
                else min(previous, stats["target_obstacle_min_distance"])
            )
        if stats["effector_non_target_min_distance"] is not None:
            previous = run_metrics["min_effector_non_target_distance"]
            run_metrics["min_effector_non_target_distance"] = (
                stats["effector_non_target_min_distance"]
                if previous is None
                else min(previous, stats["effector_non_target_min_distance"])
            )
        return stats

    init_task_path = args.log_dir / "init_task.png"
    if init_task_path.is_file():
        initial_scene_stats = vlmpc.scene_distance_stats(str(init_task_path), force_refresh=True)
        run_metrics["initial_scene_distance_sum"] = initial_scene_stats["scene_distance_sum"]
        run_metrics["initial_scene_distance_mean"] = initial_scene_stats["scene_distance_mean"]
        run_metrics["scene_visible_count_initial"] = initial_scene_stats["visible_count"]

    state = env._compute_state(request_task_update=False)
    vlmpc.update_oracle_state(state)
    initial_world_distance = target_world_distance(state, evaluated_target_object())
    if initial_world_distance is not None:
        run_metrics["initial_target_world_distance"] = initial_world_distance
        run_metrics["target_world_distance_history"].append(initial_world_distance)
    record_interference_state(state)

    num_steps = 0
    while num_steps < args.max_traj_length:
        logger.info("step %s", num_steps)
        state = env._compute_state(request_task_update=False)
        vlmpc.update_oracle_state(state)
        record_interference_state(state)
        current_world_distance = target_world_distance(state, evaluated_target_object())
        if current_world_distance is not None and current_world_distance <= args.success_distance_world:
            run_metrics["overall_success"] = True
            run_metrics["target_success"] = True
            run_metrics["terminated_early"] = True
            logger.info("Target object reached the world-coordinate success region before acting.")
            break

        time0 = time.time()
        best_action = vlmpc.act(num_steps, frames)
        if run_metrics["initial_target_distance"] is None and hasattr(vlmpc, "obj_pos"):
            run_metrics["initial_target_distance"] = float(
                np.linalg.norm(vlmpc.obj_pos - vlmpc.corner_pos)
            )

        if isinstance(best_action, int):
            logger.info("All the blocks have been pushed to the corner.")
            run_metrics["controller_declared_complete"] = True
            evaluation_distance = target_world_distance(state, evaluated_target_object())
            if evaluation_distance is None or evaluation_distance <= args.success_distance_world:
                run_metrics["overall_success"] = True
                run_metrics["target_success"] = True
            else:
                logger.info(
                    "Controller declared completion, but audit target %s remains at %.4f.",
                    evaluated_target_object(),
                    evaluation_distance,
                )
            run_metrics["terminated_early"] = True
            break

        logger.info("exec action is: %s", best_action)
        run_metrics["executed_actions"].append(np.asarray(best_action).tolist())
        env.step(best_action)

        last_frame = current_frame
        current_frame = env._render_camera(image_size=env._image_size)
        frames = torch.cat(
            [torch.from_numpy(last_frame[None]), torch.from_numpy(current_frame[None])]
        )

        loop_obs.append(current_frame)
        if args.presentation_export:
            highres_obs.append(
                env._render_camera(image_size=(args.presentation_height, args.presentation_width))
            )
        cv2_write_image(f"{vlmpc.log_dir}/frame_{vlmpc.num_steps}.png", current_frame[..., ::-1])
        num_steps += 1
        post_state = env._compute_state(request_task_update=False)
        vlmpc.update_oracle_state(post_state)
        record_interference_state(post_state)
        post_world_distance = target_world_distance(post_state, evaluated_target_object())
        if post_world_distance is not None:
            run_metrics["target_world_distance_history"].append(post_world_distance)
            run_metrics["final_target_world_distance"] = post_world_distance
            if run_metrics["initial_target_world_distance"] is None:
                run_metrics["initial_target_world_distance"] = post_world_distance
            if post_world_distance <= args.success_distance_world:
                run_metrics["overall_success"] = True
                run_metrics["target_success"] = True
                run_metrics["terminated_early"] = True
                logger.info(
                    "Target object reached the world-coordinate success region: %.4f",
                    post_world_distance,
                )
                step_duration = time.time() - time0
                run_metrics["step_durations"].append(step_duration)
                logger.info("one step: %s", step_duration)
                break
        step_duration = time.time() - time0
        run_metrics["step_durations"].append(step_duration)
        logger.info("one step: %s", step_duration)

    imageio.mimsave(f"{args.log_dir}/output.gif", loop_obs, "GIF", duration=0.5)
    boxed_observations = vlmpc.obs_list or [current_frame]
    imageio.mimsave(
        f"{vlmpc.log_dir}/current_obs_with_boxes.gif",
        boxed_observations,
        "GIF",
        duration=0.1,
    )
    final_frame_path = args.log_dir / "final_frame.png"
    cv2_write_image(final_frame_path, current_frame[..., ::-1])
    if getattr(vlmpc, "current_interactive_object", None) and vlmpc.det_model is not None:
        final_bbox = det_bbox(
            image_path=str(final_frame_path),
            model=vlmpc.det_model,
            obj_str=vlmpc.current_interactive_object,
        )
        if not isinstance(final_bbox, int):
            final_center = np.array(
                [
                    (final_bbox[0][0] + final_bbox[1][0]) / 2,
                    (final_bbox[0][1] + final_bbox[1][1]) / 2,
                ]
            )
            run_metrics["final_target_distance"] = float(
                np.linalg.norm(final_center - vlmpc.corner_pos)
            )
    if (
        run_metrics["initial_target_distance"] is not None
        and run_metrics["final_target_distance"] is not None
    ):
        run_metrics["distance_delta"] = float(
            run_metrics["initial_target_distance"] - run_metrics["final_target_distance"]
        )
    final_state = env._compute_state(request_task_update=False)
    record_interference_state(final_state)
    final_world_distance = target_world_distance(final_state, evaluated_target_object())
    if final_world_distance is not None:
        run_metrics["final_target_world_distance"] = final_world_distance
        if run_metrics["initial_target_world_distance"] is not None:
            run_metrics["target_world_distance_delta"] = float(
                run_metrics["initial_target_world_distance"] - final_world_distance
            )
        if final_world_distance <= args.success_distance_world:
            run_metrics["overall_success"] = True
            run_metrics["target_success"] = True
    final_scene_stats = vlmpc.scene_distance_stats(str(final_frame_path), force_refresh=True)
    run_metrics["final_scene_distance_sum"] = final_scene_stats["scene_distance_sum"]
    run_metrics["final_scene_distance_mean"] = final_scene_stats["scene_distance_mean"]
    run_metrics["scene_visible_count_final"] = final_scene_stats["visible_count"]
    if (
        run_metrics["initial_scene_distance_sum"] is not None
        and run_metrics["final_scene_distance_sum"] is not None
    ):
        run_metrics["scene_distance_delta"] = float(
            run_metrics["initial_scene_distance_sum"] - run_metrics["final_scene_distance_sum"]
        )
    if (
        run_metrics["initial_scene_distance_mean"] is not None
        and run_metrics["final_scene_distance_mean"] is not None
    ):
        run_metrics["scene_distance_mean_delta"] = float(
            run_metrics["initial_scene_distance_mean"] - run_metrics["final_scene_distance_mean"]
        )
    run_metrics["num_steps_executed"] = num_steps
    run_metrics["mean_step_duration"] = safe_mean(run_metrics["step_durations"])
    run_metrics.update(
        write_presentation_assets(
            args,
            loop_obs,
            vlmpc.obs_list,
            highres_obs,
            label=args.presentation_label or args.controller_variant,
        )
    )
    return run_metrics


def collect_run_metrics(args, vlmpc, loop_metrics, total_runtime_seconds):
    planner_metrics = vlmpc.metrics
    return {
        "tag": args.tag,
        "task": args.task,
        "target_object": args.target_object,
        "target_instruction": args.target_instruction,
        "target_image": str(args.target_image) if args.target_image else None,
        "target_image_selector": args.target_image_selector,
        "evaluation_target_object": args.evaluation_target_object,
        "audit_initial_target_object": args.audit_initial_target_object,
        "audit_force_event_requery_step": args.audit_force_event_requery_step,
        "seed": args.seed,
        "vlm_backend": args.vlm_backend,
        "vlm_cache_dir": str(args.vlm_cache_dir) if args.vlm_cache_dir else None,
        "openai_model": args.openai_model if args.vlm_backend == "openai" else None,
        "openai_wire_api": args.openai_wire_api if args.vlm_backend == "openai" else None,
        "openai_endpoint_configured": bool(args.openai_base_url) if args.vlm_backend == "openai" else False,
        "openai_api_key_present": bool(args.openai_api_key or os.environ.get(args.openai_api_key_env)),
        "controller_variant": args.controller_variant,
        "log_dir": str(args.log_dir),
        "num_samples": args.num_samples,
        "plan_freq": args.plan_freq,
        "action_horizon": args.action_horizon,
        "max_traj_length": args.max_traj_length,
        "zoom": args.zoom,
        "history_rate": args.history_rate,
        "ratio_tar_obj": args.ratio_tar_obj,
        "semantic_contact_offset": args.semantic_contact_offset,
        "semantic_clearance": args.semantic_clearance,
        "semantic_move_step": args.semantic_move_step,
        "semantic_push_step": args.semantic_push_step,
        "feedback_source": args.feedback_source,
        "visual_action_sign_x": args.visual_action_sign_x,
        "visual_action_sign_y": args.visual_action_sign_y,
        "force_vlm_requery_once": args.force_vlm_requery_once,
        "grounded_original_mpc": args.grounded_original_mpc,
        "enable_event_vlm_requery": args.enable_event_vlm_requery,
        "event_requery_unblock_fixed_target": args.event_requery_unblock_fixed_target,
        "event_requery_window": args.event_requery_window,
        "event_requery_min_progress": args.event_requery_min_progress,
        "event_requery_min_step": args.event_requery_min_step,
        "runtime_seconds_total": float(total_runtime_seconds),
        "overall_success": loop_metrics["overall_success"],
        "terminated_early": loop_metrics["terminated_early"],
        "evaluated_target_object": loop_metrics["evaluated_target_object"],
        "controller_declared_complete": loop_metrics["controller_declared_complete"],
        "num_steps_executed": loop_metrics["num_steps_executed"],
        "step_durations": loop_metrics["step_durations"],
        "mean_step_duration": loop_metrics["mean_step_duration"],
        "executed_actions": loop_metrics["executed_actions"],
        "initial_target_distance": loop_metrics["initial_target_distance"],
        "final_target_distance": loop_metrics["final_target_distance"],
        "distance_delta": loop_metrics["distance_delta"],
        "initial_target_world_distance": loop_metrics["initial_target_world_distance"],
        "final_target_world_distance": loop_metrics["final_target_world_distance"],
        "target_world_distance_delta": loop_metrics["target_world_distance_delta"],
        "target_world_distance_history": loop_metrics["target_world_distance_history"],
        "target_success": loop_metrics["target_success"],
        "success_distance_world": loop_metrics["success_distance_world"],
        "initial_scene_distance_sum": loop_metrics["initial_scene_distance_sum"],
        "final_scene_distance_sum": loop_metrics["final_scene_distance_sum"],
        "scene_distance_delta": loop_metrics["scene_distance_delta"],
        "initial_scene_distance_mean": loop_metrics["initial_scene_distance_mean"],
        "final_scene_distance_mean": loop_metrics["final_scene_distance_mean"],
        "scene_distance_mean_delta": loop_metrics["scene_distance_mean_delta"],
        "scene_visible_count_initial": loop_metrics["scene_visible_count_initial"],
        "scene_visible_count_final": loop_metrics["scene_visible_count_final"],
        "collision_distance_world": loop_metrics["collision_distance_world"],
        "interference_distance_world": loop_metrics["interference_distance_world"],
        "collision_proxy_events": loop_metrics["collision_proxy_events"],
        "interference_proxy_events": loop_metrics["interference_proxy_events"],
        "min_target_obstacle_distance": loop_metrics["min_target_obstacle_distance"],
        "min_effector_non_target_distance": loop_metrics["min_effector_non_target_distance"],
        "interference_history": loop_metrics["interference_history"],
        "reset_calls": planner_metrics["reset_calls"],
        "reset_reasons": planner_metrics["reset_reasons"],
        "subtask_requests": planner_metrics["subtask_requests"],
        "interactive_object_requests": planner_metrics["interactive_object_requests"],
        "subtasks": planner_metrics["subtasks"],
        "interactive_objects": planner_metrics["interactive_objects"],
        "accepted_subtask_sources": planner_metrics["accepted_subtask_sources"],
        "subtask_times": planner_metrics["subtask_times"],
        "interactive_object_times": planner_metrics["interactive_object_times"],
        "mean_subtask_time": safe_mean(planner_metrics["subtask_times"]),
        "mean_interactive_object_time": safe_mean(planner_metrics["interactive_object_times"]),
        "track_center_times": planner_metrics["track_center_times"],
        "cost_calc_times": planner_metrics["cost_calc_times"],
        "mean_track_center_time": safe_mean(planner_metrics["track_center_times"]),
        "mean_cost_calc_time": safe_mean(planner_metrics["cost_calc_times"]),
        "plan_calls": planner_metrics["plan_calls"],
        "end_effector_track_fallbacks": planner_metrics["end_effector_track_fallbacks"],
        "object_track_fallbacks": planner_metrics["object_track_fallbacks"],
        "object_jump_fallbacks": planner_metrics["object_jump_fallbacks"],
        "reuse_last_bbox_count": planner_metrics["reuse_last_bbox_count"],
        "invalid_vlm_object_count": planner_metrics["invalid_vlm_object_count"],
        "subtask_corrections": planner_metrics["subtask_corrections"],
        "event_requeries": planner_metrics["event_requeries"],
        "event_requery_checks": planner_metrics.get("event_requery_checks", 0),
        "natural_event_requeries": planner_metrics.get("natural_event_requeries", 0),
        "event_requery_blocked_fixed_target": planner_metrics.get("event_requery_blocked_fixed_target", 0),
        "requery_reasons": planner_metrics["requery_reasons"],
        "active_num_samples": planner_metrics["active_num_samples"],
        "active_plan_freq": planner_metrics["active_plan_freq"],
        "budget_history": planner_metrics["budget_history"],
        "budget_context_history": planner_metrics.get("budget_context_history", []),
        "distance_history": planner_metrics["distance_history"],
        "progress_history": planner_metrics["progress_history"],
        "stagnation_events": planner_metrics["stagnation_events"],
        "stall_replans": planner_metrics["stall_replans"],
        "progress_reselections": planner_metrics["progress_reselections"],
        "stall_subtask_switches": planner_metrics["stall_subtask_switches"],
        "semantic_policy_calls": planner_metrics["semantic_policy_calls"],
        "semantic_phases": planner_metrics["semantic_phases"],
        "semantic_world_distances": planner_metrics["semantic_world_distances"],
        "semantic_feedback_source": planner_metrics.get("semantic_feedback_source", args.feedback_source),
        "visual_servo_calls": planner_metrics.get("visual_servo_calls", 0),
        "visual_servo_phases": planner_metrics.get("visual_servo_phases", []),
        "visual_distance_pixels": planner_metrics.get("visual_distance_pixels", []),
        "visual_object_pixels": planner_metrics.get("visual_object_pixels", []),
        "visual_effector_pixels": planner_metrics.get("visual_effector_pixels", []),
        "visual_contact_pixels": planner_metrics.get("visual_contact_pixels", []),
        "visual_contact_error_pixels": planner_metrics.get("visual_contact_error_pixels", []),
        "visual_requested_delta_pixels": planner_metrics.get("visual_requested_delta_pixels", []),
        "visual_adaptive_actions": planner_metrics.get("visual_adaptive_actions", []),
        "visual_jacobian_history": planner_metrics.get("visual_jacobian_history", []),
        "visual_jacobian_updates": planner_metrics.get("visual_jacobian_updates", []),
        "visual_detection_fallbacks": planner_metrics.get("visual_detection_fallbacks", 0),
        "visual_missing_detections": planner_metrics.get("visual_missing_detections", []),
        "target_image_selection_details": planner_metrics.get("target_image_selection_details", []),
        "grounded_original_mpc": planner_metrics.get("grounded_original_mpc", False),
        "grounded_original_policy_calls": planner_metrics.get("grounded_original_policy_calls", 0),
        "grounded_original_overrides": planner_metrics.get("grounded_original_overrides", 0),
        "grounded_original_phases": planner_metrics.get("grounded_original_phases", []),
        "grounded_original_world_distances": planner_metrics.get("grounded_original_world_distances", []),
        "raw_mpc_actions": planner_metrics.get("raw_mpc_actions", []),
        "grounded_original_actions": planner_metrics.get("grounded_original_actions", []),
        "event_requery_triggers": planner_metrics.get("event_requery_triggers", []),
        "mean_active_num_samples": safe_mean(planner_metrics["active_num_samples"]),
        "mean_active_plan_freq": safe_mean(planner_metrics["active_plan_freq"]),
        "current_interactive_object": (
            planner_metrics["interactive_objects"][-1]
            if planner_metrics["interactive_objects"]
            else None
        ),
        "current_subtask": planner_metrics["subtasks"][-1] if planner_metrics["subtasks"] else None,
    }


def write_metrics_file(args, metrics):
    metrics_path = args.log_dir / "metrics.json"
    with metrics_path.open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2, ensure_ascii=False)
    return metrics_path


def build_arg_parser():
    load_dotenv(PROJECT_ROOT / ".env")
    parser = argparse.ArgumentParser("VLMPC parameters")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--tag", type=str, default="run")
    parser.add_argument("--log_root", type=str, default=str(PROJECT_ROOT / "logs"))
    parser.add_argument("--model", type=str, default="dmvfn_action_2dim")
    parser.add_argument("--checkpoint_file", type=str, required=True)
    parser.add_argument("--det_path", type=str, required=True)
    parser.add_argument("--yolo_repo", type=str, default=str(PROJECT_ROOT / "yolov5"))
    parser.add_argument("--tracker_config", type=str, required=True)
    parser.add_argument("--tracker_model", type=str, required=True)
    parser.add_argument(
        "--vlm_backend",
        type=str,
        choices=["codex", "openai"],
        default=os.environ.get("VLMPC_VLM_BACKEND", "codex"),
    )
    parser.add_argument("--codex_bin", type=str, default="codex")
    parser.add_argument("--codex_model", type=str, default=os.environ.get("VLMPC_CODEX_MODEL"))
    parser.add_argument("--codex_timeout", type=int, default=600)
    parser.add_argument("--codex_home", type=str, default=os.environ.get("VLMPC_CODEX_HOME"))
    parser.add_argument("--vlm_cache_dir", type=str, default=os.environ.get("VLMPC_VLM_CACHE_DIR"))
    parser.add_argument("--openai_model", type=str, default=os.environ.get("VLMPC_OPENAI_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--openai_api_key", type=str, default=os.environ.get("VLMPC_OPENAI_API_KEY"))
    parser.add_argument(
        "--openai_api_key_env",
        type=str,
        default=os.environ.get("VLMPC_OPENAI_API_KEY_ENV", "OPENAI_API_KEY"),
    )
    parser.add_argument(
        "--openai_base_url",
        type=str,
        default=os.environ.get("VLMPC_OPENAI_BASE_URL", "https://api.openai.com/v1"),
    )
    parser.add_argument(
        "--openai_wire_api",
        type=str,
        choices=["chat", "responses"],
        default=os.environ.get("VLMPC_OPENAI_WIRE_API", "chat"),
        help="HTTP schema for OpenAI-compatible calls: chat uses /chat/completions; responses uses /responses.",
    )
    parser.add_argument("--openai_timeout", type=int, default=600)
    parser.add_argument("--action_dim", type=int, default=2)
    parser.add_argument("--action_horizon", type=int, default=20)
    parser.add_argument("--max_traj_length", type=int, default=2000)
    parser.add_argument("--task", type=str, choices=["make_line", "push_corner", "group_color"], default="push_corner")
    parser.add_argument(
        "--target_object",
        type=str,
        default=None,
        help="Optional fixed target object for push_corner, e.g. 'blue cube'. If omitted, VLM selects the target.",
    )
    parser.add_argument(
        "--target_instruction",
        type=str,
        default=None,
        help="Optional natural-language instruction. The LLM extracts the target object from this instruction.",
    )
    parser.add_argument(
        "--target_image",
        type=str,
        default=None,
        help="Optional goal/target image. The selected object is chosen by --target_image_selector.",
    )
    parser.add_argument(
        "--target_image_selector",
        type=str,
        choices=["auto", "vlm", "vision"],
        default=os.environ.get("VLMPC_TARGET_IMAGE_SELECTOR", "auto"),
        help=(
            "Target-image semantic selector. 'vlm' requires a VLM image match; "
            "'vision' uses detector/descriptor matching; 'auto' tries VLM first and records any fallback."
        ),
    )
    parser.add_argument(
        "--evaluation_target_object",
        type=str,
        default=None,
        help="Optional independent ground-truth object used only for success evaluation.",
    )
    parser.add_argument(
        "--audit_initial_target_object",
        type=str,
        default=None,
        help="Synthetic audit only: replace the initially selected controller target.",
    )
    parser.add_argument(
        "--audit_force_event_requery_step",
        type=int,
        default=-1,
        help="Synthetic audit only: force one event re-query at this semantic-controller step.",
    )
    parser.add_argument("--success_distance_world", type=float, default=0.08)
    parser.add_argument(
        "--collision_distance_world",
        type=float,
        default=0.09,
        help="World-distance threshold used to count target-vs-non-target collision proxy events.",
    )
    parser.add_argument(
        "--interference_distance_world",
        type=float,
        default=0.07,
        help="World-distance threshold used to count end-effector/non-target interference proxy events.",
    )
    parser.add_argument(
        "--load_detector_for_semantic",
        action="store_true",
        help="Load YOLO during semantic_mpc runs to compute image-space scene diagnostics.",
    )
    parser.add_argument("--semantic_contact_offset", type=float, default=0.06)
    parser.add_argument("--semantic_clearance", type=float, default=0.12)
    parser.add_argument("--semantic_move_step", type=float, default=0.06)
    parser.add_argument("--semantic_push_step", type=float, default=0.075)
    parser.add_argument(
        "--feedback_source",
        type=str,
        choices=["oracle", "visual"],
        default="oracle",
        help=(
            "Feedback state source for semantic/grounded diagnostic controllers. "
            "'oracle' uses simulator state; 'visual' uses detector/tracker image estimates."
        ),
    )
    parser.add_argument("--visual_action_sign_x", type=float, default=1.0)
    parser.add_argument("--visual_action_sign_y", type=float, default=-1.0)
    parser.add_argument(
        "--force_vlm_requery_once",
        action="store_true",
        help="Audit mode: force one second VLM subtask query with an exclusion list.",
    )
    parser.add_argument(
        "--grounded_original_mpc",
        action="store_true",
        help=(
            "Run the original video-prediction MPC planner but execute an oracle-state "
            "feedback correction. This is an enhanced original-chain variant, not the "
            "unmodified baseline."
        ),
    )
    parser.add_argument(
        "--enable_event_vlm_requery",
        action="store_true",
        help="Enable natural event-triggered VLM requery for non-semantic MPC variants.",
    )
    parser.add_argument(
        "--event_requery_unblock_fixed_target",
        action="store_true",
        help="Allow event-triggered VLM refresh even for instruction/fixed-target audit runs.",
    )
    parser.add_argument("--event_requery_window", type=int, default=3)
    parser.add_argument("--event_requery_min_progress", type=float, default=1.0)
    parser.add_argument("--event_requery_min_step", type=int, default=3)
    parser.add_argument("--plan_freq", type=int, default=5)
    parser.add_argument("--init_mean", type=float, default=0.01)
    parser.add_argument("--zoom", type=float, default=0.02)
    parser.add_argument("--history_rate", type=float, default=0.5)
    parser.add_argument("--ratio_tar_obj", type=float, default=0.5)
    parser.add_argument("--num_samples", type=int, default=200)
    parser.add_argument("--presentation_export", action="store_true")
    parser.add_argument("--presentation_width", type=int, default=1280)
    parser.add_argument("--presentation_height", type=int, default=720)
    parser.add_argument("--presentation_scale", type=int, default=4)
    parser.add_argument("--presentation_fps", type=int, default=2)
    parser.add_argument("--presentation_label", type=str, default=None)
    parser.add_argument(
        "--presentation_crop",
        type=str,
        default=None,
        help="Optional crop before resizing, formatted as x,y,width,height in presentation frame pixels.",
    )
    parser.add_argument(
        "--controller_variant",
        type=str,
        choices=["baseline", "improved", "literature", "literature_v2", "semantic_mpc"],
        default="baseline",
    )
    return parser


def main(args):
    time0 = time.time()
    import_language_table_runtime()
    env = language_table.LanguageTable(
        block_mode=blocks.LanguageTableBlockVariants.BLOCK_8,
        reward_factory=block1_to_corner.Block1ToCornerLocationReward,
        control_frequency=10.0,
        seed=args.seed,
    )
    init_obs = env.reset()
    init_frame = init_obs["rgb"]
    plt.imsave(f"{args.log_dir}/init_task.png", env._render_camera(image_size=env._image_size))

    if args.controller_variant == "semantic_mpc":
        model = None
    else:
        if args.model != "dmvfn_action_2dim":
            raise ValueError(f"Unsupported video prediction model: {args.model}")

        model = DMVFNActModel(
            checkpoint_file=str(args.checkpoint_file),
            action_dim=args.action_dim,
            n_past=2,
            max_batch_size=max(args.num_samples, 10),
        )
        model.model.dmvfn.eval()

    det_model = None
    if needs_detector(args):
        det_model = torch.hub.load(
            str(args.yolo_repo),
            "custom",
            path=str(args.det_path),
            source="local",
        )

    vlm_client = create_vlm_client(
        backend=args.vlm_backend,
        workdir=PROJECT_ROOT,
        logger=logger,
        codex_bin=args.codex_bin,
        codex_model=args.codex_model,
        codex_timeout=args.codex_timeout,
        codex_home=args.codex_home,
        vlm_cache_dir=args.vlm_cache_dir,
        openai_model=args.openai_model,
        openai_api_key=args.openai_api_key,
        openai_api_key_env=args.openai_api_key_env,
        openai_base_url=args.openai_base_url,
        openai_wire_api=args.openai_wire_api,
        openai_timeout=args.openai_timeout,
    )

    vlmpc = VLMPC(
        video_prediction_model=model,
        action_dim=args.action_dim,
        det_model=det_model,
        action_horizon=args.action_horizon,
        tracker_config_path=args.tracker_config,
        tracker_model_path=args.tracker_model,
        vlm_client=vlm_client,
        logdir=args.log_dir,
        logger=logger,
        task=args.task,
        plan_freq=args.plan_freq,
        init_std=args.init_mean,
        zoom=args.zoom,
        history_rate=args.history_rate,
        ratio_tar_obj=args.ratio_tar_obj,
        num_samples=args.num_samples,
        controller_variant=args.controller_variant,
        target_object=args.target_object,
        target_instruction=args.target_instruction,
        target_image=args.target_image,
        target_image_selector=args.target_image_selector,
        semantic_contact_offset=args.semantic_contact_offset,
        semantic_clearance=args.semantic_clearance,
        semantic_move_step=args.semantic_move_step,
        semantic_push_step=args.semantic_push_step,
        success_distance_world=args.success_distance_world,
        feedback_source=args.feedback_source,
        visual_action_sign_x=args.visual_action_sign_x,
        visual_action_sign_y=args.visual_action_sign_y,
        force_vlm_requery_once=args.force_vlm_requery_once,
        grounded_original_mpc=args.grounded_original_mpc,
        enable_event_vlm_requery=args.enable_event_vlm_requery,
        event_requery_unblock_fixed_target=args.event_requery_unblock_fixed_target,
        event_requery_window=args.event_requery_window,
        event_requery_min_progress=args.event_requery_min_progress,
        event_requery_min_step=args.event_requery_min_step,
        audit_initial_target_object=args.audit_initial_target_object,
        audit_force_event_requery_step=args.audit_force_event_requery_step,
    )
    init_action = vlmpc.reset(init_frame)
    env.step(init_action)
    frame = env._render_camera(image_size=env._image_size)
    loop_metrics = mpc_loop(vlmpc, init_frame, frame, env, args, logger)
    metrics = collect_run_metrics(args, vlmpc, loop_metrics, time.time() - time0)
    metrics_path = write_metrics_file(args, metrics)
    logger.info("saved metrics to: %s", metrics_path)


if __name__ == "__main__":
    parser = build_arg_parser()
    args = parser.parse_args()

    args.log_root = resolve_path(args.log_root)
    args.log_root.mkdir(parents=True, exist_ok=True)
    args.checkpoint_file = resolve_path(args.checkpoint_file)
    args.det_path = resolve_path(args.det_path)
    args.yolo_repo = resolve_path(args.yolo_repo)
    args.tracker_config = resolve_path(args.tracker_config)
    args.tracker_model = resolve_path(args.tracker_model)
    if args.codex_home:
        args.codex_home = resolve_path(args.codex_home)
    if args.vlm_cache_dir:
        args.vlm_cache_dir = resolve_path(args.vlm_cache_dir)
    if args.target_image:
        args.target_image = resolve_path(args.target_image)

    seed_all(args.seed)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    args.log_dir = args.log_root / f"{args.tag}_{stamp}"
    args.log_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logger(output=str(args.log_dir), color=True, name="vlmpc")
    validate_runtime(args)
    main(args)
