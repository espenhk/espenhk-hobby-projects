"""
Unit tests for the TMNF project — no game/TMInterface required.

Run from repo root:
    python -m pytest tmnf/tests/ -v
"""
import math
import os
import sys
import tempfile
import unittest

import numpy as np

# Allow bare imports like `from utils import Vec3` (tmnf uses project-root-relative imports)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils import Vec3, Quat, StateData
from policies import (
    SimplePolicy,
    WeightedLinearPolicy,
    NeuralNetPolicy,
    EpsilonGreedyPolicy,
    MCTSPolicy,
    GeneticPolicy,
    _discretize_obs,
)
from track import Centerline
from rl.reward import RewardCalculator, RewardConfig


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_game_state(
    position=(0.0, 0.0, 0.0),
    linear_speed=(10.0, 0.0, 0.0),
    quat=(1.0, 0.0, 0.0, 0.0),
    angular_speed=(0.0, 0.0, 0.0),
    gear=3,
    turning_rate=0.0,
    wheel_contacts=(True, True, True, True),
    wheel_sliding=(False, False, False, False),
):
    """Build a plain Python object that satisfies StateData's attribute access."""
    class _CS:
        pass
    class _Dyna:
        current_state = _CS()
    class _Engine:
        pass
    class _Mobil:
        engine = _Engine()
    class _State:
        pass

    s = _State()
    s.dyna = _Dyna()
    s.dyna.current_state.position = position
    # StateData reads dyna = state.dyna.current_state, then dyna.linear_speed etc.
    s.dyna.current_state.linear_speed = linear_speed
    s.dyna.current_state.quat = quat
    s.dyna.current_state.angular_speed = angular_speed
    s.scene_mobil = _Mobil()
    s.scene_mobil.engine.gear = gear
    s.scene_mobil.turning_rate = turning_rate

    # Each wheel needs its own real_time_state instance (class-level attribute would be shared)
    def _make_wheel(contact, sliding):
        rts = type("_RTS", (), {"has_ground_contact": contact, "is_sliding": sliding})()
        return type("_Wheel", (), {"real_time_state": rts})()

    s.simulation_wheels = [_make_wheel(wheel_contacts[i], wheel_sliding[i]) for i in range(4)]
    return s


def _make_state_data(position=(0.0, 0.0, 0.0), speed=(10.0, 0.0, 0.0),
                     track_progress=0.5, lateral_offset=0.0, vertical_offset=0.0,
                     wheel_contacts=(True, True, True, True)):
    """Build a StateData-like object with track projection pre-filled."""
    gs = _make_game_state(position=position, linear_speed=speed,
                          wheel_contacts=wheel_contacts)
    sd = StateData(gs)
    sd.track_progress = track_progress
    sd.lateral_offset = lateral_offset
    sd.vertical_offset = vertical_offset
    return sd


def _zero_obs(n=15):
    return np.zeros(n, dtype=np.float32)


def _make_wlp(steer_weights=None, throttle_weights=None,
              steer_threshold=0.5, throttle_threshold=0.5):
    """Construct a WeightedLinearPolicy from explicit weight vectors."""
    names = WeightedLinearPolicy.OBS_NAMES
    n = len(names)
    sw = steer_weights if steer_weights is not None else np.zeros(n, dtype=np.float32)
    tw = throttle_weights if throttle_weights is not None else np.zeros(n, dtype=np.float32)
    cfg = {
        "steer_threshold": steer_threshold,
        "throttle_threshold": throttle_threshold,
        "steer_weights": {names[i]: float(sw[i]) for i in range(n)},
        "throttle_weights": {names[i]: float(tw[i]) for i in range(n)},
    }
    return WeightedLinearPolicy.from_cfg(cfg)


# ---------------------------------------------------------------------------
# TestVec3
# ---------------------------------------------------------------------------

