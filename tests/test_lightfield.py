"""Light-field engine tests: smoothness, not just correctness."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from lightfield import breath_to_field, field_frame, gamma_encode, stillness, travel


def test_peak_between_diodes():
    f = field_frame(8, 0.5, 0.12, 1.0)
    peak = max(range(len(f)), key=lambda i: f[i])
    # neighbours of the peak must both be lit: no isolated spikes
    assert f[max(0, peak - 1)] > 0 and f[min(7, peak + 1)] > 0


def test_monotone_wings():
    f = field_frame(20, 0.5, 0.2, 1.0)
    peak = max(range(len(f)), key=lambda i: f[i])
    left = f[:peak]
    right = f[peak + 1:]
    assert all(a <= b for a, b in zip(left, left[1:])), left
    assert all(a >= b for a, b in zip(right, right[1:])), right


def test_gamma_lifts_mids():
    assert gamma_encode(0) == 0
    assert gamma_encode(1.0) == 255
    assert gamma_encode(0.25) > 64  # perceptual lift, not linear


def test_travel_is_continuous():
    a = travel(20, 0.3)["track0"]
    b = travel(20, 0.35)["track0"]
    jumps = sum(1 for x, y in zip(a, b) if abs(x - y) > 60)
    assert jumps <= 4  # small step, no teleporting


def test_breath_and_stillness():
    low = breath_to_field(0.0)["track0"]
    high = breath_to_field(1.0)["track0"]
    assert max(high) > max(low) >= 0
    s = stillness()["track0"]
    assert all(v == 0 for v in s)
