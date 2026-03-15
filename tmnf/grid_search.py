"""
grid_search.py — Run a Cartesian-product sweep over training and reward params.

Usage (from tmnf/):
    python grid_search.py config/my_grid.yaml [--no-interrupt]

Config format (YAML):
    base_name: "gs_v1"
    training_params:
        speed: 10.0
        n_sims: 50
        mutation_scale: [0.05, 0.1, 0.2]   # list = search axis
        ...
    reward_params:
        centerline_weight: [-0.1, -0.5]     # list = search axis
        accel_bonus: 1.0
        ...

Any param set to a list becomes a search axis; all others are fixed.
One experiment is run per unique combination. Names encode only the varied params.
"""

from __future__ import annotations

import argparse
import itertools
import os

import yaml


# ---------------------------------------------------------------------------
# Param name → short abbreviation for experiment directory names
# ---------------------------------------------------------------------------

_ABBREV = {
    # training params
    "speed":           "speed",
    "n_sims":          "nsims",
    "in_game_episode_s": "ep",
    "mutation_scale":  "ms",
    "probe_s":         "probe",
    "cold_restarts":   "cr",
    "cold_sims":       "cs",
    # reward params
    "progress_weight": "pw",
    "centerline_weight": "cw",
    "centerline_exp":  "ce",
    "speed_weight":    "sw",
    "step_penalty":    "sp",
    "finish_bonus":    "fb",
    "finish_time_weight": "ftw",
    "par_time_s":      "par",
    "accel_bonus":     "ab",
    "airborne_penalty": "ap",
    "crash_threshold_m": "ct",
}


def _fmt_value(v) -> str:
    """Format a param value for use in a directory name.

    - Integers: plain digits (50 → '50')
    - Floats: strip trailing zeros; replace leading '-' with 'n' (−0.1 → 'n0.1')
    - Others: str()
    """
    if isinstance(v, float):
        s = f"{v:g}"          # e.g. '10', '-0.1', '0.05'
        s = s.replace("-", "n")
        return s
    if isinstance(v, int):
        return str(v)
    return str(v).replace("-", "n")


def _make_experiment_name(base_name: str, combo: dict, varied_keys: list[str]) -> str:
    """Build experiment name from base + only the varied param values."""
    parts = [base_name]
    for key in varied_keys:
        abbrev = _ABBREV.get(key, key)
        parts.append(f"{abbrev}{_fmt_value(combo[key])}")
    return "__".join(parts)


# ---------------------------------------------------------------------------
# Config loading and grid expansion
# ---------------------------------------------------------------------------

def _load_grid_config(path: str) -> tuple[str, dict, dict]:
    """Load grid config YAML. Returns (base_name, training_spec, reward_spec)."""
    with open(path) as f:
        cfg = yaml.safe_load(f)
    base_name = cfg.get("base_name", "gs")
    training_spec = cfg.get("training_params", {})
    reward_spec = cfg.get("reward_params", {})
    return base_name, training_spec, reward_spec


def _expand_grid(training_spec: dict, reward_spec: dict) -> list[dict]:
    """
    Expand all list-valued params into a Cartesian product.
    Each element of the returned list is a flat dict:
        {"training_params": {...}, "reward_params": {...}}
    Also returns the list of varied keys (in order) for name generation.
    """
    # Collect axes: (key, [values], "training"|"reward")
    axes = []
    for key, val in training_spec.items():
        if isinstance(val, list):
            axes.append((key, val, "training"))
    for key, val in reward_spec.items():
        if isinstance(val, list):
            axes.append((key, val, "reward"))

    if not axes:
        # No variation — single run with fixed values
        return [{"training_params": dict(training_spec), "reward_params": dict(reward_spec)}], []

    varied_keys = [a[0] for a in axes]
    value_lists = [a[1] for a in axes]
    sources     = [a[2] for a in axes]

    combos = []
    for combo_values in itertools.product(*value_lists):
        t_params = dict(training_spec)
        r_params = dict(reward_spec)
        flat = {}
        for key, val, src in zip(varied_keys, combo_values, sources):
            flat[key] = val
            if src == "training":
                t_params[key] = val
            else:
                r_params[key] = val
        combos.append({"training_params": t_params, "reward_params": r_params, "_flat": flat})

    return combos, varied_keys


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Grid search over TMNF training/reward params")
    parser.add_argument("config", help="Path to grid search YAML config")
    parser.add_argument("--no-interrupt", action="store_true",
                        help="Skip all 'Press Enter' prompts (run fully automated)")
    args = parser.parse_args()

    base_name, training_spec, reward_spec = _load_grid_config(args.config)
    combos, varied_keys = _expand_grid(training_spec, reward_spec)

    n = len(combos)
    print(f"\n{'='*60}")
    print(f"  Grid search: {n} combination(s)")
    print(f"  Base name:   {base_name}")
    if varied_keys:
        print(f"  Varied:      {', '.join(varied_keys)}")
    print(f"{'='*60}\n")

    # Print all experiment names upfront so the user knows what's coming
    names = []
    for c in combos:
        name = _make_experiment_name(base_name, c["_flat"], varied_keys)
        names.append(name)
        print(f"  {name}")
    print()

    from analytics import save_experiment_results
    from main import train_rl

    results_summary = []

    for i, (combo, name) in enumerate(zip(combos, names), 1):
        t = combo["training_params"]
        r = combo["reward_params"]

        print(f"\n{'='*60}")
        print(f"  Run {i}/{n}: {name}")
        print(f"{'='*60}")

        experiment_dir = f"experiments/{name}"
        weights_file   = f"{experiment_dir}/policy_weights.yaml"
        reward_cfg_file = f"{experiment_dir}/reward_config.yaml"
        training_params_file = f"{experiment_dir}/training_params.yaml"

        os.makedirs(experiment_dir, exist_ok=True)

        # Always write both configs from the combo values (overwrite if exists)
        with open(reward_cfg_file, "w") as f:
            yaml.dump(r, f, default_flow_style=False, sort_keys=False)
        with open(training_params_file, "w") as f:
            yaml.dump(t, f, default_flow_style=False, sort_keys=False)

        data = train_rl(
            experiment_name=name,
            speed=t["speed"],
            n_sims=t["n_sims"],
            in_game_episode_s=t["in_game_episode_s"],
            weights_file=weights_file,
            reward_config_file=reward_cfg_file,
            mutation_scale=t["mutation_scale"],
            probe_in_game_s=t["probe_s"],
            cold_start_restarts=t["cold_restarts"],
            cold_start_sims=t["cold_sims"],
            training_params=t,
            no_interrupt=args.no_interrupt,
        )

        save_experiment_results(data, results_dir=f"{experiment_dir}/results")

        best = max((s.reward for s in data.greedy_sims), default=float("-inf"))
        results_summary.append((name, best))
        print(f"\n  [{i}/{n}] {name}  best_reward={best:+.1f}\n")

    # Final summary table
    print(f"\n{'='*60}")
    print(f"  Grid search complete — {n} run(s)")
    print(f"  {'Experiment':<50}  {'Best Reward':>12}")
    print(f"  {'-'*64}")
    for exp_name, best in sorted(results_summary, key=lambda x: -x[1]):
        print(f"  {exp_name:<50}  {best:>+12.1f}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