class TestVec3(unittest.TestCase):

    def test_magnitude_zero(self):
        self.assertEqual(Vec3(0, 0, 0).magnitude(), 0.0)

    def test_magnitude_unit(self):
        self.assertAlmostEqual(Vec3(1, 0, 0).magnitude(), 1.0)

    def test_magnitude_3d(self):
        self.assertAlmostEqual(Vec3(3, 4, 0).magnitude(), 5.0)

    def test_compute_speed_alias(self):
        v = Vec3(1, 2, 3)
        self.assertEqual(v.compute_speed(), v.magnitude())


# ---------------------------------------------------------------------------
# TestQuat
# ---------------------------------------------------------------------------

class TestQuat(unittest.TestCase):

    def test_identity_yaw_zero(self):
        self.assertAlmostEqual(Quat(1, 0, 0, 0).yaw(), 0.0)

    def test_identity_pitch_zero(self):
        self.assertAlmostEqual(Quat(1, 0, 0, 0).pitch(), 0.0)

    def test_identity_roll_zero(self):
        self.assertAlmostEqual(Quat(1, 0, 0, 0).roll(), 0.0)

    def test_90deg_yaw(self):
        # 90° rotation around Y axis: w=cos(45°), y=sin(45°)
        half = math.sqrt(2) / 2
        q = Quat(half, 0, half, 0)
        self.assertAlmostEqual(q.yaw(), math.pi / 2, places=5)


# ---------------------------------------------------------------------------
# TestStateData
# ---------------------------------------------------------------------------

class TestStateData(unittest.TestCase):

    def test_extracts_velocity(self):
        gs = _make_game_state(linear_speed=(5.0, 2.0, 3.0))
        sd = StateData(gs)
        self.assertAlmostEqual(sd.velocity.x, 5.0)
        self.assertAlmostEqual(sd.velocity.y, 2.0)
        self.assertAlmostEqual(sd.velocity.z, 3.0)

    def test_extracts_wheels(self):
        gs = _make_game_state(
            wheel_contacts=(True, False, True, False),
            wheel_sliding=(False, True, False, True),
        )
        sd = StateData(gs)
        self.assertTrue(sd.wheels[0].contact)
        self.assertFalse(sd.wheels[1].contact)
        self.assertTrue(sd.wheels[1].sliding)

    def test_with_centerline_sets_progress(self):
        # Build a tiny straight centerline so project() returns something
        points = np.array([[0, 0, i * 10.0] for i in range(11)], dtype=np.float32)
        with tempfile.NamedTemporaryFile(suffix=".npy", delete=False) as f:
            np.save(f.name, points)
            cl = Centerline(f.name)
        try:
            gs = _make_game_state(position=(0.0, 0.0, 50.0))
            sd = StateData(gs, centerline=cl)
            self.assertIsNotNone(sd.track_progress)
            self.assertAlmostEqual(sd.track_progress, 0.5, places=2)
        finally:
            os.unlink(f.name)


# ---------------------------------------------------------------------------
# TestCenterline  — straight line along Z: 0 → 100 m, 11 points
# ---------------------------------------------------------------------------

class TestCenterline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        points = np.array([[0.0, 0.0, i * 10.0] for i in range(11)], dtype=np.float32)
        cls._tmp = tempfile.NamedTemporaryFile(suffix=".npy", delete=False)
        np.save(cls._tmp.name, points)
        cls.cl = Centerline(cls._tmp.name)

    @classmethod
    def tearDownClass(cls):
        os.unlink(cls._tmp.name)

    def test_start_progress(self):
        progress, _, _ = self.cl.project(Vec3(0, 0, 0))
        self.assertAlmostEqual(progress, 0.0, places=3)

    def test_end_progress(self):
        progress, _, _ = self.cl.project(Vec3(0, 0, 100))
        self.assertAlmostEqual(progress, 1.0, places=3)

    def test_midpoint_progress(self):
        progress, _, _ = self.cl.project(Vec3(0, 0, 50))
        self.assertAlmostEqual(progress, 0.5, places=3)

    def test_lateral_offset_nonzero(self):
        # Point offset 2 m from centreline — lateral magnitude should be ~2
        _, lateral, _ = self.cl.project(Vec3(2.0, 0, 50))
        self.assertAlmostEqual(abs(lateral), 2.0, places=3)


