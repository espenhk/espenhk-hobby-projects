import argparse
import os
import shutil
import time
import yaml
import numpy as np
import datetime

from tminterface.interface import TMInterface

from clients import AdaptiveClient
from clients.rl_client import ACTIONS, N_ACTIONS, get_action_description
from policies import (
    BasePolicy,
    WeightedLinearPolicy,
    NeuralNetPolicy,
    EpsilonGreedyPolicy,
    MCTSPolicy,
    GeneticPolicy,
)
from rl.env import TMNFEnv
from rl.reward import RewardConfig
from analytics import (
    ProbeResult,
    RunTrace,
    ColdStartSimResult,
    ColdStartRestartResult,
    GreedySimResult,
    ExperimentData,
    save_experiment_results
)

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

def _make_env(speed: float, in_game_episode_s: float, reward_config_file: str, n_lidar_rays: int = 0):

    return TMNFEnv(
        centerline_file="tracks/a03_centerline.npy",
        speed=speed,
        reward_config=RewardConfig.from_yaml(reward_config_file),
        max_episode_time_s=in_game_episode_s / speed,
        n_lidar_rays=n_lidar_rays,
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
    def update(self, obs, action, reward, next_obs, done) -> None:
        pass


# ---------------------------------------------------------------------------
# Policy factory
# ---------------------------------------------------------------------------

def _make_policy(
    policy_type: str,
    weights_file: str,
    n_lidar_rays: int,
    policy_params: dict,
    re_initialize: bool,
) -> BasePolicy:
    """Construct the appropriate policy given type, file, and hyperparams."""

    if policy_type == "hill_climbing":
        if os.path.exists(weights_file) and not re_initialize:
            return WeightedLinearPolicy(weights_file, n_lidar_rays)
        # Random init (cold-start will handle this path normally)
        rng = __import__("numpy").random.default_rng()
        obs_names = WeightedLinearPolicy.get_obs_names(n_lidar_rays)
        cfg = {
            "steer_threshold":    0.5,
            "throttle_threshold": 0.5,
            "steer_weights":    {n: float(rng.standard_normal()) for n in obs_names},
            "throttle_weights": {n: float(rng.standard_normal()) for n in obs_names},
        }
        return WeightedLinearPolicy.from_cfg(cfg, n_lidar_rays)

    elif policy_type == "neural_net":
        if os.path.exists(weights_file) and not re_initialize:
            with open(weights_file) as f:
                cfg = yaml.safe_load(f)
            if cfg.get("policy_type") == "neural_net":
                print(f"[NeuralNetPolicy] loaded from {weights_file}")
                return NeuralNetPolicy.from_cfg(cfg, n_lidar_rays)
        hidden = policy_params.get("hidden_sizes", [16, 16])
        print(f"[NeuralNetPolicy] initialised random weights (hidden={hidden})")
        return NeuralNetPolicy(hidden_sizes=hidden, n_lidar_rays=n_lidar_rays)

    elif policy_type == "epsilon_greedy":
        # Q-table always starts fresh (no meaningful file resume)
        return EpsilonGreedyPolicy.from_cfg(policy_params, n_lidar_rays)

    elif policy_type == "mcts":
        return MCTSPolicy.from_cfg(policy_params, n_lidar_rays)

    elif policy_type == "genetic":
        pop_size = policy_params.get("population_size", 10)
        elite_k  = policy_params.get("elite_k", 3)
        policy   = GeneticPolicy(
            population_size = pop_size,
            elite_k         = elite_k,
            mutation_scale  = policy_params.get("mutation_scale",
                              policy_params.get("_mutation_scale_fallback", 0.1)),
            n_lidar_rays    = n_lidar_rays,
        )
        if os.path.exists(weights_file) and not re_initialize:
            champion = WeightedLinearPolicy(weights_file, n_lidar_rays)
            policy.initialize_from_champion(champion)
            print(f"[GeneticPolicy] seeded population from champion at {weights_file}")
        else:
            policy.initialize_random()
            print(f"[GeneticPolicy] random population of {pop_size}")
        return policy

    else:
        raise ValueError(f"Unknown policy_type: {policy_type!r}. "
                         f"Choose from: hill_climbing, neural_net, epsilon_greedy, mcts, genetic")


# ---------------------------------------------------------------------------
# Probe phase: run each of the 9 actions for probe_in_game_s seconds,
# return the best reward as a baseline floor for hill-climbing.
# ---------------------------------------------------------------------------

def _run_probes(env, probe_in_game_s: float, speed: float):
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

_TRACE_SAMPLE_EVERY = 2  # record position every N steps
_WARMUP_STEPS = 100       # 1 in-game second of forced straight acceleration at episode start
_WARMUP_ACTION = 7        # action 7: accelerate + straight

def _run_episode(env, policy, obs):
    """Run one episode from *obs* until terminated/truncated.

    Calls policy.update() after each post-warmup step so that online policies
    (EpsilonGreedyPolicy, MCTSPolicy) can update their Q-tables in real time.

    Returns:
        total_reward    — float
        info            — final step info dict from env
        throttle_counts — [brake_steps, coast_steps, accel_steps]
        total_steps     — int
        trace           — RunTrace
    """

    total_reward = 0.0
    steps = 0
    info = {}
    throttle_counts = [0, 0, 0]   # brake / coast / accel
    turning_steps   = 0            # any action with steer != straight (action % 3 != 1)
    pos_x: list[float] = []
    pos_z: list[float] = []
    throttle_state: list[int] = []
    prev_obs = obs

    while True:
        in_warmup = steps < _WARMUP_STEPS
        action = _WARMUP_ACTION if in_warmup else policy(obs)
        next_obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        steps += 1

        # Feed online policies the transition (skip warmup to avoid poisoning Q-table
        # with forced behaviour that doesn't reflect the policy's decisions)
        if not in_warmup:
            policy.update(prev_obs, action, reward, next_obs, terminated or truncated)

        prev_obs = next_obs
        obs      = next_obs

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
            laps = info.get("laps_completed", 0)
            lap_str = f"  laps={laps}" if laps > 0 else ""
            print(
                f"    Done ({reason}) — "
                f"steps={steps}  progress={info['track_progress']:.3f}{lap_str}"
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

def run_rl_policy(speed: float, policy, in_game_episode_s: float = 20.0, reward_config_file: str = "config/reward_config.yaml"):
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
    n_lidar_rays: int = 0,
) -> tuple:
    """
    Try up to n_restarts random policy initializations.
    Each restart runs sims_per_restart hill-climb sims.
    Stops early if a policy beats probe_best_reward.
    Returns (best_policy, best_reward, restart_results) across all restarts.
    """

    overall_best_policy = None
    overall_best_reward = float("-inf")
    restart_results = []

    print(f"\n{'='*60}")
    print(f"  Cold-start search — up to {n_restarts} restarts × {sims_per_restart} sims")
    print(f"  Target to beat: {probe_best_reward:+.1f}  (best probe reward)")
    print(f"{'='*60}")


    for restart in range(1, n_restarts + 1):
        print(f"\n  -- Restart {restart}/{n_restarts}: random init --")

        # Generate a fresh random policy in memory — do NOT touch weights_file here
        # so the best result from previous restarts is always preserved on disk.
        rng = np.random.default_rng()
        obs_names = WeightedLinearPolicy.get_obs_names(n_lidar_rays)
        random_cfg = {
            "steer_threshold":    0.5,
            "throttle_threshold": 0.5,
            "steer_weights":    {n: float(rng.standard_normal()) for n in obs_names},
            "throttle_weights": {n: float(rng.standard_normal()) for n in obs_names},
        }
        local_best_policy = WeightedLinearPolicy.from_cfg(random_cfg, n_lidar_rays=n_lidar_rays)
        local_best_reward = float("-inf")
        sim_results = []

        for sim in range(1, sims_per_restart + 1):
            candidate = local_best_policy.mutated(scale=mutation_scale)
            print(f"  Restart {restart} sim {sim}/{sims_per_restart} (respawning)", end="", flush=True)
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
# Greedy loops (one per training strategy)
# ---------------------------------------------------------------------------

def _greedy_loop_hill_climb(
    env,
    best_policy,
    best_reward: float,
    n_sims: int,
    mutation_scale: float,
    weights_file: str,
) -> tuple:
    """
    Hill-climbing greedy loop (hill_climbing and neural_net policy types).
    Mutate the current best policy, evaluate, keep if improved.
    Returns (best_policy, best_reward, greedy_sims).
    """

    greedy_sims = []
    try:
        for sim in range(1, n_sims + 1):
            candidate = best_policy.mutated(scale=mutation_scale)

            print(f"--- Sim {sim}/{n_sims} --- (respawning)")
            obs, _ = env.reset()
            reward, info, throttle_counts, total_steps, trace = _run_episode(env, candidate, obs)

            improved = reward > best_reward
            if improved:
                prev_best   = best_reward
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
                weights=candidate.to_cfg(),
                final_track_progress=info.get("track_progress", 0.0),
                laps_completed=info.get("laps_completed", 0),
            ))
    except KeyboardInterrupt:
        print("\nTraining interrupted.")

    return best_policy, best_reward, greedy_sims


