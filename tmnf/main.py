import argparse
import os
import shutil
import time

from tminterface.interface import TMInterface

from clients import AdaptiveClient
from clients.rl_client import ACTIONS, N_ACTIONS, get_action_description
from policies import WeightedLinearPolicy


def run_adaptive(speed):
    """Follow the centreline using the hand-tuned PD controller."""
    client = AdaptiveClient("tracks/a03_centerline.npy")
    iface = TMInterface()
    iface.execute_command(f"set speed {speed}")

    print("Waiting for TMInterface connection...")
    iface.register(client)
    try:
        while iface.running:
            time.sleep(0)
    except KeyboardInterrupt:
        pass
    iface.close()


# ---------------------------------------------------------------------------
# Env factory (shared setup)
# ---------------------------------------------------------------------------

def _make_env(speed: float, in_game_episode_s: float, reward_config_file: str):
    from rl.env import TMNFEnv
    from rl.reward import RewardConfig

    return TMNFEnv(
        centerline_file="tracks/a03_centerline.npy",
        speed=speed,
        reward_config=RewardConfig.from_yaml(reward_config_file),
        max_episode_time_s=in_game_episode_s / speed,
    )


# ---------------------------------------------------------------------------
# Constant-action policy (used by probe phase)
# ---------------------------------------------------------------------------

class _ConstantPolicy:
    """Always returns the same action — used during cold-start probing."""
    def __init__(self, action: int):
        self._action = action
    def __call__(self, obs) -> int:
        return self._action


# ---------------------------------------------------------------------------
# Probe phase: run each of the 9 actions for probe_in_game_s seconds,
# return the best reward as a baseline floor for hill-climbing.
# ---------------------------------------------------------------------------

def _run_probes(env, probe_in_game_s: float, speed: float):
    from analytics import ProbeResult
    saved_limit = env._max_episode_time_s
    env._max_episode_time_s = probe_in_game_s / speed

    print(f"\n  No weights file found — running {N_ACTIONS} probe episodes "
          f"({probe_in_game_s}s each) to establish a baseline.\n")

    results = {}  # action_idx -> reward
    probe_results = []
    for i, action in enumerate(ACTIONS):
        print(f"  Probe {i + 1}/{N_ACTIONS}: {ACTIONS[i][3]}")
        if "coast" in action[3]:  # skip coast probes
            continue
        obs, _ = env.reset()
        reward, _, throttle_counts, total_steps, trace = _run_episode(env, _ConstantPolicy(i), obs)
        results[i] = reward
        probe_results.append(ProbeResult(action_idx=i, action_name=ACTIONS[i][3], reward=reward, trace=trace))

    env._max_episode_time_s = saved_limit

    best_idx = max(results, key=lambda i: results[i])
    print(f"\n  Probe results:")
    for i, r in results.items():
        marker = " <-- best" if i == best_idx else ""
        print(f"    action {i} ({ACTIONS[i][3]:15s})  reward={r:+.1f}{marker}")
    print(f"\n  Using probe best ({results[best_idx]:+.1f}) as initial reward floor.\n")

    time.sleep(1)

    return results[best_idx], probe_results


# ---------------------------------------------------------------------------
# Single episode
# ---------------------------------------------------------------------------

_TRACE_SAMPLE_EVERY = 10  # record position every N steps

def _run_episode(env, policy, obs):
    """Run one episode from *obs* until terminated/truncated.

    Returns:
        total_reward    — float
        info            — final step info dict from env
        throttle_counts — [brake_steps, coast_steps, accel_steps]
        total_steps     — int
    """
    from analytics import RunTrace

    total_reward = 0.0
    steps = 0
    info = {}
    throttle_counts = [0, 0, 0]   # brake / coast / accel
    turning_steps   = 0            # any action with steer != straight (action % 3 != 1)
    pos_x: list[float] = []
    pos_z: list[float] = []
    throttle_state: list[int] = []

    while True:
        action = policy(obs)
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        steps += 1

        t = action // 3   # 0=brake, 1=coast, 2=accel
        throttle_counts[t] += 1
        throttle_state.append(t)
        if action % 3 != 1:
            turning_steps += 1

        if steps % _TRACE_SAMPLE_EVERY == 0:
            pos_x.append(info["pos_x"])
            pos_z.append(info["pos_z"])

        if terminated or truncated:
            reason = (
                "finished"  if info["finished"]  else
                "truncated" if truncated          else
                "crashed"
            )
            print(
                f"    Done ({reason}) — "
                f"steps={steps}  progress={info['track_progress']:.3f}"
                f"  total_reward={total_reward:.1f}"
            )
            #_print_action_stats(throttle_counts, turning_steps, steps)
            break

    trace = RunTrace(pos_x=pos_x, pos_z=pos_z,
                     throttle_state=throttle_state, total_reward=total_reward)
    return total_reward, info, throttle_counts, steps, trace