# ---------------------------------------------------------------------------
# TestSimplePolicy
# ---------------------------------------------------------------------------

class TestSimplePolicy(unittest.TestCase):

    def _obs(self, lateral=0.0, yaw=0.0):
        obs = _zero_obs()
        obs[1] = lateral
        obs[3] = yaw
        return obs

    def test_on_center_goes_straight(self):
        self.assertEqual(SimplePolicy()(self._obs()), 7)

    def test_right_of_center_steers_left(self):
        # lateral=+3 → steer_pct = -16*3 = -48 < -2 → action 6
        self.assertEqual(SimplePolicy()(self._obs(lateral=3.0)), 6)

    def test_left_of_center_steers_right(self):
        # lateral=-3 → steer_pct = +48 > +2 → action 8
        self.assertEqual(SimplePolicy()(self._obs(lateral=-3.0)), 8)

    def test_yaw_error_only_right(self):
        # yaw=+1 → heading term = +5*1 = +5 > 2 → steer right → action 8
        self.assertEqual(SimplePolicy()(self._obs(yaw=1.0)), 8)

    def test_yaw_error_only_left(self):
        # yaw=-1 → heading term = -5 < -2 → steer left → action 6
        self.assertEqual(SimplePolicy()(self._obs(yaw=-1.0)), 6)

    def test_threshold_boundary(self):
        # lateral=0.01 → P = -0.16, D = -0.08 (prev_lateral starts at 0) → total -0.24, within ±2 → straight
        self.assertEqual(SimplePolicy()(self._obs(lateral=0.01)), 7)

    def test_derivative_term(self):
        # First call: lateral=4 → steer left (action 6)
        # Second call: lateral=2 → D term = -8*(2-4)=+16 partly cancels P term=-32
        # steer_pct = -32 + 16 = -16 → still < -2 → still action 6
        # But the D term is definitely active (reduces the raw P value from -64 to -16)
        p = SimplePolicy()
        a1 = p(self._obs(lateral=4.0))
        a2 = p(self._obs(lateral=2.0))
        self.assertEqual(a1, 6)  # strongly left
        self.assertEqual(a2, 6)  # still left but derivative reduced it


# ---------------------------------------------------------------------------
# TestWeightedLinearPolicy
# ---------------------------------------------------------------------------

class TestWeightedLinearPolicy(unittest.TestCase):

    def test_action_in_range(self):
        p = _make_wlp()
        for _ in range(10):
            obs = np.random.randn(15).astype(np.float32)
            self.assertIn(p(obs), range(9))

    def test_deterministic(self):
        p = _make_wlp()
        obs = np.ones(15, dtype=np.float32)
        self.assertEqual(p(obs), p(obs))

    def test_accel_weights_dominate(self):
        # Large positive weight on speed_ms (index 0) → throttle score >> threshold → accel
        tw = np.zeros(15, dtype=np.float32)
        tw[0] = 1000.0  # speed feature, always positive in obs
        obs = np.array([50.0] + [0.0] * 14, dtype=np.float32)
        p = _make_wlp(throttle_weights=tw, throttle_threshold=0.5)
        self.assertIn(p(obs), {6, 7, 8})

    def test_brake_weights_dominate(self):
        tw = np.zeros(15, dtype=np.float32)
        tw[0] = -1000.0
        obs = np.array([50.0] + [0.0] * 14, dtype=np.float32)
        p = _make_wlp(throttle_weights=tw, throttle_threshold=0.5)
        self.assertIn(p(obs), {0, 1, 2})

    def test_coast_within_threshold(self):
        # All zero weights → throttle score = 0 → within threshold → coast
        obs = np.ones(15, dtype=np.float32)
        p = _make_wlp()  # all zero weights, threshold=0.5
        self.assertIn(p(obs), {3, 4, 5})

    def test_steer_left_action(self):
        # Large negative weight on lateral_offset (index 1) → steer score << -threshold → left
        # Large positive throttle weight → accel
        sw = np.zeros(15, dtype=np.float32)
        sw[1] = -1000.0  # lateral offset feature
        tw = np.zeros(15, dtype=np.float32)
        tw[0] = 1000.0
        obs = np.array([50.0, 1.0] + [0.0] * 13, dtype=np.float32)
        p = _make_wlp(steer_weights=sw, throttle_weights=tw)
        self.assertEqual(p(obs), 6)  # accel(2)*3 + left(0) = 6

    def test_steer_right_action(self):
        sw = np.zeros(15, dtype=np.float32)
        sw[1] = 1000.0
        tw = np.zeros(15, dtype=np.float32)
        tw[0] = 1000.0
        obs = np.array([50.0, 1.0] + [0.0] * 13, dtype=np.float32)
        p = _make_wlp(steer_weights=sw, throttle_weights=tw)
        self.assertEqual(p(obs), 8)  # accel(2)*3 + right(2) = 8

    def test_from_cfg_roundtrip(self):
        p = _make_wlp()
        cfg = p.to_cfg()
        p2 = WeightedLinearPolicy.from_cfg(cfg)
        obs = np.random.randn(15).astype(np.float32)
        self.assertEqual(p(obs), p2(obs))

    def test_mutated_weights_differ(self):
        p = _make_wlp()
        # Give it some non-zero weights so mutation has something to change
        sw = np.ones(15, dtype=np.float32)
        p2 = _make_wlp(steer_weights=sw)
        mutated = p2.mutated(scale=1.0)
        orig_sw = list(p2.to_cfg()["steer_weights"].values())
        mut_sw = list(mutated.to_cfg()["steer_weights"].values())
        self.assertFalse(np.allclose(orig_sw, mut_sw))