def _greedy_loop_q_learning(
    env,
    policy,
    n_episodes: int,
    weights_file: str,
) -> tuple:
    """
    Q-learning greedy loop for epsilon_greedy and mcts policy types.
    The policy updates its Q-table in-place via policy.update() inside _run_episode().
    No mutation is performed; the policy itself is the state that improves over time.
    Returns (policy, best_reward, greedy_sims).
    """

    best_reward = float("-inf")
    greedy_sims = []
    try:
        for episode in range(1, n_episodes + 1):
            print(f"--- Episode {episode}/{n_episodes} --- (respawning)")
            obs, _ = env.reset()
            reward, info, throttle_counts, total_steps, trace = _run_episode(env, policy, obs)
            policy.on_episode_end()

            improved = reward > best_reward
            if improved:
                prev_best   = best_reward
                best_reward = reward
                policy.save(weights_file)
                verdict = f"NEW BEST  {reward:+.1f}  (was {prev_best:+.1f})"
            else:
                verdict = f"no improvement  episode={reward:+.1f}  best={best_reward:+.1f}"

            cfg = policy.to_cfg()
            print(f"  >> {verdict}  [states visited: {cfg.get('n_states_visited', '?')}]\n")
            greedy_sims.append(GreedySimResult(
                sim=episode, reward=reward, improved=improved,
                throttle_counts=list(throttle_counts), total_steps=total_steps,
                trace=trace,
                weights=cfg,
                final_track_progress=info.get("track_progress", 0.0),
                laps_completed=info.get("laps_completed", 0),
            ))
    except KeyboardInterrupt:
        print("\nTraining interrupted.")

    return policy, best_reward, greedy_sims


