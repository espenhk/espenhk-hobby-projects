"""
Driving policies for TMNF.

BasePolicy           — abstract base class for all policies
PDPolicy             — hand-tuned PD controller (reference baseline, non-trainable)
WeightedLinearPolicy — trainable linear policy; weights stored in YAML
NeuralNetPolicy      — small MLP policy; trained via hill-climbing
QTablePolicy         — shared base for tabular Q-learning policies
EpsilonGreedyPolicy  — Q-table with epsilon-greedy exploration
MCTSPolicy           — Q-table with UCB1 (UCT-style) action selection
GeneticPolicy        — population of WeightedLinearPolicy, evolutionary training
"""

from __future__ import annotations

import math
import os
from abc import ABC, abstractmethod

import numpy as np
import yaml

from constants import N_ACTIONS
from obs_spec import OBS_NAMES, OBS_SCALES, obs_names_with_lidar, obs_scales_with_lidar
from steering import PDHeadingController


# ---------------------------------------------------------------------------
# BasePolicy
# ---------------------------------------------------------------------------

class BasePolicy(ABC):
    """Abstract base class for all driving policies."""

    @abstractmethod
    def __call__(self, obs: np.ndarray) -> int:
        """Select action given observation array."""

    @abstractmethod
    def to_cfg(self) -> dict:
        """Return a YAML-serializable dict representing this policy's state."""

    def update(self, obs: np.ndarray, action: int, reward: float,
               next_obs: np.ndarray, done: bool) -> None:
        """Per-step feedback from the environment. No-op for non-online policies."""

    def on_episode_end(self) -> None:
        """Called once at the end of each episode. No-op by default."""

    def save(self, path: str) -> None:
        """Write to_cfg() to YAML at path."""
        with open(path, "w") as f:
            yaml.dump(self.to_cfg(), f, default_flow_style=False, sort_keys=False)


# ---------------------------------------------------------------------------
# PDPolicy  (formerly SimplePolicy)
# ---------------------------------------------------------------------------

_pd_controller = PDHeadingController()


class PDPolicy(BasePolicy):
    """
    Hand-tuned PD+heading policy using PDHeadingController.

    Maps obs[1] (lateral offset) and obs[3] (yaw error) to three discrete
    steering actions (accel+left / accel+straight / accel+right).

    The D term approximates lateral velocity as Δlateral_offset per tick.

    This is a reference baseline and is not trainable.  update() and
    on_episode_end() are no-ops.
    """

    STEER_THRESHOLD = 2.0   # deadzone before committing to left/right

    def __init__(self) -> None:
        self._prev_lateral = 0.0

    def __call__(self, obs: np.ndarray) -> int:
        lateral = obs[1]
        yaw     = obs[3]

        lateral_vel        = lateral - self._prev_lateral
        self._prev_lateral = lateral

        steer_pct = _pd_controller.compute_steer(lateral, lateral_vel, yaw)

        if steer_pct < -self.STEER_THRESHOLD:
            return 6   # accel + left
        elif steer_pct > self.STEER_THRESHOLD:
            return 8   # accel + right
        else:
            return 7   # accel + straight

    def to_cfg(self) -> dict:
        return {"policy_type": "pd"}


# Keep the old name as an alias so existing call sites don't break.
SimplePolicy = PDPolicy


# ---------------------------------------------------------------------------
# WeightedLinearPolicy
# ---------------------------------------------------------------------------