# ---------------------------------------------------------------------------
# TestNeuralNetPolicy
# ---------------------------------------------------------------------------

class TestNeuralNetPolicy(unittest.TestCase):

    def test_action_in_range(self):
        p = NeuralNetPolicy(hidden_sizes=[8])
        obs = np.random.randn(15).astype(np.float32)
        self.assertIn(p(obs), range(9))

    def test_from_cfg_roundtrip(self):
        p = NeuralNetPolicy(hidden_sizes=[8, 8])
        obs = np.random.randn(15).astype(np.float32)
        p2 = NeuralNetPolicy.from_cfg(p.to_cfg())
        self.assertEqual(p(obs), p2(obs))

    def test_hidden_sizes_preserved_in_cfg(self):
        p = NeuralNetPolicy(hidden_sizes=[32, 16])
        self.assertEqual(p.to_cfg()["hidden_sizes"], [32, 16])

    def test_output_always_9_actions(self):
        p = NeuralNetPolicy(hidden_sizes=[4])
        for _ in range(20):
            obs = np.random.randn(15).astype(np.float32) * 100
            self.assertIn(p(obs), range(9))

    def test_mutated_has_different_weights(self):
        p = NeuralNetPolicy(hidden_sizes=[8])
        m = p.mutated(scale=1.0)
        orig = p.to_cfg()["weights"][0]
        mutd = m.to_cfg()["weights"][0]
        self.assertFalse(np.allclose(orig, mutd))


# ---------------------------------------------------------------------------
# TestDiscretizeObs
# ---------------------------------------------------------------------------

class TestDiscretizeObs(unittest.TestCase):

    def _scales(self):
        return WeightedLinearPolicy.OBS_SCALES  # (15,)

    def test_zero_obs_maps_to_middle_bin(self):
        obs = _zero_obs()
        bins = _discretize_obs(obs, self._scales(), n_bins=3)
        self.assertTrue(all(b == 1 for b in bins))

    def test_clipped_high_obs(self):
        obs = np.full(15, 1e9, dtype=np.float32)
        bins = _discretize_obs(obs, self._scales(), n_bins=3)
        self.assertTrue(all(b == 2 for b in bins))

    def test_clipped_low_obs(self):
        obs = np.full(15, -1e9, dtype=np.float32)
        bins = _discretize_obs(obs, self._scales(), n_bins=3)
        self.assertTrue(all(b == 0 for b in bins))

    def test_symmetry(self):
        scales = self._scales()
        pos_obs = scales.copy()    # norm = 1.0 → clipped to 1, bin = 2/6*2 = 0.666 → 0
        neg_obs = -scales.copy()   # norm = -1.0 → clipped to -1
        pos_bins = _discretize_obs(pos_obs, scales, n_bins=7)
        neg_bins = _discretize_obs(neg_obs, scales, n_bins=7)
        mid = 3
        for p, n in zip(pos_bins, neg_bins):
            self.assertEqual(p + n, 2 * mid)


