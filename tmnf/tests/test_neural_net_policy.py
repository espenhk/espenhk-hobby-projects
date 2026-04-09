"""Tests for NeuralNetPolicy in tmnf/policies.py."""
import unittest

import numpy as np

from policies import NeuralNetPolicy


class TestNeuralNetPolicy(unittest.TestCase):

    def test_action_in_range(self):
        p = NeuralNetPolicy(hidden_sizes=[8])
        obs = np.random.randn(15).astype(np.float32)
        self.assertIn(p(obs), range(9))

    def test_deterministic(self):
        p = NeuralNetPolicy(hidden_sizes=[8])
        obs = np.random.randn(15).astype(np.float32)
        self.assertEqual(p(obs), p(obs))

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

    def test_weight_matrix_shapes(self):
        p = NeuralNetPolicy(hidden_sizes=[16, 8])
        cfg = p.to_cfg()
        weights = cfg["weights"]
        # Layer dims: [15, 16, 8, 9]
        self.assertEqual(np.array(weights[0]).shape, (16, 15))
        self.assertEqual(np.array(weights[1]).shape, (8, 16))
        self.assertEqual(np.array(weights[2]).shape, (9, 8))


if __name__ == "__main__":
    unittest.main(verbosity=2)