class WeightedLinearPolicy(BasePolicy):
    """
    Linear policy: steer and throttle decisions from independent dot products.

        steer_score    = dot(steer_weights,    obs)
        throttle_score = dot(throttle_weights, obs)

    Steer score:
        < -steer_threshold    → left   (action +0)
        within threshold      → straight (action +1)
        > +steer_threshold    → right  (action +2)

    Throttle score:
        < -throttle_threshold → brake  (action 0–2)
        within threshold      → coast  (action 3–5)
        > +throttle_threshold → accel  (action 6–8)

    action = throttle_idx * 3 + steer_idx

    Weights are loaded from / saved to a YAML file for observability.
    Create via WeightedLinearPolicy(file) or WeightedLinearPolicy.from_cfg(dict).
    """

    # Observation names and scales are imported from obs_spec.py — one source of truth.
    OBS_NAMES  = OBS_NAMES
    OBS_SCALES = OBS_SCALES

    @classmethod
    def get_obs_names(cls, n_lidar_rays: int = 0) -> list[str]:
        return obs_names_with_lidar(n_lidar_rays)

    @classmethod
    def get_obs_scales(cls, n_lidar_rays: int = 0) -> np.ndarray:
        return obs_scales_with_lidar(n_lidar_rays)

    def __init__(self, weights_file: str, n_lidar_rays: int = 0) -> None:
        self._weights_file = weights_file
        self._n_lidar_rays = n_lidar_rays
        cfg = self._load_or_init()
        self._apply_cfg(cfg)
        print(f"[WeightedLinearPolicy] loaded weights from {weights_file}")

    @classmethod
    def from_cfg(cls, cfg: dict, n_lidar_rays: int = 0) -> WeightedLinearPolicy:
        """Create a policy from a weights dict (not backed by a file)."""
        obj = object.__new__(cls)
        obj._weights_file = None
        obj._n_lidar_rays = n_lidar_rays
        obj._apply_cfg(cfg)
        return obj

    # ------------------------------------------------------------------
    # Weights dict I/O
    # ------------------------------------------------------------------

    def to_cfg(self) -> dict:
        names = self.get_obs_names(self._n_lidar_rays)
        return {
            "steer_threshold":    float(self._steer_t),
            "throttle_threshold": float(self._throttle_t),
            "steer_weights":    {n: float(self._steer_w[i])    for i, n in enumerate(names)},
            "throttle_weights": {n: float(self._throttle_w[i]) for i, n in enumerate(names)},
        }

    def save(self, path: str) -> None:
        with open(path, "w") as f:
            yaml.dump(self.to_cfg(), f, default_flow_style=False, sort_keys=False)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def mutated(self, scale: float = 0.1) -> WeightedLinearPolicy:
        """Return a new policy with small Gaussian perturbation applied to all weights."""
        rng = np.random.default_rng()
        cfg = self.to_cfg()
        for group in ("steer_weights", "throttle_weights"):
            for k in cfg[group]:
                cfg[group][k] += float(rng.normal(0.0, scale))
        return WeightedLinearPolicy.from_cfg(cfg, n_lidar_rays=self._n_lidar_rays)

    # ------------------------------------------------------------------
    # Callable interface
    # ------------------------------------------------------------------

    def __call__(self, obs: np.ndarray) -> int:
        norm_obs       = obs / self.get_obs_scales(self._n_lidar_rays)
        steer_score    = float(np.dot(self._steer_w,    norm_obs))
        throttle_score = float(np.dot(self._throttle_w, norm_obs))

        if steer_score < -self._steer_t:
            steer_idx = 0
        elif steer_score > self._steer_t:
            steer_idx = 2
        else:
            steer_idx = 1

        if throttle_score < -self._throttle_t:
            throttle_idx = 0
        elif throttle_score > self._throttle_t:
            throttle_idx = 2
        else:
            throttle_idx = 1

        return throttle_idx * 3 + steer_idx

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_cfg(self, cfg: dict) -> None:
        names = self.get_obs_names(self._n_lidar_rays)
        self._steer_w    = np.array([cfg["steer_weights"][n]    for n in names], dtype=np.float32)
        self._throttle_w = np.array([cfg["throttle_weights"][n] for n in names], dtype=np.float32)
        self._steer_t    = float(cfg["steer_threshold"])
        self._throttle_t = float(cfg["throttle_threshold"])

    def _load_or_init(self) -> dict:
        names = self.get_obs_names(self._n_lidar_rays)
        if os.path.exists(self._weights_file):
            with open(self._weights_file) as f:
                cfg = yaml.safe_load(f)
            # Migrate: fill in any missing LIDAR keys with 0.0 (neutral starting point)
            migrated = False
            for group in ("steer_weights", "throttle_weights"):
                for n in names:
                    if n not in cfg[group]:
                        cfg[group][n] = 0.0
                        migrated = True
            if migrated:
                with open(self._weights_file, "w") as f:
                    yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)
                print(f"[WeightedLinearPolicy] migrated weights file with new LIDAR keys → {self._weights_file}")
            return cfg

        rng = np.random.default_rng()
        cfg = {
            "steer_threshold":    0.5,
            "throttle_threshold": 0.5,
            "steer_weights":    {n: float(rng.standard_normal()) for n in names},
            "throttle_weights": {n: float(rng.standard_normal()) for n in names},
        }
        with open(self._weights_file, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)
        print(f"[WeightedLinearPolicy] initialised random weights → {self._weights_file}")
        return cfg


