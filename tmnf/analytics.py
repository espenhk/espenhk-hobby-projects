"""
analytics.py — Generate plots and summary tables at the end of a TMNF experiment.

Entry point:
    save_experiment_results(data: ExperimentData, results_dir: str) -> None

All output goes to results_dir/. The directory is created if it doesn't exist.
Files that belong to a skipped phase (e.g. probe/cold-start on a resumed run)
are simply not written.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data containers (populated by main.py during training)
# ---------------------------------------------------------------------------

@dataclass
class RunTrace:
    """Sampled position + per-step throttle state for one episode."""
    pos_x: list          # world X, sampled every TRACE_SAMPLE_EVERY steps
    pos_z: list          # world Z (horizontal plane in TMNF; Y is up)
    throttle_state: list # per step: 0=brake, 1=coast, 2=accel
    total_reward: float


@dataclass
class ProbeResult:
    action_idx: int
    action_name: str
    reward: float
    trace: RunTrace | None = None


@dataclass
class ColdStartSimResult:
    sim: int           # 1-based within its restart
    reward: float
    throttle_counts: list  # [brake_steps, coast_steps, accel_steps]
    total_steps: int
    trace: RunTrace | None = None


@dataclass
class ColdStartRestartResult:
    restart: int
    sims: list         # list[ColdStartSimResult]
    best_reward: float
    beat_probe_floor: bool


@dataclass
class GreedySimResult:
    sim: int
    reward: float
    improved: bool
    throttle_counts: list  # [brake_steps, coast_steps, accel_steps]
    total_steps: int
    trace: RunTrace | None = None


@dataclass
class ExperimentData:
    experiment_name: str
    probe_results: list        # list[ProbeResult]; empty if weights pre-existed
    cold_start_restarts: list  # list[ColdStartRestartResult]; empty if skipped
    greedy_sims: list          # list[GreedySimResult]
    probe_floor: float | None  # best probe reward, or None if probe was skipped
    weights_file: str          # absolute or relative path to policy_weights.yaml
    reward_config_file: str    # path to the experiment's reward_config.yaml
    training_params: dict      # SPEED, N_SIMS, etc. from main()
    timings: dict              # start, end, total_s, probe_s, cold_start_s, greedy_s


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _save(fig, path: str) -> None:
    fig.savefig(path, dpi=150, bbox_inches="tight")
    import matplotlib.pyplot as plt
    plt.close(fig)


_THROTTLE_COLORS = ["#c0392b", "#95a5a6", "#27ae60"]   # brake / coast / accel
_THROTTLE_LABELS = ["brake", "coast", "accel"]


# ---------------------------------------------------------------------------
# Probe phase
# ---------------------------------------------------------------------------

def _probe_table_md(data: ExperimentData) -> str:
    best_reward = max(p.reward for p in data.probe_results)
    lines = [
        "## Probe Phase\n\n",
        f"Best probe reward: **{best_reward:+.1f}**\n\n",
        "| Action | Name            | Reward   |          |\n",
        "|--------|-----------------|----------|----------|\n",
    ]
    for p in sorted(data.probe_results, key=lambda x: x.action_idx):
        marker = "← best" if p.reward == best_reward else ""
        lines.append(f"| {p.action_idx:6d} | {p.action_name:15s} | {p.reward:+8.1f} | {marker} |\n")
    return "".join(lines)


def plot_probe_rewards(data: ExperimentData, results_dir: str) -> None:
    import matplotlib.pyplot as plt

    probes = sorted(data.probe_results, key=lambda p: p.action_idx)
    names  = [p.action_name for p in probes]
    rewards = [p.reward for p in probes]
    best_r = max(rewards)

    colors = ["#f1c40f" if r == best_r else "#3498db" for r in rewards]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(names, rewards, color=colors, edgecolor="white", linewidth=0.6)

    if data.probe_floor is not None:
        ax.axhline(data.probe_floor, color="#e74c3c", linestyle="--",
                   linewidth=1.4, label=f"probe floor ({data.probe_floor:+.1f})")
        ax.legend(fontsize=9)

    ax.set_title(f"{data.experiment_name} — Probe Phase: Reward per Constant Action")
    ax.set_xlabel("Action")
    ax.set_ylabel("Total Episode Reward")
    ax.tick_params(axis="x", rotation=20)

    for bar, r in zip(bars, rewards):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + abs(bar.get_height()) * 0.01,
                f"{r:+.0f}", ha="center", va="bottom", fontsize=8)

    fig.tight_layout()
    _save(fig, os.path.join(results_dir, "probe_rewards.png"))


# ---------------------------------------------------------------------------
# Cold-start phase
# ---------------------------------------------------------------------------

def _cold_start_table_md(data: ExperimentData) -> str:
    best_r = max(r.best_reward for r in data.cold_start_restarts)
    lines = [
        "## Cold-Start Search\n\n",
        f"Best cold-start reward: **{best_r:+.1f}**\n",
        f"Probe floor: **{data.probe_floor:+.1f}**\n\n" if data.probe_floor is not None else "\n",
        "| Restart | Best Reward | Beat Probe Floor |          |\n",
        "|---------|-------------|------------------|----------|\n",
    ]
    for r in data.cold_start_restarts:
        marker = "← best" if r.best_reward == best_r else ""
        beat   = "yes" if r.beat_probe_floor else "no"
        lines.append(f"| {r.restart:7d} | {r.best_reward:+11.1f} | {beat:16s} | {marker} |\n")
    return "".join(lines)


def plot_cold_start_rewards(data: ExperimentData, results_dir: str) -> None:
    import matplotlib.pyplot as plt

    restarts = data.cold_start_restarts
    xs      = [r.restart for r in restarts]
    rewards = [r.best_reward for r in restarts]
    colors  = ["#27ae60" if r.beat_probe_floor else "#c0392b" for r in restarts]

    fig, ax = plt.subplots(figsize=(max(6, len(xs) * 0.8), 5))
    bars = ax.bar(xs, rewards, color=colors, edgecolor="white", linewidth=0.6)

    if data.probe_floor is not None:
        ax.axhline(data.probe_floor, color="#f39c12", linestyle="--",
                   linewidth=1.4, label=f"probe floor ({data.probe_floor:+.1f})")

    # legend patches for beat/miss
    import matplotlib.patches as mpatches
    ax.legend(handles=[
        mpatches.Patch(color="#27ae60", label="beat probe floor"),
        mpatches.Patch(color="#c0392b", label="below probe floor"),
    ] + ([ax.get_legend_handles_labels()[0][0]] if data.probe_floor is not None else []),
        fontsize=9)

    ax.set_title(f"{data.experiment_name} — Cold-Start: Best Reward per Restart")
    ax.set_xlabel("Restart")
    ax.set_ylabel("Best Episode Reward")
    ax.set_xticks(xs)

    for bar, r in zip(bars, rewards):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                f"{r:+.0f}", ha="center", va="bottom", fontsize=8)

    fig.tight_layout()
    _save(fig, os.path.join(results_dir, "cold_start_best_rewards.png"))


def plot_cold_start_action_dist(data: ExperimentData, results_dir: str) -> None:
    """Stacked bar: mean throttle distribution (brake/coast/accel) per restart."""
    import matplotlib.pyplot as plt
    import numpy as np

    restarts = data.cold_start_restarts
    xs = [r.restart for r in restarts]

    pcts = []  # shape (n_restarts, 3)  — percent for brake/coast/accel
    for r in restarts:
        total_b = total_c = total_a = 0
        for s in r.sims:
            b, c, a = s.throttle_counts
            total_b += b; total_c += c; total_a += a
        total = total_b + total_c + total_a or 1
        pcts.append([100 * total_b / total, 100 * total_c / total, 100 * total_a / total])
    pcts = np.array(pcts)

    fig, ax = plt.subplots(figsize=(max(6, len(xs) * 0.8), 5))
    bottoms = np.zeros(len(xs))
    for i, (label, color) in enumerate(zip(_THROTTLE_LABELS, _THROTTLE_COLORS)):
        ax.bar(xs, pcts[:, i], bottom=bottoms, color=color, label=label,
               edgecolor="white", linewidth=0.4)
        bottoms += pcts[:, i]

    ax.set_title(f"{data.experiment_name} — Cold-Start: Throttle Distribution per Restart")
    ax.set_xlabel("Restart")
    ax.set_ylabel("% Steps")
    ax.set_xticks(xs)
    ax.set_ylim(0, 100)
    ax.legend(fontsize=9)
    fig.tight_layout()
    _save(fig, os.path.join(results_dir, "cold_start_action_dist.png"))


# ---------------------------------------------------------------------------
# Greedy phase
# ---------------------------------------------------------------------------

def _greedy_table_md(data: ExperimentData) -> str:
    best_r = max((s.reward for s in data.greedy_sims), default=float("-inf"))
    lines = [
        "## Greedy Phase\n\n",
        f"Best reward: **{best_r:+.1f}**\n\n",
        "| Sim  | Reward   | Result       |\n",
        "|------|----------|--------------|\n",
    ]
    for s in data.greedy_sims:
        tag = "**NEW BEST**" if s.improved else ""
        lines.append(f"| {s.sim:4d} | {s.reward:+8.1f} | {tag} |\n")
    return "".join(lines)


def plot_greedy_rewards(data: ExperimentData, results_dir: str) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    sims    = [s.sim for s in data.greedy_sims]
    rewards = [s.reward for s in data.greedy_sims]

    # best-so-far step function
    best_so_far = []
    running_best = float("-inf")
    for r in rewards:
        if r > running_best:
            running_best = r
        best_so_far.append(running_best)

    improvement_xs = [s.sim for s in data.greedy_sims if s.improved]
    improvement_ys = [s.reward for s in data.greedy_sims if s.improved]

    fig, ax = plt.subplots(figsize=(max(8, len(sims) * 0.15), 5))
    ax.scatter(sims, rewards, color="#95a5a6", s=18, alpha=0.7, zorder=2, label="candidate reward")
    ax.step(sims, best_so_far, where="post", color="#e67e22",
            linewidth=2.0, zorder=3, label="best so far")
    ax.scatter(improvement_xs, improvement_ys, color="#27ae60",
               s=60, zorder=4, marker="^", label="improvement")

    ax.set_title(f"{data.experiment_name} — Greedy Phase: Reward per Simulation")
    ax.set_xlabel("Simulation")
    ax.set_ylabel("Total Episode Reward")
    ax.legend(fontsize=9)
    fig.tight_layout()
    _save(fig, os.path.join(results_dir, "greedy_rewards.png"))


# ---------------------------------------------------------------------------
# Suggested extras
# ---------------------------------------------------------------------------

def plot_greedy_action_dist(data: ExperimentData, results_dir: str) -> None:
    """100% stacked bar: throttle mix per greedy sim — shows if policy shifts toward accel."""
    import matplotlib.pyplot as plt
    import numpy as np

    sims = data.greedy_sims
    xs   = [s.sim for s in sims]
    pcts = []
    for s in sims:
        b, c, a = s.throttle_counts
        total = (b + c + a) or 1
        pcts.append([100 * b / total, 100 * c / total, 100 * a / total])
    pcts = np.array(pcts)

    fig, ax = plt.subplots(figsize=(max(8, len(xs) * 0.15), 5))
    bottoms = np.zeros(len(xs))
    for i, (label, color) in enumerate(zip(_THROTTLE_LABELS, _THROTTLE_COLORS)):
        ax.bar(xs, pcts[:, i], bottom=bottoms, color=color, label=label,
               width=1.0, edgecolor="none")
        bottoms += pcts[:, i]

    ax.set_title(f"{data.experiment_name} — Greedy Phase: Throttle Mix per Sim")
    ax.set_xlabel("Simulation")
    ax.set_ylabel("% Steps")
    ax.set_ylim(0, 100)
    ax.legend(fontsize=9)
    fig.tight_layout()
    _save(fig, os.path.join(results_dir, "greedy_action_dist.png"))


def plot_reward_trajectory(data: ExperimentData, results_dir: str) -> None:
    """All-phases best reward on a single cumulative-sim axis."""
    import matplotlib.pyplot as plt

    xs, ys, colors = [], [], []
    x = 0

    # Probe phase — one horizontal line segment per action (not hill-climbing)
    if data.probe_results:
        probe_sorted = sorted(data.probe_results, key=lambda p: p.action_idx)
        for p in probe_sorted:
            xs.append(x); ys.append(p.reward); colors.append("#3498db")
            x += 1

    # Cold-start — one point per sim, across all restarts
    if data.cold_start_restarts:
        for restart in data.cold_start_restarts:
            for s in restart.sims:
                xs.append(x); ys.append(s.reward); colors.append("#9b59b6")
                x += 1

    # Greedy
    for s in data.greedy_sims:
        xs.append(x); ys.append(s.reward); colors.append("#e67e22")
        x += 1

    # best-so-far overlay
    running_best = float("-inf")
    best_xs, best_ys = [], []
    for xi, yi in zip(xs, ys):
        if yi > running_best:
            running_best = yi
        best_xs.append(xi)
        best_ys.append(running_best)

    fig, ax = plt.subplots(figsize=(max(8, len(xs) * 0.12), 5))
    ax.scatter(xs, ys, c=colors, s=14, alpha=0.6, zorder=2)
    ax.step(best_xs, best_ys, where="post", color="black",
            linewidth=1.8, zorder=3, label="best so far")

    # phase boundary markers
    boundary = len(data.probe_results or [])
    if boundary > 0 and (data.cold_start_restarts or data.greedy_sims):
        ax.axvline(boundary - 0.5, color="#3498db", linestyle=":", linewidth=1, alpha=0.6)
    cs_total = sum(len(r.sims) for r in (data.cold_start_restarts or []))
    if cs_total > 0 and data.greedy_sims:
        ax.axvline(boundary + cs_total - 0.5, color="#9b59b6", linestyle=":", linewidth=1, alpha=0.6)

    import matplotlib.patches as mpatches
    legend_patches = []
    if data.probe_results:
        legend_patches.append(mpatches.Patch(color="#3498db", label="probe"))
    if data.cold_start_restarts:
        legend_patches.append(mpatches.Patch(color="#9b59b6", label="cold-start"))
    if data.greedy_sims:
        legend_patches.append(mpatches.Patch(color="#e67e22", label="greedy"))
    ax.legend(handles=legend_patches + [ax.get_legend_handles_labels()[0][-1]],
              fontsize=9)

    ax.set_title(f"{data.experiment_name} — Reward Trajectory Across All Phases")
    ax.set_xlabel("Cumulative simulation")
    ax.set_ylabel("Total Episode Reward")
    fig.tight_layout()
    _save(fig, os.path.join(results_dir, "reward_trajectory.png"))


def plot_weight_heatmap(data: ExperimentData, results_dir: str) -> None:
    """2×15 heatmap of steer/throttle weights from the saved policy YAML."""
    import yaml
    import numpy as np
    import matplotlib.pyplot as plt
    from policies import WeightedLinearPolicy

    if not os.path.exists(data.weights_file):
        return

    with open(data.weights_file) as f:
        cfg = yaml.safe_load(f)

    obs_names = WeightedLinearPolicy.OBS_NAMES
    steer_w    = np.array([cfg["steer_weights"][n]    for n in obs_names])
    throttle_w = np.array([cfg["throttle_weights"][n] for n in obs_names])
    matrix = np.vstack([steer_w, throttle_w])

    vmax = max(abs(matrix).max(), 1e-6)

    fig, ax = plt.subplots(figsize=(13, 3))
    im = ax.imshow(matrix, cmap="RdBu", aspect="auto", vmin=-vmax, vmax=vmax)
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)

    ax.set_xticks(range(len(obs_names)))
    ax.set_xticklabels(obs_names, rotation=45, ha="right", fontsize=8)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["steer", "throttle"])
    ax.set_title(f"{data.experiment_name} — Final Policy Weight Heatmap")
    fig.tight_layout()
    _save(fig, os.path.join(results_dir, "policy_weights_heatmap.png"))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _plot_throttle_trace(ax, throttle_state: list, title: str) -> None:
    """Draw a throttle/brake trace as two binary step lines on *ax*."""
    steps = range(len(throttle_state))
    accel = [1 if t == 2 else 0 for t in throttle_state]
    brake = [1 if t == 0 else 0 for t in throttle_state]
    ax.step(steps, accel, where="post", color=_THROTTLE_COLORS[2], linewidth=1.0, label="accel")
    ax.step(steps, [-b for b in brake], where="post", color=_THROTTLE_COLORS[0], linewidth=1.0, label="brake")
    ax.axhline(0, color="#aaa", linewidth=0.5, linestyle="--")
    ax.set_ylim(-1.3, 1.3)
    ax.set_yticks([-1, 0, 1])
    ax.set_yticklabels(["brake", "", "accel"], fontsize=8)
    ax.set_xlabel("Step")
    ax.set_title(title, fontsize=9)
    ax.legend(fontsize=8, loc="upper right")


def plot_probe_paths(data: ExperimentData, results_dir: str) -> None:
    """One path per probe action, all overlaid on a single bird's-eye plot."""
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm
    import numpy as np

    probes = [p for p in sorted(data.probe_results, key=lambda p: p.action_idx)
              if p.trace and p.trace.pos_x]
    if not probes:
        return

    fig, ax = plt.subplots(figsize=(8, 8))
    colors = cm.tab10(np.linspace(0, 1, len(probes)))

    for p, color in zip(probes, colors):
        ax.plot(p.trace.pos_x, p.trace.pos_z, color=color, linewidth=1.2,
                label=p.action_name, alpha=0.85)
        ax.plot(p.trace.pos_x[0], p.trace.pos_z[0], "o", color=color, markersize=5)

    ax.set_title(f"{data.experiment_name} — Probe Phase: Paths (bird's eye)")
    ax.set_xlabel("World X")
    ax.set_ylabel("World Z")
    ax.legend(fontsize=8, loc="best")
    ax.set_aspect("equal", adjustable="datalim")
    fig.tight_layout()
    _save(fig, os.path.join(results_dir, "probe_paths.png"))


