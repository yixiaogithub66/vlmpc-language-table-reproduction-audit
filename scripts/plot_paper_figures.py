#!/usr/bin/env python3
"""Render the manuscript figures from the v1.0.5 evidence files.

The script intentionally reads the authoritative CSVs rather than embedding
summary values in plotting code.  It produces figures at approximately their
final IEEE column widths so that typography is checked at the size readers
will see in the paper.
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle


ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "figures"
DATA = ROOT / "data"
SUPPLEMENT_DATA = ROOT / "supplement_v9_sanitized" / "data"

SKILL_SCRIPTS = Path.home() / ".codex" / "skills" / "nature-figure" / "scripts"
if SKILL_SCRIPTS.is_dir():
    sys.path.insert(0, str(SKILL_SCRIPTS))
try:
    from audit_panel_alignment import require_matplotlib_panel_alignment
except ImportError:  # The public repository can still render without Codex tools.
    require_matplotlib_panel_alignment = None


COLORS = {
    "ink": "#243447",
    "muted": "#64748B",
    "grid": "#DCE3EA",
    "red": "#B24A4A",
    "blue": "#3D75C9",
    "teal": "#2D8B7A",
    "amber": "#A36A08",
    "light_red": "#F5E7E7",
    "light_blue": "#E7F0FC",
    "light_teal": "#E4F2EE",
    "light_amber": "#FBF1D8",
    "light_neutral": "#F2F5F8",
}


mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 7.0,
        "axes.titlesize": 8.0,
        "axes.labelsize": 7.0,
        "xtick.labelsize": 6.2,
        "ytick.labelsize": 6.2,
        "legend.fontsize": 6.1,
        "axes.linewidth": 0.65,
        "axes.edgecolor": COLORS["ink"],
        "axes.labelcolor": COLORS["ink"],
        "xtick.color": COLORS["ink"],
        "ytick.color": COLORS["ink"],
        "xtick.major.width": 0.65,
        "ytick.major.width": 0.65,
        "xtick.major.size": 3.0,
        "ytick.major.size": 3.0,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "savefig.facecolor": "white",
        "figure.facecolor": "white",
    }
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def values(rows: list[dict[str, str]], column: str) -> list[float]:
    return [float(row[column]) for row in rows]


def style_axes(ax: mpl.axes.Axes, *, grid_axis: str = "y") -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(COLORS["ink"])
    ax.spines["bottom"].set_color(COLORS["ink"])
    ax.grid(True, axis=grid_axis, color=COLORS["grid"], linewidth=0.55, zorder=0)
    ax.set_axisbelow(True)


def save_figure(fig: mpl.figure.Figure, stem: str, *, raster: bool = True) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / f"{stem}.pdf", bbox_inches=None, pad_inches=0)
    if raster:
        fig.savefig(FIGURES / f"{stem}.png", dpi=600, bbox_inches=None, pad_inches=0)
    plt.close(fig)


def audit_alignment(fig: mpl.figure.Figure, stem: str, **kwargs: object) -> None:
    if require_matplotlib_panel_alignment is None:
        return
    require_matplotlib_panel_alignment(
        fig,
        json_out=FIGURES / f"{stem}.alignment.json",
        overlay_svg=FIGURES / f"{stem}.alignment.svg",
        tolerance_pt=1.5,
        gutter_tolerance_pt=1.5,
        strict=True,
        **kwargs,
    )


def plot_distance_distribution() -> None:
    archived = read_csv(DATA / "archived_nonsemantic_branch_runs_v8.csv")
    raw = read_csv(DATA / "raw_controller_multiseed_runs_v9.csv")
    semantic = read_csv(DATA / "semantic_mpc_live_runs_v9.csv")
    target = read_csv(SUPPLEMENT_DATA / "revision_20260922" / "target_image_matrix_runs_v9.csv")
    visual = read_csv(SUPPLEMENT_DATA / "revision_20260922" / "visual_feedback_runs_v9.csv")

    groups = [
        ("Raw MPC\n(16)", raw, COLORS["red"], "final_target_world_distance"),
        ("Grounded\n(12)", [r for r in archived if r["suite"] in {"Grounded controller", "Grounded ablation"}], COLORS["blue"], "final_distance"),
        ("Semantic\n(18)", semantic, COLORS["teal"], "final_target_world_distance"),
        ("Target image\n(9)", target, COLORS["amber"], "final_target_world_distance"),
        ("Visual fb\n(6)", visual, COLORS["muted"], "final_target_world_distance"),
    ]

    fig, ax = plt.subplots(figsize=(3.36, 2.18))
    style_axes(ax)
    ax.axhspan(0, 0.08, color=COLORS["light_teal"], alpha=0.72, zorder=0)
    ax.axhline(0.08, color=COLORS["teal"], linestyle=(0, (4, 2)), linewidth=1.0, zorder=1)
    ax.axhline(0.05, color=COLORS["muted"], linestyle=(0, (1, 2)), linewidth=0.9, zorder=1)

    for index, (label, rows, color, column) in enumerate(groups):
        sample = values(rows, column)
        offsets = np.linspace(-0.13, 0.13, len(sample)) if len(sample) > 1 else np.array([0.0])
        ax.scatter(
            np.full(len(sample), index) + offsets,
            sample,
            s=18,
            color=color,
            edgecolor="white",
            linewidth=0.55,
            zorder=3,
        )
        median = float(np.median(sample))
        ax.plot([index - 0.16, index + 0.16], [median, median], color=color, linewidth=1.8, zorder=4)

    ax.set_xlim(-0.5, len(groups) - 0.5)
    ax.set_ylim(0, 0.52)
    ax.set_ylabel("Final world distance")
    ax.set_xticks(range(len(groups)), [label for label, _rows, _color, _column in groups])
    ax.tick_params(axis="x", length=0, pad=3)
    ax.set_yticks([0.00, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50])
    ax.set_yticklabels(["0.00", "0.05", "0.10", "0.20", "0.30", "0.40", "0.50"])
    fig.subplots_adjust(left=0.14, right=0.985, bottom=0.29, top=0.98)
    save_figure(fig, "final_distance_distribution_v9")


def plot_threshold_matrix() -> None:
    archived = read_csv(DATA / "archived_nonsemantic_branch_runs_v8.csv")
    suites = [
        ("Fresh raw MPC", read_csv(DATA / "raw_controller_multiseed_runs_v9.csv"), "final_target_world_distance"),
        ("Archived ablation", [r for r in archived if r["suite"] == "Unmodified ablation"], "final_distance"),
        ("Grounded diagnostics", [r for r in archived if r["suite"] in {"Grounded controller", "Grounded ablation"}], "final_distance"),
        ("Semantic MPC", read_csv(DATA / "semantic_mpc_live_runs_v9.csv"), "final_target_world_distance"),
        ("Target image", read_csv(SUPPLEMENT_DATA / "revision_20260922" / "target_image_matrix_runs_v9.csv"), "final_target_world_distance"),
        ("Visual feedback", read_csv(SUPPLEMENT_DATA / "revision_20260922" / "visual_feedback_runs_v9.csv"), "final_target_world_distance"),
    ]
    thresholds = ["0.05", "0.08", "0.10"]
    lookup: dict[tuple[str, str], tuple[str, float]] = {}
    for suite, rows, column in suites:
        sample = values(rows, column)
        for threshold in thresholds:
            count = sum(value <= float(threshold) for value in sample)
            lookup[(suite, threshold)] = (f"{count}/{len(sample)}", count / len(sample))

    fig, ax = plt.subplots(figsize=(3.36, 2.15))
    cmap = LinearSegmentedColormap.from_list("success", ["#EEF2F5", "#A8C6DF", COLORS["teal"]])
    image = np.array([[lookup[(suite, threshold)][1] for threshold in thresholds] for suite, _rows, _column in suites])
    ax.imshow(image, cmap=cmap, norm=Normalize(0, 1), aspect="auto", interpolation="nearest")
    for row_index, (suite, rows, _column) in enumerate(suites):
        for col_index, threshold in enumerate(thresholds):
            count, rate = lookup[(suite, threshold)]
            text_color = "white" if rate >= 0.72 else COLORS["ink"]
            ax.text(col_index, row_index, count, ha="center", va="center", color=text_color, fontsize=7.0, fontweight="bold")
        ax.text(-0.53, row_index, f"{suite}\n(n={len(rows)})", ha="right", va="center", fontsize=5.8, color=COLORS["ink"])

    ax.add_patch(Rectangle((0.5, -0.5), 1, len(suites), fill=False, edgecolor=COLORS["amber"], linewidth=1.25, zorder=4))
    ax.set_xticks(range(len(thresholds)), [f"<= {threshold}" for threshold in thresholds])
    ax.set_yticks([])
    ax.tick_params(axis="x", length=0, pad=4)
    ax.set_xlim(-0.5, 2.5)
    ax.set_ylim(len(suites) - 0.5, -0.5)
    ax.set_title("Threshold sensitivity", loc="left", fontsize=8.0, fontweight="bold", color=COLORS["ink"], pad=8)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.subplots_adjust(left=0.36, right=0.985, bottom=0.16, top=0.82)
    save_figure(fig, "threshold_sensitivity_v9")


def plot_event_audit() -> None:
    target_rows = read_csv(SUPPLEMENT_DATA / "revision_20260922" / "target_image_selection_audit_v9.csv")
    target_matches = [
        sum(row["full_frame_corner_heuristic_match"] == "True" for row in target_rows),
        sum(row["vlm_semantic_match"] == "True" for row in target_rows),
    ]
    event_rows = read_csv(SUPPLEMENT_DATA / "revision_20260922" / "event_requery_controls_v9.csv")
    no_event = [row for row in event_rows if row["case"] == "matched_no_event_instruction"]
    event_enabled = [row for row in event_rows if row["case"] == "matched_event_instruction"]
    no_event_by_seed = {int(row["seed"]): float(row["final_target_world_distance"]) for row in no_event}
    event_by_seed = {int(row["seed"]): float(row["final_target_world_distance"]) for row in event_enabled}
    seeds = sorted(no_event_by_seed)

    fig = plt.figure(figsize=(3.36, 2.16))
    grid = fig.add_gridspec(1, 2, width_ratios=[0.86, 1.34], wspace=0.42)
    left = fig.add_subplot(grid[0, 0])
    right = fig.add_subplot(grid[0, 1])
    style_axes(left)
    style_axes(right)

    left.bar(range(2), target_matches, width=0.58, color=[COLORS["red"], COLORS["teal"]], zorder=3)
    for index, match in enumerate(target_matches):
        left.text(index, match + 0.12, f"{match}/4", ha="center", va="bottom", fontsize=6.7, fontweight="bold", color=COLORS["ink"])
    left.set_xticks(range(2), ["Full-frame\nheuristic", "VLM\nsemantic"])
    left.set_ylim(0, 4.65)
    left.set_yticks([0, 2, 4])
    left.set_ylabel("Correct / 4")
    left.set_title("Target-image audit", fontsize=7.6, fontweight="bold", pad=6)

    x = np.arange(len(seeds))
    right.plot(x - 0.035, [no_event_by_seed[s] for s in seeds], color=COLORS["muted"], marker="o", markersize=3.8, linewidth=1.0, zorder=3)
    right.plot(x + 0.035, [event_by_seed[s] for s in seeds], color=COLORS["amber"], marker="s", markersize=3.8, linewidth=1.0, zorder=4)
    right.axhline(0.08, color=COLORS["teal"], linestyle=(0, (4, 2)), linewidth=0.9, zorder=1)
    right.text(0.03, 0.96, "same final distance\nby seed", transform=right.transAxes, ha="left", va="top", fontsize=5.9, color=COLORS["ink"], bbox={"boxstyle": "round,pad=0.22", "facecolor": "white", "edgecolor": COLORS["grid"], "linewidth": 0.5})
    right.set_xticks(x, [str(seed) for seed in seeds])
    right.set_xlabel("Seed")
    right.set_ylabel("Final distance")
    right.set_ylim(0.025, 0.091)
    right.set_yticks([0.03, 0.05, 0.07, 0.08])
    right.set_title("Matched event controls", fontsize=7.6, fontweight="bold", pad=6)
    for axis, label in ((left, "a"), (right, "b")):
        axis.text(-0.23, 1.08, label, transform=axis.transAxes, fontsize=8.0, fontweight="bold", color=COLORS["ink"], va="top")
    fig.subplots_adjust(left=0.11, right=0.99, bottom=0.20, top=0.91)
    audit_alignment(fig, "target_event_audit_v9", require_panel_labels=True)
    save_figure(fig, "target_event_audit_v9", raster=True)


def add_box(
    ax: mpl.axes.Axes,
    xy: tuple[float, float],
    width: float,
    height: float,
    title: str,
    body: str,
    face: str,
    edge: str,
    *,
    title_size: float = 8.6,
    body_size: float = 6.8,
) -> None:
    x, y = xy
    box = FancyBboxPatch(
        (x, y), width, height,
        boxstyle="round,pad=0.012,rounding_size=0.035",
        linewidth=1.45,
        edgecolor=edge,
        facecolor=face,
        transform=ax.transAxes,
        zorder=2,
    )
    ax.add_patch(box)
    ax.text(x + width / 2, y + height * 0.80, title, transform=ax.transAxes, ha="center", va="center", fontsize=title_size, fontweight="bold", linespacing=1.15, color=COLORS["ink"], zorder=3)
    ax.text(x + width / 2, y + height * 0.32, body, transform=ax.transAxes, ha="center", va="center", fontsize=body_size, linespacing=1.22, color=COLORS["ink"], zorder=3)


def add_arrow(ax: mpl.axes.Axes, start: tuple[float, float], end: tuple[float, float], label: str | None = None, label_xy: tuple[float, float] | None = None) -> None:
    arrow = FancyArrowPatch(start, end, transform=ax.transAxes, arrowstyle="-|>", mutation_scale=12, linewidth=1.3, color=COLORS["ink"], connectionstyle="arc3,rad=0", zorder=1)
    ax.add_patch(arrow)
    if label and label_xy:
        ax.text(label_xy[0], label_xy[1], label, transform=ax.transAxes, ha="center", va="center", fontsize=6.4, color=COLORS["muted"], bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.2}, zorder=4)


def plot_method_pipeline() -> None:
    fig, ax = plt.subplots(figsize=(7.05, 2.42))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.add_patch(Rectangle((0.018, 0.49), 0.964, 0.44, transform=ax.transAxes, facecolor="#FAFBFC", edgecolor="none", zorder=0))
    ax.add_patch(Rectangle((0.018, 0.07), 0.964, 0.32, transform=ax.transAxes, facecolor="#FFFFFF", edgecolor=COLORS["grid"], linewidth=0.7, zorder=0))
    ax.text(0.03, 0.945, "COMMON PIPELINE", transform=ax.transAxes, fontsize=6.3, fontweight="bold", color=COLORS["muted"], va="top")
    ax.text(0.03, 0.425, "EVIDENCE BRANCHES", transform=ax.transAxes, fontsize=6.3, fontweight="bold", color=COLORS["muted"], va="top")

    top_y, top_w, top_h = 0.59, 0.18, 0.27
    top_x = [0.035, 0.275, 0.515, 0.755]
    top_specs = [
        ("Inputs", "fixed label\nlanguage\nscene VLM\ntarget image", COLORS["light_blue"], "#5A7396"),
        ("Semantic target", "VLM selection\ntarget audit", COLORS["light_teal"], "#47816F"),
        ("Raw VLMPC", "sampling\nprediction\ncost ranking", "#FBF0E0", "#A36F20"),
        ("Artifacts", "CSV/JSON logs\nfigures and videos", COLORS["light_neutral"], "#697587"),
    ]
    for x, spec in zip(top_x, top_specs):
        add_box(ax, (x, top_y), top_w, top_h, *spec)
    for start_x, end_x in zip(top_x[:-1], top_x[1:]):
        add_arrow(ax, (start_x + top_w + 0.008, top_y + top_h / 2), (end_x - 0.008, top_y + top_h / 2))

    bottom_y, bottom_w, bottom_h = 0.13, 0.205, 0.23
    bottom_specs = [
        (0.035, "Raw MPC", "no state feedback\nfresh 0/16\nseeds 45--48", COLORS["light_red"], COLORS["red"]),
        (0.275, "Oracle feedback", "privileged state\n23/23 overrides\nsemantic 18/18", COLORS["light_blue"], COLORS["blue"]),
        (0.515, "Visual feedback", "detector/tracker\nno simulator state\n0/6", COLORS["light_neutral"], COLORS["muted"]),
        (0.755, "Event controls", "no-cache pairs\ntrigger executes\nno causal gain", COLORS["light_amber"], COLORS["amber"]),
    ]
    for x, title, body, face, edge in bottom_specs:
        add_box(ax, (x, bottom_y), bottom_w, bottom_h, title, body, face, edge, title_size=8.1, body_size=6.35)

    add_arrow(ax, (0.575, top_y - 0.01), (0.137, bottom_y + bottom_h + 0.01))
    add_arrow(ax, (0.605, top_y - 0.01), (0.377, bottom_y + bottom_h + 0.01))
    add_arrow(ax, (0.635, top_y - 0.01), (0.617, bottom_y + bottom_h + 0.01))
    add_arrow(ax, (0.845, top_y - 0.01), (0.857, bottom_y + bottom_h + 0.01))

    ax.add_patch(FancyBboxPatch((0.035, 0.005), 0.93, 0.045, boxstyle="round,pad=0.008,rounding_size=0.012", transform=ax.transAxes, facecolor="#F4F6F8", edgecolor="none", zorder=1))
    ax.text(0.5, 0.027, "Reporting boundary: successful diagnostic branches use privileged simulator-state feedback; event controls verify trigger execution, not causal recovery.", transform=ax.transAxes, ha="center", va="center", fontsize=7.0, color=COLORS["ink"], zorder=2)
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    save_figure(fig, "method_pipeline_v9")


def plot_qualitative_frames() -> None:
    source_frames = [
        FIGURES / "source" / "qualitative_frame_0.png",
        FIGURES / "source" / "qualitative_frame_11.png",
        FIGURES / "source" / "qualitative_frame_22.png",
    ]
    crops = [plt.imread(path) for path in source_frames]

    fig, axes = plt.subplots(1, 3, figsize=(3.36, 1.30), gridspec_kw={"wspace": 0.035})
    labels = ["Initial", "Intermediate", "Final"]
    for axis, crop, label in zip(axes, crops, labels):
        axis.imshow(crop)
        axis.axis("off")
        axis.set_title(label, fontsize=7.0, fontweight="bold", color=COLORS["ink"], pad=3)
    fig.text(0.02, 0.015, "Target: red moon", fontsize=6.2, color=COLORS["red"], ha="left", va="bottom", fontweight="bold")
    fig.text(0.98, 0.015, "Final distance: 0.0643", fontsize=6.2, color=COLORS["muted"], ha="right", va="bottom")
    fig.subplots_adjust(left=0.005, right=0.995, bottom=0.12, top=0.80)
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / "qualitative_frames_v9.png", dpi=600, bbox_inches=None, pad_inches=0, facecolor="white")
    plt.close(fig)


def main() -> None:
    plot_distance_distribution()
    plot_threshold_matrix()
    plot_event_audit()
    plot_method_pipeline()
    plot_qualitative_frames()
    print("Rendered v1.0.5 manuscript figures from live and archived CSVs.")


if __name__ == "__main__":
    main()