# ---------------------------------------------------------------------------
# TestEpsilonGreedyPolicy
# ---------------------------------------------------------------------------

class TestEpsilonGreedyPolicy(unittest.TestCase):

    def _obs(self):
        return _zero_obs()

    def test_action_in_range(self):
        p = EpsilonGreedyPolicy(epsilon=1.0)
        self.assertIn(p(self._obs()), range(9))

    def test_greedy_with_epsilon_zero(self):
        p = EpsilonGreedyPolicy(epsilon=0.0)
        obs = self._obs()
        from policies import _discretize_obs
        scales = WeightedLinearPolicy.OBS_SCALES
        key = _discretize_obs(obs, scales, n_bins=3)
        # Pre-set Q(s, action=1) = 10
        p._q_table[key] = np.zeros(9, dtype=np.float32)
        p._q_table[key][1] = 10.0
        for _ in range(10):
            self.assertEqual(p(obs), 1)

    def test_update_increases_q_for_positive_reward(self):
        p = EpsilonGreedyPolicy(epsilon=0.0, alpha=0.5, gamma=0.0)
        obs = self._obs()
        next_obs = self._obs()
        p.update(obs, action=3, reward=10.0, next_obs=next_obs, done=True)
        scales = WeightedLinearPolicy.OBS_SCALES
        key = _discretize_obs(obs, scales, n_bins=3)
        self.assertGreater(p._q_table[key][3], 0.0)

    def test_update_decreases_q_for_negative_reward(self):
        p = EpsilonGreedyPolicy(epsilon=0.0, alpha=0.5, gamma=0.0)
        obs = self._obs()
        p.update(obs, action=5, reward=-10.0, next_obs=self._obs(), done=True)
        scales = WeightedLinearPolicy.OBS_SCALES
        key = _discretize_obs(obs, scales, n_bins=3)
        self.assertLess(p._q_table[key][5], 0.0)

    def test_bellman_backup(self):
        alpha, gamma = 0.5, 0.9
        p = EpsilonGreedyPolicy(epsilon=0.0, alpha=alpha, gamma=gamma)
        obs = self._obs()
        next_obs = np.ones(15, dtype=np.float32)  # different state
        scales = WeightedLinearPolicy.OBS_SCALES
        s  = _discretize_obs(obs, scales, n_bins=3)
        s_ = _discretize_obs(next_obs, scales, n_bins=3)
        # Seed Q(s', 2) = 5 so max_Q(s') = 5
        p._q_table[s_] = np.zeros(9, dtype=np.float32)
        p._q_table[s_][2] = 5.0
        p.update(obs, action=0, reward=2.0, next_obs=next_obs, done=False)
        # Expected: Q(s,0) += alpha * (2 + 0.9*5 - 0) = 0.5 * 6.5 = 3.25
        self.assertAlmostEqual(float(p._q_table[s][0]), 3.25, places=4)

    def test_epsilon_decays_on_episode_end(self):
        p = EpsilonGreedyPolicy(epsilon=1.0, epsilon_decay=0.5, epsilon_min=0.0)
        p.on_episode_end()
        self.assertAlmostEqual(p._epsilon, 0.5)


# ---------------------------------------------------------------------------
# TestMCTSPolicy
# ---------------------------------------------------------------------------