def _best_cold_start_trace(data: ExperimentData):
    """Return the RunTrace of the highest-reward sim across all cold-start restarts."""
    best_sim = None
    best_reward = float("-inf")
    for restart in data.cold_start_restarts:
        for s in restart.sims:
            if s.reward > best_reward:
                best_reward = s.reward
                best_sim = s
    return best_sim.trace if best_sim else None


def plot_cold_start_best_run(data: ExperimentData, results_dir: str) -> None:
    """Path + throttle trace for the best cold-start sim."""
    import matplotlib.pyplot as plt

    trace = _best_cold_start_trace(data)
    if not trace or not trace.pos_x:
        return

    fig, (ax_path, ax_throttle) = plt.subplots(1, 2, figsize=(14, 6))

    ax_path.plot(trace.pos_x, trace.pos_z, color="#9b59b6", linewidth=1.4)
    ax_path.plot(trace.pos_x[0], trace.pos_z[0], "o", color="#9b59b6", markersize=6)
    ax_path.set_title("Path (bird's eye)")
    ax_path.set_xlabel("World X")
    ax_path.set_ylabel("World Z")
    ax_path.set_aspect("equal", adjustable="datalim")

    _plot_throttle_trace(ax_throttle, trace.throttle_state,
                         f"Throttle/brake trace  (reward {trace.total_reward:+.1f})")

    fig.suptitle(f"{data.experiment_name} — Cold-Start Best Run", fontsize=11)
    fig.tight_layout()
    _save(fig, os.path.join(results_dir, "cold_start_best_run.png"))


