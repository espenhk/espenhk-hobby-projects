import time

from tminterface.interface import TMInterface

from clients import AdaptiveClient
from clients.rl_client import get_action_description
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

def _make_env(speed: float, in_game_episode_s: float):
    from rl.env import TMNFEnv
    from rl.reward import RewardConfig

    return TMNFEnv(
        centerline_file="tracks/a03_centerline.npy",
        speed=speed,
        reward_config=RewardConfig(crash_threshold_m=25.0),
        max_episode_time_s=in_game_episode_s / speed,
    )


# ---------------------------------------------------------------------------
# Single episode
# ---------------------------------------------------------------------------

def _run_episode(env, policy, obs) -> tuple[float, dict]:
    """Run one episode from *obs* until terminated/truncated; return (total_reward, info)."""
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

        if steps % 200 == 0:
            print(
                f"    action={get_action_description(action):15s}"
                f"  step={steps:4d}  progress={info['track_progress']:.3f}"
                f"  lateral={info['lateral_offset']:+.2f} m"
                f"  reward={reward:+.3f}  total={total_reward:+.1f}"
            )

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

    return total_reward, info


def _print_action_stats(throttle_counts: list, turning_steps: int, steps: int) -> None:
    b, c, a = throttle_counts
    print(
        f"    throttle — brake: {100*b/steps:4.1f}%  coast: {100*c/steps:4.1f}%  accel: {100*a/steps:4.1f}%"
        f"    steer — straight: {100*(steps-turning_steps)/steps:4.1f}%  turning: {100*turning_steps/steps:4.1f}%"
    )


# ---------------------------------------------------------------------------
# Watch mode: run indefinitely, resetting every in_game_episode_s seconds
# ---------------------------------------------------------------------------

def run_rl_policy(speed: float, policy, in_game_episode_s: float = 20.0):
    """
    Repeatedly drive the track with *policy*, resetting every
    *in_game_episode_s* in-game seconds.  Ctrl+C to stop.
    """
    env = _make_env(speed, in_game_episode_s)
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
# Training: hill-climb by random weight mutation
# ---------------------------------------------------------------------------

def train_rl(
    speed: float,
    n_sims: int = 10,
    in_game_episode_s: float = 20.0,
    weights_file: str = "policy_weights.yaml",
    mutation_scale: float = 0.1,
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
    """
    print("waiting for alt-tab...")
    time.sleep(2) # time to alt-tab into game
    print("wait done, making env.")

    env = _make_env(speed, in_game_episode_s)

    best_policy = WeightedLinearPolicy(weights_file)
    best_reward = float("-inf")
    history: list[dict] = []

    print(f"\n{'='*60}")
    print(f"  Training — {n_sims} simulations, speed={speed}x, "
          f"episode={in_game_episode_s}s in-game")
    print(f"  mutation_scale={mutation_scale}  weights → {weights_file}")
    print(f"{'='*60}\n")

    try:
        for sim in range(1, n_sims + 1):
            candidate = best_policy.mutated(scale=mutation_scale)

            print(f"--- Sim {sim}/{n_sims} --- (respawning)")
            obs, _ = env.reset()
            reward, _ = _run_episode(env, candidate, obs)

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
            history.append({"sim": sim, "reward": reward, "improved": improved})

    except KeyboardInterrupt:
        print("\nTraining interrupted.")
    finally:
        env.close()

    # Summary
    print(f"\n{'='*60}")
    print(f"  Training complete — best total reward: {best_reward:+.1f}")
    print(f"  {'Sim':>4}  {'Reward':>8}  Result")
    print(f"  {'-'*30}")
    for h in history:
        tag = "NEW BEST" if h["improved"] else "        "
        print(f"  {h['sim']:>4}  {h['reward']:>8.1f}  {tag}")
    print(f"{'='*60}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    SPEED             = 10.0 # looks like 10.0 is max
    IN_GAME_EPISODE_S = 30.0
    WEIGHTS_FILE      = "policy_weights.yaml"
    N_SIMS            = 100

    train_rl(
        speed=SPEED,
        n_sims=N_SIMS,
        in_game_episode_s=IN_GAME_EPISODE_S,
        weights_file=WEIGHTS_FILE,
        mutation_scale=0.02,
    )


if __name__ == "__main__":
    main()
