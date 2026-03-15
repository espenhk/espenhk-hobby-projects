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
        reward, _, throttle_counts, total_steps = _run_episode(env, _ConstantPolicy(i), obs)
        results[i] = reward
        probe_results.append(ProbeResult(action_idx=i, action_name=ACTIONS[i][3], reward=reward))

    env._max_episode_time_s = saved_limit

    best_idx = max(results, key=lambda i: results[i])
    print(f"\n  Probe results:")
    for i, r in results.items():
        marker = " <-- best" if i == best_idx else ""
        print(f"    action {i} ({ACTIONS[i][3]:15s})  reward={r:+.1f}{marker}")
    print(f"\n  Using probe best ({results[best_idx]:+.1f}) as initial reward floor.\n")

    time.sleep(3)

    return results[best_idx], probe_results


# ---------------------------------------------------------------------------
# Single episode
# ---------------------------------------------------------------------------

def _run_episode(env, policy, obs) -> tuple[float, dict, list, int]:
    """Run one episode from *obs* until terminated/truncated.

    Returns:
        total_reward    — float
        info            — final step info dict from env
        throttle_counts — [brake_steps, coast_steps, accel_steps]
        total_steps     — int
    """
    total_reward = 0.0
    steps = 0
    info = {}
    throttle_counts = [0, 0, 0]   # brake / coast / accel
    turning_steps   = 0            # any action with steer != straight (action % 3 != 1)

    while True:
        action = policy(obs)
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        steps += 1

        throttle_counts[action // 3] += 1
        if action % 3 != 1:
            turning_steps += 1

        #if steps % 200 == 0:
        #    print(
        #        f"    action={get_action_description(action):15s}"
        #        f"  step={steps:4d}  progress={info['track_progress']:.3f}"
        #        f"  lateral={info['lateral_offset']:+.2f} m"
        #        f"  reward={reward:+.3f}  total={total_reward:+.1f}"
        #    )

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
            _print_action_stats(throttle_counts, turning_steps, steps)
            break

    return total_reward, info, throttle_counts, steps


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
    time.sleep(5)

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
            reward, _, throttle_counts, total_steps = _run_episode(env, candidate, obs)

            sim_results.append(ColdStartSimResult(
                sim=sim, reward=reward,
                throttle_counts=list(throttle_counts), total_steps=total_steps,
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
    from analytics import ExperimentData, GreedySimResult

    cold_start = not os.path.exists(weights_file)

    if cold_start:
        input("\n  [PROBE PHASE]  Press Enter to connect and start probe runs...")
    time.sleep(2) # time to alt-tab into game

    print("Connecting to game...")
    env = _make_env(speed, in_game_episode_s, reward_config_file)

    probe_results = []
    cold_start_data = []
    probe_best = None

    if cold_start:
        probe_best, probe_results = _run_probes(env, probe_in_game_s=probe_in_game_s, speed=speed)

        input("\n  [COLD-START SEARCH]  Press Enter to start random-restart search...")
        time.sleep(3)
        best_policy, best_reward, cold_start_data = _cold_start_search(
            env, probe_best, weights_file, mutation_scale,
            n_restarts=cold_start_restarts, sims_per_restart=cold_start_sims,
        )
    else:
        best_policy = WeightedLinearPolicy(weights_file)
        best_reward = float("-inf")

    greedy_sims: list[GreedySimResult] = []

    print(f"\n{'='*60}")
    print(f"  Training — {n_sims} simulations, speed={speed}x, "
          f"episode={in_game_episode_s}s in-game")
    print(f"  mutation_scale={mutation_scale}  weights → {weights_file}")
    print(f"{'='*60}")
    input("\n  [GREEDY PHASE]  Press Enter to start greedy optimisation...\n")
    time.sleep(3)

    try:
        for sim in range(1, n_sims + 1):
            candidate = best_policy.mutated(scale=mutation_scale)

            print(f"--- Sim {sim}/{n_sims} --- (respawning)")
            obs, _ = env.reset()
            reward, _, throttle_counts, total_steps = _run_episode(env, candidate, obs)

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

    return ExperimentData(
        experiment_name=experiment_name,
        probe_results=probe_results,
        cold_start_restarts=cold_start_data,
        greedy_sims=greedy_sims,
        probe_floor=probe_best,
        weights_file=weights_file,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="TMNF RL training")
    parser.add_argument("experiment", help="Experiment name — files stored in experiments/<name>/")
    args = parser.parse_args()

    experiment_dir  = f"experiments/{args.experiment}"
    weights_file    = f"{experiment_dir}/policy_weights.yaml"
    reward_cfg_file = f"{experiment_dir}/reward_config.yaml"

    os.makedirs(experiment_dir, exist_ok=True)
    if not os.path.exists(reward_cfg_file):
        shutil.copy("rl/reward_config.yaml", reward_cfg_file)
        print(f"  Copied master reward config → {reward_cfg_file}")

    SPEED             = 10.0        # game speed multiplier (10.0 is the TMInterface max)
    IN_GAME_EPISODE_S = 3.0 + 10.0  # in-game seconds per episode (braking phase + driving)
    N_SIMS            = 200          # greedy hill-climb simulations after cold-start
    MUTATION_SCALE    = 0.1         # std-dev of Gaussian noise applied to normalised weights each mutation
    PROBE_S           = 8.0         # in-game seconds for each of the 9 single-action probe runs
    COLD_RESTARTS     = 10           # max random restarts during cold-start search
    COLD_SIMS         = 3           # hill-climb sims per cold-start restart

    data = train_rl(
        experiment_name=args.experiment,
        speed=SPEED,
        n_sims=N_SIMS,
        in_game_episode_s=IN_GAME_EPISODE_S,
        weights_file=weights_file,
        reward_config_file=reward_cfg_file,
        mutation_scale=MUTATION_SCALE,
        probe_in_game_s=PROBE_S,
        cold_start_restarts=COLD_RESTARTS,
        cold_start_sims=COLD_SIMS,
    )

    from analytics import save_experiment_results
    save_experiment_results(data, results_dir=f"{experiment_dir}/results")


if __name__ == "__main__":
    main()
