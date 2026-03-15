import random
import time

from tminterface.interface import TMInterface

from clients import AdaptiveClient
from clients.rl_client import N_ACTIONS, get_action_description


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


def run_rl_random(speed):
    """
    Demonstrate the RLClient with random actions.

    Shows the step/reset loop that a trained RL agent would use:
      1. reset() — respawn + brake to stop, get initial state
      2. step()  — pick action, receive (obs, reward, terminated, truncated)
      3. Repeat until the episode ends, then reset again.

    Uses random action selection so no trained model is needed.
    """
    from rl.env import TMNFEnv
    from rl.reward import RewardConfig

    N_EPISODES = 3

    env = TMNFEnv(
        centerline_file="tracks/a03_centerline.npy",
        speed=speed,
        reward_config=RewardConfig(),   # default weights
        max_episode_time_s=30.0,        # short episodes for the demo
    )

    for episode in range(N_EPISODES):
        env.reset()
        total_reward = 0.0
        steps = 0

        print(f"\n--- Episode {episode + 1} ---")

        while True:
            action = random.randrange(N_ACTIONS)
            action_str = get_action_description(action)
            _, reward, terminated, truncated, info = env.step(action)
            total_reward += reward
            steps += 1

            if steps % 50 == 0:
                print(
                    f"  action={action_str:15s}"
                    f"  step={steps:4d}  progress={info['track_progress']:.3f}"
                    f"  lateral={info['lateral_offset']:+.2f} m"
                    f"  reward={reward:+.3f}  total={total_reward:+.1f}"
                )

            if terminated or truncated:
                reason = "finished" if info["finished"] else ("truncated" if truncated else "crashed")
                print(
                    f"  Episode done ({reason}) — "
                    f"steps={steps}  progress={info['track_progress']:.3f}"
                    f"  total_reward={total_reward:.1f}"
                )
                break

    env.close()


def main():
    # Switch between the two modes by commenting/uncommenting:
    SPEED = 5.0

    #run_adaptive(speed=SPEED)
    run_rl_random(speed=SPEED)


if __name__ == "__main__":
    main()