# ---------------------------------------------------------------------------
# NeuralNetPolicy
# ---------------------------------------------------------------------------

class NeuralNetPolicy(BasePolicy):
    """
    Small MLP policy trained via hill-climbing (same loop as WeightedLinearPolicy).

    Architecture: obs → Linear → ReLU → ... → Linear(N_ACTIONS) → argmax
    Pure numpy, no external ML framework required.
    Weights serialized to YAML as nested lists.
    """

    def __init__(self, hidden_sizes: list[int] | None = None, n_lidar_rays: int = 0) -> None:
        from obs_spec import BASE_OBS_DIM
        self._hidden = list(hidden_sizes or [16, 16])
        self._n_lidar_rays = n_lidar_rays
        obs_dim = BASE_OBS_DIM + n_lidar_rays
        layer_dims = [obs_dim] + self._hidden + [N_ACTIONS]
        rng = np.random.default_rng()
        self._weights: list[np.ndarray] = []
        self._biases:  list[np.ndarray] = []
        for i in range(len(layer_dims) - 1):
            fan_in = layer_dims[i]
            w = rng.standard_normal((layer_dims[i + 1], fan_in)).astype(np.float32)
            w *= np.sqrt(2.0 / fan_in)   # He init
            b = np.zeros(layer_dims[i + 1], dtype=np.float32)
            self._weights.append(w)
            self._biases.append(b)

    @classmethod
    def from_cfg(cls, cfg: dict, n_lidar_rays: int = 0) -> NeuralNetPolicy:
        obj = cls.__new__(cls)
        obj._hidden = cfg["hidden_sizes"]
        obj._n_lidar_rays = n_lidar_rays
        obj._weights = [np.array(w, dtype=np.float32) for w in cfg["weights"]]
        obj._biases  = [np.array(b, dtype=np.float32) for b in cfg["biases"]]
        return obj

    def __call__(self, obs: np.ndarray) -> int:
        scales = obs_scales_with_lidar(self._n_lidar_rays)
        x = (obs / scales).astype(np.float32)
        for i, (w, b) in enumerate(zip(self._weights, self._biases)):
            x = w @ x + b
            if i < len(self._weights) - 1:
                x = np.maximum(0.0, x)   # ReLU on all but output layer
        return int(np.argmax(x))

    def mutated(self, scale: float = 0.1) -> NeuralNetPolicy:
        """Return a new policy with Gaussian noise added to all weights and biases."""
        rng = np.random.default_rng()
        obj = NeuralNetPolicy.__new__(NeuralNetPolicy)
        obj._hidden = self._hidden
        obj._n_lidar_rays = self._n_lidar_rays
        obj._weights = [w + rng.normal(0.0, scale, w.shape).astype(np.float32)
                        for w in self._weights]
        obj._biases  = [b + rng.normal(0.0, scale, b.shape).astype(np.float32)
                        for b in self._biases]
        return obj

    def to_cfg(self) -> dict:
        return {
            "policy_type":  "neural_net",
            "hidden_sizes": self._hidden,
            "n_lidar_rays": self._n_lidar_rays,
            "weights": [w.tolist() for w in self._weights],
            "biases":  [b.tolist() for b in self._biases],
        }


# ---------------------------------------------------------------------------
# QTablePolicy — shared base for tabular Q-learning policies
# ---------------------------------------------------------------------------

def _discretize_obs(obs: np.ndarray, scales: np.ndarray, n_bins: int) -> tuple[int, ...]:
    """
    Map a continuous observation vector to a discrete state key.

    Each feature is normalised by *scales*, clipped to [-3, 3], then
    mapped to one of *n_bins* integer buckets.  Returns a hashable tuple.
    """
    norm    = obs / scales
    clipped = np.clip(norm, -3.0, 3.0)
    bins    = ((clipped + 3.0) / 6.0 * (n_bins - 1)).astype(np.int32)
    return tuple(bins.tolist())


