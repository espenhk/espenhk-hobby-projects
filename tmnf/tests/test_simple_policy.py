"""Tests for SimplePolicy in tmnf/policies.py."""
import unittest

import numpy as np

from policies import SimplePolicy


def _obs(lateral=0.0, yaw=0.0) -> np.ndarray:
    obs = np.zeros(15, dtype=np.float32)
    obs[1] = lateral
    obs[3] = yaw
    return obs


class TestSimplePolicy(unittest.TestCase):

    def test_on_center_goes_straight(self):
        self.assertEqual(SimplePolicy()(_obs()), 7)

    def test_right_of_center_steers_left(self):
        # lateral=+3 → steer_pct = -16*3 = -48 < -2 → action 6 (accel+left)
        self.assertEqual(SimplePolicy()(_obs(lateral=3.0)), 6)

    def test_left_of_center_steers_right(self):
        # lateral=-3 → steer_pct = +48 > +2 → action 8 (accel+right)
        self.assertEqual(SimplePolicy()(_obs(lateral=-3.0)), 8)

    def test_yaw_error_only_right(self):
        # yaw=+1 → heading term = +5*1 = +5 > 2 → steer right → action 8
        self.assertEqual(SimplePolicy()(_obs(yaw=1.0)), 8)

    def test_yaw_error_only_left(self):
        # yaw=-1 → heading term = -5 < -2 → steer left → action 6
        self.assertEqual(SimplePolicy()(_obs(yaw=-1.0)), 6)

    def test_threshold_boundary(self):
        # lateral=0.01 → P=-0.16, D=-0.08 (prev_lateral starts at 0) → total -0.24 within ±2 → straight
        self.assertEqual(SimplePolicy()(_obs(lateral=0.01)), 7)

    def test_derivative_term_active(self):
        # Call 1: lateral=4 → strongly steers left (action 6)
        # Call 2: lateral=2 → D term = -8*(2-4)=+16 partially cancels P=-32 → still left
        p = SimplePolicy()
        a1 = p(_obs(lateral=4.0))
        a2 = p(_obs(lateral=2.0))
        self.assertEqual(a1, 6)
        self.assertEqual(a2, 6)

    def test_derivative_reduces_steer_value(self):
        # With no derivative term, lateral=0.13 gives P=-2.08 → action 6 (left).
        # Moving toward centre (prev=0.13, curr=0.1) adds D=+0.24, total=-1.84 → action 7 (straight).
        p = SimplePolicy()
        p(_obs(lateral=0.13))       # primes _prev_lateral to 0.13
        a2 = p(_obs(lateral=0.1))   # D term brings it back within threshold
        self.assertEqual(a2, 7)


if __name__ == "__main__":
    unittest.main(verbosity=2)