def _print_action_stats(throttle_counts: list, turning_steps: int, steps: int) -> None:
    b, c, a = throttle_counts
    print(
        f"    throttle — brake: {100*b/steps:4.1f}%  coast: {100*c/steps:4.1f}%  accel: {100*a/steps:4.1f}%"
        f"    steer — straight: {100*(steps-turning_steps)/steps:4.1f}%  turning: {100*turning_steps/steps:4.1f}%"
    )


# ---------------------------------------------------------------------------
# Watch mode: run indefinitely, resetting every in_game_episode_s seconds
# ---------------------------------------------------------------------------

def run_rl_policy(speed: float, policy, in_game_episode_s: float = 20.0, reward_config_file: str = "rl/reward_config.yaml"):
    """
    Repeatedly drive the track with *policy*, resetting every
    *in_game_episode_s* in-game seconds.  Ctrl+C to stop.
    """
    env = _make_env(speed, in_game_episode_s, reward_config_file)
    time.sleep(1)

    run = 0
    try:
        while True:
            run += 1
            print(f"\n--- Run {run} --- (respawning)")
            obs, _ = env.reset()
            _run_episode(env, policy, obs)
    except KeyboardInterrupt:
        pass
    finally:
        env.close()


# ---------------------------------------------------------------------------
# Cold-start search: random restarts until a policy beats the probe floor
# ---------------------------------------------------------------------------

def _cold_start_search(
    env,
    probe_best_reward: float,
    weights_file: str,
    mutation_scale: float,
    n_restarts: int = 5,
    sims_per_restart: int = 10,
) -> tuple:
    """
    Try up to n_restarts random policy initializations.
    Each restart runs sims_per_restart hill-climb sims.
    Stops early if a policy beats probe_best_reward.
    Returns (best_policy, best_reward, restart_results) across all restarts.
    """
    from analytics import ColdStartSimResult, ColdStartRestartResult

    overall_best_policy = None
    overall_best_reward = float("-inf")
    restart_results = []

    print(f"\n{'='*60}")
    print(f"  Cold-start search — up to {n_restarts} restarts × {sims_per_restart} sims")
    print(f"  Target to beat: {probe_best_reward:+.1f}  (best probe reward)")
    print(f"{'='*60}")

    import numpy as np

    for restart in range(1, n_restarts + 1):
        print(f"\n  -- Restart {restart}/{n_restarts}: random init --")

        # Generate a fresh random policy in memory — do NOT touch weights_file here
        # so the best result from previous restarts is always preserved on disk.
        rng = np.random.default_rng()
        random_cfg = {
            "steer_threshold":    0.5,
            "throttle_threshold": 0.5,
            "steer_weights":    {n: float(rng.standard_normal()) for n in WeightedLinearPolicy.OBS_NAMES},
            "throttle_weights": {n: float(rng.standard_normal()) for n in WeightedLinearPolicy.OBS_NAMES},
        }
        local_best_policy = WeightedLinearPolicy.from_cfg(random_cfg)
        local_best_reward = float("-inf")
        sim_results = []

        for sim in range(1, sims_per_restart + 1):
            candidate = local_best_policy.mutated(scale=mutation_scale)
            print(f"  Restart {restart} sim {sim}/{sims_per_restart} (respawning)")
            obs, _ = env.reset()
            reward, _, throttle_counts, total_steps, trace = _run_episode(env, candidate, obs)

            sim_results.append(ColdStartSimResult(
                sim=sim, reward=reward,
                throttle_counts=list(throttle_counts), total_steps=total_steps,
                trace=trace,
            ))

            if reward > local_best_reward:
                local_best_reward = reward
                local_best_policy = candidate

            if reward > overall_best_reward:
                overall_best_reward = reward
                overall_best_policy = candidate

        beat = local_best_reward > probe_best_reward
        print(f"\n  Restart {restart} best: {local_best_reward:+.1f}  "
              f"({'beats' if beat else 'below'} probe floor {probe_best_reward:+.1f})")

        restart_results.append(ColdStartRestartResult(
            restart=restart, sims=sim_results,
            best_reward=local_best_reward, beat_probe_floor=beat,
        ))

        # Save after every restart so the file always holds the best seen so far.
        # An interruption between restarts will never lose completed work.
        if overall_best_policy is not None:
            overall_best_policy.save(weights_file)

        if beat:
            print("  Beat probe floor — ending cold-start early.")
            break

    if overall_best_policy is None:
        # Only reachable if n_restarts == 0; create a random fallback.
        overall_best_policy = WeightedLinearPolicy(weights_file)
        overall_best_policy.save(weights_file)
    print(f"\n  Cold-start complete — best reward: {overall_best_reward:+.1f}  "
          f"Weights saved to {weights_file}")
    return overall_best_policy, overall_best_reward, restart_results


