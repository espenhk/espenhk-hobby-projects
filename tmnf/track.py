import numpy as np

from utils import Vec3


class Centerline:
    def __init__(self, path: str):
        self._points = np.load(path)  # (N, 3) float32
        diffs = np.diff(self._points, axis=0)
        seg_lengths = np.linalg.norm(diffs, axis=1)
        self._arc = np.concatenate([[0.0], np.cumsum(seg_lengths)])
        self._total_length = self._arc[-1]

    def forward_at(self, pos: Vec3) -> np.ndarray:
        """Return the unit forward direction of the track at the closest point to pos."""
        p = np.array([pos.x, pos.y, pos.z], dtype=np.float64)
        dists = np.linalg.norm(self._points - p, axis=1)
        idx = int(np.argmin(dists))
        idx = min(idx, len(self._points) - 2)
        ab = self._points[idx + 1].astype(np.float64) - self._points[idx].astype(np.float64)
        length = float(np.linalg.norm(ab))
        return ab / length if length > 1e-9 else np.array([0.0, 0.0, 1.0])

    def project(self, pos: Vec3) -> tuple[float, float, float]:
        """
        Returns (progress, lateral_offset, vertical_offset).
        progress        : 0.0–1.0 along track
        lateral_offset  : metres, negative = left, positive = right
        vertical_offset : metres, negative = below, positive = above
        """
        p = np.array([pos.x, pos.y, pos.z], dtype=np.float64)

        # Closest point index, clamped so segment [idx, idx+1] is always valid
        dists = np.linalg.norm(self._points - p, axis=1)
        idx = int(np.argmin(dists))
        idx = min(idx, len(self._points) - 2)

        # Project onto the segment
        a = self._points[idx].astype(np.float64)
        b = self._points[idx + 1].astype(np.float64)
        ab = b - a
        seg_len = float(np.linalg.norm(ab))
        t = float(np.dot(p - a, ab) / (seg_len ** 2)) if seg_len > 1e-9 else 0.0
        t = max(0.0, min(1.0, t))

        foot = a + t * ab
        progress = (self._arc[idx] + t * seg_len) / self._total_length

        offset = p - foot
        forward = ab / seg_len if seg_len > 1e-9 else np.array([1.0, 0.0, 0.0])

        # World up is Y in TMNF
        up = np.array([0.0, 1.0, 0.0])
        right = np.cross(forward, up)
        right_len = np.linalg.norm(right)
        if right_len > 1e-9:
            right /= right_len
        else:
            right = np.array([1.0, 0.0, 0.0])

        lateral_offset = float(np.dot(offset, right))
        vertical_offset = float(offset[1])

        return float(progress), lateral_offset, vertical_offset
