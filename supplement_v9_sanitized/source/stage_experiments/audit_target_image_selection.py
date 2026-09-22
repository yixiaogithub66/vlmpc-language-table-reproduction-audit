"""Audit target-image object selection.

The archived target-image run used a full final frame as the target image.  The
detector then selected the visible object nearest the target corner, which made
the run executable but semantically mismatched with the intended red-moon query.
This script creates explicit cropped target-image assets from archived frames and
records what the target-image selector would choose.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import pathlib
import sys
from datetime import datetime
from pathlib import Path

sys.path = [path for path in sys.path if "vlmpcdeps" not in str(path).lower()]
pythonpath = os.environ.get("PYTHONPATH")
if pythonpath:
    os.environ["PYTHONPATH"] = os.pathsep.join(
        path for path in pythonpath.split(os.pathsep) if "vlmpcdeps" not in path.lower()
    )

import cv2
import numpy as np
import torch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
ARCHIVED_SITE_PACKAGES = PROJECT_ROOT / ".venv312" / "Lib" / "site-packages"
if ARCHIVED_SITE_PACKAGES.is_dir() and str(ARCHIVED_SITE_PACKAGES) not in sys.path:
    sys.path.append(str(ARCHIVED_SITE_PACKAGES))
os.environ.setdefault(
    "YOLO_CONFIG_DIR",
    str(PROJECT_ROOT / "stage_experiments" / ".ultralytics"),
)
if os.name == "nt":
    pathlib.PosixPath = pathlib.WindowsPath

from detect_bbx import detect_visible_objects
from prompt_gpt import SCENE_OBJECTS, canonicalize_object
from vlm_client import create_vlm_client


DEFAULT_CASES = [
    {
        "name": "red_moon_init_crop",
        "expected_object": "red moon",
        "source_run": PROJECT_ROOT / "logs" / "full_rerun_20260606_170225_input_forms_fixed_target_2026-06-06_17-02-33",
        "source_image": "init_task.png",
    },
    {
        "name": "blue_cube_init_crop",
        "expected_object": "blue cube",
        "source_run": PROJECT_ROOT / "logs" / "full_rerun_20260606_170225_multi_target_blue_cube_2026-06-06_17-08-41",
        "source_image": "init_task.png",
    },
    {
        "name": "yellow_pentagon_init_crop",
        "expected_object": "yellow pentagon",
        "source_run": PROJECT_ROOT / "logs" / "full_rerun_20260606_170225_multi_target_yellow_pentagon_2026-06-06_17-12-20",
        "source_image": "init_task.png",
    },
    {
        "name": "archived_full_frame_target_image",
        "expected_object": "red moon",
        "source_run": PROJECT_ROOT / "logs" / "full_rerun_20260606_170225_input_forms_fixed_target_2026-06-06_17-02-33",
        "source_image": "final_frame.png",
        "full_frame_only": True,
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
    parser = argparse.ArgumentParser("Audit target-image selection with detector crops.")
    parser.add_argument("--det_path", type=str, default=str(WORKSPACE_ROOT / "detector_checkpoint.pt"))
    parser.add_argument("--yolo_repo", type=str, default=str(PROJECT_ROOT / "yolov5"))
    parser.add_argument(
        "--output_dir",
        type=str,
        default=str(PROJECT_ROOT / "stage_experiments" / "target_image_selection_audit"),
    )
    parser.add_argument("--padding", type=int, default=14)
    parser.add_argument("--skip_vlm", action="store_true", help="Run only detector/descriptor target-image audit.")
    parser.add_argument("--vlm_backend", type=str, choices=["codex", "openai"], default=os.environ.get("VLMPC_VLM_BACKEND", "openai"))
    parser.add_argument("--codex_bin", type=str, default="codex")
    parser.add_argument("--codex_home", type=str, default=os.environ.get("VLMPC_CODEX_HOME"))
    parser.add_argument("--codex_model", type=str, default=os.environ.get("VLMPC_CODEX_MODEL"))
    parser.add_argument("--codex_timeout", type=int, default=600)
    parser.add_argument("--openai_base_url", type=str, default=os.environ.get("VLMPC_OPENAI_BASE_URL", "https://api.openai.com/v1"))
    parser.add_argument("--openai_model", type=str, default=os.environ.get("VLMPC_OPENAI_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--openai_wire_api", type=str, choices=["chat", "responses"], default=os.environ.get("VLMPC_OPENAI_WIRE_API", "chat"))
    parser.add_argument("--openai_api_key", type=str, default=os.environ.get("VLMPC_OPENAI_API_KEY"))
    parser.add_argument("--openai_api_key_env", type=str, default=os.environ.get("VLMPC_OPENAI_API_KEY_ENV", "OPENAI_API_KEY"))
    parser.add_argument("--openai_timeout", type=int, default=600)
    parser.add_argument(
        "--vlm_cache_dir",
        type=str,
        default=os.environ.get("VLMPC_VLM_CACHE_DIR") or None,
        help="Leave empty for strict no-cache VLM audits.",
    )
    return parser.parse_args()


def resolve(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def bbox_center(bbox: list[list[int]]) -> np.ndarray:
    return np.asarray([(bbox[0][0] + bbox[1][0]) / 2.0, (bbox[0][1] + bbox[1][1]) / 2.0], dtype=np.float32)


def clip_bbox_to_image(bbox: list[list[int]], image_shape: tuple[int, int, int], padding: int = 0) -> tuple[int, int, int, int]:
    height, width = image_shape[:2]
    x1, y1 = bbox[0]
    x2, y2 = bbox[1]
    x1 = max(0, min(width - 1, int(x1) - padding))
    y1 = max(0, min(height - 1, int(y1) - padding))
    x2 = max(x1 + 1, min(width, int(x2) + padding))
    y2 = max(y1 + 1, min(height, int(y2) + padding))
    return x1, y1, x2, y2


def crop_from_bbox(image: np.ndarray, bbox: list[list[int]], padding: int = 0) -> np.ndarray:
    x1, y1, x2, y2 = clip_bbox_to_image(bbox, image.shape, padding=padding)
    return image[y1:y2, x1:x2].copy()


def crop_descriptor(image: np.ndarray) -> dict[str, np.ndarray] | None:
    if image is None or image.size == 0:
        return None
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [24, 16], [0, 180, 0, 256])
    hist = cv2.normalize(hist, hist).flatten()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    circularity = 0.0
    area_ratio = 0.0
    extent = 0.0
    if contours:
        contour = max(contours, key=cv2.contourArea)
        area = float(cv2.contourArea(contour))
        perimeter = float(cv2.arcLength(contour, True))
        if perimeter > 1e-8:
            circularity = float(4.0 * np.pi * area / (perimeter * perimeter))
        area_ratio = area / float(max(image.shape[0] * image.shape[1], 1))
        _, _, width, height = cv2.boundingRect(contour)
        extent = area / float(max(width * height, 1))
    return {
        "hist": hist,
        "shape": np.asarray([circularity, area_ratio, extent], dtype=np.float32),
    }


def descriptor_distance(desc_a: dict[str, np.ndarray] | None, desc_b: dict[str, np.ndarray] | None) -> float:
    if desc_a is None or desc_b is None:
        return float("inf")
    hist_dist = cv2.compareHist(
        desc_a["hist"].astype(np.float32),
        desc_b["hist"].astype(np.float32),
        cv2.HISTCMP_BHATTACHARYYA,
    )
    shape_dist = float(np.linalg.norm(desc_a["shape"] - desc_b["shape"]))
    return float(hist_dist + 0.35 * shape_dist)


def foreground_component_mask(image: np.ndarray) -> np.ndarray | None:
    if image is None or image.size == 0:
        return None
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = ((hsv[:, :, 1] > 45) & (hsv[:, :, 2] > 45)).astype(np.uint8) * 255
    kernel = np.ones((3, 3), dtype=np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if num_labels <= 1:
        return mask if int(mask.sum()) > 0 else None
    image_center = np.asarray([image.shape[1] / 2.0, image.shape[0] / 2.0], dtype=np.float32)
    best_label = None
    best_score = -1.0
    for label in range(1, num_labels):
        area = float(stats[label, cv2.CC_STAT_AREA])
        if area < 8.0:
            continue
        center = np.asarray(centroids[label], dtype=np.float32)
        center_distance = float(np.linalg.norm(center - image_center))
        score = -center_distance + 0.08 * np.sqrt(area)
        if score > best_score:
            best_score = score
            best_label = label
    if best_label is None:
        return None
    return (labels == best_label).astype(np.uint8) * 255


def estimate_color_name(image: np.ndarray, mask: np.ndarray | None) -> str | None:
    if image is None or mask is None or int(mask.sum()) == 0:
        return None
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    pixels = hsv[mask > 0]
    if pixels.size == 0:
        return None
    hue = pixels[:, 0]
    saturation = pixels[:, 1]
    hue = hue[saturation > 45]
    if hue.size == 0:
        return None
    votes = {
        "red": int(np.sum((hue <= 10) | (hue >= 160))),
        "yellow": int(np.sum((hue >= 18) & (hue <= 42))),
        "green": int(np.sum((hue >= 43) & (hue <= 88))),
        "blue": int(np.sum((hue >= 89) & (hue <= 135))),
    }
    color, count = max(votes.items(), key=lambda item: item[1])
    return color if count > 0 else None


def estimate_shape_name(mask: np.ndarray | None, color_name: str | None = None) -> str | None:
    if mask is None or int(mask.sum()) == 0:
        return None
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    area = float(cv2.contourArea(contour))
    perimeter = float(cv2.arcLength(contour, True))
    if area < 5.0 or perimeter < 1e-8:
        return None
    approx = cv2.approxPolyDP(contour, 0.045 * perimeter, True)
    vertices = len(approx)
    hull = cv2.convexHull(contour)
    hull_area = float(cv2.contourArea(hull))
    solidity = area / max(hull_area, 1e-8)
    _, _, width, height = cv2.boundingRect(contour)
    aspect = width / max(float(height), 1e-8)
    circularity = float(4.0 * np.pi * area / (perimeter * perimeter))
    if color_name == "blue" and solidity >= 0.82 and 0.68 <= aspect <= 1.45:
        return "cube"
    if color_name in {"red", "blue"} and solidity < 0.86 and circularity < 0.82 and aspect <= 1.15:
        return "moon"
    if solidity < 0.72:
        if color_name in {"red", "blue"} and circularity < 0.78:
            return "moon"
        return "star"
    if 4 <= vertices <= 6 and 0.72 <= aspect <= 1.35:
        if vertices >= 5:
            return "pentagon"
        return "cube"
    if circularity > 0.58 and color_name in {"red", "blue"}:
        return "moon"
    return "cube" if aspect <= 1.35 else "pentagon"


def semantic_object_from_crop(image: np.ndarray) -> tuple[str | None, dict[str, str | None]]:
    mask = foreground_component_mask(image)
    color_name = estimate_color_name(image, mask)
    shape_name = estimate_shape_name(mask, color_name=color_name)
    if color_name and shape_name:
        candidate = f"{color_name} {shape_name}"
        if candidate in SCENE_OBJECTS:
            return candidate, {
                "estimated_color": color_name,
                "estimated_shape": shape_name,
            }
    return None, {
        "estimated_color": color_name,
        "estimated_shape": shape_name,
    }


def choose_corner_heuristic_object(detections: dict[str, dict[str, object]], image_shape: tuple[int, int, int]) -> str | None:
    if not detections:
        return None
    height, width = image_shape[:2]
    bottom_right = np.asarray([width - 1, height - 1], dtype=np.float32)
    candidates = {name: item["bbox"] for name, item in detections.items() if name != "end effector"}
    if not candidates:
        return None
    return min(candidates, key=lambda name: float(np.linalg.norm(bbox_center(candidates[name]) - bottom_right)))


def choose_visual_match_object(
    target_image: np.ndarray,
    target_detections: dict[str, dict[str, object]],
    scene_image: np.ndarray,
    scene_detections: dict[str, dict[str, object]],
) -> tuple[str | None, list[dict[str, object]]]:
    target_candidates = {name: item for name, item in target_detections.items() if name != "end effector"}
    scene_candidates = {name: item for name, item in scene_detections.items() if name != "end effector"}
    if not target_candidates or not scene_candidates:
        return None, []

    whole_semantic_name, whole_semantic_details = semantic_object_from_crop(target_image)
    if whole_semantic_name and whole_semantic_name in scene_candidates:
        return whole_semantic_name, [
            {
                "object": whole_semantic_name,
                "score": 0.0,
                "confidence": float(scene_candidates[whole_semantic_name].get("confidence", 0.0)),
                "rule": "whole_image_foreground_semantic_match",
                **whole_semantic_details,
            }
        ]

    target_name, target_item = max(
        target_candidates.items(),
        key=lambda item: float(item[1].get("confidence", 0.0)),
    )
    target_crop = crop_from_bbox(target_image, target_item["bbox"], padding=8)
    semantic_name, semantic_details = semantic_object_from_crop(target_crop)
    if semantic_name and semantic_name in scene_candidates:
        return semantic_name, [
            {
                "object": semantic_name,
                "score": 0.0,
                "confidence": float(scene_candidates[semantic_name].get("confidence", 0.0)),
                "rule": "foreground_semantic_match",
                **semantic_details,
            }
        ]

    target_descriptor = crop_descriptor(target_crop)

    scored = []
    for scene_name, scene_item in scene_candidates.items():
        scene_crop = crop_from_bbox(scene_image, scene_item["bbox"], padding=8)
        score = descriptor_distance(target_descriptor, crop_descriptor(scene_crop))
        score += 0.0 if scene_name == target_name else 0.18
        score += -0.05 * float(scene_item.get("confidence", 0.0))
        scored.append(
            {
                "object": scene_name,
                "score": float(score),
                "confidence": float(scene_item.get("confidence", 0.0)),
            }
        )
    scored.sort(key=lambda item: item["score"])
    return scored[0]["object"] if scored else None, scored


def choose_vlm_match_object(
    client,
    target_image_path: Path,
    scene_image_path: Path,
    scene_detections: dict[str, dict[str, object]],
) -> tuple[str, str]:
    candidates = sorted(name for name in scene_detections if name != "end effector")
    if not candidates:
        raise RuntimeError("No visible scene candidates for VLM target-image selection.")
    prompt = f"""