# ---------------------------------------------------------------------------
# Training: hill-climb by random weight mutation
# ---------------------------------------------------------------------------

def train_rl(
    experiment_name: str,
    speed: float,
    n_sims: int = 10,
    in_game_episode_s: float = 20.0,
    weights_file: str = "policy_weights.yaml",
    reward_config_file: str = "rl/reward_config.yaml",
    mutation_scale: float = 0.1,
    probe_in_game_s: float = 8.0,
    cold_start_restarts: int = 5,
    cold_start_sims: int = 10,
    training_params: dict | None = None,
    no_interrupt: bool = False,
):
    """
    Hill-climb the WeightedLinearPolicy weights via random mutation.

    Each simulation:
      1. Mutate the current best weights by a small random perturbation.
      2. Run the candidate policy for one episode.
      3. If the candidate beats the best total reward, it becomes the new best
         and its weights are saved to *weights_file*.

    After *n_sims* simulations a summary is printed showing which policy
    (candidate vs best) won each round.
    Returns an ExperimentData object with all collected metrics.
    """
    import datetime
    from analytics import ExperimentData, GreedySimResult

    t_start = datetime.datetime.now()
    cold_start = not os.path.exists(weights_file)

    if cold_start:
        if not no_interrupt:
            input("\n  [PROBE PHASE]  Press Enter to connect and start probe runs...")

    print("Connecting to game...")
    env = _make_env(speed, in_game_episode_s, reward_config_file)

    probe_results = []
    cold_start_data = []
    probe_best = None
    t_after_probe = t_after_cold = None

    if cold_start:
        probe_best, probe_results = _run_probes(env, probe_in_game_s=probe_in_game_s, speed=speed)
        t_after_probe = datetime.datetime.now()

        if not no_interrupt:
            input("\n  [COLD-START SEARCH]  Press Enter to start random-restart search...")
        time.sleep(1)
        best_policy, best_reward, cold_start_data = _cold_start_search(
            env, probe_best, weights_file, mutation_scale,
            n_restarts=cold_start_restarts, sims_per_restart=cold_start_sims,
        )
        t_after_cold = datetime.datetime.now()
    else:
        best_policy = WeightedLinearPolicy(weights_file)
        best_reward = float("-inf")

    greedy_sims: list[GreedySimResult] = []

    print(f"\n{'='*60}")
    print(f"  Training — {n_sims} simulations, speed={speed}x, "
          f"episode={in_game_episode_s}s in-game")
    print(f"  mutation_scale={mutation_scale}  weights → {weights_file}")
    print(f"{'='*60}")
    if not no_interrupt:
        input("\n  [GREEDY PHASE]  Press Enter to start greedy optimisation...\n")
    time.sleep(1)
    t_greedy_start = datetime.datetime.now()

    try:
        for sim in range(1, n_sims + 1):
            candidate = best_policy.mutated(scale=mutation_scale)

            print(f"--- Sim {sim}/{n_sims} --- (respawning)")
            obs, _ = env.reset()
            reward, _, throttle_counts, total_steps, trace = _run_episode(env, candidate, obs)

            improved = reward > best_reward
            if improved:
                prev_best = best_reward
                best_reward = reward
                best_policy = candidate
                best_policy.save(weights_file)
                verdict = f"NEW BEST  {reward:+.1f}  (was {prev_best:+.1f})"
            else:
                verdict = f"no improvement  candidate={reward:+.1f}  best={best_reward:+.1f}"

            print(f"  >> {verdict}\n")
            greedy_sims.append(GreedySimResult(
                sim=sim, reward=reward, improved=improved,
                throttle_counts=list(throttle_counts), total_steps=total_steps,
                trace=trace,
            ))

    except KeyboardInterrupt:
        print("\nTraining interrupted.")
    finally:
        env.close()

    # Summary
    print(f"\n{'='*60}")
    print(f"  Training complete — best total reward: {best_reward:+.1f}")
    print(f"  {'Sim':>4}  {'Reward':>8}  Result")
    print(f"  {'-'*30}")
    for s in greedy_sims:
        tag = "NEW BEST" if s.improved else "        "
        print(f"  {s.sim:>4}  {s.reward:>8.1f}  {tag}")
    print(f"{'='*60}\n")

    t_end = datetime.datetime.now()
    fmt = "%Y-%m-%d %H:%M:%S"
    timings = {
        "start":        t_start.strftime(fmt),
        "end":          t_end.strftime(fmt),
        "total_s":      (t_end - t_start).total_seconds(),
        "probe_s":      (t_after_probe - t_start).total_seconds()         if t_after_probe else None,
        "cold_start_s": (t_after_cold  - t_after_probe).total_seconds()   if t_after_cold and t_after_probe else None,
        "greedy_s":     (t_end         - t_greedy_start).total_seconds(),
    }

    return ExperimentData(
        experiment_name=experiment_name,
        probe_results=probe_results,
        cold_start_restarts=cold_start_data,
        greedy_sims=greedy_sims,
        probe_floor=probe_best,
        weights_file=weights_file,
        reward_config_file=reward_config_file,
        training_params=training_params or {},
        timings=timings,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="TMNF RL training")
    parser.add_argument("experiment", help="Experiment name — files stored in experiments/<name>/")
    parser.add_argument("--no-interrupt", action="store_true",
                        help="Skip all 'Press Enter' prompts and run all phases automatically")
    args = parser.parse_args()

    experiment_dir  = f"experiments/{args.experiment}"
    weights_file    = f"{experiment_dir}/policy_weights.yaml"
    reward_cfg_file = f"{experiment_dir}/reward_config.yaml"

    training_params_file = f"{experiment_dir}/training_params.yaml"

    os.makedirs(experiment_dir, exist_ok=True)
    if not os.path.exists(reward_cfg_file):
        shutil.copy("rl/reward_config.yaml", reward_cfg_file)
        print(f"  Copied master reward config → {reward_cfg_file}")
    if not os.path.exists(training_params_file):
        shutil.copy("training_params.yaml", training_params_file)
        print(f"  Copied master training params → {training_params_file}")

    import yaml
    with open(training_params_file) as f:
        p = yaml.safe_load(f)

    data = train_rl(
        experiment_name=args.experiment,
        speed=p["speed"],
        n_sims=p["n_sims"],
        in_game_episode_s=p["in_game_episode_s"],
        weights_file=weights_file,
        reward_config_file=reward_cfg_file,
        mutation_scale=p["mutation_scale"],
        probe_in_game_s=p["probe_s"],
        cold_start_restarts=p["cold_restarts"],
        cold_start_sims=p["cold_sims"],
        training_params=p,
        no_interrupt=args.no_interrupt,
    )

    from analytics import save_experiment_results
    save_experiment_results(data, results_dir=f"{experiment_dir}/results")


if __name__ == "__main__":
    main()