class TestMCTSPolicy(unittest.TestCase):

    def _obs(self):
        return _zero_obs()

    def test_action_in_range(self):
        p = MCTSPolicy()
        self.assertIn(p(self._obs()), range(9))

    def test_unseen_state_uses_random(self):
        # With an empty table every call is random — we expect non-constant output
        # over enough calls. (Flaky risk is ~9^{-20} ≈ 0.)
        p = MCTSPolicy()
        actions = {p(np.random.randn(15).astype(np.float32)) for _ in range(30)}
        self.assertGreater(len(actions), 1)

    def test_update_increments_visit_count(self):
        p = MCTSPolicy()
        obs = self._obs()
        next_obs = self._obs()
        p.update(obs, action=4, reward=1.0, next_obs=next_obs, done=False)
        scales = WeightedLinearPolicy.OBS_SCALES
        key = _discretize_obs(obs, scales, n_bins=3)
        self.assertEqual(p._n_sa[key][4], 1.0)
        self.assertEqual(p._n_s[key], 1)

    def test_update_changes_q_value(self):
        p = MCTSPolicy(alpha=1.0, gamma=0.0)
        obs = self._obs()
        p.update(obs, action=2, reward=7.0, next_obs=self._obs(), done=True)
        scales = WeightedLinearPolicy.OBS_SCALES
        key = _discretize_obs(obs, scales, n_bins=3)
        self.assertAlmostEqual(float(p._q_table[key][2]), 7.0, places=4)

    def test_high_q_action_preferred_after_visits(self):
        # After many visits, UCB exploration bonus shrinks; action with highest Q wins
        p = MCTSPolicy(c=0.0)  # c=0 → pure exploitation
        obs = self._obs()
        next_obs = self._obs()
        scales = WeightedLinearPolicy.OBS_SCALES
        key = _discretize_obs(obs, scales, n_bins=3)
        # Seed via updates: give action 3 a very high reward
        for _ in range(5):
            p.update(obs, action=3, reward=100.0, next_obs=next_obs, done=True)
            p.update(obs, action=0, reward=-100.0, next_obs=next_obs, done=True)
        # With c=0 and high Q(s,3), it should pick 3
        self.assertEqual(p(obs), 3)


# ---------------------------------------------------------------------------
# TestGeneticPolicy
# ---------------------------------------------------------------------------

class TestGeneticPolicy(unittest.TestCase):

    def _make_policy(self, pop=6, elite=2):
        return GeneticPolicy(population_size=pop, elite_k=elite, mutation_scale=0.1)

    def test_initialize_random_population_size(self):
        gp = self._make_policy(pop=6)
        gp.initialize_random()
        self.assertEqual(len(gp._population), 6)

    def test_champion_set_after_initialize_random(self):
        gp = self._make_policy()
        gp.initialize_random()
        self.assertIsNotNone(gp._champion)

    def test_initialize_from_champion_seeds_population(self):
        gp = self._make_policy(pop=5)
        champion = _make_wlp()
        gp.initialize_from_champion(champion)
        self.assertEqual(len(gp._population), 5)
        self.assertIs(gp._champion, champion)

    def test_evaluate_and_evolve_updates_champion(self):
        gp = self._make_policy(pop=4, elite=2)
        gp.initialize_random()
        rewards = [10.0, 20.0, 5.0, 1.0]
        gp.evaluate_and_evolve(rewards)
        self.assertAlmostEqual(gp._champion_reward, 20.0)

    def test_evaluate_and_evolve_returns_true_when_improved(self):
        gp = self._make_policy(pop=4)
        gp.initialize_random()
        improved = gp.evaluate_and_evolve([10.0, 20.0, 5.0, 1.0])
        self.assertTrue(improved)

    def test_evaluate_and_evolve_returns_false_when_no_improvement(self):
        gp = self._make_policy(pop=4)
        gp.initialize_random()
        gp.evaluate_and_evolve([100.0, 90.0, 80.0, 70.0])  # sets champion_reward=100
        improved = gp.evaluate_and_evolve([50.0, 40.0, 30.0, 20.0])
        self.assertFalse(improved)

    def test_crossover_draws_from_both_parents(self):
        names = WeightedLinearPolicy.OBS_NAMES
        # Parent 1: all steer weights = +1
        cfg1 = {
            "steer_threshold": 0.5, "throttle_threshold": 0.5,
            "steer_weights": {n: 1.0 for n in names},
            "throttle_weights": {n: 0.0 for n in names},
        }
        # Parent 2: all steer weights = -1
        cfg2 = {
            "steer_threshold": 0.5, "throttle_threshold": 0.5,
            "steer_weights": {n: -1.0 for n in names},
            "throttle_weights": {n: 0.0 for n in names},
        }
        child_cfg = GeneticPolicy._crossover(cfg1, cfg2)
        sw = list(child_cfg["steer_weights"].values())
        # With 15 features drawn from {+1, -1}, expect both values to appear
        self.assertIn(1.0, sw)
        self.assertIn(-1.0, sw)