def _greedy_loop_genetic(
    env,
    policy: GeneticPolicy,
    n_generations: int,
    weights_file: str,
) -> tuple:
    """
    Genetic algorithm greedy loop.
    Each "sim" is one generation: evaluate all population members, then evolve.
    Total episodes = n_generations × population_size.
    Returns (policy, best_reward, greedy_sims).
    """

    pop_size    = len(policy._population)
    best_reward = policy._champion_reward
    greedy_sims = []

    print(f"  [Genetic] population_size={pop_size}, "
          f"total episodes = {n_generations} × {pop_size} = {n_generations * pop_size}")

    try:
        for gen in range(1, n_generations + 1):
            print(f"--- Generation {gen}/{n_generations} --- evaluating {pop_size} individuals")
            rewards = []
            for idx, individual in enumerate(policy._population):
                print(f"  Individual {idx + 1}/{pop_size} (respawning)", end="", flush=True)
                obs, _ = env.reset()
                reward, info, _, total_steps, trace = _run_episode(env, individual, obs)
                rewards.append(reward)

            improved = policy.evaluate_and_evolve(rewards)
            gen_best = max(rewards)
            if gen_best > best_reward:
                best_reward = gen_best

            if improved:
                policy.save(weights_file)
                verdict = f"NEW BEST champion  reward={policy._champion_reward:+.1f}"
            else:
                verdict = f"no improvement  gen_best={gen_best:+.1f}  champion={policy._champion_reward:+.1f}"

            print(f"  >> {verdict}\n")
            greedy_sims.append(GreedySimResult(
                sim=gen, reward=gen_best, improved=improved,
                throttle_counts=[0, 0, 0], total_steps=total_steps,
                trace=trace,
                weights=policy.to_cfg(),
                final_track_progress=info.get("track_progress", 0.0),
                laps_completed=info.get("laps_completed", 0),
            ))
    except KeyboardInterrupt:
        print("\nTraining interrupted.")

    return policy, best_reward, greedy_sims


# ---------------------------------------------------------------------------
# Training orchestrator
# ---------------------------------------------------------------------------