class QTablePolicy(BasePolicy):
    """
    Shared base for tabular Q-learning policies (EpsilonGreedy and MCTS).

    Manages the Q-table, visit counts, discretization, and Bellman updates.
    Subclasses override _select_action() to implement their exploration strategy.
    """

    def __init__(
        self,
        alpha: float = 0.1,
        gamma: float = 0.99,
        n_bins: int = 3,
        n_lidar_rays: int = 0,
    ) -> None:
        self._alpha        = alpha
        self._gamma        = gamma
        self._n_bins       = n_bins
        self._n_lidar_rays = n_lidar_rays
        self._scales       = obs_scales_with_lidar(n_lidar_rays)
        self._q_table: dict[tuple, np.ndarray] = {}
        self._n_sa:    dict[tuple, np.ndarray] = {}   # N(s, a) — visit counts
        self._n_s:     dict[tuple, int]        = {}   # N(s) = Σ N(s, a)
        self._last_obs    = None
        self._last_action = None

    def _q(self, s: tuple) -> np.ndarray:
        if s not in self._q_table:
            self._q_table[s] = np.zeros(N_ACTIONS, dtype=np.float32)
        return self._q_table[s]

    def _n(self, s: tuple) -> np.ndarray:
        if s not in self._n_sa:
            self._n_sa[s] = np.zeros(N_ACTIONS, dtype=np.float32)
        return self._n_sa[s]

    @abstractmethod
    def _select_action(self, s: tuple) -> int:
        """Choose an action for state key s. Implemented by subclasses."""

    def __call__(self, obs: np.ndarray) -> int:
        s = _discretize_obs(obs, self._scales, self._n_bins)
        self._last_obs = obs
        action = self._select_action(s)
        self._last_action = action
        return action

    def update(self, obs: np.ndarray, action: int, reward: float,
               next_obs: np.ndarray, done: bool) -> None:
        s  = _discretize_obs(obs,      self._scales, self._n_bins)
        s_ = _discretize_obs(next_obs, self._scales, self._n_bins)
        q_next = 0.0 if done else float(np.max(self._q(s_)))
        td = reward + self._gamma * q_next - self._q(s)[action]
        self._q(s)[action] += self._alpha * td
        self._n(s)[action] += 1.0
        self._n_s[s] = self._n_s.get(s, 0) + 1

    def on_episode_end(self) -> None:
        self._last_obs    = None
        self._last_action = None

    @property
    def n_states_visited(self) -> int:
        return len(self._q_table)


# ---------------------------------------------------------------------------
# EpsilonGreedyPolicy
# ---------------------------------------------------------------------------

class EpsilonGreedyPolicy(QTablePolicy):
    """
    Tabular Q-learning with epsilon-greedy exploration.

    State space is the observation vector discretized into n_bins buckets per
    feature (default 3).  Epsilon decays each episode.

    Note: the Q-table is NOT persisted to policy_weights.yaml (it can be very
    large).  to_cfg() records only hyperparameters; the table lives in memory
    for the duration of a training run.
    """

    def __init__(
        self,
        n_bins: int = 3,
        epsilon: float = 1.0,
        epsilon_decay: float = 0.995,
        epsilon_min: float = 0.05,
        alpha: float = 0.1,
        gamma: float = 0.99,
        n_lidar_rays: int = 0,
    ) -> None:
        super().__init__(alpha=alpha, gamma=gamma, n_bins=n_bins, n_lidar_rays=n_lidar_rays)
        self._epsilon       = epsilon
        self._epsilon_decay = epsilon_decay
        self._epsilon_min   = epsilon_min

    @classmethod
    def from_cfg(cls, cfg: dict, n_lidar_rays: int = 0) -> EpsilonGreedyPolicy:
        return cls(
            n_bins        = cfg.get("n_bins",        3),
            epsilon       = cfg.get("epsilon",       1.0),
            epsilon_decay = cfg.get("epsilon_decay", 0.995),
            epsilon_min   = cfg.get("epsilon_min",   0.05),
            alpha         = cfg.get("alpha",         0.1),
            gamma         = cfg.get("gamma",         0.99),
            n_lidar_rays  = n_lidar_rays,
        )

    def _select_action(self, s: tuple) -> int:
        if np.random.random() < self._epsilon:
            return int(np.random.randint(N_ACTIONS))
        return int(np.argmax(self._q(s)))

    def on_episode_end(self) -> None:
        super().on_episode_end()
        self._epsilon = max(self._epsilon_min,
                            self._epsilon * self._epsilon_decay)

    def to_cfg(self) -> dict:
        return {
            "policy_type":      "epsilon_greedy",
            "n_bins":           self._n_bins,
            "epsilon":          float(self._epsilon),
            "epsilon_decay":    float(self._epsilon_decay),
            "epsilon_min":      float(self._epsilon_min),
            "alpha":            float(self._alpha),
            "gamma":            float(self._gamma),
            "n_states_visited": self.n_states_visited,
        }