# ---------------------------------------------------------------------------
# TestRewardCalculator
# ---------------------------------------------------------------------------

class TestRewardCalculator(unittest.TestCase):

    def setUp(self):
        self.cfg = RewardConfig()
        self.calc = RewardCalculator(self.cfg)

    def _r(self, prev, curr, finished=False, elapsed_s=0.0, accelerating=False):
        return self.calc.compute(prev, curr, finished, elapsed_s, accelerating)

    def test_progress_reward(self):
        prev = _make_state_data(track_progress=0.0)
        curr = _make_state_data(track_progress=0.1, speed=(0.0, 0.0, 0.0))
        reward = self._r(prev, curr)
        # progress contribution: 0.1 * 10.0 = 1.0
        self.assertAlmostEqual(reward, 1.0 + self.cfg.step_penalty, places=4)

    def test_no_progress_no_progress_reward(self):
        state = _make_state_data(track_progress=0.5, speed=(0.0, 0.0, 0.0),
                                 lateral_offset=0.0)
        reward = self._r(state, state)
        # No progress delta, no lateral penalty, just step penalty + speed bonus (0)
        self.assertAlmostEqual(reward, self.cfg.step_penalty, places=4)

    def test_centerline_penalty_quadratic(self):
        prev = _make_state_data(track_progress=0.5, lateral_offset=0.0)
        curr = _make_state_data(track_progress=0.5, lateral_offset=2.0, speed=(0.0, 0.0, 0.0))
        reward = self._r(prev, curr)
        # centerline contribution: -0.5 * 2^2 = -2.0
        expected = -2.0 + self.cfg.step_penalty
        self.assertAlmostEqual(reward, expected, places=4)

    def test_centerline_on_center_no_penalty(self):
        prev = _make_state_data(track_progress=0.5, lateral_offset=0.0)
        curr = _make_state_data(track_progress=0.5, lateral_offset=0.0, speed=(0.0, 0.0, 0.0))
        reward = self._r(prev, curr)
        self.assertAlmostEqual(reward, self.cfg.step_penalty, places=4)

    def test_finish_bonus(self):
        prev = _make_state_data(track_progress=0.9)
        curr = _make_state_data(track_progress=1.0, speed=(0.0, 0.0, 0.0))
        reward = self._r(prev, curr, finished=True, elapsed_s=self.cfg.par_time_s)
        self.assertGreater(reward, self.cfg.finish_bonus * 0.9)

    def test_finish_time_penalty_over_par(self):
        prev = _make_state_data(track_progress=1.0)
        curr = _make_state_data(track_progress=1.0, speed=(0.0, 0.0, 0.0))
        reward_on_par  = self._r(prev, curr, finished=True, elapsed_s=60.0)
        reward_over_par = self._r(prev, curr, finished=True, elapsed_s=70.0)
        # 10 s over par → extra -0.1*10 = -1.0
        self.assertAlmostEqual(reward_on_par - reward_over_par, 1.0, places=4)

    def test_accel_bonus(self):
        state = _make_state_data(track_progress=0.5, speed=(0.0, 0.0, 0.0))
        r_accel = self._r(state, state, accelerating=True)
        r_coast  = self._r(state, state, accelerating=False)
        self.assertAlmostEqual(r_accel - r_coast, self.cfg.accel_bonus, places=4)

    def test_step_penalty_always_applied(self):
        state = _make_state_data(track_progress=0.5, speed=(0.0, 0.0, 0.0))
        reward = self._r(state, state)
        self.assertLessEqual(reward, 0.0)  # step penalty dominates when nothing else happens


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