You are matching a target-object image to the current tabletop scene.

Attached images are in this order:
1. Target image: an image or crop of the object the robot should manipulate.
2. Current scene: the tabletop scene where the robot will act.

Choose exactly one object from this closed candidate set:
{", ".join(candidates)}

Rules:
- Match by semantic object identity: color plus shape.
- If the target image is a crop, identify the object in the crop and choose the same object in the current scene.
- If the target image is a full frame with multiple objects, choose the most salient foreground object that best represents the intended target image.
- Return exactly one candidate object name and nothing else.
""".strip()
    raw_response = client.complete(prompt, image_paths=[target_image_path, scene_image_path])
    selected = canonicalize_object(raw_response)
    if selected not in candidates:
        raise ValueError(f"VLM selected {selected!r}, not one of {candidates!r}")
    return selected, raw_response


def crop_object(image: np.ndarray, bbox: list[list[int]], padding: int) -> np.ndarray:
    height, width = image.shape[:2]
    x1, y1 = bbox[0]
    x2, y2 = bbox[1]
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(width, x2 + padding)
    y2 = min(height, y2 + padding)
    return image[y1:y2, x1:x2].copy()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def audit_case(model, out_dir: Path, case: dict[str, object], padding: int, vlm_client=None) -> dict[str, object]:
    source_image = resolve(Path(case["source_run"]) / str(case["source_image"]))
    image = cv2.imread(str(source_image))
    if image is None:
        raise FileNotFoundError(source_image)

    full_detections = detect_visible_objects(source_image, model, include_end_effector=False)
    full_choice = choose_corner_heuristic_object(full_detections, image.shape)
    expected = str(case["expected_object"])
    crop_path = ""
    crop_corner_choice = ""
    crop_visual_choice = ""
    vlm_choice = ""
    vlm_raw_response = ""
    vlm_error = ""
    crop_confidence = ""
    visual_scores = ""
    vlm_target_path = source_image

    if not case.get("full_frame_only"):
        expected_detection = full_detections.get(expected)
        if expected_detection is None:
            raise RuntimeError(f"{expected} not detected in {source_image}")
        crop = crop_object(image, expected_detection["bbox"], padding)
        crop_path_obj = out_dir / f"{case['name']}.png"
        cv2.imwrite(str(crop_path_obj), crop)
        vlm_target_path = crop_path_obj
        crop_detections = detect_visible_objects(crop_path_obj, model, include_end_effector=False)
        crop_corner_choice = choose_corner_heuristic_object(crop_detections, crop.shape) or ""
        crop_visual_choice, scored = choose_visual_match_object(
            target_image=crop,
            target_detections=crop_detections,
            scene_image=image,
            scene_detections=full_detections,
        )
        crop_visual_choice = crop_visual_choice or ""
        if crop_corner_choice:
            crop_confidence = crop_detections[crop_corner_choice]["confidence"]
        visual_scores = "|".join(f"{item['object']}:{item['score']:.4f}" for item in scored)
        crop_path = rel(crop_path_obj)

    if vlm_client is not None:
        try:
            vlm_choice, vlm_raw_response = choose_vlm_match_object(
                client=vlm_client,
                target_image_path=vlm_target_path,
                scene_image_path=source_image,
                scene_detections=full_detections,
            )
        except Exception as exc:
            vlm_error = repr(exc)

    full_confidence = full_detections.get(full_choice, {}).get("confidence", "") if full_choice else ""
    return {
        "case": case["name"],
        "expected_object": expected,
        "source_image": rel(source_image),
        "full_frame_corner_heuristic_choice": full_choice or "",
        "full_frame_confidence": full_confidence,
        "full_frame_corner_heuristic_match": full_choice == expected,
        "crop_image": crop_path,
        "crop_corner_heuristic_choice": crop_corner_choice,
        "crop_visual_match_choice": crop_visual_choice,
        "vlm_semantic_choice": vlm_choice,
        "vlm_semantic_match": (vlm_choice == expected) if vlm_choice else "",
        "vlm_raw_response": vlm_raw_response,
        "vlm_error": vlm_error,
        "crop_confidence": crop_confidence,
        "crop_corner_heuristic_match": (crop_corner_choice == expected) if crop_corner_choice else "",
        "crop_visual_match": (crop_visual_choice == expected) if crop_visual_choice else "",
        "visual_match_scores": visual_scores,
        "detected_objects_full_frame": "|".join(sorted(full_detections)),
    }


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    args = parse_args()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = resolve(args.output_dir) / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    model = torch.hub.load(
        str(resolve(args.yolo_repo)),
        "custom",
        path=str(resolve(args.det_path)),
        source="local",
    )
    model.conf = 0.5

    vlm_client = None
    if not args.skip_vlm:
        vlm_client = create_vlm_client(
            backend=args.vlm_backend,
            workdir=PROJECT_ROOT,
            codex_bin=args.codex_bin,
            codex_home=args.codex_home,
            codex_model=args.codex_model,
            codex_timeout=args.codex_timeout,
            vlm_cache_dir=args.vlm_cache_dir,
            openai_base_url=args.openai_base_url,
            openai_model=args.openai_model,
            openai_wire_api=args.openai_wire_api,
            openai_api_key=args.openai_api_key,
            openai_api_key_env=args.openai_api_key_env,
            openai_timeout=args.openai_timeout,
        )

    rows = [audit_case(model, out_dir, case, args.padding, vlm_client=vlm_client) for case in DEFAULT_CASES]
    csv_path = out_dir / "target_image_selection_audit.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Target-Image Selection Audit",
        "",
        "This audit separates two selectors: the archived corner heuristic and the repaired visual-matching selector. Cropped target-object images test whether target-image semantics can be matched back to the current scene.",
        "",
        "| case | expected | full-frame heuristic | crop heuristic | descriptor/semantic fallback | VLM semantic match | VLM ok |",
        "| --- | --- | --- | --- | --- | --- | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['case']} | {row['expected_object']} | {row['full_frame_corner_heuristic_choice']} | "
            f"{row['crop_corner_heuristic_choice'] or '-'} | {row['crop_visual_match_choice'] or '-'} | "
            f"{row['vlm_semantic_choice'] or '-'} | {row['vlm_semantic_match']} |"
        )
    lines.extend(
        [
            "",
            "Interpretation: VLM semantic match uses the project VLM backend and sends both the target image and the current scene image. Cropped target images audit semantic recognition only. They do not replace end-to-end target-image control unless followed by a full run using the crop as `--target_image`.",
        ]
    )
    (out_dir / "target_image_selection_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / "manifest.json").write_text(
        json.dumps(
            {
                "created_at": datetime.now().isoformat(),
                "project_root": str(PROJECT_ROOT),
                "workspace_root": str(WORKSPACE_ROOT),
                "vlm_backend": None if args.skip_vlm else args.vlm_backend,
                "openai_model": None if args.skip_vlm or args.vlm_backend != "openai" else args.openai_model,
                "openai_wire_api": None if args.skip_vlm or args.vlm_backend != "openai" else args.openai_wire_api,
                "vlm_cache_dir": args.vlm_cache_dir,
                "rows": rows,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"[done] wrote {out_dir}", flush=True)


if __name__ == "__main__":
    main()