def plot_greedy_best_run(data: ExperimentData, results_dir: str) -> None:
    """Path + throttle trace for the highest-reward greedy sim."""
    import matplotlib.pyplot as plt

    if not data.greedy_sims:
        return
    best = max(data.greedy_sims, key=lambda s: s.reward)
    trace = best.trace
    if not trace or not trace.pos_x:
        return

    fig, (ax_path, ax_throttle) = plt.subplots(1, 2, figsize=(14, 6))

    ax_path.plot(trace.pos_x, trace.pos_z, color="#e67e22", linewidth=1.4)
    ax_path.plot(trace.pos_x[0], trace.pos_z[0], "o", color="#e67e22", markersize=6)
    ax_path.set_title("Path (bird's eye)")
    ax_path.set_xlabel("World X")
    ax_path.set_ylabel("World Z")
    ax_path.set_aspect("equal", adjustable="datalim")

    _plot_throttle_trace(ax_throttle, trace.throttle_state,
                         f"Throttle/brake trace  (reward {trace.total_reward:+.1f})")

    fig.suptitle(f"{data.experiment_name} — Greedy Best Run (sim {best.sim})", fontsize=11)
    fig.tight_layout()
    _save(fig, os.path.join(results_dir, "greedy_best_run.png"))


def _fmt_duration(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    if h:
        return f"{h}h {m:02d}m {s:04.1f}s"
    if m:
        return f"{m}m {s:04.1f}s"
    return f"{s:.1f}s"


def _timings_md(data: ExperimentData) -> str:
    t = data.timings
    lines = [
        "## Timings\n\n",
        f"- **Start:** {t['start']}\n",
        f"- **End:** {t['end']}\n",
        f"- **Total runtime:** {_fmt_duration(t['total_s'])}\n\n",
        "| Phase | Duration |\n",
        "|-------|----------|\n",
    ]
    if t.get("probe_s") is not None:
        lines.append(f"| Probe | {_fmt_duration(t['probe_s'])} |\n")
    if t.get("cold_start_s") is not None:
        lines.append(f"| Cold-start | {_fmt_duration(t['cold_start_s'])} |\n")
    if t.get("greedy_s") is not None:
        lines.append(f"| Greedy | {_fmt_duration(t['greedy_s'])} |\n")
    return "".join(lines) + "\n"


def _summary_md(data: ExperimentData) -> str:
    import yaml

    lines = ["## Run Parameters\n\n"]

    # Training hyperparameters
    lines.append("### Training\n\n")
    lines.append("| Parameter | Value |\n")
    lines.append("|-----------|-------|\n")
    for k, v in data.training_params.items():
        lines.append(f"| {k} | {v} |\n")

    # Reward config
    lines.append("\n### Reward Config\n\n")
    if os.path.exists(data.reward_config_file):
        with open(data.reward_config_file) as f:
            cfg = yaml.safe_load(f)
        lines.append("| Parameter | Value |\n")
        lines.append("|-----------|-------|\n")
        for k, v in cfg.items():
            lines.append(f"| {k} | {v} |\n")
    else:
        lines.append(f"_(reward config not found at `{data.reward_config_file}`)_\n")

    return "".join(lines) + "\n"


def save_experiment_results(data: ExperimentData, results_dir: str) -> None:
    """Generate all plots and write a single results.md report to *results_dir*."""
    os.makedirs(results_dir, exist_ok=True)

    sections = [f"# Experiment: {data.experiment_name}\n\n", _timings_md(data), _summary_md(data)]

    if data.probe_results:
        plot_probe_rewards(data, results_dir)
        plot_probe_paths(data, results_dir)
        sections.append(_probe_table_md(data))
        sections.append("\n![Probe rewards](probe_rewards.png)\n\n")
        sections.append("![Probe paths](probe_paths.png)\n\n")

    if data.cold_start_restarts:
        plot_cold_start_rewards(data, results_dir)
        plot_cold_start_action_dist(data, results_dir)
        plot_cold_start_best_run(data, results_dir)
        sections.append(_cold_start_table_md(data))
        sections.append("\n![Cold-start best rewards](cold_start_best_rewards.png)\n\n")
        sections.append("![Cold-start action distribution](cold_start_action_dist.png)\n\n")
        sections.append("![Cold-start best run](cold_start_best_run.png)\n\n")

    if data.greedy_sims:
        plot_greedy_rewards(data, results_dir)
        plot_greedy_best_run(data, results_dir)
        sections.append(_greedy_table_md(data))
        sections.append("\n![Greedy rewards](greedy_rewards.png)\n\n")
        sections.append("![Greedy best run](greedy_best_run.png)\n\n")

    plot_greedy_action_dist(data, results_dir)
    plot_reward_trajectory(data, results_dir)
    plot_weight_heatmap(data, results_dir)
    sections.append("## Additional Plots\n\n")
    if data.greedy_sims:
        sections.append("![Greedy action distribution](greedy_action_dist.png)\n\n")
    sections.append("![Reward trajectory](reward_trajectory.png)\n\n")
    if os.path.exists(data.weights_file):
        sections.append("![Policy weight heatmap](policy_weights_heatmap.png)\n\n")

    report_path = os.path.join(results_dir, "results.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.writelines(sections)

    n = len(os.listdir(results_dir))
    print(f"  Saved {n} file(s) to {results_dir}/ (report: results.md)")