def train_rl(
    experiment_name: str,
    speed: float,
    n_sims: int = 10,
    in_game_episode_s: float = 20.0,
    weights_file: str = "config/policy_weights.yaml",
    reward_config_file: str = "config/reward_config.yaml",
    mutation_scale: float = 0.1,
    probe_in_game_s: float = 8.0,
    cold_start_restarts: int = 5,
    cold_start_sims: int = 10,
    training_params: dict | None = None,
    no_interrupt: bool = False,
    n_lidar_rays: int = 0,
    re_initialize: bool = False,
    policy_type: str = "hill_climbing",
    policy_params: dict | None = None,
):
    """
    Train a driving policy via the selected algorithm.

    policy_type options:
      hill_climbing  — random weight mutation, keep if improved (default)
      neural_net     — MLP policy, same hill-climbing loop
      epsilon_greedy — tabular Q-learning with epsilon-greedy exploration
      mcts           — UCT-style online Q-learner with UCB1 action selection
      genetic        — population of linear policies, evolutionary selection

    Returns an ExperimentData object with all collected metrics.
    """

    policy_params = policy_params or {}
    t_start = datetime.datetime.now()

    # Cold-start only applies to hill_climbing (needs a baseline reward floor)
    cold_start = (not os.path.exists(weights_file) or re_initialize)
    cold_start = cold_start and (policy_type == "hill_climbing")

    if cold_start:
        if not no_interrupt:
            input("\n  [PROBE PHASE]  Press Enter to connect and start probe runs...")

    print("Connecting to game...")
    env = _make_env(speed, in_game_episode_s, reward_config_file, n_lidar_rays=n_lidar_rays)

    probe_results  = []
    cold_start_data = []
    probe_best     = None
    t_after_probe  = t_after_cold = None

    if cold_start:
        probe_best, probe_results = _run_probes(env, probe_in_game_s=probe_in_game_s, speed=speed)
        t_after_probe = datetime.datetime.now()

        if not no_interrupt:
            input("\n  [COLD-START SEARCH]  Press Enter to start random-restart search...")
        time.sleep(1)
        best_policy, best_reward, cold_start_data = _cold_start_search(
            env, probe_best, weights_file, mutation_scale,
            n_restarts=cold_start_restarts, sims_per_restart=cold_start_sims,
            n_lidar_rays=n_lidar_rays,
        )
        t_after_cold = datetime.datetime.now()
    else:
        # Build the policy via the factory (handles all types)
        best_policy = _make_policy(
            policy_type    = policy_type,
            weights_file   = weights_file,
            n_lidar_rays   = n_lidar_rays,
            policy_params  = {**policy_params,
                              "_mutation_scale_fallback": mutation_scale},
            re_initialize  = re_initialize,
        )
        best_reward = float("-inf")

    print(f"\n{'='*60}")
    print(f"  Training — {n_sims} sims/generations, speed={speed}x, "
          f"episode={in_game_episode_s}s in-game")
    print(f"  policy_type={policy_type}  mutation_scale={mutation_scale}")
    print(f"  weights → {weights_file}")
    print(f"{'='*60}")
    if not no_interrupt:
        input("\n  [GREEDY PHASE]  Press Enter to start optimisation...\n")
    time.sleep(1)
    t_greedy_start = datetime.datetime.now()

    # Dispatch to the appropriate greedy loop
    if policy_type in ("hill_climbing", "neural_net"):
        best_policy, best_reward, greedy_sims = _greedy_loop_hill_climb(
            env, best_policy, best_reward, n_sims, mutation_scale, weights_file
        )
    elif policy_type in ("epsilon_greedy", "mcts"):
        best_policy, best_reward, greedy_sims = _greedy_loop_q_learning(
            env, best_policy, n_sims, weights_file
        )
    elif policy_type == "genetic":
        best_policy, best_reward, greedy_sims = _greedy_loop_genetic(
            env, best_policy, n_sims, weights_file  # type: ignore[arg-type]
        )
    else:
        raise ValueError(f"Unknown policy_type: {policy_type!r}")

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
    parser.add_argument("--re-initialize", action="store_true",
                        help="Ignore any existing weights file and restart from scratch, "
                             "including probe and cold-start phases.")
    args = parser.parse_args()

    experiment_dir  = f"experiments/{args.experiment}"
    weights_file    = f"{experiment_dir}/policy_weights.yaml"
    reward_cfg_file = f"{experiment_dir}/reward_config.yaml"

    training_params_file = f"{experiment_dir}/training_params.yaml"

    os.makedirs(experiment_dir, exist_ok=True)
    if not os.path.exists(reward_cfg_file):
        shutil.copy("config/reward_config.yaml", reward_cfg_file)
        print(f"  Copied master reward config → {reward_cfg_file}")
    if not os.path.exists(training_params_file):
        shutil.copy("config/training_params.yaml", training_params_file)
        print(f"  Copied master training params → {training_params_file}")

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
        n_lidar_rays=p.get("n_lidar_rays", 0),
        re_initialize=args.re_initialize,
        policy_type=p.get("policy_type", "hill_climbing"),
        policy_params=p.get("policy_params") or {},
    )

    save_experiment_results(data, results_dir=f"{experiment_dir}/results")


if __name__ == "__main__":
    main()