# ---------------------------------------------------------------------------
# MCTSPolicy  (UCT-style online learner)
# ---------------------------------------------------------------------------

class MCTSPolicy(QTablePolicy):
    """
    UCT-inspired online Q-learner.

    Action selection uses the UCB1 formula:
        score(s, a) = Q(s, a) + c * sqrt(ln(N(s) + 1) / (N(s, a) + 1e-8))

    where N(s, a) is the visit count for (state, action) and N(s) = Σ_a N(s, a).

    NOTE: True Monte Carlo Tree Search requires cloning the environment state,
    which is not possible with TMInterface.  This is a UCT-style approximation
    that builds value/count tables incrementally over real episodes.
    """

    def __init__(
        self,
        c: float = 1.41,
        alpha: float = 0.1,
        gamma: float = 0.99,
        n_bins: int = 3,
        n_lidar_rays: int = 0,
    ) -> None:
        super().__init__(alpha=alpha, gamma=gamma, n_bins=n_bins, n_lidar_rays=n_lidar_rays)
        self._c = c

    @classmethod
    def from_cfg(cls, cfg: dict, n_lidar_rays: int = 0) -> MCTSPolicy:
        return cls(
            c            = cfg.get("c",     1.41),
            alpha        = cfg.get("alpha", 0.1),
            gamma        = cfg.get("gamma", 0.99),
            n_bins       = cfg.get("n_bins", 3),
            n_lidar_rays = n_lidar_rays,
        )

    def _select_action(self, s: tuple) -> int:
        n_s = self._n_s.get(s, 0)
        if n_s == 0:
            return int(np.random.randint(N_ACTIONS))
        ucb = self._q(s) + self._c * np.sqrt(
            math.log(n_s + 1) / (self._n(s) + 1e-8)
        )
        return int(np.argmax(ucb))

    def to_cfg(self) -> dict:
        return {
            "policy_type":      "mcts",
            "c":                float(self._c),
            "alpha":            float(self._alpha),
            "gamma":            float(self._gamma),
            "n_bins":           self._n_bins,
            "n_states_visited": self.n_states_visited,
        }


# ---------------------------------------------------------------------------
# GeneticPolicy
# ---------------------------------------------------------------------------

