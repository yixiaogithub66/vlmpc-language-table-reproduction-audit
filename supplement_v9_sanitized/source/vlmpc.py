import os
import sys
import time
from pathlib import Path

import cv2
import imageio
import matplotlib.pyplot as plt
import numpy as np
import torch

PROJECT_ROOT = Path(__file__).resolve().parent
PYSOT_ROOT = PROJECT_ROOT / "pysot_tracker"
if str(PYSOT_ROOT) not in sys.path:
    sys.path.insert(0, str(PYSOT_ROOT))

from language_table.environments import constants
from language_table.environments.rewards import block1_to_corner
from detect_bbx import det_bbox, detect_visible_objects
from prompt_gpt import SCENE_OBJECTS, canonicalize_object, get_interactive_object, get_subtasks
from pysot.core.config import cfg
from pysot.models.model_builder import ModelBuilder
from pysot.tracker.tracker_builder import build_tracker
from pysot.utils.model_load import load_pretrain
from pysot_tracker.tools.pysort_track_batch import centers_by_track_batch
from sampler import CorrelatedNoiseSampler
from tools import bbox_convert_vert_to_xywh, cv2_read_image, cv2_write_image
from vlm_client import CodexCLIClient


class VLMPC:
    def __init__(
        self,
        video_prediction_model,
        action_dim,
        action_horizon,
        det_model,
        tracker_config_path,
        tracker_model_path,
        vlm_client=None,
        init_action=None,
        init_std=0.01,
        num_samples=200,
        logdir=None,
        logger=None,
        task=None,
        plan_freq=3,
        zoom=0.02,
        history_rate=0.5,
        ratio_tar_obj=0.5,
        controller_variant="baseline",
        target_object=None,
        target_instruction=None,
        target_image=None,
        target_image_selector="auto",
        semantic_contact_offset=0.06,
        semantic_clearance=0.12,
        semantic_move_step=0.06,
        semantic_push_step=0.075,
        success_distance_world=None,
        feedback_source="oracle",
        visual_action_sign_x=1.0,
        visual_action_sign_y=-1.0,
        force_vlm_requery_once=False,
        grounded_original_mpc=False,
        enable_event_vlm_requery=False,
        event_requery_unblock_fixed_target=False,
        event_requery_window=3,
        event_requery_min_progress=1.0,
        event_requery_min_step=3,
        semantic_event_requery_window=4,
        semantic_event_requery_min_progress=0.002,
        audit_initial_target_object=None,
        audit_force_event_requery_step=-1,
    ):
        self.video_prediciton_model = video_prediction_model
        self.action_dim = action_dim
        self.action_horizon = action_horizon
        self.std = np.ones([self.action_horizon, self.action_dim]) * init_std
        self.sampler = CorrelatedNoiseSampler(a_dim=action_dim, beta=0.5, horizon=action_horizon)
        self.num_samples = num_samples
        self.log_dir = logdir
        self.logger = logger
        self.task = task
        self.subtasks = []
        self.plan_freq = plan_freq
        self.obs_list = []
        self.zoom = zoom
        self.history_rate = history_rate
        self.ratio_tar_obj = ratio_tar_obj
        self.controller_variant = controller_variant
        self.fixed_target_object = canonicalize_object(target_object) if target_object else None
        self.target_instruction = target_instruction
        self.target_image = str(target_image) if target_image else None
        self.target_image_selector = str(target_image_selector or "auto").strip().lower()
        if self.target_image_selector not in {"auto", "vlm", "vision"}:
            raise ValueError(f"Unsupported target-image selector: {self.target_image_selector}")
        self.force_vlm_requery_once = bool(force_vlm_requery_once)
        self._forced_vlm_requery_used = False
        self.grounded_original_mpc = bool(grounded_original_mpc)
        self.enable_event_vlm_requery = bool(enable_event_vlm_requery)
        self.event_requery_unblock_fixed_target = bool(event_requery_unblock_fixed_target)
        self.event_requery_window = max(1, int(event_requery_window))
        self.event_requery_min_progress = float(event_requery_min_progress)
        self.event_requery_min_step = max(0, int(event_requery_min_step))
        self.audit_initial_target_object = (
            canonicalize_object(audit_initial_target_object) if audit_initial_target_object else None
        )
        self.audit_force_event_requery_step = int(audit_force_event_requery_step)
        self._audit_initial_target_injected = False
        self._event_vlm_requery_used = False
        self.use_semantic_mpc = controller_variant == "semantic_mpc"
        self.use_detector_cache = controller_variant in {"improved", "literature", "literature_v2"}
        self.use_adaptive_budget = controller_variant in {"improved", "literature", "literature_v2", "semantic_mpc"}
        self.use_literature_cost = controller_variant in {"literature", "literature_v2"}
        self.use_stall_replan = controller_variant in {"literature", "literature_v2"}
        self.use_progress_object_reselect = controller_variant == "literature_v2"
        self._semantic_event_requery_used = False
        self.det_model = det_model
        if self.det_model is not None:
            self.det_model.conf = 0.5
            self.class_names = (
                list(self.det_model.names.values())
                if isinstance(self.det_model.names, dict)
                else list(self.det_model.names)
            )
        else:
            self.class_names = []
        self.classes_rev = {name: idx for idx, name in enumerate(self.class_names)}
        self.vlm_client = vlm_client or CodexCLIClient(workdir=PROJECT_ROOT, logger=logger)
        self.tracker_config_path = Path(tracker_config_path).resolve()
        self.tracker_model_path = Path(tracker_model_path).resolve()

        self.end_tracker = None if self.use_semantic_mpc else self.get_tracker()
        self.obj_tracker = None if self.use_semantic_mpc else self.get_tracker()
        self.video_prediction_tracker = None if self.use_semantic_mpc else self.get_tracker(mode="batch")

        self.init_action = np.zeros(self.action_dim) if init_action is None else init_action
        self.num_steps = 0
        self.corner_pos = np.array([310, 164]) if self.task == "push_corner" else None
        self.corner_translation = np.array(block1_to_corner.ABSOLUTE_LOCATIONS["bottom_left"], dtype=np.float32)
        self.best_actions = None
        self._scene_detections = {}
        self._scene_detections_path = None
        self.oracle_state = None

        # Adaptive-budget defaults for the improved controller.
        self.low_num_samples = max(4, int(np.ceil(self.num_samples / 2)))
        self.high_num_samples = self.num_samples
        self.low_plan_freq = 1
        self.high_plan_freq = max(1, self.plan_freq)
        self.close_target_distance = 150.0
        self.stagnation_window = 2
        self.stagnation_delta = 2.0
        self.stall_replan_window = 2
        self.stall_replan_delta = 1.0
        self.focus_obstacle_count = 3
        self.progress_volatility_threshold = 12.0
        self._last_budget_context = {}

        # Literature-inspired structured cost defaults.
        self.contact_offset_pixels = 28.0
        self.contact_cost_weight = 0.35
        self.approach_cost_weight = 0.15
        self.alignment_cost_weight = 18.0
        self.obstacle_cost_weight = 24.0
        self.progress_reward_weight = 1.2
        self.non_progress_penalty = 12.0
        self.obstacle_decay_pixels = 42.0
        self.min_progress_gain = 1.0
        self.near_target_reselect_distance = 130.0
        self.close_range_distance = 135.0
        self.close_range_contact_weight = 0.10
        self.close_range_alignment_weight = 6.0
        self.close_range_progress_reward = 1.8
        self.close_range_non_progress_penalty = 20.0
        self.stall_switch_window = 3
        self.stall_switch_progress = 0.5

        # Reliable semantic closed-loop controller for the final completed
        # experiments. VLM/language still selects the object; low-level control
        # uses simulator state as an oracle feedback signal.
        self.semantic_contact_offset = float(semantic_contact_offset)
        self.semantic_clearance = float(semantic_clearance)
        self.semantic_move_step = float(semantic_move_step)
        self.semantic_push_step = float(semantic_push_step)
        self.semantic_contact_tolerance = 0.018
        self.semantic_success_distance = (
            float(success_distance_world)
            if success_distance_world is not None
            else block1_to_corner.BLOCK2ABSOLUTELOCATION_TARGET_DISTANCE
        )
        self.feedback_source = str(feedback_source)
        if self.feedback_source not in {"oracle", "visual"}:
            raise ValueError(f"Unsupported feedback source: {self.feedback_source}")
        self.visual_success_distance_px = 34.0
        self.visual_contact_offset_px = 34.0
        self.visual_clearance_px = 44.0
        self.visual_contact_tolerance_px = 10.0
        self.visual_world_per_px_x = (
            (constants.WORKSPACE_BOUNDS[1][0] - constants.WORKSPACE_BOUNDS[0][0])
            / constants.IMAGE_WIDTH
        )
        self.visual_world_per_px_y = (
            (constants.WORKSPACE_BOUNDS[1][1] - constants.WORKSPACE_BOUNDS[0][1])
            / constants.IMAGE_HEIGHT
        )
        self.visual_action_sign_x = float(visual_action_sign_x)
        self.visual_action_sign_y = float(visual_action_sign_y)
        self.visual_adaptive_gain = 0.35
        self.visual_action_limit = 0.08
        self.visual_min_action_norm_for_jacobian = 0.003
        self.visual_jacobian = np.asarray(
            [
                [
                    1.0
                    / (
                        np.sign(self.visual_action_sign_x or 1.0)
                        * max(self.visual_world_per_px_x, 1e-6)
                    ),
                    0.0,
                ],
                [
                    0.0,
                    1.0
                    / (
                        np.sign(self.visual_action_sign_y or 1.0)
                        * max(self.visual_world_per_px_y, 1e-6)
                    ),
                ],
            ],
            dtype=np.float32,
        )
        self._last_visual_eff_px = None
        self._last_visual_obj_px = None
        self._last_visual_action = None
        self._last_visual_obj_bbox = None
        self._last_visual_end_bbox = None
        # Semantic progress is measured as a decrease in world-coordinate
        # object-to-goal distance. Keep these controls separate from the
        # original planner's event-detector parameters.
        self.semantic_event_requery_window = max(1, int(semantic_event_requery_window))
        self.semantic_event_requery_min_progress = float(semantic_event_requery_min_progress)
        self.semantic_event_requery_distance_floor = self.semantic_success_distance * 1.5

        self.metrics = {
            "reset_calls": 0,
            "reset_reasons": [],
            "subtask_requests": 0,
            "interactive_object_requests": 0,
            "subtasks": [],
            "interactive_objects": [],
            "accepted_subtask_sources": [],
            "subtask_times": [],
            "interactive_object_times": [],
            "track_center_times": [],
            "cost_calc_times": [],
            "plan_calls": 0,
            "end_effector_track_fallbacks": 0,
            "object_track_fallbacks": 0,
            "object_jump_fallbacks": 0,
            "reuse_last_bbox_count": 0,
            "invalid_vlm_object_count": 0,
            "subtask_corrections": 0,
            "event_requeries": 0,
            "event_requery_checks": 0,
            "natural_event_requeries": 0,
            "event_requery_blocked_fixed_target": 0,
            "requery_reasons": [],
            "active_num_samples": [],
            "active_plan_freq": [],
            "budget_history": [],
            "budget_context_history": [],
            "distance_history": [],
            "progress_history": [],
            "stagnation_events": 0,
            "stall_replans": 0,
            "progress_reselections": 0,
            "stall_subtask_switches": 0,
            "semantic_policy_calls": 0,
            "semantic_phases": [],
            "semantic_world_distances": [],
            "semantic_feedback_source": self.feedback_source,
            "visual_servo_calls": 0,
            "visual_servo_phases": [],
            "visual_distance_pixels": [],
            "visual_object_pixels": [],
            "visual_effector_pixels": [],
            "visual_contact_pixels": [],
            "visual_contact_error_pixels": [],
            "visual_requested_delta_pixels": [],
            "visual_adaptive_actions": [],
            "visual_jacobian_history": [],
            "visual_jacobian_updates": [],
            "visual_detection_fallbacks": 0,
            "visual_missing_detections": [],
            "target_image_selector": self.target_image_selector,
            "target_image_selection_details": [],
            "grounded_original_mpc": bool(grounded_original_mpc),
            "grounded_original_policy_calls": 0,
            "grounded_original_overrides": 0,
            "grounded_original_phases": [],
            "grounded_original_world_distances": [],
            "raw_mpc_actions": [],
            "grounded_original_actions": [],
            "event_requery_triggers": [],
            "audit_initial_target_object": self.audit_initial_target_object,
            "audit_force_event_requery_step": self.audit_force_event_requery_step,
            "audit_target_injections": [],
        }

    def update_oracle_state(self, state):
        self.oracle_state = state

    def get_tracker(self, mode="single"):
        cfg.merge_from_file(str(self.tracker_config_path))
        cfg.CUDA = torch.cuda.is_available() and cfg.CUDA
        device = torch.device("cuda:0" if cfg.CUDA else "cpu")

        if mode == "batch":
            cfg.TRACK.TYPE = "SiamRPNBatchTracker"
        else:
            cfg.TRACK.TYPE = "SiamRPNTracker"

        model = ModelBuilder()
        if cfg.CUDA:
            model = load_pretrain(model, str(self.tracker_model_path))
        else:
            state_dict = torch.load(str(self.tracker_model_path), map_location=device)
            if isinstance(state_dict, dict) and "state_dict" in state_dict:
                state_dict = state_dict["state_dict"]
            if isinstance(state_dict, dict) and all(key.startswith("module.") for key in state_dict):
                state_dict = {key[len("module.") :]: value for key, value in state_dict.items()}
            model.load_state_dict(state_dict, strict=False)
        model.eval().to(device)
        return build_tracker(model)

    @staticmethod
    def _bbox_center(bbox):
        return np.array(
            [
                (bbox[0][0] + bbox[1][0]) / 2,
                (bbox[0][1] + bbox[1][1]) / 2,
            ]
        )

    @staticmethod
    def _clip_bbox_to_image(bbox, image_shape, padding=0):
        height, width = image_shape[:2]
        x1, y1 = bbox[0]
        x2, y2 = bbox[1]
        x1 = max(0, min(width - 1, int(x1) - padding))
        y1 = max(0, min(height - 1, int(y1) - padding))
        x2 = max(x1 + 1, min(width, int(x2) + padding))
        y2 = max(y1 + 1, min(height, int(y2) + padding))
        return x1, y1, x2, y2

    @staticmethod
    def _crop_from_bbox(image, bbox, padding=0):
        x1, y1, x2, y2 = VLMPC._clip_bbox_to_image(bbox, image.shape, padding=padding)
        return image[y1:y2, x1:x2].copy()

    @staticmethod
    def _crop_descriptor(image):
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
            x, y, w, h = cv2.boundingRect(contour)
            extent = area / float(max(w * h, 1))
        return {
            "hist": hist,
            "shape": np.asarray([circularity, area_ratio, extent], dtype=np.float32),
        }

    @staticmethod
    def _foreground_component_mask(image):
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

    @staticmethod
    def _estimate_color_name(image, mask):
        if image is None or mask is None or int(mask.sum()) == 0:
            return None
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        pixels = hsv[mask > 0]
        if pixels.size == 0:
            return None
        hue = pixels[:, 0]
        saturation = pixels[:, 1]
        valid = saturation > 45
        hue = hue[valid]
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

    @staticmethod
    def _estimate_shape_name(mask, color_name=None):
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
        x, y, width, height = cv2.boundingRect(contour)
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

    @classmethod
    def _semantic_object_from_crop(cls, image):
        mask = cls._foreground_component_mask(image)
        color_name = cls._estimate_color_name(image, mask)
        shape_name = cls._estimate_shape_name(mask, color_name=color_name)
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

    @staticmethod
    def _descriptor_distance(desc_a, desc_b):
        if desc_a is None or desc_b is None:
            return float("inf")
        hist_dist = cv2.compareHist(
            desc_a["hist"].astype(np.float32),
            desc_b["hist"].astype(np.float32),
            cv2.HISTCMP_BHATTACHARYYA,
        )
        shape_dist = float(np.linalg.norm(desc_a["shape"] - desc_b["shape"]))
        return float(hist_dist + 0.35 * shape_dist)

    @staticmethod
    def _unit_vectors(vectors):
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / np.maximum(norms, 1e-8)

    def _exp_decay(self, distances, scale):
        scale = max(float(scale), 1e-8)
        return np.exp(-np.maximum(distances, 0.0) / scale)

    def _refresh_scene_detections(self, image_path, force=False):
        if not self.use_detector_cache or self.det_model is None:
            return {}

        resolved = str(Path(image_path).resolve())
        if force or self._scene_detections_path != resolved:
            detected = detect_visible_objects(
                image_path=resolved,
                model=self.det_model,
                include_end_effector=True,
            )
            self._scene_detections = {
                name: item["bbox"] for name, item in detected.items()
            }
            self._scene_detections_path = resolved
        return self._scene_detections

    def _lookup_bbox(self, image_path, obj_str, force_refresh=False):
        if self.det_model is None:
            return 0
        if self.use_detector_cache:
            detections = self._refresh_scene_detections(image_path, force=force_refresh)
            return detections.get(obj_str, 0)
        return det_bbox(image_path=image_path, model=self.det_model, obj_str=obj_str)

    def _visible_scene_objects(self, image_path, force_refresh=False):
        if self.det_model is None:
            return {}
        if self.use_detector_cache:
            detections = self._refresh_scene_detections(image_path, force=force_refresh)
            return {
                name: bbox
                for name, bbox in detections.items()
                if name != "end effector"
            }

        visible_objects = {}
        for class_name in self.class_names:
            if class_name == "end effector":
                continue
            bbox = det_bbox(image_path=image_path, model=self.det_model, obj_str=class_name)
            if bbox != 0:
                visible_objects[class_name] = bbox
        return visible_objects

    def scene_distance_stats(self, image_path, force_refresh=False):
        visible_objects = self._visible_scene_objects(image_path, force_refresh=force_refresh)
        if not visible_objects:
            return {
                "visible_count": 0,
                "scene_distance_sum": None,
                "scene_distance_mean": None,
            }
        distances = [
            float(np.linalg.norm(self._bbox_center(bbox) - self.corner_pos))
            for bbox in visible_objects.values()
        ]
        return {
            "visible_count": len(distances),
            "scene_distance_sum": float(sum(distances)),
            "scene_distance_mean": float(sum(distances) / len(distances)),
        }

    def _rewrite_subtask_for_object(self, object_name):
        if self.task == "push_corner":
            return f"push the {object_name} to the bottom left corner."
        return self.current_subtask

    def _pick_fallback_object(self, visible_objects, excluding=None):
        excluding = set(excluding or [])
        candidates = [
            name
            for name in visible_objects
            if name not in excluding and name != "end effector"
        ]
        if not candidates:
            return None
        if self.task == "push_corner" and self.corner_pos is not None:
            return min(
                candidates,
                key=lambda name: np.linalg.norm(self._bbox_center(visible_objects[name]) - self.corner_pos),
            )
        return candidates[0]

    def _pick_progress_object(self, visible_objects, excluding=None, min_distance=None):
        excluding = set(excluding or [])
        min_distance = 0.0 if min_distance is None else float(min_distance)
        end_effector_bbox = self._scene_detections.get("end effector") if self._scene_detections else None
        end_effector_center = self._bbox_center(end_effector_bbox) if end_effector_bbox is not None else None
        candidates = []
        for name, bbox in visible_objects.items():
            if name in excluding or name == "end effector":
                continue
            distance = np.linalg.norm(self._bbox_center(bbox) - self.corner_pos)
            if distance <= min_distance:
                continue
            arm_distance = 0.0
            if end_effector_center is not None:
                arm_distance = np.linalg.norm(self._bbox_center(bbox) - end_effector_center)
            score = distance - 0.6 * arm_distance
            candidates.append((score, name))
        if not candidates:
            return None
        candidates.sort(reverse=True)
        return candidates[0][1]

    def _object_from_target_image_vlm(self, target_path, current_image_path, scene_objects):
        candidates = [name for name in sorted(scene_objects) if name != "end effector"]
        if not candidates:
            raise RuntimeError("Target-image VLM selection requires visible scene candidates.")

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
        response = self.vlm_client.complete(
            prompt,
            image_paths=[Path(target_path).resolve(), Path(current_image_path).resolve()],
        )
        selected = canonicalize_object(response)
        if selected not in candidates:
            raise ValueError(
                f"VLM target-image selector returned {selected!r}, not in visible candidates {candidates!r}"
            )
        details = {
            "target_image": str(Path(target_path).resolve()),
            "current_image": str(Path(current_image_path).resolve()),
            "selected_scene_object": selected,
            "selection_rule": "vlm_target_scene_semantic_match",
            "target_image_selector": self.target_image_selector,
            "vlm_raw_response": response,
            "scene_candidates": [
                {
                    "object": name,
                    "confidence": float(scene_objects[name].get("confidence", 0.0)),
                }
                for name in candidates
            ],
        }
        self.metrics["target_image_selection_details"].append(details)
        if self.logger:
            self.logger.info("target-image VLM semantic match: %s", details)
        return selected

    def _object_from_target_image(self):
        if not self.target_image:
            return None
        if self.det_model is None:
            raise RuntimeError("Target-image selection requires a detector model.")
        target_path = Path(self.target_image).resolve()
        target_image = cv2_read_image(target_path)
        if target_image is None:
            raise FileNotFoundError(f"Cannot read target image: {target_path}")
        whole_semantic_name, whole_semantic_details = self._semantic_object_from_crop(target_image)

        current_image_path = Path(self.log_dir) / "init_task.png"
        if getattr(self, "current_obs_image_path", None):
            current_image_path = Path(self.current_obs_image_path)
        scene_image = cv2_read_image(current_image_path)
        scene_objects = {}
        if scene_image is not None and self.det_model is not None:
            scene_objects = detect_visible_objects(
                image_path=str(current_image_path),
                model=self.det_model,
                include_end_effector=False,
            )

        if self.target_image_selector in {"auto", "vlm"}:
            try:
                return self._object_from_target_image_vlm(
                    target_path=target_path,
                    current_image_path=current_image_path,
                    scene_objects=scene_objects,
                )
            except Exception as exc:
                details = {
                    "target_image": str(target_path),
                    "current_image": str(current_image_path),
                    "selection_rule": "vlm_target_scene_semantic_match_failed",
                    "target_image_selector": self.target_image_selector,
                    "vlm_error": repr(exc),
                    "scene_candidates": [
                        {
                            "object": name,
                            "confidence": float(item.get("confidence", 0.0)),
                        }
                        for name, item in sorted(scene_objects.items())
                        if name != "end effector"
                    ],
                }
                self.metrics["target_image_selection_details"].append(details)
                if self.logger:
                    self.logger.warning("target-image VLM semantic match failed: %s", details)
                if self.target_image_selector == "vlm":
                    raise RuntimeError(
                        f"Strict VLM target-image selection failed for {target_path}: {exc}"
                    ) from exc

        target_detections = detect_visible_objects(
            image_path=str(target_path),
            model=self.det_model,
            include_end_effector=False,
        )
        target_candidates = {
            name: item for name, item in target_detections.items() if name != "end effector"
        }
        target_name = None
        target_item = None
        if target_candidates:
            # Pick the most confident object inside the target image. For cropped
            # references this is the intended object; for full-frame references it
            # is still auditable through the recorded selection details.
            target_name, target_item = max(
                target_candidates.items(),
                key=lambda item: float(item[1].get("confidence", 0.0)),
            )
            target_crop = self._crop_from_bbox(target_image, target_item["bbox"], padding=8)
        else:
            target_crop = target_image
        semantic_name, semantic_details = self._semantic_object_from_crop(target_crop)
        target_descriptor = self._crop_descriptor(target_crop)

        if whole_semantic_name and whole_semantic_name in scene_objects:
            details = {
                "target_image": str(target_path),
                "semantic_estimate": whole_semantic_name,
                "semantic_estimate_details": whole_semantic_details,
                "selected_scene_object": whole_semantic_name,
                "selection_rule": "whole_image_foreground_semantic_match",
                "target_image_selector": self.target_image_selector,
            }
            self.metrics["target_image_selection_details"].append(details)
            if self.logger:
                self.logger.info("target-image whole-crop semantic match: %s", details)
            return whole_semantic_name

        if semantic_name and semantic_name in scene_objects:
            details = {
                "target_image": str(target_path),
                "target_detected_object": target_name,
                "target_detected_confidence": float(target_item.get("confidence", 0.0)) if target_item else None,
                "semantic_estimate": semantic_name,
                "semantic_estimate_details": semantic_details,
                "selected_scene_object": semantic_name,
                "selection_rule": "foreground_semantic_match",
                "target_image_selector": self.target_image_selector,
            }
            self.metrics["target_image_selection_details"].append(details)
            if self.logger:
                self.logger.info("target-image semantic match: %s", details)
            return semantic_name

        scored = []
        for scene_name, scene_item in scene_objects.items():
            scene_crop = self._crop_from_bbox(scene_image, scene_item["bbox"], padding=8)
            score = self._descriptor_distance(target_descriptor, self._crop_descriptor(scene_crop))
            class_bonus = 0.0 if target_name and scene_name == target_name else 0.18
            confidence_bonus = -0.05 * float(scene_item.get("confidence", 0.0))
            scored.append((score + class_bonus + confidence_bonus, scene_name, scene_item))

        if scored:
            scored.sort(key=lambda item: item[0])
            selected_name = scored[0][1]
            details = {
                "target_image": str(target_path),
                "target_detected_object": target_name,
                "target_detected_confidence": float(target_item.get("confidence", 0.0)) if target_item else None,
                "semantic_estimate": semantic_name,
                "semantic_estimate_details": semantic_details,
                "selected_scene_object": selected_name,
                "selected_score": float(scored[0][0]),
                "selection_rule": "descriptor_fallback",
                "target_image_selector": self.target_image_selector,
                "scene_candidates": [
                    {
                        "object": name,
                        "score": float(score),
                        "confidence": float(item.get("confidence", 0.0)),
                    }
                    for score, name, item in scored
                ],
            }
            self.metrics["target_image_selection_details"].append(details)
            if self.logger:
                self.logger.info("target-image visual match: %s", details)
            return selected_name

        # Fallback for standalone target-image audits where no current scene is
        # available. This preserves executable behavior but records that no
        # scene-level matching was possible.
        self.metrics["target_image_selection_details"].append(
            {
                "target_image": str(target_path),
                "target_detected_object": target_name,
                "target_detected_confidence": float(target_item.get("confidence", 0.0)) if target_item else None,
                "semantic_estimate": semantic_name,
                "semantic_estimate_details": semantic_details,
                "selected_scene_object": target_name or whole_semantic_name or semantic_name,
                "target_image_selector": self.target_image_selector,
                "fallback": "target_image_only",
            }
        )
        if target_name or whole_semantic_name or semantic_name:
            return target_name or whole_semantic_name or semantic_name
        raise RuntimeError(f"No target object could be selected from target image: {self.target_image}")

    def _select_subtask(self, image_path, excluding=None):
        exclusion_list = list(excluding or [])

        if self.fixed_target_object:
            response_subtask = self._rewrite_subtask_for_object(self.fixed_target_object)
            interactive_object = self.fixed_target_object
            self.metrics["subtask_times"].append(0.0)
            self.metrics["interactive_object_times"].append(0.0)
            selection_source = "fixed_target"
        elif self.target_image:
            time0 = time.time()
            interactive_object = self._object_from_target_image()
            time1 = time.time()
            response_subtask = self._rewrite_subtask_for_object(interactive_object)
            self.metrics["interactive_object_requests"] += 1
            self.metrics["subtask_times"].append(0.0)
            self.metrics["interactive_object_times"].append(time1 - time0)
            selection_source = "target_image"
        elif self.target_instruction:
            time0 = time.time()
            interactive_object = get_interactive_object(self.vlm_client, self.target_instruction)
            time1 = time.time()
            response_subtask = self._rewrite_subtask_for_object(interactive_object)
            self.metrics["interactive_object_requests"] += 1
            self.metrics["subtask_times"].append(0.0)
            self.metrics["interactive_object_times"].append(time1 - time0)
            selection_source = "llm_instruction"
        else:
            time0 = time.time()
            response_subtask = get_subtasks(
                image_path=image_path,
                client=self.vlm_client,
                task=self.task,
                excluding=exclusion_list or None,
            )
            time1 = time.time()
            interactive_object = get_interactive_object(self.vlm_client, response_subtask)
            time2 = time.time()

            self.metrics["subtask_requests"] += 1
            self.metrics["interactive_object_requests"] += 1
            self.metrics["subtask_times"].append(time1 - time0)
            self.metrics["interactive_object_times"].append(time2 - time1)

            selection_source = "vlm"
            if self.force_vlm_requery_once and not self._forced_vlm_requery_used:
                self._forced_vlm_requery_used = True
                self.metrics["event_requeries"] += 1
                self.metrics["requery_reasons"].append("forced_audit_vlm_requery")
                exclusion_list.append(interactive_object)
                self.logger.info(
                    "Audit mode forces one VLM requery; excluding initial object: %s",
                    interactive_object,
                )
                time3 = time.time()
                response_subtask = get_subtasks(
                    image_path=image_path,
                    client=self.vlm_client,
                    task=self.task,
                    excluding=exclusion_list,
                )
                time4 = time.time()
                interactive_object = get_interactive_object(self.vlm_client, response_subtask)
                time5 = time.time()
                self.metrics["subtask_requests"] += 1
                self.metrics["interactive_object_requests"] += 1
                self.metrics["subtask_times"].append(time4 - time3)
                self.metrics["interactive_object_times"].append(time5 - time4)
                selection_source = "forced_vlm_requery"
        visible_objects = None
        if self.use_detector_cache:
            visible_objects = self._visible_scene_objects(image_path, force_refresh=True)
            if (
                (self.fixed_target_object or self.target_instruction or self.target_image)
                and interactive_object not in visible_objects
                and not self.use_semantic_mpc
            ):
                raise RuntimeError(f"Fixed target object is not visible: {interactive_object}")
            if not self.fixed_target_object and not self.target_instruction and interactive_object not in visible_objects:
                self.metrics["invalid_vlm_object_count"] += 1
                fallback_object = self._pick_fallback_object(
                    visible_objects,
                    excluding=exclusion_list + [interactive_object],
                )
                if fallback_object is not None:
                    self.metrics["subtask_corrections"] += 1
                    response_subtask = self._rewrite_subtask_for_object(fallback_object)
                    interactive_object = fallback_object
                    selection_source = "detector_fallback"
                else:
                    self.metrics["event_requeries"] += 1
                    self.metrics["requery_reasons"].append("invalid_vlm_choice")
                    exclusion_list.append(interactive_object)
                    time3 = time.time()
                    response_subtask = get_subtasks(
                        image_path=image_path,
                        client=self.vlm_client,
                        task=self.task,
                        excluding=exclusion_list,
                    )
                    time4 = time.time()
                    interactive_object = get_interactive_object(self.vlm_client, response_subtask)
                    time5 = time.time()
                    self.metrics["subtask_requests"] += 1
                    self.metrics["interactive_object_requests"] += 1
                    self.metrics["subtask_times"].append(time4 - time3)
                    self.metrics["interactive_object_times"].append(time5 - time4)
                    selection_source = "vlm_requery"

        if (
            self.use_progress_object_reselect
            and self.task == "push_corner"
            and self.fixed_target_object is None
            and self.target_instruction is None
            and visible_objects is not None
            and exclusion_list
            and interactive_object in visible_objects
        ):
            current_distance = np.linalg.norm(
                self._bbox_center(visible_objects[interactive_object]) - self.corner_pos
            )
            if current_distance <= self.near_target_reselect_distance:
                progress_object = self._pick_progress_object(
                    visible_objects,
                    excluding=exclusion_list + [interactive_object],
                    min_distance=self.near_target_reselect_distance,
                )
                if progress_object is not None:
                    self.metrics["progress_reselections"] += 1
                    interactive_object = progress_object
                    response_subtask = self._rewrite_subtask_for_object(progress_object)
                    selection_source = "progress_reselect"

        self.logger.info(response_subtask)
        self.logger.info("current interactive object is: %s", interactive_object)
        self.logger.info("get subtask time: %s", self.metrics["subtask_times"][-1])
        self.logger.info("get interactive object time: %s", self.metrics["interactive_object_times"][-1])

        self.subtasks.append(response_subtask)
        self.current_subtask = response_subtask
        self.current_interactive_object = interactive_object
        self.metrics["subtasks"].append(response_subtask)
        self.metrics["interactive_objects"].append(interactive_object)
        self.metrics["accepted_subtask_sources"].append(selection_source)

    def reset(self, init_frame=None, reason="manual"):
        self.metrics["reset_calls"] += 1
        self.metrics["reset_reasons"].append(reason)
        self.init_frame = init_frame
        self.history_mu = np.zeros([self.action_horizon, self.action_dim])
        self.best_actions = None

        if self.num_steps == 0:
            image_path = Path(self.log_dir) / "init_task.png"
            excluding = None
        else:
            image_path = Path(self.log_dir) / "current_obs.png"
            excluding = [self.current_interactive_object] if getattr(self, "current_interactive_object", None) else None

        self._select_subtask(image_path=image_path, excluding=excluding)
        if (
            self.num_steps == 0
            and self.audit_initial_target_object
            and not self._audit_initial_target_injected
        ):
            previous_object = self.current_interactive_object
            self._audit_initial_target_injected = True
            self.current_interactive_object = self.audit_initial_target_object
            self.current_subtask = self._rewrite_subtask_for_object(self.audit_initial_target_object)
            self.subtasks.append(self.current_subtask)
            self.metrics["subtasks"].append(self.current_subtask)
            self.metrics["interactive_objects"].append(self.audit_initial_target_object)
            self.metrics["accepted_subtask_sources"].append("audit_injected_initial_target")
            self.metrics["audit_target_injections"].append(
                {
                    "step": int(self.num_steps),
                    "previous_object": previous_object,
                    "injected_object": self.audit_initial_target_object,
                }
            )
            self.logger.info(
                "Synthetic audit replaced initial target %s with %s.",
                previous_object,
                self.audit_initial_target_object,
            )
        return np.zeros(self.action_dim)

    def _state_block_key(self):
        if not getattr(self, "current_interactive_object", None):
            return None
        return "block_" + self.current_interactive_object.replace(" ", "_") + "_translation"

    def _semantic_state_positions(self):
        if self.oracle_state is None:
            return None, None
        block_key = self._state_block_key()
        if block_key not in self.oracle_state:
            return None, None
        obj_pos = np.asarray(self.oracle_state[block_key], dtype=np.float32)
        eff_pos = np.asarray(self.oracle_state["effector_target_translation"], dtype=np.float32)
        return obj_pos, eff_pos

    def _visual_state_positions(self):
        if not getattr(self, "current_obs_image_path", None):
            return None, None
        if self.det_model is None:
            return None, None
        if self.use_detector_cache:
            self._refresh_scene_detections(self.current_obs_image_path, force=True)
        obj_bbox = self._lookup_bbox(
            image_path=self.current_obs_image_path,
            obj_str=getattr(self, "current_interactive_object", None),
            force_refresh=False,
        )
        end_bbox = self._lookup_bbox(
            image_path=self.current_obs_image_path,
            obj_str="end effector",
            force_refresh=False,
        )
        missing = []
        if obj_bbox == 0:
            missing.append(str(getattr(self, "current_interactive_object", None)))
            obj_bbox = self._last_visual_obj_bbox
        if end_bbox == 0:
            missing.append("end effector")
            end_bbox = self._last_visual_end_bbox
        if obj_bbox is None or end_bbox is None or obj_bbox == 0 or end_bbox == 0:
            if missing:
                self.metrics["visual_missing_detections"].append(
                    {"step": int(self.num_steps), "missing": missing, "fallback": False}
                )
            return None, None
        if missing:
            self.metrics["visual_detection_fallbacks"] += 1
            self.metrics["visual_missing_detections"].append(
                {"step": int(self.num_steps), "missing": missing, "fallback": True}
            )
        obj_px = self._bbox_center(obj_bbox).astype(np.float32)
        eff_px = np.asarray(
            [
                (end_bbox[0][0] + end_bbox[1][0]) / 2.0,
                end_bbox[1][1],
            ],
            dtype=np.float32,
        )
        self._update_visual_jacobian(eff_px)
        self._last_visual_obj_bbox = obj_bbox
        self._last_visual_end_bbox = end_bbox
        return obj_px, eff_px

    def _update_visual_jacobian(self, eff_px):
        if self.feedback_source != "visual":
            return
        if self._last_visual_eff_px is None or self._last_visual_action is None:
            return
        last_action = np.asarray(self._last_visual_action, dtype=np.float32)
        action_norm_sq = float(last_action @ last_action)
        if action_norm_sq < self.visual_min_action_norm_for_jacobian**2:
            return
        observed_delta = np.asarray(eff_px, dtype=np.float32) - np.asarray(
            self._last_visual_eff_px, dtype=np.float32
        )
        if not np.all(np.isfinite(observed_delta)):
            return
        predicted_delta = self.visual_jacobian @ last_action
        residual = observed_delta - predicted_delta
        update = (
            self.visual_adaptive_gain
            * np.outer(residual, last_action)
            / max(action_norm_sq, 1e-8)
        )
        candidate = self.visual_jacobian + update.astype(np.float32)
        if not np.all(np.isfinite(candidate)):
            return
        candidate = np.clip(candidate, -2500.0, 2500.0).astype(np.float32)
        if np.linalg.cond(candidate) > 120.0:
            return
        self.visual_jacobian = candidate
        self.metrics["visual_jacobian_updates"].append(
            {
                "last_action": last_action.tolist(),
                "observed_effector_delta_px": observed_delta.tolist(),
                "predicted_effector_delta_px": predicted_delta.tolist(),
                "residual_px": residual.tolist(),
                "jacobian": self.visual_jacobian.tolist(),
            }
        )

    def _pixel_delta_to_action(self, delta_px):
        delta_px = np.asarray(delta_px, dtype=np.float32)
        if self.feedback_source == "visual":
            try:
                action = np.linalg.lstsq(self.visual_jacobian, delta_px, rcond=None)[0]
            except np.linalg.LinAlgError:
                action = None
            if action is not None and np.all(np.isfinite(action)):
                return np.clip(action.astype(np.float32), -self.visual_action_limit, self.visual_action_limit)

        action = np.asarray(
            [
                delta_px[0] * self.visual_world_per_px_x,
                delta_px[1] * self.visual_world_per_px_y,
            ],
            dtype=np.float32,
        )
        action[0] *= self.visual_action_sign_x
        action[1] *= self.visual_action_sign_y
        return np.clip(action, -self.visual_action_limit, self.visual_action_limit)

    def _record_state_feedback_action(self, namespace, distance, phase, action):
        if namespace == "semantic":
            self.metrics["semantic_world_distances"].append(distance)
            self.metrics["semantic_policy_calls"] += 1
            self.metrics["semantic_phases"].append(phase)
        elif namespace == "grounded_original":
            self.metrics["grounded_original_world_distances"].append(distance)
            self.metrics["grounded_original_policy_calls"] += 1
            self.metrics["grounded_original_phases"].append(phase)
            if not isinstance(action, int):
                self.metrics["grounded_original_actions"].append(np.asarray(action).tolist())

    def _visual_feedback_push_action(self, namespace="semantic"):
        obj_px, eff_px = self._visual_state_positions()
        if obj_px is None or eff_px is None:
            raise RuntimeError(
                f"Cannot estimate visual state for target object: {getattr(self, 'current_interactive_object', None)}"
            )

        target_px = np.asarray(self.corner_pos, dtype=np.float32)
        push_vec = target_px - obj_px
        distance_px = float(np.linalg.norm(push_vec))
        self.metrics["visual_distance_pixels"].append(distance_px)
        self.metrics["visual_object_pixels"].append(obj_px.tolist())
        self.metrics["visual_effector_pixels"].append(eff_px.tolist())
        if distance_px <= self.visual_success_distance_px:
            self.metrics["visual_servo_calls"] += 1
            self.metrics["visual_servo_phases"].append("success")
            self._record_state_feedback_action(namespace, distance_px, "visual_success", 0)
            return 0, "visual_success"

        push_dir = push_vec / max(np.linalg.norm(push_vec), 1e-8)
        contact = obj_px - push_dir * self.visual_contact_offset_px
        contact_error = contact - eff_px
        contact_distance = float(np.linalg.norm(contact_error))
        self.metrics["visual_contact_pixels"].append(contact.tolist())
        self.metrics["visual_contact_error_pixels"].append(float(contact_distance))

        if contact_distance > self.visual_contact_tolerance_px:
            phase = "visual_contact"
            delta_px = contact_error
            max_px_step = 22.0
        else:
            phase = "visual_push"
            push_step = 18.0 if distance_px > 70.0 else 9.0
            delta_px = push_dir * push_step + 0.30 * contact_error
            max_px_step = push_step + 6.0

        norm = np.linalg.norm(delta_px)
        delta_px = delta_px / max(norm, 1e-8) * min(max_px_step, norm)
        action = self._pixel_delta_to_action(delta_px)
        self._last_visual_eff_px = eff_px.copy()
        self._last_visual_obj_px = obj_px.copy()
        self._last_visual_action = np.asarray(action, dtype=np.float32).copy()
        self.metrics["visual_servo_calls"] += 1
        self.metrics["visual_servo_phases"].append(phase)
        self.metrics["visual_requested_delta_pixels"].append(delta_px.tolist())
        self.metrics["visual_adaptive_actions"].append(np.asarray(action).tolist())
        self.metrics["visual_jacobian_history"].append(self.visual_jacobian.tolist())
        self._record_state_feedback_action(namespace, distance_px, phase, action)
        return action, phase

    def _state_feedback_push_action(self, namespace="semantic"):
        if self.feedback_source == "visual":
            return self._visual_feedback_push_action(namespace=namespace)

        obj_pos, eff_pos = self._semantic_state_positions()
        if obj_pos is None or eff_pos is None:
            raise RuntimeError(
                f"Cannot find oracle state for target object: {getattr(self, 'current_interactive_object', None)}"
            )

        target = self.corner_translation
        push_vec = target - obj_pos
        distance = float(np.linalg.norm(push_vec))
        if distance <= self.semantic_success_distance:
            self._record_state_feedback_action(namespace, distance, "success", 0)
            return 0, "success"

        push_dir = push_vec / max(np.linalg.norm(push_vec), 1e-8)
        side_dir = np.array([-push_dir[1], push_dir[0]], dtype=np.float32)
        signed = float(np.dot(eff_pos - obj_pos, push_dir))
        lateral = float(np.dot(eff_pos - obj_pos, side_dir))
        side = -1.0 if lateral > 0 else 1.0

        contact = obj_pos - push_dir * self.semantic_contact_offset
        staging = contact + side * side_dir * self.semantic_clearance
        staging = np.clip(
            staging,
            constants.WORKSPACE_BOUNDS[0] + 0.01,
            constants.WORKSPACE_BOUNDS[1] - 0.01,
        )
        contact_error = contact - eff_pos
        contact_distance = float(np.linalg.norm(contact_error))

        recent_progress = self.metrics.get("progress_history", [])[-6:]
        recent_phases = self.metrics.get(f"{namespace}_phases", [])[-6:]
        stalled_near_target = (
            distance <= max(self.semantic_success_distance * 1.65, 0.13)
            and len(recent_progress) >= 6
            and max(recent_progress) <= 1e-4
            and "push" in recent_phases
            and "contact" in recent_phases
            and contact_distance <= max(self.semantic_contact_tolerance * 3.0, 0.055)
        )
        if stalled_near_target:
            phase = "recovery_push"
            action = push_dir * min(0.08, self.semantic_push_step * 1.15) + 0.12 * contact_error
            self._record_state_feedback_action(namespace, distance, phase, action)
            return np.clip(action, -0.08, 0.08), phase

        if signed > -self.semantic_contact_offset * 0.4 and abs(lateral) < self.semantic_clearance * 0.75:
            phase = "stage"
            goal = staging
            max_step = self.semantic_move_step
        elif contact_distance > self.semantic_contact_tolerance:
            phase = "contact"
            goal = contact
            max_step = self.semantic_move_step
        else:
            phase = "push"
            fine_scale = 0.45 if distance <= max(self.semantic_success_distance * 1.5, 0.055) else 1.0
            correction = 0.45 * contact_error
            action = push_dir * self.semantic_push_step * fine_scale + correction
            self._record_state_feedback_action(namespace, distance, phase, action)
            return np.clip(action, -0.08, 0.08), phase

        delta = goal - eff_pos
        norm = np.linalg.norm(delta)
        action = delta / max(norm, 1e-8) * min(max_step, norm)
        self._record_state_feedback_action(namespace, distance, phase, action)
        return np.clip(action, -0.08, 0.08), phase

    def _semantic_push_action(self):
        return self._state_feedback_push_action(namespace="semantic")

    def _grounded_original_action(self, raw_action):
        self.metrics["raw_mpc_actions"].append(np.asarray(raw_action).tolist())
        action, phase = self._state_feedback_push_action(namespace="grounded_original")
        if isinstance(action, int):
            return action
        self.metrics["grounded_original_overrides"] += 1
        self.logger.info(
            "Grounded original MPC overrides raw action %s with state-feedback action %s (%s).",
            raw_action,
            action,
            phase,
        )
        return action

    def _draw_semantic_frame(self):
        current_obs = cv2_read_image(self.current_obs_image_path)
        if current_obs is None:
            return
        detections = {}
        if self.use_detector_cache:
            detections = self._visible_scene_objects(self.current_obs_image_path)
            end_bbox = self._scene_detections.get("end effector")
            if end_bbox is not None:
                detections["end effector"] = end_bbox
        for name, bbox in detections.items():
            color = (0, 255, 0) if name == self.current_interactive_object else (140, 140, 140)
            if name == "end effector":
                color = (0, 0, 255)
            cv2.rectangle(current_obs, tuple(bbox[0]), tuple(bbox[1]), color, 2, 4)
        cv2.putText(
            current_obs,
            str(self.current_interactive_object),
            (15, 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 255),
            2,
        )
        current_obs = cv2.cvtColor(current_obs, cv2.COLOR_BGR2RGB)
        cv2_write_image(f"{self.log_dir}/frame_bbx_{self.num_steps}.png", current_obs[..., ::-1])
        self.obs_list.append(current_obs)

    def _semantic_event_requery_needed(self, current_distance):
        self.metrics["event_requery_checks"] += 1
        if self._semantic_event_requery_used:
            return False, None
        if current_distance is None or current_distance <= self.semantic_event_requery_distance_floor:
            return False, None

        recent_progress = self.metrics["progress_history"][-self.semantic_event_requery_window :]
        stalled = (
            len(recent_progress) >= self.semantic_event_requery_window
            and all(progress <= self.semantic_event_requery_min_progress for progress in recent_progress)
        )
        if not stalled:
            return False, None

        if (
            (self.fixed_target_object or self.target_instruction or self.target_image)
            and not self.event_requery_unblock_fixed_target
        ):
            self.metrics["event_requery_blocked_fixed_target"] += 1
            return False, "semantic_stagnation_fixed_target_blocked"
        return True, "semantic_stagnation_event_requery"

    def _event_requery_blocked_by_target_mode(self):
        has_fixed_mode = bool(self.fixed_target_object or self.target_instruction or self.target_image)
        return has_fixed_mode and not self.event_requery_unblock_fixed_target

    def _original_event_vlm_requery_needed(self, current_distance, tracking_unstable):
        if not self.enable_event_vlm_requery:
            return False, None
        self.metrics["event_requery_checks"] += 1
        if self._event_vlm_requery_used:
            return False, None
        if self.num_steps < self.event_requery_min_step:
            return False, None
        if self._event_requery_blocked_by_target_mode():
            self.metrics["event_requery_blocked_fixed_target"] += 1
            return False, "event_requery_fixed_target_blocked"

        if tracking_unstable:
            return True, "tracking_unstable_event_vlm_requery"

        recent_progress = self.metrics["progress_history"][-self.event_requery_window :]
        stalled = (
            len(recent_progress) >= self.event_requery_window
            and all(progress <= self.event_requery_min_progress for progress in recent_progress)
        )
        if stalled:
            return True, "low_progress_event_vlm_requery"
        return False, None

    def _perform_event_vlm_requery(self, reason, natural=True):
        self.logger.info("Event trigger requests a fresh VLM query: %s", reason)
        self._event_vlm_requery_used = True
        self.metrics["event_requeries"] += 1
        if natural:
            self.metrics["natural_event_requeries"] += 1
        self.metrics["requery_reasons"].append(reason)
        self.metrics["event_requery_triggers"].append(
            {
                "step": int(self.num_steps),
                "reason": reason,
                "trigger_type": "natural" if natural else "synthetic_audit",
                "previous_object": getattr(self, "current_interactive_object", None),
            }
        )
        self.best_actions = None

        time0 = time.time()
        selection_source = f"event_requery:{reason}"
        if self.target_instruction:
            interactive_object = get_interactive_object(self.vlm_client, self.target_instruction)
            response_subtask = self._rewrite_subtask_for_object(interactive_object)
            self.metrics["subtask_times"].append(0.0)
            self.metrics["interactive_object_times"].append(time.time() - time0)
            self.metrics["interactive_object_requests"] += 1
            selection_source = "event_requery_instruction"
        elif self.target_image:
            interactive_object = self._object_from_target_image()
            response_subtask = self._rewrite_subtask_for_object(interactive_object)
            self.metrics["subtask_times"].append(0.0)
            self.metrics["interactive_object_times"].append(time.time() - time0)
            self.metrics["interactive_object_requests"] += 1
            selection_source = "event_requery_target_image"
        elif self.fixed_target_object:
            interactive_object = self.fixed_target_object
            response_subtask = self._rewrite_subtask_for_object(interactive_object)
            self.metrics["subtask_times"].append(0.0)
            self.metrics["interactive_object_times"].append(0.0)
            selection_source = "event_requery_fixed_target_refresh"
        else:
            response_subtask = get_subtasks(
                image_path=self.current_obs_image_path,
                client=self.vlm_client,
                task=self.task,
                excluding=[self.current_interactive_object]
                if getattr(self, "current_interactive_object", None)
                else None,
            )
            time1 = time.time()
            interactive_object = get_interactive_object(self.vlm_client, response_subtask)
            time2 = time.time()
            self.metrics["subtask_requests"] += 1
            self.metrics["interactive_object_requests"] += 1
            self.metrics["subtask_times"].append(time1 - time0)
            self.metrics["interactive_object_times"].append(time2 - time1)
            selection_source = "event_requery_vlm_scene"

        self.logger.info(response_subtask)
        self.logger.info("event requery interactive object is: %s", interactive_object)
        self.subtasks.append(response_subtask)
        self.current_subtask = response_subtask
        self.current_interactive_object = interactive_object
        self.metrics["subtasks"].append(response_subtask)
        self.metrics["interactive_objects"].append(interactive_object)
        self.metrics["accepted_subtask_sources"].append(selection_source)
        self.metrics["event_requery_triggers"][-1]["new_object"] = interactive_object

    def _act_semantic_mpc(self):
        if (
            self.enable_event_vlm_requery
            and self.audit_force_event_requery_step >= 0
            and self.num_steps >= self.audit_force_event_requery_step
            and not self._semantic_event_requery_used
        ):
            self.logger.info(
                "Synthetic audit forces an event VLM re-query at step %s.",
                self.num_steps,
            )
            self._semantic_event_requery_used = True
            self._perform_event_vlm_requery(
                "audit_forced_semantic_fault_recovery",
                natural=False,
            )

        obj_pos, _ = self._semantic_state_positions()
        current_distance = None
        if obj_pos is not None:
            current_distance = float(np.linalg.norm(obj_pos - self.corner_translation))
            self.metrics["distance_history"].append(current_distance)
            if len(self.metrics["distance_history"]) > 1:
                progress = self.metrics["distance_history"][-2] - current_distance
                self.metrics["progress_history"].append(float(progress))

        requery_needed, requery_reason = self._semantic_event_requery_needed(current_distance)
        if requery_needed:
            self.logger.info("Semantic controller detected stalled progress; requesting a fresh VLM subtask.")
            self._semantic_event_requery_used = True
            self.best_actions = None
            if self.enable_event_vlm_requery:
                self._perform_event_vlm_requery(requery_reason)
            else:
                self.metrics["event_requeries"] += 1
                self.metrics["natural_event_requeries"] += 1
                self.metrics["requery_reasons"].append(requery_reason)
                self.reset(reason=requery_reason)
        elif requery_reason:
            self.logger.info("Semantic event requery suppressed: %s", requery_reason)

        self._draw_semantic_frame()
        action, phase = self._semantic_push_action()
        if isinstance(action, int):
            return action
        budget_context = {
            "semantic_controller": True,
            "state_feedback": "detector_visual_state" if self.feedback_source == "visual" else "oracle_world_state",
            "event_requery_used": bool(self._semantic_event_requery_used),
        }
        self.metrics["active_num_samples"].append(0)
        self.metrics["active_plan_freq"].append(1)
        self.metrics["budget_history"].append(
            {
                "step": int(self.num_steps),
                "mode": f"semantic_{phase}",
                "num_samples": 0,
                "plan_freq": 1,
                "distance_to_target": self.metrics["distance_history"][-1] if self.metrics["distance_history"] else None,
                "tracking_unstable": False,
                "budget_context": budget_context,
            }
        )
        self.metrics["budget_context_history"].append(budget_context)
        return action

    def _current_obstacle_centers(self):
        obstacle_centers = []
        if self.use_detector_cache:
            visible_objects = self._visible_scene_objects(self.current_obs_image_path)
            for class_name, obstacle_bbx in visible_objects.items():
                if class_name == self.current_interactive_object:
                    continue
                obstacle_centers.append(self._bbox_center(obstacle_bbx))
            return obstacle_centers

        for class_name in self.class_names:
            if class_name in (self.current_interactive_object, "end effector"):
                continue
            obstacle_bbx = det_bbox(
                image_path=self.current_obs_image_path,
                model=self.det_model,
                obj_str=class_name,
            )
            if obstacle_bbx == 0:
                continue
            obstacle_centers.append(self._bbox_center(obstacle_bbx))
        return obstacle_centers

    def _legacy_push_corner_cost(self, arm_bbxes, arm_centers, subtask_obj_bbxes, subtask_obj_centers):
        target_center = self.corner_pos
        iou = calculate_iou(arm_bbxes, subtask_obj_bbxes)
        flags = iou > 1e-8
        dis_arm_obj = compute_dis(arm_centers, subtask_obj_centers)
        dis_obj_target = compute_dis(subtask_obj_centers, target_center)

        origin_center = self._bbox_center(self.subtask_obj_bbox)
        origin_dis = np.linalg.norm(origin_center - target_center)

        obstacle_dises = []
        for obstacle_center in self._current_obstacle_centers():
            obstacle_dises.append(compute_dis(arm_centers, obstacle_center))

        dis_obstacles_average = 0
        if obstacle_dises:
            dis_obstacles_average = np.sum(np.array(obstacle_dises), axis=0) / len(obstacle_dises)

        if np.any(dis_obj_target < origin_dis):
            cost = dis_obj_target - dis_obstacles_average
        else:
            cost = (
                (dis_arm_obj - dis_obstacles_average) * np.logical_not(flags)
                + (
                    dis_obj_target * self.ratio_tar_obj
                    + dis_arm_obj * self.ratio_tar_obj
                    - dis_obstacles_average * 0.25
                )
                * flags
            )
        return cost.argsort()

    def _literature_push_corner_cost(self, arm_centers, subtask_obj_centers):
        target_center = np.asarray(self.corner_pos, dtype=np.float32)
        arm_centers = np.asarray(arm_centers, dtype=np.float32)
        subtask_obj_centers = np.asarray(subtask_obj_centers, dtype=np.float32)

        origin_center = np.asarray(self._bbox_center(self.subtask_obj_bbox), dtype=np.float32)
        origin_dis = float(np.linalg.norm(origin_center - target_center))
        contact_cost_weight = self.contact_cost_weight
        alignment_cost_weight = self.alignment_cost_weight
        progress_reward_weight = self.progress_reward_weight
        non_progress_penalty = self.non_progress_penalty
        if self.use_progress_object_reselect and origin_dis <= self.close_range_distance:
            contact_cost_weight = self.close_range_contact_weight
            alignment_cost_weight = self.close_range_alignment_weight
            progress_reward_weight = self.close_range_progress_reward
            non_progress_penalty = self.close_range_non_progress_penalty

        push_vectors = target_center[None, :] - subtask_obj_centers
        push_dirs = self._unit_vectors(push_vectors)

        arm_obj_vectors = subtask_obj_centers - arm_centers
        arm_obj_dirs = self._unit_vectors(arm_obj_vectors)
        alignment = np.sum(arm_obj_dirs * push_dirs, axis=1)
        alignment_penalty = 1.0 - alignment

        desired_contact_points = subtask_obj_centers - push_dirs * self.contact_offset_pixels
        dis_contact_point = compute_dis(arm_centers, desired_contact_points)
        dis_arm_obj = compute_dis(arm_centers, subtask_obj_centers)
        dis_obj_target = compute_dis(subtask_obj_centers, target_center)
        progress_gain = np.maximum(0.0, origin_dis - dis_obj_target)

        obstacle_penalty = np.zeros(len(arm_centers), dtype=np.float32)
        for obstacle_center in self._current_obstacle_centers():
            obstacle_penalty += self._exp_decay(
                compute_dis(arm_centers, obstacle_center),
                self.obstacle_decay_pixels,
            )
            obstacle_penalty += 0.6 * self._exp_decay(
                compute_dis(subtask_obj_centers, obstacle_center),
                self.obstacle_decay_pixels,
            )

        cost = (
            dis_obj_target
            + contact_cost_weight * dis_contact_point
            + self.approach_cost_weight * dis_arm_obj
            + alignment_cost_weight * alignment_penalty
            + self.obstacle_cost_weight * obstacle_penalty
            - progress_reward_weight * progress_gain
        )
        cost += (progress_gain < self.min_progress_gain).astype(np.float32) * non_progress_penalty
        return cost.argsort()

    def cost_fn(self, frames, predictions):
        time0 = time.time()
        arm_bbxes, arm_centers = centers_by_track_batch(
            self.video_prediction_tracker,
            predictions * 255,
            self.current_end_bbox,
        )
        subtask_obj_bbxes, subtask_obj_centers = centers_by_track_batch(
            self.video_prediction_tracker,
            predictions * 255,
            self.subtask_obj_bbox,
        )
        time1 = time.time()

        if self.task != "push_corner":
            raise NotImplementedError("Only push_corner is implemented end-to-end.")
        time2 = time.time()
        self.metrics["track_center_times"].append(time1 - time0)
        self.metrics["cost_calc_times"].append(time2 - time1)
        self.logger.info("time track_center: %s", time1 - time0)
        self.logger.info("time calculate cost: %s", time2 - time1)
        if self.use_literature_cost:
            return self._literature_push_corner_cost(arm_centers, subtask_obj_centers)
        return self._legacy_push_corner_cost(arm_bbxes, arm_centers, subtask_obj_bbxes, subtask_obj_centers)

    def plan(self, frames, num_samples=None, plan_freq=None):
        num_samples = self.num_samples if num_samples is None else int(num_samples)
        plan_freq = self.plan_freq if plan_freq is None else int(plan_freq)

        action_samples = self.sampler.sample_actions(num_samples, self.mu, self.std)
        action_samples = np.clip(action_samples, -0.02, 0.02)
        batch = {
            "video": frames[None].repeat(num_samples, 1, 1, 1, 1).numpy(),
            "actions": action_samples,
        }

        self.metrics["plan_calls"] += 1
        predictions = self.video_prediciton_model(batch)["rgb"]
        scores = self.cost_fn(frames, predictions)
        best_action = action_samples[scores][0][:plan_freq]
        self.history_action_samples = action_samples[scores][0][plan_freq:]

        self.history_mu = np.zeros([self.action_horizon, self.action_dim])
        history_len = min(len(self.history_action_samples), self.action_horizon - plan_freq)
        if history_len > 0:
            self.history_mu[:history_len] = self.history_action_samples[:history_len]
            self.history_mu[-plan_freq:] = self.history_action_samples[-1]
        return best_action

    def check_subtask(self):
        if self.task != "push_corner":
            raise NotImplementedError("Only push_corner is implemented end-to-end.")
        if np.linalg.norm(self.obj_pos - self.corner_pos) <= 100:
            self.logger.info("subtask object is moved to the target region")
            return True
        return False

    def check_overall_task(self, image_path):
        state = False
        if self.use_detector_cache:
            self._refresh_scene_detections(image_path, force=True)
        for class_name in self.class_names:
            if class_name == "end effector":
                continue
            obj_bbx = self._lookup_bbox(image_path=image_path, obj_str=class_name)
            if obj_bbx == 0:
                self.logger.info("%s is not detected in the current frame.", class_name)
                return False

            obj_pos = self._bbox_center(obj_bbx)
            if np.linalg.norm(obj_pos - self.corner_pos) <= 100:
                self.logger.info("%s has been moved to the target corner.", class_name)
                state = True
            else:
                self.logger.info("%s has not been moved to the target corner.", class_name)
                return False
        return state

    def _select_planning_budget(self, tracking_unstable):
        self._last_budget_context = {
            "tracking_unstable": bool(tracking_unstable),
            "stagnating": False,
            "close_target": False,
            "obstacle_count": 0,
            "crowded_scene": False,
            "progress_volatility": 0.0,
            "volatile_progress": False,
        }
        if not self.use_adaptive_budget:
            self._last_budget_context["mode_reason"] = "adaptive_budget_disabled"
            return self.num_samples, self.plan_freq, "fixed"

        current_distance = self.metrics["distance_history"][-1] if self.metrics["distance_history"] else None
        recent_progress = self.metrics["progress_history"][-self.stagnation_window :]
        stagnating = (
            len(recent_progress) >= self.stagnation_window
            and all(progress < self.stagnation_delta for progress in recent_progress)
        )
        if stagnating:
            self.metrics["stagnation_events"] += 1

        progress_window = self.metrics["progress_history"][-max(self.stagnation_window, 3) :]
        progress_volatility = (
            float(max(progress_window) - min(progress_window))
            if len(progress_window) >= 2
            else 0.0
        )
        try:
            obstacle_count = len(self._current_obstacle_centers())
        except Exception as exc:
            self.logger.info("Could not estimate obstacle density for adaptive budget: %s", exc)
            obstacle_count = 0

        close_target = current_distance is not None and current_distance <= self.close_target_distance
        crowded_scene = obstacle_count >= self.focus_obstacle_count
        volatile_progress = progress_volatility >= self.progress_volatility_threshold

        needs_focus = tracking_unstable or stagnating or close_target or crowded_scene or volatile_progress
        self._last_budget_context = {
            "tracking_unstable": bool(tracking_unstable),
            "stagnating": bool(stagnating),
            "close_target": bool(close_target),
            "obstacle_count": int(obstacle_count),
            "crowded_scene": bool(crowded_scene),
            "progress_volatility": progress_volatility,
            "volatile_progress": bool(volatile_progress),
        }
        if current_distance is not None and current_distance <= self.close_target_distance:
            needs_focus = True

        if needs_focus:
            self._last_budget_context["mode_reason"] = "tracking_or_progress_or_obstacle_focus"
            return self.high_num_samples, self.low_plan_freq, "focused"
        self._last_budget_context["mode_reason"] = "stable_cruise"
        return self.low_num_samples, self.high_plan_freq, "cruise"

    def _should_force_stall_replan(self):
        if not self.use_stall_replan or self.best_actions is None or len(self.best_actions) == 0:
            return False
        recent_progress = self.metrics["progress_history"][-self.stall_replan_window :]
        if len(recent_progress) < self.stall_replan_window:
            return False
        return all(progress < self.stall_replan_delta for progress in recent_progress)

    def _should_switch_subtask(self, current_distance):
        if not self.use_progress_object_reselect:
            return False
        if current_distance is None or current_distance > self.near_target_reselect_distance:
            return False
        recent_progress = self.metrics["progress_history"][-self.stall_switch_window :]
        if len(recent_progress) < self.stall_switch_window:
            return False
        return all(progress <= self.stall_switch_progress for progress in recent_progress)

    def act(self, num_steps, frames, subtask_finish_status=False):
        self.num_steps = num_steps

        if self.num_steps > 0 and not self.use_semantic_mpc and not self.grounded_original_mpc:
            subtask_finish_status = self.check_subtask()

        self.current_obs_image_path = str(Path(self.log_dir) / "current_obs.png")
        plt.imsave(self.current_obs_image_path, frames[1].numpy())
        if self.use_detector_cache:
            self._refresh_scene_detections(self.current_obs_image_path, force=True)

        if self.use_semantic_mpc:
            return self._act_semantic_mpc()

        if subtask_finish_status:
            self.logger.info("Check overall task.")
            overall_task_status = self.check_overall_task(self.current_obs_image_path)
            if overall_task_status:
                self.logger.info("All the blocks have been moved to the corner.")
                imageio.mimsave(
                    f"{self.log_dir}/current_obs_with_boxes.gif",
                    self.obs_list,
                    "GIF",
                    duration=1,
                )
                return 0
            self.reset(reason="subtask_complete")
            if self.use_detector_cache:
                self._refresh_scene_detections(self.current_obs_image_path, force=True)

        tracking_unstable = False

        if self.num_steps == 0 or subtask_finish_status:
            self.subtask_obj_bbox = self._lookup_bbox(
                image_path=self.current_obs_image_path,
                obj_str=self.current_interactive_object,
            )
            while isinstance(self.subtask_obj_bbox, int):
                if self.fixed_target_object or self.target_instruction:
                    raise RuntimeError(f"Cannot find fixed target object: {self.current_interactive_object}")
                self.logger.info("Cannot find %s, resetting subtask.", self.current_interactive_object)
                self.reset(reason="object_not_visible")
                if self.use_detector_cache:
                    self._refresh_scene_detections(self.current_obs_image_path, force=True)
                self.subtask_obj_bbox = self._lookup_bbox(
                    image_path=self.current_obs_image_path,
                    obj_str=self.current_interactive_object,
                )

            self.obj_pos = self._bbox_center(self.subtask_obj_bbox)
            self.last_obj_pos = self.obj_pos
            self.last_subtask_obj_bbox = self.subtask_obj_bbox

            self.current_end_bbox = self._lookup_bbox(
                image_path=self.current_obs_image_path,
                obj_str="end effector",
            )
            if self.current_end_bbox == 0:
                raise RuntimeError("Cannot detect the end effector in the current frame.")

            self.end_pos = np.array(
                [
                    (self.current_end_bbox[0][0] + self.current_end_bbox[1][0]) / 2,
                    self.current_end_bbox[1][1],
                ]
            )

            self.end_tracker.init(
                cv2_read_image(self.current_obs_image_path),
                bbox_convert_vert_to_xywh(self.current_end_bbox),
            )
            self.obj_tracker.init(
                cv2_read_image(self.current_obs_image_path),
                bbox_convert_vert_to_xywh(self.subtask_obj_bbox),
            )
        else:
            self.current_end_bbox = self._lookup_bbox(
                image_path=self.current_obs_image_path,
                obj_str="end effector",
            )
            if self.current_end_bbox == 0:
                tracking_unstable = True
                self.metrics["end_effector_track_fallbacks"] += 1
                tracker_outputs_end = self.end_tracker.track(cv2_read_image(self.current_obs_image_path))["bbox"]
                self.current_end_bbox = np.array(
                    [
                        [tracker_outputs_end[0], tracker_outputs_end[1]],
                        [
                            tracker_outputs_end[0] + tracker_outputs_end[2],
                            tracker_outputs_end[1] + tracker_outputs_end[3],
                        ],
                    ]
                ).astype(np.int64)
            self.end_tracker.init(
                cv2_read_image(self.current_obs_image_path),
                bbox_convert_vert_to_xywh(self.current_end_bbox),
            )
            self.end_pos = np.array(
                [
                    (self.current_end_bbox[0][0] + self.current_end_bbox[1][0]) / 2,
                    self.current_end_bbox[1][1],
                ]
            )

            self.subtask_obj_bbox = self._lookup_bbox(
                image_path=self.current_obs_image_path,
                obj_str=self.current_interactive_object,
            )
            if self.subtask_obj_bbox == 0:
                tracking_unstable = True
                self.logger.info("Can't detect the object. Falling back to tracking.")
                self.metrics["object_track_fallbacks"] += 1
                tracker_outputs_obj = self.obj_tracker.track(cv2_read_image(self.current_obs_image_path))["bbox"]
                self.subtask_obj_bbox = np.array(
                    [
                        [tracker_outputs_obj[0], tracker_outputs_obj[1]],
                        [
                            tracker_outputs_obj[0] + tracker_outputs_obj[2],
                            tracker_outputs_obj[1] + tracker_outputs_obj[3],
                        ],
                    ]
                ).astype(np.int64)

            self.obj_pos = self._bbox_center(self.subtask_obj_bbox)

            if np.linalg.norm(self.obj_pos - self.last_obj_pos) > 80:
                tracking_unstable = True
                self.logger.info("Object position jumped. Falling back to tracking.")
                self.metrics["object_jump_fallbacks"] += 1
                tracker_outputs_obj = self.obj_tracker.track(cv2_read_image(self.current_obs_image_path))["bbox"]
                self.subtask_obj_bbox = np.array(
                    [
                        [tracker_outputs_obj[0], tracker_outputs_obj[1]],
                        [
                            tracker_outputs_obj[0] + tracker_outputs_obj[2],
                            tracker_outputs_obj[1] + tracker_outputs_obj[3],
                        ],
                    ]
                ).astype(np.int64)
                self.obj_pos = self._bbox_center(self.subtask_obj_bbox)

            if np.linalg.norm(self.obj_pos - self.last_obj_pos) > 80:
                tracking_unstable = True
                self.logger.info("Tracking still unstable. Reusing last object position.")
                self.metrics["reuse_last_bbox_count"] += 1
                self.subtask_obj_bbox = self.last_subtask_obj_bbox
                self.obj_pos = self.last_obj_pos

            self.obj_tracker.init(
                cv2_read_image(self.current_obs_image_path),
                bbox_convert_vert_to_xywh(self.subtask_obj_bbox),
            )
            self.last_obj_pos = self.obj_pos
            self.last_subtask_obj_bbox = self.subtask_obj_bbox

        current_distance = None
        if self.task == "push_corner":
            current_distance = float(np.linalg.norm(self.obj_pos - self.corner_pos))
            self.metrics["distance_history"].append(current_distance)
            if len(self.metrics["distance_history"]) > 1:
                progress = self.metrics["distance_history"][-2] - current_distance
                self.metrics["progress_history"].append(float(progress))

        requery_needed, requery_reason = self._original_event_vlm_requery_needed(
            current_distance,
            tracking_unstable,
        )
        if requery_needed:
            self._perform_event_vlm_requery(requery_reason)
            if self.use_detector_cache:
                self._refresh_scene_detections(self.current_obs_image_path, force=True)
            self.subtask_obj_bbox = self._lookup_bbox(
                image_path=self.current_obs_image_path,
                obj_str=self.current_interactive_object,
            )
            if isinstance(self.subtask_obj_bbox, int):
                raise RuntimeError(f"Cannot find event-requery object: {self.current_interactive_object}")
            self.obj_pos = self._bbox_center(self.subtask_obj_bbox)
            self.last_obj_pos = self.obj_pos
            self.last_subtask_obj_bbox = self.subtask_obj_bbox
            self.obj_tracker.init(
                cv2_read_image(self.current_obs_image_path),
                bbox_convert_vert_to_xywh(self.subtask_obj_bbox),
            )
            if self.task == "push_corner":
                current_distance = float(np.linalg.norm(self.obj_pos - self.corner_pos))
                self.metrics["distance_history"].append(current_distance)
        elif requery_reason:
            self.logger.info("Event VLM requery suppressed: %s", requery_reason)

        if self._should_switch_subtask(current_distance):
            self.logger.info("Literature_v2 detected a near-target stalled subtask; switching target object.")
            self.metrics["stall_subtask_switches"] += 1
            self.best_actions = None
            self.reset(reason="stall_subtask_switch")
            if self.use_detector_cache:
                self._refresh_scene_detections(self.current_obs_image_path, force=True)
            self.subtask_obj_bbox = self._lookup_bbox(
                image_path=self.current_obs_image_path,
                obj_str=self.current_interactive_object,
            )
            while isinstance(self.subtask_obj_bbox, int):
                self.reset(reason="stall_switch_object_not_visible")
                if self.use_detector_cache:
                    self._refresh_scene_detections(self.current_obs_image_path, force=True)
                self.subtask_obj_bbox = self._lookup_bbox(
                    image_path=self.current_obs_image_path,
                    obj_str=self.current_interactive_object,
                )
            self.obj_pos = self._bbox_center(self.subtask_obj_bbox)
            self.last_obj_pos = self.obj_pos
            self.last_subtask_obj_bbox = self.subtask_obj_bbox

        if self._should_force_stall_replan():
            self.logger.info("Literature controller detected stalled progress; forcing immediate replanning.")
            self.best_actions = None
            self.metrics["stall_replans"] += 1

        current_obs = cv2_read_image(self.current_obs_image_path)
        cv2.rectangle(current_obs, tuple(self.subtask_obj_bbox[0]), tuple(self.subtask_obj_bbox[1]), (0, 255, 0), 2, 4)
        cv2.rectangle(current_obs, tuple(self.current_end_bbox[0]), tuple(self.current_end_bbox[1]), (0, 0, 255), 2, 4)
        cv2.circle(current_obs, np.array(self.end_pos).astype(int), 3, (0, 0, 255), 0)
        cv2.circle(current_obs, np.array(self.obj_pos).astype(int), 3, (0, 255, 0), 0)
        cv2.putText(current_obs, str(self.current_interactive_object), (15, 15), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        current_obs = cv2.cvtColor(current_obs, cv2.COLOR_BGR2RGB)

        cv2_write_image(f"{self.log_dir}/frame_bbx_{self.num_steps}.png", current_obs[..., ::-1])
        self.obs_list.append(current_obs)

        if self.best_actions is None or len(self.best_actions) == 0:
            moving_direction = self.obj_pos - self.end_pos
            norm = np.linalg.norm(moving_direction)
            if norm < 1e-8:
                moving_direction = np.zeros_like(moving_direction)
            else:
                moving_direction = moving_direction / norm
            moving_direction *= self.zoom

            self.mu = np.zeros([self.action_horizon, self.action_dim])
            self.mu[:,] = moving_direction
            self.mu = self.history_rate * self.mu + (1 - self.history_rate) * self.history_mu

            active_num_samples, active_plan_freq, budget_mode = self._select_planning_budget(tracking_unstable)
            budget_context = dict(self._last_budget_context)
            self.metrics["active_num_samples"].append(active_num_samples)
            self.metrics["active_plan_freq"].append(active_plan_freq)
            self.metrics["budget_history"].append(
                {
                    "step": int(self.num_steps),
                    "mode": budget_mode,
                    "num_samples": int(active_num_samples),
                    "plan_freq": int(active_plan_freq),
                    "distance_to_target": current_distance,
                    "tracking_unstable": bool(tracking_unstable),
                    "budget_context": budget_context,
                }
            )
            self.metrics["budget_context_history"].append(budget_context)

            best_action = self.plan(
                frames,
                num_samples=active_num_samples,
                plan_freq=active_plan_freq,
            )
            self.best_actions = convert_env_action(best_action)

        exec_action = self.best_actions[0]
        self.best_actions = np.delete(self.best_actions, 0, axis=0)
        if self.grounded_original_mpc:
            return self._grounded_original_action(exec_action)
        return exec_action


def convert_env_action(action):
    new_action = np.zeros_like(action)
    new_action[:, 0] = action[:, 1]
    new_action[:, 1] = action[:, 0]
    return new_action


def calculate_iou(boxes1, boxes2):
    x1 = boxes1[:, 0, 0]
    y1 = boxes1[:, 0, 1]
    w1 = boxes1[:, 1, 0]
    h1 = boxes1[:, 1, 1]
    x1_br = x1 + w1
    y1_br = y1 + h1

    x2 = boxes2[:, 0, 0]
    y2 = boxes2[:, 0, 1]
    w2 = boxes2[:, 1, 0]
    h2 = boxes2[:, 1, 1]
    x2_br = x2 + w2
    y2_br = y2 + h2

    x_left = np.maximum(x1, x2)
    y_top = np.maximum(y1, y2)
    x_right = np.minimum(x1_br, x2_br)
    y_bottom = np.minimum(y1_br, y2_br)
    intersection_area = np.maximum(0, x_right - x_left) * np.maximum(0, y_bottom - y_top)

    box1_area = (x1_br - x1) * (y1_br - y1)
    box2_area = (x2_br - x2) * (y2_br - y2)
    union_area = box1_area + box2_area - intersection_area
    return intersection_area / np.maximum(union_area, 1e-8)


def compute_dis(centers1, centers2):
    return np.linalg.norm(centers1 - centers2, axis=1)
