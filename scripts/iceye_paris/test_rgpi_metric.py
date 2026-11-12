"""Independent numerical checks for the paper-formula RGPI implementation.

Run from the repository root:
    python -m unittest discover -s scripts/iceye_paris -p test_rgpi_metric.py -v
"""
import unittest

import numpy as np
from scipy.ndimage import uniform_filter
from scipy.stats import betaprime

from rgpi_metric import evaluate, prepare_reference


def direct_rgpi(noisy, restored, looks, roi=None, ddof=1):
    """Scalar oracle: explicit patch extraction + scipy's Beta-prime density.

    This deliberately avoids the implementation's filters, shifted-array
    indexing, cached features, and algebraic log-density expression.
    """
    h, w = noisy.shape
    if roi is None:
        r0, c0, rh, rw = 0, 0, h, w
    else:
        r0, c0, rh, rw = roi
    pairs = [((-2, 0), (2, 0)), ((0, -2), (0, 2)),
             ((-2, -2), (2, 2)), ((-2, 2), (2, -2))]
    scores = []
    for row in range(max(3, r0), min(h - 3, r0 + rh)):
        for col in range(max(3, c0), min(w - 3, c0 + rw)):
            local = noisy[row - 3:row + 4, col - 3:col + 4]
            if not (np.isfinite(local).all() and (local > 0).all()):
                continue
            variance = np.var(local, ddof=ddof)
            weight = (max(0.0, min(1.0, (variance - np.mean(local) ** 2 / looks)
                          / ((1 + 1 / looks) * variance))) if variance > 0 else 0.0)
            for first, second in pairs:
                observed_means, estimated_means = [], []
                valid = True
                for dy, dx in (first, second):
                    rows = slice(row + dy - 1, row + dy + 2)
                    cols = slice(col + dx - 1, col + dx + 2)
                    observed = noisy[rows, cols]
                    estimated = restored[rows, cols]
                    valid &= np.isfinite(estimated).all() and (estimated > 0).all()
                    observed_means.append(np.mean(observed))
                    estimated_means.append(np.mean(estimated))
                if not valid:
                    continue
                Q = observed_means[0] / observed_means[1]
                q = estimated_means[0] / estimated_means[1]
                scores.append(weight * (betaprime.logpdf(Q / q, 9 * looks, 9 * looks)
                                        - np.log(q)))
    return np.mean(scores), len(scores)


class TestRGPI(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(20261113)
        self.noisy = rng.lognormal(0.0, 1.1, size=(17, 20))
        self.restored = uniform_filter(self.noisy, size=3, mode="reflect")
        self.looks = 4.37

    def test_scalar_beta_prime_oracle_and_sample_variance(self):
        for ddof in (0, 1):
            with self.subTest(ddof=ddof):
                expected, pairs = direct_rgpi(self.noisy, self.restored, self.looks, ddof=ddof)
                reference = prepare_reference(self.noisy, self.looks, variance_ddof=ddof)
                actual = evaluate(reference, self.restored)["Whole"]
                self.assertAlmostEqual(actual["rgpi"], expected, places=12)
                self.assertEqual(actual["valid_pairs"], pairs)
                self.assertEqual(pairs, (17 - 6) * (20 - 6) * 4)

    def test_roi_uses_full_image_context(self):
        # The first ROI is deliberately smaller than the support window. Its
        # score is nevertheless defined from context outside the ROI.
        regions = {"small": (8, 9, 2, 3), "edge": (0, 1, 7, 9)}
        reference = prepare_reference(self.noisy, self.looks)
        actual = evaluate(reference, self.restored, regions)
        for name, roi in regions.items():
            with self.subTest(roi=name):
                expected, pairs = direct_rgpi(self.noisy, self.restored, self.looks, roi=roi)
                self.assertAlmostEqual(actual[name]["rgpi"], expected, places=12)
                self.assertEqual(actual[name]["valid_pairs"], pairs)

    def test_positive_output_gain_invariance(self):
        reference = prepare_reference(self.noisy, self.looks)
        baseline = evaluate(reference, self.restored)["Whole"]["rgpi"]
        for gain in (0.1652901977687432, 100.0, 1e-120, 1e120):
            with self.subTest(gain=gain):
                actual = evaluate(reference, self.restored * gain)["Whole"]["rgpi"]
                self.assertTrue(np.isfinite(actual))
                self.assertAlmostEqual(actual, baseline, places=11)

    def test_identity_is_likelihood_upper_bound_not_denoising_quality(self):
        reference = prepare_reference(self.noisy, self.looks)
        ceiling = evaluate(reference, self.noisy)["Whole"]["rgpi"]
        for estimate in (self.restored, np.ones_like(self.noisy), self.noisy ** 2):
            score = evaluate(reference, estimate)["Whole"]["rgpi"]
            self.assertLessEqual(score, ceiling + 1e-12)

    def test_constant_observation_has_zero_weight(self):
        reference = prepare_reference(np.full((17, 20), 0.13), 5.0)
        score = evaluate(reference, self.restored)["Whole"]
        self.assertEqual(score["rgpi"], 0.0)
        self.assertEqual(score["mean_weight"], 0.0)

    def test_zero_output_pixel_excludes_only_affected_directions(self):
        estimate = self.restored.copy()
        estimate[8, 9] = 0.0
        expected, pairs = direct_rgpi(self.noisy, estimate, self.looks)
        reference = prepare_reference(self.noisy, self.looks)
        actual = evaluate(reference, estimate)["Whole"]
        self.assertAlmostEqual(actual["rgpi"], expected, places=12)
        self.assertEqual(actual["valid_pairs"], pairs)
        self.assertLess(actual["valid_pair_fraction"], 1.0)


if __name__ == "__main__":
    unittest.main()