class GeneticPolicy(BasePolicy):
    """
    Evolutionary policy: a population of WeightedLinearPolicy instances.

    Each training generation:
      1. Evaluate all population members (one episode each).
      2. Select the top `elite_k` individuals (elites survive unchanged).
      3. Fill the rest via uniform crossover between two random elites + mutation.
      4. Update the champion if any individual beats the previous best.

    Inference always uses the champion (best individual seen so far).
    `save()` writes the champion in WeightedLinearPolicy YAML format so
    existing analytics (weight heatmaps, etc.) work without changes.
    """

    def __init__(
        self,
        population_size: int = 10,
        elite_k: int = 3,
        mutation_scale: float = 0.1,
        n_lidar_rays: int = 0,
    ) -> None:
        self._pop_size      = population_size
        self._elite_k       = min(elite_k, population_size)
        self._mutation_scale = mutation_scale
        self._n_lidar_rays  = n_lidar_rays
        self._population: list[WeightedLinearPolicy] = []
        self._champion: WeightedLinearPolicy | None = None
        self._champion_reward: float = float("-inf")

    @classmethod
    def from_cfg(cls, cfg: dict, n_lidar_rays: int = 0) -> GeneticPolicy:
        obj = cls(
            population_size = cfg.get("population_size", 10),
            elite_k         = cfg.get("elite_k", 3),
            mutation_scale  = cfg.get("mutation_scale", 0.1),
            n_lidar_rays    = n_lidar_rays,
        )
        champion_w = cfg.get("champion_weights")
        if champion_w:
            obj._champion = WeightedLinearPolicy.from_cfg(champion_w, n_lidar_rays)
            obj._champion_reward = float(cfg.get("champion_reward", float("-inf")))
        return obj

    @property
    def population(self) -> list[WeightedLinearPolicy]:
        return self._population

    @property
    def champion_reward(self) -> float:
        return self._champion_reward

    def initialize_random(self) -> None:
        """Build a fresh random population."""
        rng = np.random.default_rng()
        names = obs_names_with_lidar(self._n_lidar_rays)
        pop = []
        for _ in range(self._pop_size):
            cfg = {
                "steer_threshold":    0.5,
                "throttle_threshold": 0.5,
                "steer_weights":    {n: float(rng.standard_normal()) for n in names},
                "throttle_weights": {n: float(rng.standard_normal()) for n in names},
            }
            pop.append(WeightedLinearPolicy.from_cfg(cfg, self._n_lidar_rays))
        self._population = pop
        if self._champion is None:
            self._champion = pop[0]

    def initialize_from_champion(self, champion: WeightedLinearPolicy) -> None:
        """Seed the population by mutating the given champion."""
        self._champion = champion
        self._population = [
            champion.mutated(self._mutation_scale)
            for _ in range(self._pop_size)
        ]

    def __call__(self, obs: np.ndarray) -> int:
        assert self._champion is not None, "GeneticPolicy: champion not set — call initialize_*() first"
        return self._champion(obs)

    def evaluate_and_evolve(self, rewards: list[float]) -> bool:
        """
        Update population based on episode rewards.

        Args:
            rewards: episode reward[i] for self._population[i].

        Returns:
            True if the champion was updated this generation.
        """
        assert len(rewards) == len(self._population)
        ranked  = sorted(zip(rewards, self._population), key=lambda x: -x[0])
        improved = False

        if ranked[0][0] > self._champion_reward:
            self._champion_reward = ranked[0][0]
            self._champion        = ranked[0][1]
            improved              = True

        elites  = [ind for _, ind in ranked[:self._elite_k]]
        new_pop = list(elites)
        rng_idx = np.random.default_rng()

        while len(new_pop) < self._pop_size:
            i1 = int(rng_idx.integers(self._elite_k))
            i2 = int(rng_idx.integers(self._elite_k))
            child_cfg = self._crossover(elites[i1].to_cfg(), elites[i2].to_cfg())
            child     = WeightedLinearPolicy.from_cfg(child_cfg, self._n_lidar_rays)
            new_pop.append(child.mutated(self._mutation_scale))

        self._population = new_pop
        return improved

    @staticmethod
    def _crossover(cfg1: dict, cfg2: dict) -> dict:
        """Uniform weight crossover: each weight is randomly drawn from parent 1 or 2."""
        result = {
            "steer_threshold":    cfg1["steer_threshold"],
            "throttle_threshold": cfg1["throttle_threshold"],
            "steer_weights":    {},
            "throttle_weights": {},
        }
        for group in ("steer_weights", "throttle_weights"):
            for k in cfg1[group]:
                result[group][k] = (cfg1[group][k] if np.random.random() < 0.5
                                    else cfg2[group][k])
        return result

    def to_cfg(self) -> dict:
        return {
            "policy_type":      "genetic",
            "population_size":  self._pop_size,
            "elite_k":          self._elite_k,
            "mutation_scale":   float(self._mutation_scale),
            "champion_reward":  float(self._champion_reward),
            "champion_weights": self._champion.to_cfg() if self._champion else {},
        }

    def save(self, path: str) -> None:
        """Save champion in WeightedLinearPolicy YAML format for analytics compatibility."""
        if self._champion is not None:
            self._champion.save(path)
